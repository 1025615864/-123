"""支付API路由"""
import base64
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
import re
from typing import Annotated, cast
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
import uuid
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode, parse_qsl, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, cast as sa_cast, Integer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import ColumnElement
from pydantic import BaseModel

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key

from ..config import get_settings
from ..database import get_db
from ..services.critical_event_reporter import critical_event_reporter
from ..services.cache_service import cache_service
from ..models.payment import PaymentOrder, UserBalance, BalanceTransaction, PaymentStatus, PaymentCallbackEvent
from ..models.system import SystemConfig, AdminLog, LogAction, LogModule
from ..models.user import User
from ..models.user_quota import UserQuotaPackBalance
from ..utils.deps import get_current_user, require_admin
from ..utils.rate_limiter import rate_limit, RateLimitConfig, get_client_ip
from ..utils.wechatpay_v3 import (
    WeChatPayPlatformCert,
    fetch_platform_certificates,
    load_platform_certs_json,
    dump_platform_certs_json,
    wechatpay_verify_signature,
    wechatpay_decrypt_resource,
)

router = APIRouter(prefix="/payment", tags=["支付管理"])

settings = get_settings()


def _resolve_env_file_path() -> Path:
    explicit = os.getenv("ENV_FILE", "").strip()
    here = Path(__file__).resolve()
    backend_dir = here.parents[2]
    repo_root = here.parents[3]

    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            backend_candidate = backend_dir / explicit
            repo_candidate = repo_root / explicit
            if backend_candidate.exists():
                return backend_candidate
            if repo_candidate.exists():
                return repo_candidate
            return backend_candidate
        return p

    backend_env = backend_dir / ".env"
    if backend_env.exists():
        return backend_env
    repo_env = repo_root / ".env"
    if repo_env.exists():
        return repo_env
    return backend_env


def _format_env_value(key: str, value: str) -> str:
    raw = str(value)
    raw = raw.replace("\r\n", "\n").strip()
    raw = raw.replace("\\", "\\\\")
    raw = raw.replace('"', '\\"')
    if "\n" in raw:
        raw = raw.replace("\n", "\\n")
    return f'"{raw}"'


def _read_env_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()


def _write_env_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines).rstrip("\n") + "\n"
    path.write_text(text, encoding="utf-8")


def _update_env_file(path: Path, updates: dict[str, str | None]) -> list[str]:
    allowed = {
        "PAYMENT_WEBHOOK_SECRET",
        "ALIPAY_APP_ID",
        "ALIPAY_PRIVATE_KEY",
        "ALIPAY_PUBLIC_KEY",
        "ALIPAY_GATEWAY_URL",
        "ALIPAY_NOTIFY_URL",
        "ALIPAY_RETURN_URL",
        "IKUNPAY_PID",
        "IKUNPAY_KEY",
        "IKUNPAY_GATEWAY_URL",
        "IKUNPAY_NOTIFY_URL",
        "IKUNPAY_RETURN_URL",
        "IKUNPAY_DEFAULT_TYPE",
        "WECHATPAY_MCH_ID",
        "WECHATPAY_MCH_SERIAL_NO",
        "WECHATPAY_PRIVATE_KEY",
        "WECHATPAY_API_V3_KEY",
        "WECHATPAY_CERTIFICATES_URL",
        "FRONTEND_BASE_URL",
    }

    normalized: dict[str, str | None] = {}
    for k, v in updates.items():
        kk = str(k or "").strip().upper()
        if not kk or kk not in allowed:
            continue
        if v is None:
            normalized[kk] = None
        else:
            vv = str(v).strip()
            normalized[kk] = vv if vv else None

    if not normalized:
        return []

    lines = _read_env_lines(path)
    key_re = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=.*$")

    used: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out.append(line)
            continue
        m = key_re.match(line)
        if not m:
            out.append(line)
            continue
        k = str(m.group(1) or "").strip().upper()
        if k not in normalized:
            out.append(line)
            continue

        used.add(k)
        v = normalized.get(k)
        if v is None:
            continue
        out.append(f"{k}={_format_env_value(k, v)}")

    for k, v in normalized.items():
        if k in used:
            continue
        if v is None:
            continue
        out.append(f"{k}={_format_env_value(k, v)}")

    _write_env_lines(path, out)
    return sorted(list(normalized.keys()))


async def _log_config_change(db: AsyncSession, *, user_id: int, request: Request | None, description: str) -> None:
    ip_address: str | None = None
    user_agent: str | None = None
    if request is not None:
        try:
            ip_address = (getattr(getattr(request, "client", None), "host", None) or None)
        except Exception:
            ip_address = None
        try:
            user_agent = str(request.headers.get("user-agent", ""))[:500] or None
        except Exception:
            user_agent = None

    log = AdminLog(
        user_id=int(user_id),
        action=LogAction.CONFIG,
        module=LogModule.SYSTEM,
        target_id=None,
        target_type="payment_env",
        description=str(description)[:2000],
        ip_address=ip_address,
        user_agent=user_agent,
        extra_data=None,
    )
    db.add(log)
    await db.flush()

def _get_int_env(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _get_float_env(key: str, default: float) -> float:
    raw = os.getenv(key, "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


VIP_DEFAULT_DAYS = _get_int_env("VIP_DEFAULT_DAYS", 30)
VIP_DEFAULT_PRICE = _get_float_env("VIP_DEFAULT_PRICE", 29.0)

LIGHT_CONSULT_REVIEW_DEFAULT_PRICE = _get_float_env("LIGHT_CONSULT_REVIEW_DEFAULT_PRICE", 19.9)

AI_CHAT_PACK_OPTIONS: dict[int, float] = {
    10: 12.0,
    50: 49.0,
    100: 79.0,
}

DOCUMENT_GENERATE_PACK_OPTIONS: dict[int, float] = dict(AI_CHAT_PACK_OPTIONS)

AI_PACK_RELATED_TYPES = {"ai_chat", "document_generate"}


def _parse_pack_options(value: str | None, *, fallback: dict[int, float]) -> dict[int, float]:
    raw = str(value or "").strip()
    if not raw:
        return dict(fallback)
    try:
        obj: object = cast(object, json.loads(raw))
    except Exception:
        return dict(fallback)
    if not isinstance(obj, dict):
        return dict(fallback)

    out: dict[int, float] = {}
    obj_dict = cast(dict[object, object], obj)
    for k_obj, v_obj in obj_dict.items():
        try:
            kk = int(str(k_obj).strip())
            vv = float(str(v_obj).strip())
        except Exception:
            continue
        if kk <= 0 or vv <= 0:
            continue
        out[kk] = vv
    return out or dict(fallback)


async def _get_system_config_value(db: AsyncSession, key: str) -> str | None:
    res = await db.execute(select(SystemConfig.value).where(SystemConfig.key == str(key).strip()))
    v = res.scalar_one_or_none()
    return str(v) if isinstance(v, str) else None


async def _get_int_config(db: AsyncSession, key: str, default: int) -> int:
    raw = await _get_system_config_value(db, key)
    if raw is None:
        return int(default)
    try:
        return int(str(raw).strip())
    except Exception:
        return int(default)


async def _get_float_config(db: AsyncSession, key: str, default: float) -> float:
    raw = await _get_system_config_value(db, key)
    if raw is None:
        return float(default)
    try:
        return float(str(raw).strip())
    except Exception:
        return float(default)


async def _get_vip_plan(db: AsyncSession) -> tuple[int, float]:
    days = await _get_int_config(db, "VIP_DEFAULT_DAYS", VIP_DEFAULT_DAYS)
    price = await _get_float_config(db, "VIP_DEFAULT_PRICE", VIP_DEFAULT_PRICE)
    if days <= 0:
        days = int(VIP_DEFAULT_DAYS)
    if price <= 0:
        price = float(VIP_DEFAULT_PRICE)
    return int(days), float(price)


async def _get_pack_options(db: AsyncSession, related_type: str) -> dict[int, float]:
    rt = str(related_type or "").strip().lower() or "ai_chat"
    if rt == "document_generate":
        raw = await _get_system_config_value(db, "DOCUMENT_GENERATE_PACK_OPTIONS_JSON")
        return _parse_pack_options(raw, fallback=DOCUMENT_GENERATE_PACK_OPTIONS)
    raw = await _get_system_config_value(db, "AI_CHAT_PACK_OPTIONS_JSON")
    return _parse_pack_options(raw, fallback=AI_CHAT_PACK_OPTIONS)


async def _get_review_price(db: AsyncSession) -> float:
    price = await _get_float_config(db, "LIGHT_CONSULT_REVIEW_PRICE", float(LIGHT_CONSULT_REVIEW_DEFAULT_PRICE))
    if price <= 0:
        price = float(LIGHT_CONSULT_REVIEW_DEFAULT_PRICE)
    return float(price)


# ============ 请求/响应模型 ============

class CreateOrderRequest(BaseModel):
    order_type: str  # consultation/service/vip/recharge
    amount: float
    title: str
    description: str | None = None
    related_id: int | None = None
    related_type: str | None = None


class PayOrderRequest(BaseModel):
    payment_method: str  # alipay/wechat/balance/ikunpay


class MarkPaidRequest(BaseModel):
    payment_method: str  # alipay/wechat


class PaymentWebhookRequest(BaseModel):
    order_no: str
    trade_no: str
    payment_method: str
    amount: float
    signature: str


class OrderResponse(BaseModel):
    id: int
    order_no: str
    order_type: str
    amount: float
    actual_amount: float
    status: str
    payment_method: str | None
    title: str
    created_at: datetime
    paid_at: datetime | None


class ReconcileEventItem(BaseModel):
    provider: str
    order_no: str | None
    trade_no: str | None
    amount: float | None
    verified: bool
    error_message: str | None
    created_at: datetime


class ReconcileResponse(BaseModel):
    order_no: str
    order_status: str
    payment_method: str | None
    actual_amount: float
    trade_no: str | None
    callbacks_total: int
    callbacks_verified: int
    callbacks_failed: int
    diagnosis: str
    details: dict[str, object]
    paid_at: datetime | None
    recent_events: list[ReconcileEventItem]


class BalanceResponse(BaseModel):
    balance: float
    frozen: float
    total_recharged: float
    total_consumed: float


class CallbackEventResponse(BaseModel):
    id: int
    provider: str
    order_no: str | None
    trade_no: str | None
    amount: float | None
    verified: bool
    error_message: str | None
    created_at: datetime


class CallbackEventDetailResponse(CallbackEventResponse):
    raw_payload: str | None
    masked_payload: str | None
    raw_payload_hash: str | None
    source_ip: str | None
    user_agent: str | None


class PaymentChannelStatusResponse(BaseModel):
    alipay_configured: bool
    wechatpay_configured: bool
    ikunpay_configured: bool
    payment_webhook_secret_configured: bool
    wechatpay_platform_certs_cached: bool
    wechatpay_platform_certs_total: int
    wechatpay_platform_certs_updated_at: int | None
    wechatpay_cert_refresh_enabled: bool
    details: dict[str, object]


class PublicPaymentChannelStatusResponse(BaseModel):
    alipay_configured: bool
    wechatpay_configured: bool
    ikunpay_configured: bool
    available_methods: list[str]


class WechatPlatformCertImportRequest(BaseModel):
    platform_certs_json: str | None = None
    cert_pem: str | None = None
    serial_no: str | None = None
    expire_time: str | None = None
    merge: bool = True


# ============ 工具函数 ============

def generate_order_no() -> str:
    """生成订单号"""
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


def _quantize_amount(amount: float) -> Decimal:
    return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _decimal_to_cents(amount: Decimal) -> int:
    return int(amount * 100)


def _append_query_param(url: str, key: str, value: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return raw
    try:
        parts = urlsplit(raw)
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        pairs = [(k, v) for (k, v) in pairs if k != key]
        pairs.append((key, str(value)))
        query = urlencode(pairs)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))
    except Exception:
        sep = "&" if "?" in raw else "?"
        return f"{raw}{sep}{key}={value}"


async def _record_callback_event(
    db: AsyncSession,
    *,
    provider: str,
    order_no: str | None,
    trade_no: str | None,
    amount: Decimal | None,
    verified: bool,
    error_message: str | None,
    raw_payload: str | None,
    source_ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    trade_no_for_key = trade_no if (verified and not error_message) else None
    amount_cents: int | None = None
    amount_float: float | None = None
    if amount is not None:
        q = _quantize_amount(float(amount))
        amount_float = float(q)
        amount_cents = _decimal_to_cents(q)

    payload_hash: str | None = None
    raw_payload_str = str(raw_payload or "")
    if raw_payload_str.strip():
        try:
            payload_hash = hashlib.sha256(raw_payload_str.encode("utf-8")).hexdigest()
        except Exception:
            payload_hash = None

    ua = None
    if user_agent is not None:
        ua = str(user_agent)
        if len(ua) > 512:
            ua = ua[:512]

    ip = None
    if source_ip is not None:
        ip = str(source_ip)
        if len(ip) > 45:
            ip = ip[:45]

    evt = PaymentCallbackEvent(
        provider=str(provider),
        order_no=str(order_no) if order_no else None,
        trade_no=str(trade_no_for_key) if trade_no_for_key else None,
        amount=amount_float,
        amount_cents=amount_cents,
        verified=bool(verified),
        error_message=str(error_message) if error_message else None,
        raw_payload=raw_payload,
        raw_payload_hash=payload_hash,
        source_ip=ip,
        user_agent=ua,
    )

    try:
        db.add(evt)
        await db.commit()
    except IntegrityError:
        await db.rollback()
    except Exception:
        await db.rollback()


async def _set_system_config_value(
    db: AsyncSession,
    *,
    key: str,
    value: str | None,
    category: str = "payment",
    description: str | None = None,
    updated_by: int | None = None,
) -> None:
    res = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    row = res.scalar_one_or_none()
    if row is None:
        row = SystemConfig(
            key=str(key),
            value=value,
            category=str(category),
            description=description,
            updated_by=updated_by,
        )
        db.add(row)
        await db.flush()
        return
    row.value = value
    if description is not None:
        row.description = description
    row.category = str(category)
    row.updated_by = updated_by
    db.add(row)
    await db.flush()


def _normalize_pem(value: str) -> str:
    if not value:
        return ""
    return value.strip().replace("\\n", "\n")


def _mask_payload(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw)
    if not s.strip():
        return s

    sensitive_keys = {
        "sign",
        "signature",
        "sign_data",
        "sign_info",
        "app_cert_sn",
        "alipay_cert_sn",
    }

    def _mask_value(v: object) -> object:
        if v is None:
            return None
        if isinstance(v, (int, float, bool)):
            return v
        ss = str(v)
        if not ss:
            return ss
        if len(ss) <= 8:
            return "*" * len(ss)
        return f"{ss[:3]}***{ss[-3:]}"

    def _mask_obj(obj: object) -> object:
        if isinstance(obj, dict):
            obj_dict = cast(dict[object, object], obj)
            out: dict[object, object] = {}
            for k, v in obj_dict.items():
                ks = str(k).strip().lower()
                if ks in sensitive_keys:
                    out[k] = _mask_value(v)
                else:
                    out[k] = _mask_obj(v)
            return out
        if isinstance(obj, list):
            obj_list = cast(list[object], obj)
            return [_mask_obj(x) for x in obj_list]
        return obj

    try:
        obj = cast(object, json.loads(s))
        masked = _mask_obj(obj)
        return json.dumps(masked, ensure_ascii=False, indent=2)
    except Exception:
        pass

    try:
        pairs = parse_qsl(s, keep_blank_values=True)
        if pairs:
            obj2: dict[str, object] = {}
            for k, v in pairs:
                obj2[k] = v
            masked2 = _mask_obj(obj2)
            return json.dumps(masked2, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return s


def _alipay_private_key_check(private_key_pem: str | None) -> dict[str, object] | None:
    raw = str(private_key_pem or "").strip()
    if not raw:
        return None
    try:
        key = cast(
            RSAPrivateKey,
            load_pem_private_key(_normalize_pem(raw).encode("utf-8"), password=None),
        )
        return {"ok": True, "key_size": int(getattr(key, "key_size", 0) or 0)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _alipay_public_key_check(public_key_pem: str | None) -> dict[str, object] | None:
    raw = str(public_key_pem or "").strip()
    if not raw:
        return None
    try:
        key = cast(RSAPublicKey, load_pem_public_key(_normalize_pem(raw).encode("utf-8")))
        return {"ok": True, "key_size": int(getattr(key, "key_size", 0) or 0)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _alipay_build_sign_string(params: dict[str, str]) -> str:
    items: list[tuple[str, str]] = []
    for k, v in params.items():
        if k in {"sign", "sign_type"}:
            continue
        s = str(v)
        if s == "":
            continue
        items.append((k, s))
    items.sort(key=lambda x: x[0])
    return "&".join([f"{k}={v}" for k, v in items])


def _alipay_sign_rsa2(params: dict[str, str], private_key_pem: str) -> str:
    sign_content = _alipay_build_sign_string(params)
    key = cast(
        RSAPrivateKey,
        load_pem_private_key(_normalize_pem(private_key_pem).encode("utf-8"), password=None),
    )
    signature = key.sign(
        sign_content.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def _alipay_verify_rsa2(params: dict[str, str], public_key_pem: str) -> bool:
    sign = params.get("sign")
    if not sign:
        return False
    try:
        signature = base64.b64decode(sign)
    except Exception:
        return False

    sign_content = _alipay_build_sign_string(params)
    key = cast(RSAPublicKey, load_pem_public_key(_normalize_pem(public_key_pem).encode("utf-8")))
    try:
        key.verify(
            signature,
            sign_content.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def _alipay_build_page_pay_url(
    *,
    gateway_url: str,
    app_id: str,
    private_key: str,
    notify_url: str,
    return_url: str | None,
    out_trade_no: str,
    total_amount: Decimal,
    subject: str,
) -> str:
    params: dict[str, str] = {
        "app_id": app_id,
        "method": "alipay.trade.page.pay",
        "format": "JSON",
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "notify_url": notify_url,
        "biz_content": json.dumps(
            {
                "out_trade_no": out_trade_no,
                "product_code": "FAST_INSTANT_TRADE_PAY",
                "total_amount": str(total_amount),
                "subject": subject,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    if return_url:
        params["return_url"] = return_url
    params["sign"] = _alipay_sign_rsa2(params, private_key)
    return f"{gateway_url}?{urlencode(params)}"


def _ikunpay_build_sign_string(params: dict[str, str]) -> str:
    items: list[tuple[str, str]] = []
    for k, v in params.items():
        if k in {"sign", "sign_type"}:
            continue
        s = str(v)
        if s == "":
            continue
        items.append((k, s))
    items.sort(key=lambda x: x[0])
    return "&".join([f"{k}={v}" for k, v in items])


def _ikunpay_sign_md5(params: dict[str, str], key: str) -> str:
    sign_content = _ikunpay_build_sign_string(params)
    raw = (sign_content + str(key)).encode("utf-8")
    return hashlib.md5(raw).hexdigest().lower()


def _ikunpay_verify_md5(params: dict[str, str], key: str) -> bool:
    sign = str(params.get("sign") or "").strip().lower()
    if not sign:
        return False
    expected = _ikunpay_sign_md5(params, key)
    return hmac.compare_digest(expected, sign)


def _ikunpay_build_submit_pay_url(
    *,
    gateway_url: str,
    pid: str,
    pay_type: str | None,
    out_trade_no: str,
    notify_url: str,
    return_url: str | None,
    name: str,
    money: Decimal,
    key: str,
) -> str:
    params: dict[str, str] = {
        "pid": str(pid).strip(),
        "out_trade_no": str(out_trade_no).strip(),
        "notify_url": str(notify_url).strip(),
        "name": str(name).strip(),
        "money": str(_quantize_amount(float(money))),
        "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
        "sign_type": "MD5",
    }
    if pay_type:
        params["type"] = str(pay_type).strip()
    if return_url:
        params["return_url"] = str(return_url).strip()
    params["sign"] = _ikunpay_sign_md5(params, key)
    return f"{gateway_url}?{urlencode(params)}"


async def _maybe_confirm_lawyer_consultation_in_tx(db: AsyncSession, order: PaymentOrder) -> None:
    if getattr(order, "related_type", None) != "lawyer_consultation":
        return

    related_id_raw: object | None = cast(object | None, getattr(order, "related_id", None))
    if related_id_raw is None:
        return

    related_id: int
    if isinstance(related_id_raw, bool):
        return
    if isinstance(related_id_raw, int):
        related_id = related_id_raw
    elif isinstance(related_id_raw, float):
        related_id = int(related_id_raw)
    elif isinstance(related_id_raw, str) and related_id_raw.strip():
        try:
            related_id = int(related_id_raw.strip())
        except Exception:
            return
    else:
        return

    from ..models.lawfirm import LawyerConsultation

    _ = await db.execute(
        update(LawyerConsultation)
        .where(
            LawyerConsultation.id == related_id,
            LawyerConsultation.user_id == int(order.user_id),
            LawyerConsultation.status == "pending",
        )
        .values(
            status="confirmed",
            updated_at=func.now(),
        )
    )


async def _maybe_create_consultation_review_task_in_tx(db: AsyncSession, order: PaymentOrder) -> None:
    if str(getattr(order, "order_type", "") or "").lower() != "light_consult_review":
        return

    related_type = str(getattr(order, "related_type", "") or "").strip().lower()
    if related_type != "ai_consultation":
        return

    related_id_raw: object | None = cast(object | None, getattr(order, "related_id", None))
    related_id: int | None = None
    if isinstance(related_id_raw, bool) or related_id_raw is None:
        related_id = None
    elif isinstance(related_id_raw, int):
        related_id = related_id_raw
    elif isinstance(related_id_raw, float):
        related_id = int(related_id_raw)
    elif isinstance(related_id_raw, str) and related_id_raw.strip():
        try:
            related_id = int(related_id_raw.strip())
        except Exception:
            related_id = None

    if related_id is None or related_id <= 0:
        return

    from ..models.consultation import Consultation
    from ..models.consultation_review import ConsultationReviewTask

    c_res = await db.execute(select(Consultation).where(Consultation.id == int(related_id)))
    c = c_res.scalar_one_or_none()
    if c is None:
        return
    if int(getattr(c, "user_id", 0) or 0) != int(order.user_id):
        return

    existing_res = await db.execute(
        select(ConsultationReviewTask).where(ConsultationReviewTask.order_id == int(order.id))
    )
    existing = existing_res.scalar_one_or_none()
    if existing is not None:
        return

    task = ConsultationReviewTask(
        consultation_id=int(related_id),
        user_id=int(order.user_id),
        order_id=int(order.id),
        order_no=str(order.order_no),
        status="pending",
    )
    db.add(task)


async def _maybe_apply_vip_membership_in_tx(db: AsyncSession, order: PaymentOrder) -> None:
    if str(getattr(order, "order_type", "")).lower() != "vip":
        return

    now = datetime.now(timezone.utc)
    res = await db.execute(select(User.vip_expires_at).where(User.id == int(order.user_id)))
    current = res.scalar_one_or_none()

    if isinstance(current, datetime) and current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    base = current if isinstance(current, datetime) and current > now else now
    vip_days, _vip_price = await _get_vip_plan(db)
    new_expires_at = base + timedelta(days=int(vip_days))

    _ = await db.execute(
        update(User)
        .where(User.id == int(order.user_id))
        .values(vip_expires_at=new_expires_at)
    )


async def _maybe_apply_ai_pack_in_tx(db: AsyncSession, order: PaymentOrder) -> None:
    if str(getattr(order, "order_type", "")).lower() != "ai_pack":
        return

    related_type = str(getattr(order, "related_type", "") or "").strip().lower() or "ai_chat"
    if related_type not in AI_PACK_RELATED_TYPES:
        return

    related_id_raw: object | None = cast(object | None, getattr(order, "related_id", None))
    if related_id_raw is None:
        return

    pack_count: int
    if isinstance(related_id_raw, bool):
        return
    if isinstance(related_id_raw, int):
        pack_count = related_id_raw
    elif isinstance(related_id_raw, float):
        pack_count = int(related_id_raw)
    elif isinstance(related_id_raw, str) and related_id_raw.strip():
        try:
            pack_count = int(related_id_raw.strip())
        except Exception:
            return
    else:
        return

    options = await _get_pack_options(db, related_type)
    if pack_count not in options:
        return

    res = await db.execute(
        select(UserQuotaPackBalance).where(UserQuotaPackBalance.user_id == int(order.user_id))
    )
    row = res.scalar_one_or_none()
    if row is None:
        row = UserQuotaPackBalance(
            user_id=int(order.user_id),
            ai_chat_credits=0,
            document_generate_credits=0,
        )
        db.add(row)
        await db.flush()

    if related_type == "document_generate":
        current = int(getattr(row, "document_generate_credits", 0))
        row.document_generate_credits = current + int(pack_count)
    else:
        current = int(getattr(row, "ai_chat_credits", 0))
        row.ai_chat_credits = current + int(pack_count)
    db.add(row)


async def _mark_order_paid_in_tx(
    db: AsyncSession,
    *,
    order: PaymentOrder,
    payment_method: str,
    trade_no: str,
    amount: Decimal,
) -> None:
    amount = _quantize_amount(float(amount))
    amount_cents = _decimal_to_cents(amount)
    paid_at = datetime.now(timezone.utc)

    order_update = await db.execute(
        update(PaymentOrder)
        .where(PaymentOrder.id == order.id, PaymentOrder.status == PaymentStatus.PENDING)
        .values(
            status=PaymentStatus.PAID,
            payment_method=payment_method,
            paid_at=paid_at,
            trade_no=trade_no,
            amount_cents=func.coalesce(
                PaymentOrder.amount_cents,
                sa_cast(func.round(PaymentOrder.amount * 100), Integer),
            ),
            actual_amount_cents=amount_cents,
        )
    )
    if getattr(order_update, "rowcount", 0) != 1:
        return

    if order.order_type == "recharge":
        balance_account = await _get_or_create_balance_in_tx(db, order.user_id)
        balance_before = _quantize_amount(float(balance_account.balance))
        balance_before_cents = _decimal_to_cents(balance_before)

        effective_balance_cents = func.coalesce(
            UserBalance.balance_cents,
            sa_cast(func.round(func.coalesce(UserBalance.balance, 0) * 100), Integer),
        )
        effective_total_recharged_cents = func.coalesce(
            UserBalance.total_recharged_cents,
            sa_cast(func.round(func.coalesce(UserBalance.total_recharged, 0) * 100), Integer),
        )

        _ = await db.execute(
            update(UserBalance)
            .where(UserBalance.user_id == order.user_id)
            .values(
                balance=func.coalesce(UserBalance.balance, 0) + float(amount),
                total_recharged=func.coalesce(UserBalance.total_recharged, 0) + float(amount),
                balance_cents=effective_balance_cents + amount_cents,
                total_recharged_cents=effective_total_recharged_cents + amount_cents,
            )
        )

        balance_after = balance_before + amount
        balance_after_cents = balance_before_cents + amount_cents
        transaction = BalanceTransaction(
            user_id=order.user_id,
            order_id=order.id,
            type="recharge",
            amount=float(amount),
            balance_before=float(balance_before),
            balance_after=float(balance_after),
            amount_cents=amount_cents,
            balance_before_cents=balance_before_cents,
            balance_after_cents=balance_after_cents,
            description=f"充值: {order.title}",
        )
        db.add(transaction)

    await _maybe_apply_vip_membership_in_tx(db, order)
    await _maybe_apply_ai_pack_in_tx(db, order)
    await _maybe_confirm_lawyer_consultation_in_tx(db, order)
    await _maybe_create_consultation_review_task_in_tx(db, order)


async def _get_or_create_balance_in_tx(db: AsyncSession, user_id: int) -> UserBalance:
    result = await db.execute(
        select(UserBalance).where(UserBalance.user_id == user_id)
    )
    balance = result.scalar_one_or_none()
    if balance:
        return balance

    balance = UserBalance(
        user_id=user_id,
        balance=0.0,
        frozen=0.0,
        total_recharged=0.0,
        total_consumed=0.0,
        balance_cents=0,
        frozen_cents=0,
        total_recharged_cents=0,
        total_consumed_cents=0,
    )
    db.add(balance)
    await db.flush()
    return balance


async def get_or_create_balance(db: AsyncSession, user_id: int) -> UserBalance:
    """获取或创建用户余额账户"""
    result = await db.execute(
        select(UserBalance).where(UserBalance.user_id == user_id)
    )
    balance = result.scalar_one_or_none()
    
    if not balance:
        balance = UserBalance(
            user_id=user_id,
            balance=0.0,
            frozen=0.0,
            total_recharged=0.0,
            total_consumed=0.0,
            balance_cents=0,
            frozen_cents=0,
            total_recharged_cents=0,
            total_consumed_cents=0,
        )
        db.add(balance)
        await db.commit()
        await db.refresh(balance)
    
    return balance


# ============ 用户接口 ============

@router.post("/orders", summary="创建订单")
async def create_order(
    data: CreateOrderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """创建支付订单"""
    if data.order_type not in {"consultation", "service", "vip", "recharge", "ai_pack", "light_consult_review"}:
        raise HTTPException(status_code=400, detail="无效的订单类型")

    related_id = data.related_id
    related_type = data.related_type

    if data.order_type == "vip":
        vip_days, vip_price = await _get_vip_plan(db)
        amount = _quantize_amount(vip_price)
        title = f"VIP会员（{int(vip_days)}天）"
        description = data.description
    elif data.order_type == "ai_pack":
        related_type = str(getattr(data, "related_type", "") or "").strip().lower() or "ai_chat"
        if related_type not in AI_PACK_RELATED_TYPES:
            raise HTTPException(status_code=400, detail="无效的次数包类型")

        related_id_raw: object | None = cast(object | None, getattr(data, "related_id", None))
        pack_count: int | None = None
        if isinstance(related_id_raw, bool) or related_id_raw is None:
            pack_count = None
        elif isinstance(related_id_raw, int):
            pack_count = related_id_raw
        elif isinstance(related_id_raw, float):
            pack_count = int(related_id_raw)
        elif isinstance(related_id_raw, str) and related_id_raw.strip():
            try:
                pack_count = int(related_id_raw.strip())
            except Exception:
                pack_count = None

        options = await _get_pack_options(db, related_type)
        if pack_count is None or pack_count not in options:
            raise HTTPException(status_code=400, detail="无效的次数包")

        related_id = int(pack_count)

        amount = _quantize_amount(options[int(pack_count)])
        title = (
            f"文书生成次数包（{int(pack_count)}次）"
            if related_type == "document_generate"
            else f"AI咨询次数包（{int(pack_count)}次）"
        )
        description = data.description
    elif data.order_type == "light_consult_review":
        related_type = str(getattr(data, "related_type", "") or "").strip().lower() or "ai_consultation"
        if related_type != "ai_consultation":
            raise HTTPException(status_code=400, detail="无效的关联类型")

        related_id_raw: object | None = cast(object | None, getattr(data, "related_id", None))
        consultation_id: int | None = None
        if isinstance(related_id_raw, bool) or related_id_raw is None:
            consultation_id = None
        elif isinstance(related_id_raw, int):
            consultation_id = related_id_raw
        elif isinstance(related_id_raw, float):
            consultation_id = int(related_id_raw)
        elif isinstance(related_id_raw, str) and related_id_raw.strip():
            try:
                consultation_id = int(related_id_raw.strip())
            except Exception:
                consultation_id = None

        if consultation_id is None or consultation_id <= 0:
            raise HTTPException(status_code=400, detail="缺少咨询ID")

        from ..models.consultation import Consultation

        c_res = await db.execute(select(Consultation).where(Consultation.id == int(consultation_id)))
        c = c_res.scalar_one_or_none()
        if c is None:
            raise HTTPException(status_code=404, detail="咨询记录不存在")
        if int(getattr(c, "user_id", 0) or 0) != int(current_user.id):
            raise HTTPException(status_code=403, detail="无权限购买该咨询的复核")

        related_id = int(consultation_id)
        related_type = "ai_consultation"

        amount = _quantize_amount(await _get_review_price(db))
        title = "AI咨询律师复核"
        description = data.description
    else:
        amount = _quantize_amount(data.amount)
        title = data.title
        description = data.description
    amount_cents = _decimal_to_cents(amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="金额必须大于0")
    
    order = PaymentOrder(
        order_no=generate_order_no(),
        user_id=current_user.id,
        order_type=data.order_type,
        amount=float(amount),
        actual_amount=float(amount),  # 可添加优惠逻辑
        amount_cents=amount_cents,
        actual_amount_cents=amount_cents,
        status=PaymentStatus.PENDING,
        title=title,
        description=description,
        related_id=related_id,
        related_type=related_type,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),  # 2小时过期
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "amount": order.actual_amount,
        "expires_at": order.expires_at,
    }


@router.get("/pricing", summary="获取商业化价格表")
async def get_pricing(db: Annotated[AsyncSession, Depends(get_db)]):
    vip_days, vip_price = await _get_vip_plan(db)
    ai_options = await _get_pack_options(db, "ai_chat")
    doc_options = await _get_pack_options(db, "document_generate")
    review_price = await _get_review_price(db)

    def _to_list(options: dict[int, float]):
        return [
            {"count": int(k), "price": float(v)}
            for k, v in sorted(options.items(), key=lambda kv: int(kv[0]))
        ]

    return {
        "vip": {"days": int(vip_days), "price": float(vip_price)},
        "services": {
            "light_consult_review": {"price": float(review_price)},
        },
        "packs": {
            "ai_chat": _to_list(ai_options),
            "document_generate": _to_list(doc_options),
        },
    }


@router.post("/orders/{order_no}/pay", summary="支付订单")
async def pay_order(
    order_no: str,
    data: PayOrderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """支付订单"""
    if data.payment_method not in {"alipay", "wechat", "balance", "ikunpay"}:
        raise HTTPException(status_code=400, detail="无效的支付方式")

    result = await db.execute(
        select(PaymentOrder).where(
            PaymentOrder.order_no == order_no,
            PaymentOrder.user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.order_type == "recharge" and data.payment_method == "balance":
        raise HTTPException(status_code=400, detail="充值订单不支持余额支付")
    
    if order.status == PaymentStatus.PAID:
        return {"message": "支付成功", "trade_no": order.trade_no}
    if order.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"订单状态异常: {order.status}")

    expires_at = order.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at and expires_at < datetime.now(timezone.utc):
        order.status = PaymentStatus.CANCELLED
        await db.commit()
        raise HTTPException(status_code=400, detail="订单已过期")

    actual_amount = _quantize_amount(float(order.actual_amount))
    actual_amount_cents = _decimal_to_cents(actual_amount)

    if data.payment_method == "wechat":
        raise HTTPException(status_code=400, detail="微信支付暂未开放")

    # 余额支付
    if data.payment_method == "balance":
        trade_no = f"BAL{generate_order_no()}"
        paid_at = datetime.now(timezone.utc)
 
        try:
            balance_account = await _get_or_create_balance_in_tx(db, current_user.id)
            balance_before = _quantize_amount(float(balance_account.balance))
            balance_before_cents = _decimal_to_cents(balance_before)

            if balance_before < actual_amount:
                raise HTTPException(status_code=400, detail="余额不足")

            effective_balance_cents = func.coalesce(
                UserBalance.balance_cents,
                sa_cast(func.round(func.coalesce(UserBalance.balance, 0) * 100), Integer),
            )
            effective_total_consumed_cents = func.coalesce(
                UserBalance.total_consumed_cents,
                sa_cast(func.round(func.coalesce(UserBalance.total_consumed, 0) * 100), Integer),
            )

            bal_update = await db.execute(
                update(UserBalance)
                .where(
                    UserBalance.user_id == current_user.id,
                    effective_balance_cents >= actual_amount_cents,
                )
                .values(
                    balance=func.coalesce(UserBalance.balance, 0) - float(actual_amount),
                    total_consumed=func.coalesce(UserBalance.total_consumed, 0) + float(actual_amount),
                    balance_cents=effective_balance_cents - actual_amount_cents,
                    total_consumed_cents=effective_total_consumed_cents + actual_amount_cents,
                )
            )
            if getattr(bal_update, "rowcount", 0) != 1:
                raise HTTPException(status_code=400, detail="余额不足")

            order_update = await db.execute(
                update(PaymentOrder)
                .where(PaymentOrder.id == order.id, PaymentOrder.status == PaymentStatus.PENDING)
                .values(
                    status=PaymentStatus.PAID,
                    payment_method=data.payment_method,
                    paid_at=paid_at,
                    trade_no=trade_no,
                    amount_cents=func.coalesce(
                        PaymentOrder.amount_cents,
                        sa_cast(func.round(PaymentOrder.amount * 100), Integer),
                    ),
                    actual_amount_cents=actual_amount_cents,
                )
            )
            if getattr(order_update, "rowcount", 0) != 1:
                raise HTTPException(status_code=400, detail="订单状态异常")

            balance_after = balance_before - actual_amount
            balance_after_cents = balance_before_cents - actual_amount_cents
            transaction = BalanceTransaction(
                user_id=current_user.id,
                order_id=order.id,
                type="consume",
                amount=-float(actual_amount),
                balance_before=float(balance_before),
                balance_after=float(balance_after),
                amount_cents=-actual_amount_cents,
                balance_before_cents=balance_before_cents,
                balance_after_cents=balance_after_cents,
                description=f"支付订单: {order.title}",
            )
            db.add(transaction)

            await _maybe_apply_vip_membership_in_tx(db, order)
            await _maybe_apply_ai_pack_in_tx(db, order)
            await _maybe_confirm_lawyer_consultation_in_tx(db, order)
            await _maybe_create_consultation_review_task_in_tx(db, order)

            await db.commit()
        except HTTPException:
            await db.rollback()
            raise
        except Exception:
            await db.rollback()
            raise

        await db.refresh(order)
        return {"message": "支付成功", "trade_no": order.trade_no}
    
    # 其他支付方式（返回支付链接/二维码）
    if data.payment_method == "ikunpay":
        if not (settings.ikunpay_pid or "").strip():
            raise HTTPException(status_code=400, detail="IKUNPAY_PID 未设置")
        if not (settings.ikunpay_key or "").strip():
            raise HTTPException(status_code=400, detail="IKUNPAY_KEY 未设置")
        if not (settings.ikunpay_notify_url or "").strip():
            raise HTTPException(status_code=400, detail="IKUNPAY_NOTIFY_URL 未设置")

        if order.payment_method != "ikunpay":
            order.payment_method = "ikunpay"
            db.add(order)
            await db.commit()
            await db.refresh(order)

        pay_type_raw = (settings.ikunpay_default_type or "").strip()
        pay_type = pay_type_raw or None
        return_url = (settings.ikunpay_return_url or "").strip() or None
        if return_url is None:
            frontend_base = str(getattr(settings, "frontend_base_url", "") or "").strip().rstrip("/")
            if frontend_base:
                return_url = f"{frontend_base}/payment/return"

        if return_url:
            return_url = _append_query_param(return_url, "order_no", order.order_no)

        pay_url = _ikunpay_build_submit_pay_url(
            gateway_url=(settings.ikunpay_gateway_url or "").strip() or "https://ikunpay.com/submit.php",
            pid=settings.ikunpay_pid,
            pay_type=pay_type,
            out_trade_no=order.order_no,
            notify_url=settings.ikunpay_notify_url,
            return_url=return_url,
            name=order.title,
            money=_quantize_amount(float(order.actual_amount)),
            key=settings.ikunpay_key,
        )
        return {
            "message": "OK",
            "payment_method": "ikunpay",
            "amount": order.actual_amount,
            "order_no": order.order_no,
            "pay_url": pay_url,
        }

    if data.payment_method == "alipay":
        if not settings.alipay_app_id or not settings.alipay_private_key:
            raise HTTPException(status_code=400, detail="支付宝配置未设置")
        if not settings.alipay_notify_url:
            raise HTTPException(status_code=400, detail="ALIPAY_NOTIFY_URL 未设置")

        if order.payment_method != "alipay":
            order.payment_method = "alipay"
            db.add(order)
            await db.commit()
            await db.refresh(order)

        return_url = (settings.alipay_return_url or "").strip() or None
        if return_url is None:
            frontend_base = str(getattr(settings, "frontend_base_url", "") or "").strip().rstrip("/")
            if frontend_base:
                return_url = f"{frontend_base}/payment/return"

        if return_url:
            return_url = _append_query_param(return_url, "order_no", order.order_no)

        pay_url = _alipay_build_page_pay_url(
            gateway_url=settings.alipay_gateway_url,
            app_id=settings.alipay_app_id,
            private_key=settings.alipay_private_key,
            notify_url=settings.alipay_notify_url,
            return_url=return_url,
            out_trade_no=order.order_no,
            total_amount=_quantize_amount(float(order.actual_amount)),
            subject=order.title,
        )
        return {
            "message": "OK",
            "payment_method": "alipay",
            "amount": order.actual_amount,
            "order_no": order.order_no,
            "pay_url": pay_url,
        }

    return {
        "message": "请使用第三方支付",
        "payment_method": data.payment_method,
        "amount": order.actual_amount,
        "order_no": order.order_no,
    }


@router.post("/alipay/notify", summary="支付宝异步通知")
@rate_limit(*RateLimitConfig.PAYMENT_NOTIFY, by_ip=True)
async def alipay_notify(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    form = await request.form()
    params = {str(k): str(v) for k, v in form.items()}

    request_id = str(getattr(request.state, "request_id", "") or "").strip() or uuid.uuid4().hex

    payload_raw = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
    source_ip = get_client_ip(request)
    user_agent = str(request.headers.get("user-agent") or "")
    order_no_raw = str(params.get("out_trade_no") or "").strip() or None
    trade_no_raw = str(params.get("trade_no") or "").strip() or None
    amount_raw: Decimal | None = None
    try:
        total_amount_str = str(params.get("total_amount") or "").strip()
        if total_amount_str:
            amount_raw = _quantize_amount(float(total_amount_str))
    except Exception:
        amount_raw = None

    if not settings.alipay_public_key:
        await _record_callback_event(
            db,
            provider="alipay",
            order_no=order_no_raw,
            trade_no=trade_no_raw,
            amount=amount_raw,
            verified=False,
            error_message="ALIPAY_PUBLIC_KEY 未设置",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        critical_event_reporter.fire_and_forget(
            event="payment_config_missing",
            severity="error",
            request_id=request_id,
            title="支付回调配置缺失",
            message="ALIPAY_PUBLIC_KEY 未设置",
            data={
                "provider": "alipay",
                "order_no": order_no_raw,
                "trade_no": trade_no_raw,
                "path": str(request.url.path),
            },
            dedup_key="payment_config_missing|alipay_public_key",
        )
        return Response(content="failure", status_code=500, media_type="text/plain")

    if not _alipay_verify_rsa2(params, settings.alipay_public_key):
        await _record_callback_event(
            db,
            provider="alipay",
            order_no=order_no_raw,
            trade_no=trade_no_raw,
            amount=amount_raw,
            verified=False,
            error_message="验签失败",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return Response(content="failure", status_code=400, media_type="text/plain")

    sign_type = str(params.get("sign_type") or "").strip().upper()
    if sign_type and sign_type != "RSA2":
        await _record_callback_event(
            db,
            provider="alipay",
            order_no=order_no_raw,
            trade_no=trade_no_raw,
            amount=amount_raw,
            verified=True,
            error_message=f"unsupported_sign_type:{sign_type}",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return Response(content="failure", status_code=400, media_type="text/plain")

    trade_status = str(params.get("trade_status") or "").strip()
    if trade_status not in {"TRADE_SUCCESS", "TRADE_FINISHED"}:
        await _record_callback_event(
            db,
            provider="alipay",
            order_no=order_no_raw,
            trade_no=trade_no_raw,
            amount=amount_raw,
            verified=True,
            error_message=f"ignored_trade_status:{trade_status}" if trade_status else "ignored_trade_status",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return Response(content="success", media_type="text/plain")

    app_id = str(params.get("app_id") or "").strip()
    if settings.alipay_app_id and app_id and app_id != settings.alipay_app_id:
        await _record_callback_event(
            db,
            provider="alipay",
            order_no=order_no_raw,
            trade_no=trade_no_raw,
            amount=amount_raw,
            verified=True,
            error_message="app_id 不匹配",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return Response(content="failure", status_code=400, media_type="text/plain")

    order_no = str(params.get("out_trade_no") or "").strip()
    trade_no = str(params.get("trade_no") or "").strip()
    total_amount_str = str(params.get("total_amount") or "").strip()

    if not order_no or not trade_no or not total_amount_str:
        await _record_callback_event(
            db,
            provider="alipay",
            order_no=order_no_raw,
            trade_no=trade_no_raw,
            amount=amount_raw,
            verified=True,
            error_message="缺少字段",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return Response(content="failure", status_code=400, media_type="text/plain")

    try:
        amount = _quantize_amount(float(total_amount_str))
    except Exception:
        await _record_callback_event(
            db,
            provider="alipay",
            order_no=order_no,
            trade_no=trade_no,
            amount=amount_raw,
            verified=True,
            error_message="金额格式错误",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return Response(content="failure", status_code=400, media_type="text/plain")

    lock_key = f"locks:payment_notify:alipay:{trade_no or order_no}"
    lock_value = uuid.uuid4().hex
    acquired = await cache_service.acquire_lock(lock_key, lock_value, expire=30)
    if not acquired:
        return Response(content="failure", status_code=503, media_type="text/plain")

    try:
        result = await db.execute(select(PaymentOrder).where(PaymentOrder.order_no == order_no))
        order = result.scalar_one_or_none()
        if not order:
            await _record_callback_event(
                db,
                provider="alipay",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount,
                verified=True,
                error_message="订单不存在",
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            return Response(content="failure", status_code=404, media_type="text/plain")

        if order.status == PaymentStatus.PAID:
            await _record_callback_event(
                db,
                provider="alipay",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount,
                verified=True,
                error_message=None,
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            return Response(content="success", media_type="text/plain")

        if order.status != PaymentStatus.PENDING:
            await _record_callback_event(
                db,
                provider="alipay",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount,
                verified=True,
                error_message="订单状态异常",
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            return Response(content="failure", status_code=400, media_type="text/plain")

        if _quantize_amount(float(order.actual_amount)) != amount:
            await _record_callback_event(
                db,
                provider="alipay",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount,
                verified=True,
                error_message="金额不一致",
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            return Response(content="failure", status_code=400, media_type="text/plain")

        try:
            await _mark_order_paid_in_tx(
                db,
                order=order,
                payment_method="alipay",
                trade_no=trade_no,
                amount=amount,
            )
            await db.commit()
        except Exception as e:
            await db.rollback()
            await _record_callback_event(
                db,
                provider="alipay",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount,
                verified=True,
                error_message="订单落库失败",
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            critical_event_reporter.fire_and_forget(
                event="payment_callback_persist_failed",
                severity="error",
                request_id=request_id,
                title="支付回调落库失败",
                message=str(e),
                data={
                    "provider": "alipay",
                    "order_no": order_no,
                    "trade_no": trade_no,
                },
                dedup_key="payment_callback_persist_failed|alipay",
            )
            return Response(content="failure", status_code=500, media_type="text/plain")

        await _record_callback_event(
            db,
            provider="alipay",
            order_no=order_no,
            trade_no=trade_no,
            amount=amount,
            verified=True,
            error_message=None,
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )

        return Response(content="success", media_type="text/plain")
    finally:
        _ = await cache_service.release_lock(lock_key, lock_value)


@router.api_route("/ikunpay/notify", methods=["GET", "POST"], summary="Ikunpay 异步通知")
@rate_limit(*RateLimitConfig.PAYMENT_NOTIFY, by_ip=True)
async def ikunpay_notify(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    params: dict[str, str]
    if request.method == "GET":
        params = {str(k): str(v) for k, v in request.query_params.items()}
    else:
        form = await request.form()
        params = {str(k): str(v) for k, v in form.items()}

    request_id = str(getattr(request.state, "request_id", "") or "").strip() or uuid.uuid4().hex

    payload_raw = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
    source_ip = get_client_ip(request)
    user_agent = str(request.headers.get("user-agent") or "")
    order_no_raw = str(params.get("out_trade_no") or "").strip() or None
    trade_no_raw = str(params.get("trade_no") or "").strip() or None

    amount_raw: Decimal | None = None
    money_str = str(params.get("money") or "").strip()
    try:
        if money_str:
            amount_raw = _quantize_amount(float(money_str))
    except Exception:
        amount_raw = None

    if not (settings.ikunpay_key or "").strip():
        await _record_callback_event(
            db,
            provider="ikunpay",
            order_no=order_no_raw,
            trade_no=trade_no_raw,
            amount=amount_raw,
            verified=False,
            error_message="IKUNPAY_KEY 未设置",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        critical_event_reporter.fire_and_forget(
            event="payment_config_missing",
            severity="error",
            request_id=request_id,
            title="支付回调配置缺失",
            message="IKUNPAY_KEY 未设置",
            data={
                "provider": "ikunpay",
                "order_no": order_no_raw,
                "trade_no": trade_no_raw,
                "path": str(request.url.path),
            },
            dedup_key="payment_config_missing|ikunpay_key",
        )
        return Response(content="fail", status_code=500, media_type="text/plain")

    if not _ikunpay_verify_md5(params, settings.ikunpay_key):
        await _record_callback_event(
            db,
            provider="ikunpay",
            order_no=order_no_raw,
            trade_no=trade_no_raw,
            amount=amount_raw,
            verified=False,
            error_message="验签失败",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return Response(content="fail", status_code=400, media_type="text/plain")

    pid = str(params.get("pid") or "").strip()
    if (settings.ikunpay_pid or "").strip() and pid and pid != str(settings.ikunpay_pid).strip():
        await _record_callback_event(
            db,
            provider="ikunpay",
            order_no=order_no_raw,
            trade_no=trade_no_raw,
            amount=amount_raw,
            verified=True,
            error_message="pid 不匹配",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return Response(content="fail", status_code=400, media_type="text/plain")

    trade_status = str(params.get("trade_status") or "").strip()
    if trade_status != "TRADE_SUCCESS":
        await _record_callback_event(
            db,
            provider="ikunpay",
            order_no=order_no_raw,
            trade_no=trade_no_raw,
            amount=amount_raw,
            verified=True,
            error_message=f"ignored_trade_status:{trade_status}" if trade_status else "ignored_trade_status",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return Response(content="success", media_type="text/plain")

    order_no = str(params.get("out_trade_no") or "").strip()
    trade_no = str(params.get("trade_no") or "").strip()
    if not order_no or not trade_no or not money_str:
        await _record_callback_event(
            db,
            provider="ikunpay",
            order_no=order_no_raw,
            trade_no=trade_no_raw,
            amount=amount_raw,
            verified=True,
            error_message="缺少字段",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return Response(content="fail", status_code=400, media_type="text/plain")

    try:
        amount = _quantize_amount(float(money_str))
    except Exception:
        await _record_callback_event(
            db,
            provider="ikunpay",
            order_no=order_no,
            trade_no=trade_no,
            amount=amount_raw,
            verified=True,
            error_message="金额格式错误",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return Response(content="fail", status_code=400, media_type="text/plain")

    lock_key = f"locks:payment_notify:ikunpay:{trade_no or order_no}"
    lock_value = uuid.uuid4().hex
    acquired = await cache_service.acquire_lock(lock_key, lock_value, expire=30)
    if not acquired:
        return Response(content="fail", status_code=503, media_type="text/plain")

    try:
        result = await db.execute(select(PaymentOrder).where(PaymentOrder.order_no == order_no))
        order = result.scalar_one_or_none()
        if not order:
            await _record_callback_event(
                db,
                provider="ikunpay",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount,
                verified=True,
                error_message="订单不存在",
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            return Response(content="fail", status_code=404, media_type="text/plain")

        if order.status == PaymentStatus.PAID:
            await _record_callback_event(
                db,
                provider="ikunpay",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount,
                verified=True,
                error_message=None,
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            return Response(content="success", media_type="text/plain")

        if order.status != PaymentStatus.PENDING:
            await _record_callback_event(
                db,
                provider="ikunpay",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount,
                verified=True,
                error_message="订单状态异常",
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            return Response(content="fail", status_code=400, media_type="text/plain")

        if _quantize_amount(float(order.actual_amount)) != amount:
            await _record_callback_event(
                db,
                provider="ikunpay",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount,
                verified=True,
                error_message="金额不一致",
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            return Response(content="fail", status_code=400, media_type="text/plain")

        try:
            await _mark_order_paid_in_tx(
                db,
                order=order,
                payment_method="ikunpay",
                trade_no=trade_no,
                amount=amount,
            )
            await db.commit()
        except Exception as e:
            await db.rollback()
            await _record_callback_event(
                db,
                provider="ikunpay",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount,
                verified=True,
                error_message="订单落库失败",
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            critical_event_reporter.fire_and_forget(
                event="payment_callback_persist_failed",
                severity="error",
                request_id=request_id,
                title="支付回调落库失败",
                message=str(e),
                data={
                    "provider": "ikunpay",
                    "order_no": order_no,
                    "trade_no": trade_no,
                },
                dedup_key="payment_callback_persist_failed|ikunpay",
            )
            return Response(content="fail", status_code=500, media_type="text/plain")

        await _record_callback_event(
            db,
            provider="ikunpay",
            order_no=order_no,
            trade_no=trade_no,
            amount=amount,
            verified=True,
            error_message=None,
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )

        return Response(content="success", media_type="text/plain")
    finally:
        _ = await cache_service.release_lock(lock_key, lock_value)


@router.post("/webhook", summary="支付回调（验签）")
async def payment_webhook(
    data: PaymentWebhookRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    request_id = str(getattr(request.state, "request_id", "") or "").strip() or uuid.uuid4().hex
    source_ip = get_client_ip(request)
    user_agent = str(request.headers.get("user-agent") or "")
    if data.payment_method not in {"alipay", "wechat"}:
        await _record_callback_event(
            db,
            provider=str(data.payment_method),
            order_no=str(data.order_no),
            trade_no=None,
            amount=None,
            verified=False,
            error_message="无效的支付方式",
            raw_payload=json.dumps(data.model_dump(), ensure_ascii=False, separators=(",", ":")),
            source_ip=source_ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=400, detail="无效的支付方式")

    amount = _quantize_amount(data.amount)
    sign_payload = f"{data.order_no}|{data.trade_no}|{data.payment_method}|{amount}"
    expected_signature = hmac.new(
        settings.payment_webhook_secret.encode("utf-8"),
        sign_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, data.signature):
        await _record_callback_event(
            db,
            provider=str(data.payment_method),
            order_no=str(data.order_no),
            trade_no=str(data.trade_no),
            amount=amount,
            verified=False,
            error_message="签名校验失败",
            raw_payload=json.dumps(data.model_dump(), ensure_ascii=False, separators=(",", ":")),
            source_ip=source_ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=400, detail="签名校验失败")

    result = await db.execute(select(PaymentOrder).where(PaymentOrder.order_no == data.order_no))
    order = result.scalar_one_or_none()
    if not order:
        await _record_callback_event(
            db,
            provider=str(data.payment_method),
            order_no=str(data.order_no),
            trade_no=str(data.trade_no),
            amount=amount,
            verified=True,
            error_message="订单不存在",
            raw_payload=json.dumps(data.model_dump(), ensure_ascii=False, separators=(",", ":")),
            source_ip=source_ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.status == PaymentStatus.PAID:
        await _record_callback_event(
            db,
            provider=str(data.payment_method),
            order_no=str(data.order_no),
            trade_no=str(data.trade_no),
            amount=amount,
            verified=True,
            error_message=None,
            raw_payload=json.dumps(data.model_dump(), ensure_ascii=False, separators=(",", ":")),
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return {"message": "OK"}

    if order.status != PaymentStatus.PENDING:
        await _record_callback_event(
            db,
            provider=str(data.payment_method),
            order_no=str(data.order_no),
            trade_no=str(data.trade_no),
            amount=amount,
            verified=True,
            error_message="订单状态异常",
            raw_payload=json.dumps(data.model_dump(), ensure_ascii=False, separators=(",", ":")),
            source_ip=source_ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=400, detail="订单状态异常")

    if _quantize_amount(float(order.actual_amount)) != amount:
        await _record_callback_event(
            db,
            provider=str(data.payment_method),
            order_no=str(data.order_no),
            trade_no=str(data.trade_no),
            amount=amount,
            verified=True,
            error_message="金额不一致",
            raw_payload=json.dumps(data.model_dump(), ensure_ascii=False, separators=(",", ":")),
            source_ip=source_ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=400, detail="金额不一致")

    try:
        await _mark_order_paid_in_tx(
            db,
            order=order,
            payment_method=data.payment_method,
            trade_no=data.trade_no,
            amount=amount,
        )
        await db.commit()
    except HTTPException as e:
        await db.rollback()
        sc = int(getattr(e, "status_code", 500) or 500)
        if sc >= 500:
            critical_event_reporter.fire_and_forget(
                event="payment_webhook_failed",
                severity="error",
                request_id=request_id,
                title="支付回调处理失败",
                message=str(getattr(e, "detail", "") or ""),
                data={
                    "provider": str(data.payment_method),
                    "order_no": str(data.order_no),
                    "trade_no": str(data.trade_no),
                    "status_code": sc,
                },
                dedup_key=f"payment_webhook_failed|{str(data.payment_method)}|{sc}",
            )
        raise
    except Exception as e:
        await db.rollback()
        critical_event_reporter.fire_and_forget(
            event="payment_webhook_failed",
            severity="error",
            request_id=request_id,
            title="支付回调处理失败",
            message=str(e),
            data={
                "provider": str(data.payment_method),
                "order_no": str(data.order_no),
                "trade_no": str(data.trade_no),
                "status_code": 500,
            },
            dedup_key=f"payment_webhook_failed|{str(data.payment_method)}|500",
        )
        raise

    await _record_callback_event(
        db,
        provider=str(data.payment_method),
        order_no=str(data.order_no),
        trade_no=str(data.trade_no),
        amount=amount,
        verified=True,
        error_message=None,
        raw_payload=json.dumps(data.model_dump(), ensure_ascii=False, separators=(",", ":")),
        source_ip=source_ip,
        user_agent=user_agent,
    )

    return {"message": "OK"}


@router.post("/wechat/notify", summary="微信支付回调（验签）")
@rate_limit(*RateLimitConfig.PAYMENT_NOTIFY, by_ip=True)
async def wechat_notify(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    request_id = str(getattr(request.state, "request_id", "") or "").strip() or uuid.uuid4().hex
    body = await request.body()
    payload_raw = body.decode("utf-8", errors="replace")

    source_ip = get_client_ip(request)
    user_agent = str(request.headers.get("user-agent") or "")

    serial = str(request.headers.get("Wechatpay-Serial") or "").strip()
    timestamp = str(request.headers.get("Wechatpay-Timestamp") or "").strip()
    nonce = str(request.headers.get("Wechatpay-Nonce") or "").strip()
    signature = str(request.headers.get("Wechatpay-Signature") or "").strip()
    signature_type = str(request.headers.get("Wechatpay-Signature-Type") or "").strip()

    cfg_raw = await _get_system_config_value(db, "WECHATPAY_PLATFORM_CERTS_JSON")
    certs = load_platform_certs_json(cfg_raw or "")
    cert = certs.get(serial)
    if not cert:
        await _record_callback_event(
            db,
            provider="wechat",
            order_no=None,
            trade_no=None,
            amount=None,
            verified=False,
            error_message="平台证书未配置",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=400, detail="平台证书未配置")

    if not (timestamp and nonce and signature):
        await _record_callback_event(
            db,
            provider="wechat",
            order_no=None,
            trade_no=None,
            amount=None,
            verified=False,
            error_message="缺少签名头",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=400, detail="缺少签名头")

    if not signature_type:
        await _record_callback_event(
            db,
            provider="wechat",
            order_no=None,
            trade_no=None,
            amount=None,
            verified=False,
            error_message="缺少签名类型",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=400, detail="缺少签名类型")

    if signature_type != "WECHATPAY2-SHA256-RSA2048":
        await _record_callback_event(
            db,
            provider="wechat",
            order_no=None,
            trade_no=None,
            amount=None,
            verified=False,
            error_message=f"不支持的签名类型:{signature_type}",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=400, detail="不支持的签名类型")

    if not wechatpay_verify_signature(
        cert_pem=cert.pem,
        timestamp=timestamp,
        nonce=nonce,
        body=body,
        signature_b64=signature,
    ):
        await _record_callback_event(
            db,
            provider="wechat",
            order_no=None,
            trade_no=None,
            amount=None,
            verified=False,
            error_message="验签失败",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=400, detail="验签失败")

    if not settings.wechatpay_api_v3_key:
        await _record_callback_event(
            db,
            provider="wechat",
            order_no=None,
            trade_no=None,
            amount=None,
            verified=False,
            error_message="WECHATPAY_API_V3_KEY 未设置",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        critical_event_reporter.fire_and_forget(
            event="payment_config_missing",
            severity="error",
            request_id=request_id,
            title="支付回调配置缺失",
            message="WECHATPAY_API_V3_KEY 未设置",
            data={
                "provider": "wechat",
                "path": str(request.url.path),
            },
            dedup_key="payment_config_missing|wechatpay_api_v3_key",
        )
        raise HTTPException(status_code=500, detail="WECHATPAY_API_V3_KEY 未设置")

    try:
        data_raw: object = cast(object, json.loads(payload_raw))
        if not isinstance(data_raw, dict):
            raise ValueError("invalid body")
        data = cast(dict[str, object], data_raw)
        resource_obj = data.get("resource")
        if not isinstance(resource_obj, dict):
            raise ValueError("missing resource")
        resource = cast(dict[str, object], resource_obj)
        nonce_r = str(resource.get("nonce") or "")
        ad_r = str(resource.get("associated_data") or "")
        ciphertext_r = str(resource.get("ciphertext") or "")
        if not nonce_r or not ciphertext_r:
            raise ValueError("missing resource fields")

        plain = wechatpay_decrypt_resource(
            api_v3_key=settings.wechatpay_api_v3_key,
            nonce=nonce_r,
            associated_data=ad_r,
            ciphertext=ciphertext_r,
        )
        plain_obj_raw: object = cast(object, json.loads(plain.decode("utf-8")))
        if not isinstance(plain_obj_raw, dict):
            raise ValueError("invalid resource")
        plain_obj = cast(dict[str, object], plain_obj_raw)
    except Exception:
        await _record_callback_event(
            db,
            provider="wechat",
            order_no=None,
            trade_no=None,
            amount=None,
            verified=True,
            error_message="解密失败",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=400, detail="解密失败")

    order_no = str(plain_obj.get("out_trade_no") or "").strip() or None
    trade_no = str(plain_obj.get("transaction_id") or "").strip() or None
    trade_state = str(plain_obj.get("trade_state") or "").strip()
    amount_yuan: Decimal | None = None
    try:
        amount_obj = plain_obj.get("amount")
        if isinstance(amount_obj, dict):
            raw_total = cast(dict[str, object], amount_obj).get("total")
            total_cents: int = 0
            if isinstance(raw_total, bool):
                total_cents = 0
            elif isinstance(raw_total, (int, float)):
                total_cents = int(raw_total)
            elif isinstance(raw_total, str) and raw_total.strip():
                total_cents = int(raw_total.strip())

            amount_yuan = _quantize_amount(float(Decimal(total_cents) / 100))
    except Exception:
        amount_yuan = None

    if not order_no or not trade_no:
        await _record_callback_event(
            db,
            provider="wechat",
            order_no=order_no,
            trade_no=trade_no,
            amount=amount_yuan,
            verified=True,
            error_message="缺少字段",
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return {"code": "SUCCESS", "message": "OK"}

    lock_key = f"locks:payment_notify:wechat:{trade_no or order_no}"
    lock_value = uuid.uuid4().hex
    acquired = await cache_service.acquire_lock(lock_key, lock_value, expire=30)
    if not acquired:
        return {"code": "FAIL", "message": "BUSY"}

    try:
        if trade_state and trade_state != "SUCCESS":
            await _record_callback_event(
                db,
                provider="wechat",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount_yuan,
                verified=True,
                error_message=f"ignored_trade_state:{trade_state}",
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            return {"code": "SUCCESS", "message": "OK"}

        if amount_yuan is None:
            await _record_callback_event(
                db,
                provider="wechat",
                order_no=order_no,
                trade_no=trade_no,
                amount=None,
                verified=True,
                error_message="金额缺失",
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            return {"code": "SUCCESS", "message": "OK"}

        result = await db.execute(select(PaymentOrder).where(PaymentOrder.order_no == order_no))
        order = result.scalar_one_or_none()
        if not order:
            await _record_callback_event(
                db,
                provider="wechat",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount_yuan,
                verified=True,
                error_message="订单不存在",
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            return {"code": "SUCCESS", "message": "OK"}

        if order.status == PaymentStatus.PAID:
            await _record_callback_event(
                db,
                provider="wechat",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount_yuan,
                verified=True,
                error_message=None,
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            return {"code": "SUCCESS", "message": "OK"}

        if order.status != PaymentStatus.PENDING:
            await _record_callback_event(
                db,
                provider="wechat",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount_yuan,
                verified=True,
                error_message="订单状态异常",
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            return {"code": "SUCCESS", "message": "OK"}

        if _quantize_amount(float(order.actual_amount)) != amount_yuan:
            await _record_callback_event(
                db,
                provider="wechat",
                order_no=order_no,
                trade_no=trade_no,
                amount=amount_yuan,
                verified=True,
                error_message="金额不一致",
                raw_payload=payload_raw,
                source_ip=source_ip,
                user_agent=user_agent,
            )
            return {"code": "SUCCESS", "message": "OK"}

        try:
            await _mark_order_paid_in_tx(
                db,
                order=order,
                payment_method="wechat",
                trade_no=trade_no,
                amount=amount_yuan,
            )
            await db.commit()
        except HTTPException as e:
            await db.rollback()
            sc = int(getattr(e, "status_code", 500) or 500)
            if sc >= 500:
                critical_event_reporter.fire_and_forget(
                    event="payment_callback_persist_failed",
                    severity="error",
                    request_id=request_id,
                    title="支付回调处理失败",
                    message=str(getattr(e, "detail", "") or ""),
                    data={
                        "provider": "wechat",
                        "order_no": order_no,
                        "trade_no": trade_no,
                        "status_code": sc,
                    },
                    dedup_key=f"payment_callback_persist_failed|wechat|{sc}",
                )
            raise
        except Exception as e:
            await db.rollback()
            critical_event_reporter.fire_and_forget(
                event="payment_callback_persist_failed",
                severity="error",
                request_id=request_id,
                title="支付回调处理失败",
                message=str(e),
                data={
                    "provider": "wechat",
                    "order_no": order_no,
                    "trade_no": trade_no,
                    "status_code": 500,
                },
                dedup_key="payment_callback_persist_failed|wechat|500",
            )
            raise

        await _record_callback_event(
            db,
            provider="wechat",
            order_no=order_no,
            trade_no=trade_no,
            amount=amount_yuan,
            verified=True,
            error_message=None,
            raw_payload=payload_raw,
            source_ip=source_ip,
            user_agent=user_agent,
        )

        return {"code": "SUCCESS", "message": "OK"}
    finally:
        _ = await cache_service.release_lock(lock_key, lock_value)


@router.get("/orders", summary="获取订单列表")
async def get_orders(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: str | None = None,
):
    """获取当前用户的订单列表"""
    query = select(PaymentOrder).where(PaymentOrder.user_id == current_user.id)
    
    if status_filter:
        query = query.where(PaymentOrder.status == status_filter)
    
    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total: int = int(await db.scalar(count_query) or 0)
    
    # 分页
    query = query.order_by(PaymentOrder.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    orders = result.scalars().all()
    
    items = [
        OrderResponse(
            id=o.id,
            order_no=o.order_no,
            order_type=o.order_type,
            amount=o.amount,
            actual_amount=o.actual_amount,
            status=o.status,
            payment_method=o.payment_method,
            title=o.title,
            created_at=o.created_at,
            paid_at=o.paid_at,
        )
        for o in orders
    ]
    
    return {"items": items, "total": total}


@router.get("/orders/{order_no}", summary="获取订单详情")
async def get_order_detail(
    order_no: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取订单详情"""
    result = await db.execute(
        select(PaymentOrder).where(
            PaymentOrder.order_no == order_no,
            PaymentOrder.user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    return OrderResponse(
        id=order.id,
        order_no=order.order_no,
        order_type=order.order_type,
        amount=order.amount,
        actual_amount=order.actual_amount,
        status=order.status,
        payment_method=order.payment_method,
        title=order.title,
        created_at=order.created_at,
        paid_at=order.paid_at,
    )


@router.post("/orders/{order_no}/cancel", summary="取消订单")
async def cancel_order(
    order_no: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """取消订单"""
    result = await db.execute(
        select(PaymentOrder).where(
            PaymentOrder.order_no == order_no,
            PaymentOrder.user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    if order.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=400, detail="只能取消待支付订单")
    
    order.status = PaymentStatus.CANCELLED
    await db.commit()
    
    return {"message": "订单已取消"}


# ============ 余额相关 ============

@router.get("/balance", summary="获取余额")
async def get_balance(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取当前用户余额"""
    balance = await get_or_create_balance(db, current_user.id)
    
    return BalanceResponse(
        balance=balance.balance,
        frozen=balance.frozen,
        total_recharged=balance.total_recharged,
        total_consumed=balance.total_consumed,
    )


@router.get("/balance/transactions", summary="获取余额交易记录")
async def get_balance_transactions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """获取余额交易记录"""
    query = select(BalanceTransaction).where(
        BalanceTransaction.user_id == current_user.id
    )
    
    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total: int = int(await db.scalar(count_query) or 0)
    
    # 分页
    query = query.order_by(BalanceTransaction.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    transactions = result.scalars().all()
    
    items = [
        {
            "id": t.id,
            "type": t.type,
            "amount": t.amount,
            "balance_after": t.balance_after,
            "description": t.description,
            "created_at": t.created_at,
        }
        for t in transactions
    ]
    
    return {"items": items, "total": total}


# ============ 管理员接口 ============

@router.get("/admin/orders", summary="管理员-订单列表")
async def admin_get_orders(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: str | None = None,
    user_id: int | None = None,
):
    """管理员获取所有订单"""
    _ = current_user
    query = select(PaymentOrder, User.username).join(User, User.id == PaymentOrder.user_id)
    
    if status_filter:
        query = query.where(PaymentOrder.status == status_filter)
    if user_id:
        query = query.where(PaymentOrder.user_id == user_id)
    
    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total: int = int(await db.scalar(count_query) or 0)
    
    # 分页
    query = query.order_by(PaymentOrder.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = cast(list[tuple[PaymentOrder, str]], result.all())
     
    items: list[dict[str, object]] = []
    for o, username in rows:
        items.append({
            "id": o.id,
            "order_no": o.order_no,
            "user_id": o.user_id,
            "username": username,
            "order_type": o.order_type,
            "amount": o.amount,
            "actual_amount": o.actual_amount,
            "status": o.status,
            "payment_method": o.payment_method,
            "title": o.title,
            "created_at": o.created_at,
            "paid_at": o.paid_at,
        })
    
    return {"items": items, "total": total}


@router.post("/admin/refund/{order_no}", summary="管理员-退款")
async def admin_refund(
    order_no: str,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """管理员退款"""
    _ = current_user
    result = await db.execute(
        select(PaymentOrder).where(PaymentOrder.order_no == order_no)
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    if order.status == PaymentStatus.REFUNDED:
        return {"message": "退款成功"}

    if order.status != PaymentStatus.PAID:
        raise HTTPException(status_code=400, detail="只能退款已支付订单")

    refund_amount = _quantize_amount(float(order.actual_amount))
    refund_amount_cents = _decimal_to_cents(refund_amount)

    try:
        # 原子更新订单状态，确保幂等
        order_update = await db.execute(
            update(PaymentOrder)
            .where(PaymentOrder.id == order.id, PaymentOrder.status == PaymentStatus.PAID)
            .values(status=PaymentStatus.REFUNDED)
        )
        if getattr(order_update, "rowcount", 0) != 1:
            raise HTTPException(status_code=400, detail="订单状态异常")

        # 如果是余额支付，退回余额
        if order.payment_method == "balance":
            balance_account = await _get_or_create_balance_in_tx(db, order.user_id)
            balance_before = _quantize_amount(float(balance_account.balance))

            balance_before_cents = _decimal_to_cents(balance_before)
            effective_balance_cents = func.coalesce(
                UserBalance.balance_cents,
                sa_cast(func.round(func.coalesce(UserBalance.balance, 0) * 100), Integer),
            )

            _ = await db.execute(
                update(UserBalance)
                .where(UserBalance.user_id == order.user_id)
                .values(
                    balance=func.coalesce(UserBalance.balance, 0) + float(refund_amount),
                    balance_cents=effective_balance_cents + refund_amount_cents,
                )
            )

            balance_after = balance_before + refund_amount
            balance_after_cents = balance_before_cents + refund_amount_cents
            transaction = BalanceTransaction(
                user_id=order.user_id,
                order_id=order.id,
                type="refund",
                amount=float(refund_amount),
                balance_before=float(balance_before),
                balance_after=float(balance_after),
                amount_cents=refund_amount_cents,
                balance_before_cents=balance_before_cents,
                balance_after_cents=balance_after_cents,
                description=f"退款: {order.title}",
            )
            db.add(transaction)

        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    return {"message": "退款成功"}


@router.post("/admin/orders/{order_no}/mark-paid", summary="管理员-标记订单已支付")
async def admin_mark_paid(
    order_no: str,
    data: MarkPaidRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """管理员标记订单已支付（开发环境/人工对账用）"""
    _ = current_user

    if data.payment_method not in {"alipay", "wechat"}:
        raise HTTPException(status_code=400, detail="无效的支付方式")

    result = await db.execute(select(PaymentOrder).where(PaymentOrder.order_no == order_no))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.status == PaymentStatus.PAID:
        return {"message": "订单已是支付成功状态"}

    if order.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=400, detail="订单状态异常")

    if order.order_type != "recharge":
        raise HTTPException(status_code=400, detail="仅充值订单支持该操作")

    paid_at = datetime.now(timezone.utc)
    trade_no = f"ADM{generate_order_no()}"
    recharge_amount = _quantize_amount(float(order.actual_amount))
    recharge_amount_cents = _decimal_to_cents(recharge_amount)

    try:
        order_update = await db.execute(
            update(PaymentOrder)
            .where(PaymentOrder.id == order.id, PaymentOrder.status == PaymentStatus.PENDING)
            .values(
                status=PaymentStatus.PAID,
                payment_method=data.payment_method,
                paid_at=paid_at,
                trade_no=trade_no,
                amount_cents=func.coalesce(
                    PaymentOrder.amount_cents,
                    sa_cast(func.round(PaymentOrder.amount * 100), Integer),
                ),
                actual_amount_cents=recharge_amount_cents,
            )
        )
        if getattr(order_update, "rowcount", 0) != 1:
            raise HTTPException(status_code=400, detail="订单状态异常")

        balance_account = await _get_or_create_balance_in_tx(db, order.user_id)
        balance_before = _quantize_amount(float(balance_account.balance))

        balance_before_cents = _decimal_to_cents(balance_before)
        effective_balance_cents = func.coalesce(
            UserBalance.balance_cents,
            sa_cast(func.round(func.coalesce(UserBalance.balance, 0) * 100), Integer),
        )
        effective_total_recharged_cents = func.coalesce(
            UserBalance.total_recharged_cents,
            sa_cast(func.round(func.coalesce(UserBalance.total_recharged, 0) * 100), Integer),
        )

        _ = await db.execute(
            update(UserBalance)
            .where(UserBalance.user_id == order.user_id)
            .values(
                balance=func.coalesce(UserBalance.balance, 0) + float(recharge_amount),
                total_recharged=func.coalesce(UserBalance.total_recharged, 0) + float(recharge_amount),
                balance_cents=effective_balance_cents + recharge_amount_cents,
                total_recharged_cents=effective_total_recharged_cents + recharge_amount_cents,
            )
        )

        balance_after = balance_before + recharge_amount
        balance_after_cents = balance_before_cents + recharge_amount_cents
        transaction = BalanceTransaction(
            user_id=order.user_id,
            order_id=order.id,
            type="recharge",
            amount=float(recharge_amount),
            balance_before=float(balance_before),
            balance_after=float(balance_after),
            amount_cents=recharge_amount_cents,
            balance_before_cents=balance_before_cents,
            balance_after_cents=balance_after_cents,
            description=f"充值: {order.title}",
        )
        db.add(transaction)

        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    return {"message": "标记成功"}


@router.get("/admin/stats", summary="管理员-支付统计")
async def admin_payment_stats(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """支付统计数据"""
    _ = current_user
    # 总订单数
    total_orders = await db.scalar(select(func.count()).select_from(PaymentOrder)) or 0
    
    # 已支付订单
    paid_orders = await db.scalar(
        select(func.count()).select_from(PaymentOrder).where(
            PaymentOrder.status == PaymentStatus.PAID
        )
    ) or 0
    
    # 总收入
    total_revenue_cents = await db.scalar(
        select(
            func.sum(
                func.coalesce(
                    PaymentOrder.actual_amount_cents,
                    sa_cast(func.round(PaymentOrder.actual_amount * 100), Integer),
                )
            )
        ).where(PaymentOrder.status == PaymentStatus.PAID)
    ) or 0
    total_revenue = float((Decimal(int(total_revenue_cents)) / 100).quantize(Decimal("0.01")))
    
    # 今日收入
    today = datetime.now(timezone.utc).date()
    today_revenue_cents = await db.scalar(
        select(
            func.sum(
                func.coalesce(
                    PaymentOrder.actual_amount_cents,
                    sa_cast(func.round(PaymentOrder.actual_amount * 100), Integer),
                )
            )
        ).where(
            PaymentOrder.status == PaymentStatus.PAID,
            func.date(PaymentOrder.paid_at) == today,
        )
    ) or 0
    today_revenue = float((Decimal(int(today_revenue_cents)) / 100).quantize(Decimal("0.01")))
    
    return {
        "total_orders": total_orders,
        "paid_orders": paid_orders,
        "total_revenue": total_revenue,
        "today_revenue": today_revenue,
        "conversion_rate": round(paid_orders / max(total_orders, 1) * 100, 1),
    }


@router.get("/admin/callback-events", summary="管理员-支付回调事件")
async def admin_callback_events(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    provider: str | None = None,
    order_no: str | None = None,
    trade_no: str | None = None,
    verified: bool | None = None,
    q: str | None = None,
    has_error: bool | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
):
    _ = current_user
    query = select(PaymentCallbackEvent)

    if provider:
        query = query.where(PaymentCallbackEvent.provider == provider)
    if order_no:
        query = query.where(PaymentCallbackEvent.order_no == order_no)
    if trade_no:
        query = query.where(PaymentCallbackEvent.trade_no == trade_no)
    if verified is not None:
        query = query.where(PaymentCallbackEvent.verified == bool(verified))

    if q and str(q).strip():
        kw = f"%{str(q).strip()}%"
        query = query.where(
            (
                PaymentCallbackEvent.order_no.ilike(kw)
                | PaymentCallbackEvent.trade_no.ilike(kw)
                | PaymentCallbackEvent.error_message.ilike(kw)
            )
        )

    if has_error is not None:
        if bool(has_error):
            query = query.where(
                PaymentCallbackEvent.error_message.is_not(None)
                & (PaymentCallbackEvent.error_message != "")
            )
        else:
            query = query.where(
                (PaymentCallbackEvent.error_message.is_(None))
                | (PaymentCallbackEvent.error_message == "")
            )

    if from_ts is not None:
        try:
            dt = datetime.fromtimestamp(int(from_ts), tz=timezone.utc).replace(tzinfo=None)
            query = query.where(PaymentCallbackEvent.created_at >= dt)
        except Exception:
            pass

    if to_ts is not None:
        try:
            dt = datetime.fromtimestamp(int(to_ts), tz=timezone.utc).replace(tzinfo=None)
            query = query.where(PaymentCallbackEvent.created_at <= dt)
        except Exception:
            pass

    count_query = select(func.count()).select_from(query.subquery())
    total: int = int(await db.scalar(count_query) or 0)

    query = query.order_by(PaymentCallbackEvent.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(query)
    events = res.scalars().all()

    items = [
        CallbackEventResponse(
            id=e.id,
            provider=e.provider,
            order_no=e.order_no,
            trade_no=e.trade_no,
            amount=e.amount,
            verified=bool(e.verified),
            error_message=e.error_message,
            created_at=e.created_at,
        )
        for e in events
    ]
    return {"items": items, "total": total}


@router.get("/admin/callback-events/stats", summary="管理员-支付回调统计")
async def admin_callback_event_stats(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    minutes: Annotated[int, Query(ge=1, le=60 * 24 * 30)] = 60,
    provider: str | None = None,
):
    _ = current_user
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=int(minutes))
    since_naive = since.replace(tzinfo=None)

    base_where: list[ColumnElement[bool]] = []
    if provider:
        base_where.append(PaymentCallbackEvent.provider == provider)

    all_total = await db.scalar(
        select(func.count()).select_from(PaymentCallbackEvent).where(*base_where)
    ) or 0
    all_verified = await db.scalar(
        select(func.count())
        .select_from(PaymentCallbackEvent)
        .where(*base_where, PaymentCallbackEvent.verified == True)
    ) or 0
    all_failed = int(all_total) - int(all_verified)

    window_where: list[ColumnElement[bool]] = [
        *base_where,
        PaymentCallbackEvent.created_at >= since_naive,
    ]
    window_total = await db.scalar(
        select(func.count()).select_from(PaymentCallbackEvent).where(*window_where)
    ) or 0
    window_verified = await db.scalar(
        select(func.count())
        .select_from(PaymentCallbackEvent)
        .where(*window_where, PaymentCallbackEvent.verified == True)
    ) or 0
    window_failed = int(window_total) - int(window_verified)

    return {
        "minutes": int(minutes),
        "provider": provider,
        "all_total": int(all_total),
        "all_verified": int(all_verified),
        "all_failed": int(all_failed),
        "window_total": int(window_total),
        "window_verified": int(window_verified),
        "window_failed": int(window_failed),
    }


@router.get("/admin/callback-events/{event_id}", response_model=CallbackEventDetailResponse, summary="管理员-支付回调事件详情")
async def admin_callback_event_detail(
    event_id: int,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = current_user
    res = await db.execute(select(PaymentCallbackEvent).where(PaymentCallbackEvent.id == int(event_id)))
    e = res.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="回调事件不存在")

    return CallbackEventDetailResponse(
        id=e.id,
        provider=e.provider,
        order_no=e.order_no,
        trade_no=e.trade_no,
        amount=e.amount,
        verified=bool(e.verified),
        error_message=e.error_message,
        created_at=e.created_at,
        raw_payload=e.raw_payload,
        masked_payload=_mask_payload(e.raw_payload),
        raw_payload_hash=getattr(e, "raw_payload_hash", None),
        source_ip=getattr(e, "source_ip", None),
        user_agent=getattr(e, "user_agent", None),
    )


@router.get("/admin/wechat/platform-certs", summary="管理员-微信平台证书")
async def admin_wechat_platform_certs(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = current_user
    cfg_raw = await _get_system_config_value(db, "WECHATPAY_PLATFORM_CERTS_JSON")
    certs = load_platform_certs_json(cfg_raw or "")
    items: list[dict[str, object]] = []
    for serial, cert in certs.items():
        items.append({"serial_no": serial, "expire_time": cert.expire_time})
    items.sort(key=lambda x: str(x.get("serial_no") or ""))
    return {"items": items, "total": len(items)}


@router.get("/admin/channel-status", response_model=PaymentChannelStatusResponse, summary="管理员-支付渠道配置状态")
async def admin_payment_channel_status(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = current_user

    alipay_app_id_set = bool((settings.alipay_app_id or "").strip())
    alipay_public_key_set = bool((settings.alipay_public_key or "").strip())
    alipay_private_key_set = bool((settings.alipay_private_key or "").strip())
    alipay_notify_url_set = bool((settings.alipay_notify_url or "").strip())

    wechatpay_mch_id_set = bool((settings.wechatpay_mch_id or "").strip())
    wechatpay_serial_no_set = bool((settings.wechatpay_mch_serial_no or "").strip())
    wechatpay_private_key_set = bool((settings.wechatpay_private_key or "").strip())
    wechatpay_api_v3_key_set = bool((settings.wechatpay_api_v3_key or "").strip())

    ikunpay_pid_set = bool((settings.ikunpay_pid or "").strip())
    ikunpay_key_set = bool((settings.ikunpay_key or "").strip())
    ikunpay_notify_url_set = bool((settings.ikunpay_notify_url or "").strip())

    payment_webhook_secret_set = bool((settings.payment_webhook_secret or "").strip())

    cfg_raw = await _get_system_config_value(db, "WECHATPAY_PLATFORM_CERTS_JSON")
    certs_map = load_platform_certs_json(cfg_raw or "")

    updated_at: int | None = None
    try:
        obj_raw: object = cast(object, json.loads(cfg_raw or ""))
        if isinstance(obj_raw, dict):
            obj_dict = cast(dict[str, object], obj_raw)
            v = obj_dict.get("updated_at")
            if isinstance(v, bool):
                updated_at = None
            elif isinstance(v, (int, float)):
                updated_at = int(v)
            elif isinstance(v, str) and v.strip():
                updated_at = int(v.strip())
    except Exception:
        updated_at = None

    refresh_enabled_raw = os.getenv("WECHATPAY_CERT_REFRESH_ENABLED", "").strip().lower()
    refresh_enabled = refresh_enabled_raw in {"1", "true", "yes", "on"}

    frontend_base = str(getattr(settings, "frontend_base_url", "") or "").strip().rstrip("/")

    alipay_configured = bool(alipay_app_id_set and alipay_public_key_set and alipay_private_key_set and alipay_notify_url_set)
    wechatpay_configured = bool(
        wechatpay_mch_id_set and wechatpay_serial_no_set and wechatpay_private_key_set and wechatpay_api_v3_key_set
    )
    ikunpay_configured = bool(ikunpay_pid_set and ikunpay_key_set and ikunpay_notify_url_set)

    alipay_return_url = (settings.alipay_return_url or "").strip() or None
    alipay_effective_return_url = alipay_return_url
    if alipay_effective_return_url is None and frontend_base:
        alipay_effective_return_url = f"{frontend_base}/payment/return"

    return PaymentChannelStatusResponse(
        alipay_configured=alipay_configured,
        wechatpay_configured=wechatpay_configured,
        ikunpay_configured=ikunpay_configured,
        payment_webhook_secret_configured=payment_webhook_secret_set,
        wechatpay_platform_certs_cached=len(certs_map) > 0,
        wechatpay_platform_certs_total=len(certs_map),
        wechatpay_platform_certs_updated_at=updated_at,
        wechatpay_cert_refresh_enabled=refresh_enabled,
        details={
            "alipay": {
                "app_id_set": alipay_app_id_set,
                "public_key_set": alipay_public_key_set,
                "private_key_set": alipay_private_key_set,
                "notify_url_set": alipay_notify_url_set,
                "public_key_check": _alipay_public_key_check(settings.alipay_public_key),
                "private_key_check": _alipay_private_key_check(settings.alipay_private_key),
                "gateway_url": (settings.alipay_gateway_url or "").strip() or None,
                "notify_url": (settings.alipay_notify_url or "").strip() or None,
                "return_url": alipay_return_url,
                "effective_return_url": alipay_effective_return_url,
            },
            "ikunpay": {
                "pid_set": ikunpay_pid_set,
                "key_set": ikunpay_key_set,
                "notify_url_set": ikunpay_notify_url_set,
                "gateway_url": (settings.ikunpay_gateway_url or "").strip() or None,
                "notify_url": (settings.ikunpay_notify_url or "").strip() or None,
                "return_url": (settings.ikunpay_return_url or "").strip() or None,
                "default_type": (settings.ikunpay_default_type or "").strip() or None,
            },
            "wechatpay": {
                "mch_id_set": wechatpay_mch_id_set,
                "serial_no_set": wechatpay_serial_no_set,
                "private_key_set": wechatpay_private_key_set,
                "api_v3_key_set": wechatpay_api_v3_key_set,
            },
        },
    )


class PaymentEnvItem(BaseModel):
    key: str
    value: str | None = None


class PaymentEnvUpdateRequest(BaseModel):
    items: list[PaymentEnvItem]


@router.post("/admin/env", summary="管理员-更新支付环境变量（写入 env 文件并热加载）")
async def admin_update_payment_env(
    req: PaymentEnvUpdateRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    _ = current_user

    updates: dict[str, str | None] = {}
    for item in (req.items or []):
        k = str(getattr(item, "key", "") or "").strip().upper()
        v_obj = getattr(item, "value", None)
        v = None if v_obj is None else str(v_obj)
        if not k:
            continue
        updates[k] = v

    running_tests = bool(os.getenv("PYTEST_CURRENT_TEST")) or ("pytest" in sys.modules)

    env_file_name = "in-memory"
    updated_keys: list[str] = []
    if not running_tests:
        env_path = _resolve_env_file_path()
        updated_keys = _update_env_file(env_path, updates)
        env_file_name = str(env_path.name)
    else:
        updated_keys = sorted([str(k).strip().upper() for k in updates.keys() if str(k).strip()])

    if not updated_keys:
        raise HTTPException(status_code=400, detail="未提供可更新的配置项")

    for k in updated_keys:
        v = updates.get(k)
        if v is None or not str(v).strip():
            try:
                if k in os.environ:
                    del os.environ[k]
            except Exception:
                pass
        else:
            os.environ[k] = str(v)

    get_settings.cache_clear()
    global settings
    settings = get_settings()

    await _log_config_change(
        db,
        user_id=int(getattr(current_user, "id", 0) or 0),
        request=request,
        description=f"更新支付 env: {', '.join(updated_keys)}",
    )
    await db.commit()

    status = await admin_payment_channel_status(current_user=current_user, db=db)
    return {
        "message": "OK",
        "env_file": env_file_name,
        "updated_keys": updated_keys,
        "channel_status": status,
    }


@router.get("/channel-status", response_model=PublicPaymentChannelStatusResponse, summary="支付渠道配置状态")
async def payment_channel_status():
    alipay_configured = bool(
        (settings.alipay_app_id or "").strip()
        and (settings.alipay_public_key or "").strip()
        and (settings.alipay_private_key or "").strip()
        and (settings.alipay_notify_url or "").strip()
    )
    ikunpay_configured = bool(
        (settings.ikunpay_pid or "").strip()
        and (settings.ikunpay_key or "").strip()
        and (settings.ikunpay_notify_url or "").strip()
    )
    wechatpay_configured = bool(
        (settings.wechatpay_mch_id or "").strip()
        and (settings.wechatpay_mch_serial_no or "").strip()
        and (settings.wechatpay_private_key or "").strip()
        and (settings.wechatpay_api_v3_key or "").strip()
    )

    available_methods: list[str] = ["balance"]
    if alipay_configured:
        available_methods.append("alipay")
    if ikunpay_configured:
        available_methods.append("ikunpay")

    return PublicPaymentChannelStatusResponse(
        alipay_configured=alipay_configured,
        wechatpay_configured=wechatpay_configured,
        ikunpay_configured=ikunpay_configured,
        available_methods=available_methods,
    )


@router.post("/admin/wechat/platform-certs/import", summary="管理员-导入微信平台证书")
async def admin_import_wechat_platform_certs(
    req: WechatPlatformCertImportRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    existing_raw = await _get_system_config_value(db, "WECHATPAY_PLATFORM_CERTS_JSON")
    existing_map = load_platform_certs_json(existing_raw or "")
    merged: dict[str, WeChatPayPlatformCert] = dict(existing_map)

    if req.platform_certs_json and str(req.platform_certs_json).strip():
        incoming_raw = str(req.platform_certs_json)
        incoming_map = load_platform_certs_json(incoming_raw)
        if not incoming_map:
            raise HTTPException(status_code=400, detail="platform_certs_json 无法解析或为空（需为 dump_platform_certs_json 输出格式）")
        if req.merge:
            merged.update(incoming_map)
        else:
            merged = dict(incoming_map)

        raw = dump_platform_certs_json(list(merged.values()))
        await _set_system_config_value(
            db,
            key="WECHATPAY_PLATFORM_CERTS_JSON",
            value=raw,
            category="payment",
            description="WeChatPay platform certificates cache",
            updated_by=getattr(current_user, "id", None),
        )
        await db.commit()
        return {"message": "OK", "count": len(merged)}

    if req.cert_pem and str(req.cert_pem).strip():
        cert_pem = str(req.cert_pem).strip()
        serial_no = str(req.serial_no or "").strip()
        expire_time = str(req.expire_time or "").strip() or None

        if not serial_no or not expire_time:
            try:
                from cryptography import x509

                cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
                if not serial_no:
                    serial_no = format(int(cert.serial_number), "X").upper()
                if not expire_time:
                    dt = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after
                    expire_time = dt.replace(tzinfo=timezone.utc).isoformat()
            except Exception:
                pass

        if not serial_no:
            raise HTTPException(status_code=400, detail="无法从证书解析 serial_no，请手动填写")

        merged[serial_no] = WeChatPayPlatformCert(serial_no=serial_no, pem=cert_pem, expire_time=expire_time)
        raw = dump_platform_certs_json(list(merged.values()))
        await _set_system_config_value(
            db,
            key="WECHATPAY_PLATFORM_CERTS_JSON",
            value=raw,
            category="payment",
            description="WeChatPay platform certificates cache",
            updated_by=getattr(current_user, "id", None),
        )
        await db.commit()
        return {"message": "OK", "count": len(merged)}

    raise HTTPException(status_code=400, detail="请提供 platform_certs_json 或 cert_pem")


@router.post("/admin/wechat/platform-certs/refresh", summary="管理员-刷新微信平台证书")
async def admin_refresh_wechat_platform_certs(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not settings.wechatpay_mch_id or not settings.wechatpay_mch_serial_no:
        raise HTTPException(status_code=400, detail="WECHATPAY_MCH_ID/WECHATPAY_MCH_SERIAL_NO 未设置")
    if not settings.wechatpay_private_key:
        raise HTTPException(status_code=400, detail="WECHATPAY_PRIVATE_KEY 未设置")
    if not settings.wechatpay_api_v3_key:
        raise HTTPException(status_code=400, detail="WECHATPAY_API_V3_KEY 未设置")

    payment_mod = sys.modules.get("app.routers.payment")
    fetch_fn: Callable[..., Awaitable[list[WeChatPayPlatformCert]]] = fetch_platform_certificates
    if payment_mod is not None:
        candidate = getattr(payment_mod, "fetch_platform_certificates", None)
        if callable(candidate):
            fetch_fn = cast(Callable[..., Awaitable[list[WeChatPayPlatformCert]]], candidate)

    certs = await fetch_fn(
        certificates_url=settings.wechatpay_certificates_url,
        mch_id=settings.wechatpay_mch_id,
        mch_serial_no=settings.wechatpay_mch_serial_no,
        mch_private_key_pem=settings.wechatpay_private_key,
        api_v3_key=settings.wechatpay_api_v3_key,
    )
    raw = dump_platform_certs_json(certs)
    await _set_system_config_value(
        db,
        key="WECHATPAY_PLATFORM_CERTS_JSON",
        value=raw,
        category="payment",
        description="WeChatPay platform certificates cache",
        updated_by=getattr(current_user, "id", None),
    )
    await db.commit()

    return {"message": "OK", "count": len(certs)}


@router.get("/admin/reconcile/{order_no}", summary="管理员-订单与回调对账")
async def admin_reconcile_order(
    order_no: str,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
):
    _ = current_user
    res = await db.execute(select(PaymentOrder).where(PaymentOrder.order_no == order_no))
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    ev_res = await db.execute(
        select(PaymentCallbackEvent)
        .where(PaymentCallbackEvent.order_no == order_no)
        .order_by(PaymentCallbackEvent.created_at.desc())
        .limit(limit)
    )
    events = ev_res.scalars().all()

    recent_events = [
        ReconcileEventItem(
            provider=e.provider,
            order_no=e.order_no,
            trade_no=e.trade_no,
            amount=e.amount,
            verified=bool(e.verified),
            error_message=e.error_message,
            created_at=e.created_at,
        )
        for e in events
    ]

    callbacks_total = len(events)
    callbacks_verified = sum(1 for e in events if bool(e.verified))
    callbacks_failed = callbacks_total - callbacks_verified

    last_event = events[0] if events else None
    expected_amount = _quantize_amount(float(order.actual_amount))
    expected_amount_float = float(expected_amount)

    diagnosis = "ok"
    details: dict[str, object] = {
        "expected_amount": expected_amount_float,
        "last_event": {
            "provider": getattr(last_event, "provider", None),
            "verified": getattr(last_event, "verified", None),
            "error_message": getattr(last_event, "error_message", None),
            "created_at": getattr(last_event, "created_at", None),
        }
        if last_event
        else None,
    }

    if callbacks_total == 0:
        diagnosis = "no_callback"
    else:
        has_unverified = any(not bool(e.verified) for e in events)
        has_amount_mismatch = any(str(getattr(e, "error_message", "") or "") == "金额不一致" for e in events)
        has_decrypt_failed = any(str(getattr(e, "error_message", "") or "") == "解密失败" for e in events)
        has_sig_failed = any(str(getattr(e, "error_message", "") or "") == "验签失败" for e in events)
        has_verified_success = any(bool(e.verified) and not (getattr(e, "error_message", None)) for e in events)

        if has_amount_mismatch:
            diagnosis = "amount_mismatch"
        elif has_decrypt_failed:
            diagnosis = "decrypt_failed"
        elif has_sig_failed or has_unverified:
            diagnosis = "signature_failed"
        elif str(order.status) == PaymentStatus.PAID and not has_verified_success:
            diagnosis = "paid_without_success_callback"
        elif str(order.status) != PaymentStatus.PAID and has_verified_success:
            diagnosis = "success_callback_but_order_not_paid"

        details.update(
            {
                "has_verified_success": has_verified_success,
                "has_unverified": has_unverified,
                "has_amount_mismatch": has_amount_mismatch,
                "has_decrypt_failed": has_decrypt_failed,
                "has_sig_failed": has_sig_failed,
            }
        )

    return ReconcileResponse(
        order_no=order.order_no,
        order_status=str(order.status),
        payment_method=order.payment_method,
        actual_amount=float(order.actual_amount),
        trade_no=order.trade_no,
        callbacks_total=int(callbacks_total),
        callbacks_verified=int(callbacks_verified),
        callbacks_failed=int(callbacks_failed),
        diagnosis=str(diagnosis),
        details=details,
        paid_at=order.paid_at,
        recent_events=recent_events,
    )
