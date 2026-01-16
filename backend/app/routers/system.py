"""系统配置和日志API路由"""
from typing import Annotated, ClassVar, cast
import base64
import json
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_
from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from datetime import datetime, timedelta, timezone

from ..database import get_db
from ..models.system import SystemConfig, AdminLog, LogAction, LogModule
from ..models.user import User
from ..utils.deps import require_admin, get_current_user_optional
from ..utils.rate_limiter import get_client_ip, rate_limit, RateLimitConfig

router = APIRouter(prefix="/system", tags=["系统管理"])


def _prom_escape_label_value(value: str) -> str:
    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace("\"", "\\\"")
    s = s.replace("\n", "\\n")
    return s


# ============ 系统配置 ============

class ConfigItem(BaseModel):
    key: str
    value: str | None
    description: str | None = None
    category: str = "general"


class ConfigResponse(BaseModel):
    key: str
    value: str | None
    description: str | None
    category: str
    updated_at: datetime | None

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class ConfigBatchUpdate(BaseModel):
    configs: list[ConfigItem] = Field(validation_alias=AliasChoices("configs", "items"))


def _mask_config_value(key_name: str, value: str | None) -> str | None:
    if value is None:
        return None
    k = key_name.lower()
    if any(token in k for token in ("secret", "password", "api_key", "apikey", "providers", "private_key", "secret_key")):
        return "***"
    if re.search(r"(^|_)token($|_)", k):
        return "***"
    if re.search(r"(^|_)key($|_)", k):
        return "***"
    return value


def _news_ai_providers_config_contains_api_key(decoded_json: str) -> bool:
    s = str(decoded_json or "").strip()
    if not s:
        return False
    try:
        obj_raw: object = cast(object, json.loads(s))
        if isinstance(obj_raw, list):
            for item_obj in cast(list[object], obj_raw):
                if not isinstance(item_obj, dict):
                    continue
                item_dict = cast(dict[object, object], item_obj)
                for k_obj in item_dict.keys():
                    kk = str(k_obj or "").strip().lower()
                    if kk in {"api_key", "apikey"}:
                        return True
            return False
        if isinstance(obj_raw, dict):
            obj_dict = cast(dict[object, object], obj_raw)
            for k_obj in obj_dict.keys():
                kk = str(k_obj or "").strip().lower()
                if kk in {"api_key", "apikey"}:
                    return True
            return False
    except Exception:
        return bool(re.search(r'"api_key"|\bapi_key\b|"apikey"|\bapikey\b', s, flags=re.IGNORECASE))
    return False


def _validate_system_config_no_secrets(key: str, value: str | None) -> None:
    k = str(key or "").strip()
    if value is None or not str(value).strip():
        return

    k_upper = k.upper()
    k_lower = k.lower()
    providers_prefixes = ("NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON", "NEWS_AI_SUMMARY_LLM_PROVIDERS_B64")
    is_providers_key = k_upper in providers_prefixes or any(k_upper.startswith(f"{p}_") for p in providers_prefixes)
    if (
        any(token in k_lower for token in ("secret", "password", "api_key", "apikey", "private_key"))
        and not is_providers_key
    ):
        raise HTTPException(
            status_code=400,
            detail="Secret values must not be stored in SystemConfig. Use environment variables / Secret Manager.",
        )

    if not is_providers_key:
        return

    decoded = str(value)
    if k_upper.startswith("NEWS_AI_SUMMARY_LLM_PROVIDERS_B64"):
        try:
            decoded = base64.b64decode(str(value).strip()).decode("utf-8")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail="NEWS_AI_SUMMARY_LLM_PROVIDERS_B64 must be valid base64-encoded JSON",
            ) from e

    if _news_ai_providers_config_contains_api_key(decoded):
        raise HTTPException(
            status_code=400,
            detail=(
                "NEWS_AI providers config must not include api_key in SystemConfig. "
                "Use OPENAI_API_KEY (Secret/env) and omit api_key from providers JSON (Scheme A)."
            ),
        )


@router.get("/configs", response_model=list[ConfigResponse])
async def get_all_configs(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = None,
):
    """获取所有系统配置"""
    query = select(SystemConfig)
    if category:
        query = query.where(SystemConfig.category == category)
    query = query.order_by(SystemConfig.category, SystemConfig.key)
    
    result = await db.execute(query)
    configs = result.scalars().all()
    
    return [ConfigResponse(
        key=c.key,
        value=_mask_config_value(str(c.key), c.value),
        description=c.description,
        category=c.category,
        updated_at=c.updated_at
    ) for c in configs]


@router.get("/configs/{key}")
async def get_config(
    key: str,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取单个配置项"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        return {"key": key, "value": None}
    
    return {"key": config.key, "value": _mask_config_value(str(config.key), config.value)}


class NewsAiProviderPublic(BaseModel):
    name: str | None = None
    base_url: str
    model: str | None = None
    response_format: str | None = None
    auth_type: str | None = None
    auth_header_name: str | None = None
    auth_prefix: str | None = None
    chat_completions_path: str | None = None
    weight: int | None = None
    api_key_configured: bool = False


class NewsAiRecentError(BaseModel):
    news_id: int
    retry_count: int
    last_error: str | None
    last_error_at: datetime | None


class NewsAiErrorTrendItem(BaseModel):
    date: str
    errors: int


class NewsAiTopError(BaseModel):
    message: str
    count: int


class NewsAiStatusResponse(BaseModel):
    news_ai_enabled: bool
    news_ai_interval_seconds: float
    summary_llm_enabled: bool
    response_format: str | None
    provider_strategy: str
    providers: list[NewsAiProviderPublic]
    pending_total: int
    errors_total: int
    errors_last_24h: int
    errors_last_7d: int
    errors_trend_7d: list[NewsAiErrorTrendItem]
    top_errors: list[NewsAiTopError]
    recent_errors: list[NewsAiRecentError]
    config_overrides: dict[str, str]


@router.get("/news-ai/status", response_model=NewsAiStatusResponse)
async def get_news_ai_status(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from ..config import get_settings
    from ..models.news import News
    from ..models.news_ai import NewsAIAnnotation
    from ..services.news_ai_pipeline_service import news_ai_pipeline_service

    cfg_overrides = await news_ai_pipeline_service.load_system_config_overrides(db)

    def _env(name: str, default: str = "") -> str:
        v = cfg_overrides.get(name)
        if v is not None and str(v).strip():
            return str(v).strip()
        raw = os.getenv(name)
        if raw is None:
            return default
        return str(raw)

    def _bool(name: str, default: bool = False) -> bool:
        raw = _env(name, "")
        if not raw.strip():
            return bool(default)
        return raw.strip().lower() in {"1", "true", "yes", "y", "on"}

    settings = get_settings()
    providers_raw = news_ai_pipeline_service.get_summary_llm_providers(settings, env_overrides=cfg_overrides)
    providers: list[NewsAiProviderPublic] = []
    for p in providers_raw:
        api_key = str(p.get("api_key", "") or "").strip()
        providers.append(
            NewsAiProviderPublic(
                name=str(p.get("name", "") or "").strip() or None,
                base_url=str(p.get("base_url", "") or "").strip(),
                model=str(p.get("model", "") or "").strip() or None,
                response_format=str(p.get("response_format", "") or "").strip() or None,
                auth_type=str(p.get("auth_type", "") or "").strip() or None,
                auth_header_name=str(p.get("auth_header_name", "") or "").strip() or None,
                auth_prefix=str(p.get("auth_prefix", "") or "") if p.get("auth_prefix") is not None else None,
                chat_completions_path=str(p.get("chat_completions_path", "") or "").strip() or None,
                weight=int(p.get("weight", 0) or 0) if p.get("weight") is not None else None,
                api_key_configured=bool(api_key),
            )
        )

    where_clause = or_(
        NewsAIAnnotation.id.is_(None),
        NewsAIAnnotation.processed_at.is_(None),
        NewsAIAnnotation.highlights.is_(None),
        NewsAIAnnotation.keywords.is_(None),
    )

    pending_total_res = await db.execute(
        select(func.count(News.id))
        .select_from(News)
        .outerjoin(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id)
        .where(where_clause)
    )
    pending_total = int(pending_total_res.scalar() or 0)

    errors_total_res = await db.execute(select(func.count(NewsAIAnnotation.id)).where(NewsAIAnnotation.last_error.is_not(None)))
    errors_total = int(errors_total_res.scalar() or 0)

    now_dt = datetime.now()
    since_24h = now_dt - timedelta(hours=24)
    since_7d = now_dt - timedelta(days=7)

    errors_last_24h_res = await db.execute(
        select(func.count(NewsAIAnnotation.id)).where(
            and_(
                NewsAIAnnotation.last_error.is_not(None),
                NewsAIAnnotation.last_error_at.is_not(None),
                NewsAIAnnotation.last_error_at >= since_24h,
            )
        )
    )
    errors_last_24h = int(errors_last_24h_res.scalar() or 0)

    errors_last_7d_res = await db.execute(
        select(func.count(NewsAIAnnotation.id)).where(
            and_(
                NewsAIAnnotation.last_error.is_not(None),
                NewsAIAnnotation.last_error_at.is_not(None),
                NewsAIAnnotation.last_error_at >= since_7d,
            )
        )
    )
    errors_last_7d = int(errors_last_7d_res.scalar() or 0)

    today = now_dt.date()
    errors_trend_7d: list[NewsAiErrorTrendItem] = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=int(i))
        day_cnt_res = await db.execute(
            select(func.count(NewsAIAnnotation.id)).where(
                and_(
                    NewsAIAnnotation.last_error.is_not(None),
                    NewsAIAnnotation.last_error_at.is_not(None),
                    func.date(NewsAIAnnotation.last_error_at) == day,
                )
            )
        )
        errors_trend_7d.append(NewsAiErrorTrendItem(date=day.isoformat(), errors=int(day_cnt_res.scalar() or 0)))

    cnt = func.count(NewsAIAnnotation.id).label("cnt")
    top_res = await db.execute(
        select(NewsAIAnnotation.last_error, cnt)
        .where(NewsAIAnnotation.last_error.is_not(None))
        .group_by(NewsAIAnnotation.last_error)
        .order_by(desc(cnt))
        .limit(10)
    )
    top_any = cast(list[tuple[object, object]], list(top_res.all()))
    top_errors: list[NewsAiTopError] = []
    for msg_obj, cnt_obj in top_any:
        msg = str(msg_obj or "").strip()
        if not msg:
            continue
        c_int = 0
        if isinstance(cnt_obj, int):
            c_int = int(cnt_obj)
        elif isinstance(cnt_obj, float):
            c_int = int(cnt_obj)
        elif isinstance(cnt_obj, str):
            s = cnt_obj.strip()
            if s.isdigit():
                c_int = int(s)
        top_errors.append(NewsAiTopError(message=msg, count=int(c_int)))

    recent_res = await db.execute(
        select(
            NewsAIAnnotation.news_id,
            NewsAIAnnotation.retry_count,
            NewsAIAnnotation.last_error,
            NewsAIAnnotation.last_error_at,
        )
        .where(NewsAIAnnotation.last_error.is_not(None))
        .order_by(desc(NewsAIAnnotation.last_error_at), desc(NewsAIAnnotation.id))
        .limit(20)
    )

    recent_any = cast(list[tuple[object, object, object, object]], list(recent_res.all()))
    recent_rows: list[tuple[int, int, str | None, datetime | None]] = []
    for nid, rc, le, lea in recent_any:
        nid_int = 0
        if isinstance(nid, int):
            nid_int = int(nid)
        elif isinstance(nid, float):
            nid_int = int(nid)
        elif isinstance(nid, str):
            s = nid.strip()
            if s and re.fullmatch(r"-?\d+", s):
                nid_int = int(s)

        rc_int = 0
        if isinstance(rc, int):
            rc_int = int(rc)
        elif isinstance(rc, float):
            rc_int = int(rc)
        elif isinstance(rc, str):
            s = rc.strip()
            if s and re.fullmatch(r"-?\d+", s):
                rc_int = int(s)

        recent_rows.append(
            (
                int(nid_int),
                int(rc_int),
                (str(le) if le is not None else None),
                cast(datetime | None, lea),
            )
        )
    recent_errors = [
        NewsAiRecentError(
            news_id=int(nid),
            retry_count=int(rc or 0),
            last_error=le,
            last_error_at=lea,
        )
        for nid, rc, le, lea in recent_rows
    ]

    news_ai_enabled = str(os.getenv("NEWS_AI_ENABLED", "") or "").strip().lower() in {"1", "true", "yes", "on"}
    news_ai_interval_seconds = float(os.getenv("NEWS_AI_INTERVAL_SECONDS", "120").strip() or "120")

    provider_strategy = _env("NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY", "priority").strip() or "priority"
    response_format = _env("NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT", "").strip() or None

    return NewsAiStatusResponse(
        news_ai_enabled=bool(news_ai_enabled),
        news_ai_interval_seconds=float(news_ai_interval_seconds),
        summary_llm_enabled=bool(_bool("NEWS_AI_SUMMARY_LLM_ENABLED", False)),
        response_format=response_format,
        provider_strategy=str(provider_strategy),
        providers=providers,
        pending_total=int(pending_total),
        errors_total=int(errors_total),
        errors_last_24h=int(errors_last_24h),
        errors_last_7d=int(errors_last_7d),
        errors_trend_7d=errors_trend_7d,
        top_errors=top_errors,
        recent_errors=recent_errors,
        config_overrides={k: (_mask_config_value(k, v) or "") for k, v in cfg_overrides.items()},
    )


class AiOpsRecentError(BaseModel):
    at: str
    request_id: str
    endpoint: str
    error_code: str
    status_code: int | None
    message: str | None


class AiOpsTopErrorCode(BaseModel):
    error_code: str
    count: int


class AiOpsTopEndpoint(BaseModel):
    endpoint: str
    count: int


class AiOpsStatusResponse(BaseModel):
    ai_router_enabled: bool
    openai_api_key_configured: bool
    openai_base_url: str
    providers: list[dict[str, object]]
    ai_model: str
    chroma_persist_dir: str
    started_at: float
    started_at_iso: str
    chat_requests_total: int
    chat_stream_requests_total: int
    errors_total: int
    recent_errors: list[AiOpsRecentError]
    top_error_codes: list[AiOpsTopErrorCode]
    top_endpoints: list[AiOpsTopEndpoint]


@router.get("/ai/status", response_model=AiOpsStatusResponse)
async def get_ai_ops_status(
    _current_user: Annotated[User, Depends(require_admin)],
):
    from ..config import get_settings
    from ..services.ai_metrics import ai_metrics

    settings = get_settings()

    ai_router_enabled = False
    try:
        from ..routers import ai as _ai_router

        _ = _ai_router
        ai_router_enabled = True
    except Exception:
        ai_router_enabled = False

    snap = ai_metrics.snapshot()

    recent_errors_obj = snap.get("recent_errors")
    recent_errors: list[AiOpsRecentError] = []
    if isinstance(recent_errors_obj, list):
        for row_obj in cast(list[object], recent_errors_obj):
            if not isinstance(row_obj, dict):
                continue
            row = cast(dict[str, object], row_obj)
            at = str(row.get("at") or "")
            request_id = str(row.get("request_id") or "")
            endpoint = str(row.get("endpoint") or "")
            error_code = str(row.get("error_code") or "")
            status_code_obj = row.get("status_code")

            status_code: int | None = None
            if isinstance(status_code_obj, int):
                status_code = int(status_code_obj)
            elif isinstance(status_code_obj, float):
                status_code = int(status_code_obj)
            elif isinstance(status_code_obj, str):
                s2 = status_code_obj.strip()
                if s2.isdigit():
                    status_code = int(s2)

            msg_obj = row.get("message")
            msg = str(msg_obj) if msg_obj is not None else None
            recent_errors.append(
                AiOpsRecentError(
                    at=at,
                    request_id=request_id,
                    endpoint=endpoint,
                    error_code=error_code,
                    status_code=status_code,
                    message=msg,
                )
            )

    top_error_codes_obj = snap.get("top_error_codes")
    top_error_codes: list[AiOpsTopErrorCode] = []
    if isinstance(top_error_codes_obj, list):
        for row_obj in cast(list[object], top_error_codes_obj):
            if not isinstance(row_obj, dict):
                continue
            row = cast(dict[str, object], row_obj)
            error_code = str(row.get("error_code") or "").strip()
            if not error_code:
                continue
            count_obj = row.get("count")
            count = 0
            if isinstance(count_obj, int):
                count = int(count_obj)
            elif isinstance(count_obj, float):
                count = int(count_obj)
            elif isinstance(count_obj, str):
                s3 = count_obj.strip()
                if s3.isdigit():
                    count = int(s3)
            top_error_codes.append(AiOpsTopErrorCode(error_code=error_code, count=int(count)))

    top_endpoints_obj = snap.get("top_endpoints")
    top_endpoints: list[AiOpsTopEndpoint] = []
    if isinstance(top_endpoints_obj, list):
        for row_obj in cast(list[object], top_endpoints_obj):
            if not isinstance(row_obj, dict):
                continue
            row = cast(dict[str, object], row_obj)
            endpoint = str(row.get("endpoint") or "").strip()
            if not endpoint:
                continue
            count_obj = row.get("count")
            count = 0
            if isinstance(count_obj, int):
                count = int(count_obj)
            elif isinstance(count_obj, float):
                count = int(count_obj)
            elif isinstance(count_obj, str):
                s4 = count_obj.strip()
                if s4.isdigit():
                    count = int(s4)
            top_endpoints.append(AiOpsTopEndpoint(endpoint=endpoint, count=int(count)))

    started_at_obj = snap.get("started_at")
    started_at = 0.0
    if isinstance(started_at_obj, (int, float)):
        started_at = float(started_at_obj)
    elif isinstance(started_at_obj, str):
        try:
            started_at = float(started_at_obj)
        except Exception:
            started_at = 0.0

    started_at_iso = str(snap.get("started_at_iso") or "")

    chat_requests_total_obj = snap.get("chat_requests_total")
    chat_requests_total = int(chat_requests_total_obj) if isinstance(chat_requests_total_obj, int) else 0

    chat_stream_requests_total_obj = snap.get("chat_stream_requests_total")
    chat_stream_requests_total = (
        int(chat_stream_requests_total_obj) if isinstance(chat_stream_requests_total_obj, int) else 0
    )

    errors_total_obj = snap.get("errors_total")
    errors_total = int(errors_total_obj) if isinstance(errors_total_obj, int) else 0

    return AiOpsStatusResponse(
        ai_router_enabled=bool(ai_router_enabled),
        openai_api_key_configured=bool(str(settings.openai_api_key or "").strip()),
        openai_base_url=str(settings.openai_base_url),
        providers=[],
        ai_model=str(settings.ai_model),
        chroma_persist_dir=str(settings.chroma_persist_dir),
        started_at=started_at,
        started_at_iso=started_at_iso,
        chat_requests_total=chat_requests_total,
        chat_stream_requests_total=chat_stream_requests_total,
        errors_total=errors_total,
        recent_errors=recent_errors,
        top_error_codes=top_error_codes,
        top_endpoints=top_endpoints,
    )


class PublicAiStatusResponse(BaseModel):
    voice_transcribe_enabled: bool
    reason: str | None = None


@router.get("/public/ai/status", response_model=PublicAiStatusResponse)
async def get_public_ai_status(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from ..config import get_settings

    settings = get_settings()

    effective_settings = settings
    voice_forced = False
    try:
        from ..services.voice_config_service import get_effective_voice_settings

        effective_settings, _, voice_forced = await get_effective_voice_settings(db, settings)
    except Exception:
        effective_settings = settings
        voice_forced = False

    if voice_forced:
        response.headers.setdefault("X-Voice-Config-Forced", "1")

    ai_router_enabled = False
    try:
        from ..routers import ai as _ai_router

        _ = _ai_router
        ai_router_enabled = True
    except Exception:
        ai_router_enabled = False

    provider_raw = str(getattr(effective_settings, "voice_transcribe_provider", "auto") or "").strip().lower()
    provider = provider_raw if provider_raw in {"auto", "openai", "sherpa"} else "auto"

    openai_ready = bool(
        str(getattr(settings, "openai_transcribe_api_key", "") or "").strip()
        or str(settings.openai_api_key or "").strip()
    )

    sherpa_ready = False
    try:
        from ..services.sherpa_asr_service import sherpa_is_ready

        sherpa_ready = bool(sherpa_is_ready(effective_settings))
    except Exception:
        sherpa_ready = False

    voice_ready = False
    if provider == "openai":
        voice_ready = openai_ready
    elif provider == "sherpa":
        voice_ready = sherpa_ready
    else:
        voice_ready = openai_ready or sherpa_ready

    enabled = bool(ai_router_enabled and voice_ready)
    reason: str | None = None
    if not enabled:
        reason = "AI_NOT_CONFIGURED"

    return PublicAiStatusResponse(
        voice_transcribe_enabled=enabled,
        reason=reason,
    )


@router.get("/metrics")
async def get_metrics(
    _current_user: Annotated[User, Depends(require_admin)],
):
    from ..services.ai_metrics import ai_metrics

    snap = ai_metrics.snapshot()
    started_at_obj = snap.get("started_at")
    started_at = (
        float(started_at_obj)
        if isinstance(started_at_obj, (int, float)) and not isinstance(started_at_obj, bool)
        else 0.0
    )

    chat_total_obj = snap.get("chat_requests_total")
    chat_total = (
        int(chat_total_obj)
        if isinstance(chat_total_obj, (int, float)) and not isinstance(chat_total_obj, bool)
        else 0
    )

    chat_stream_total_obj = snap.get("chat_stream_requests_total")
    chat_stream_total = (
        int(chat_stream_total_obj)
        if isinstance(chat_stream_total_obj, (int, float)) and not isinstance(chat_stream_total_obj, bool)
        else 0
    )

    errors_total_obj = snap.get("errors_total")
    errors_total = (
        int(errors_total_obj)
        if isinstance(errors_total_obj, (int, float)) and not isinstance(errors_total_obj, bool)
        else 0
    )

    error_code_counts_obj = snap.get("error_code_counts")
    endpoint_error_counts_obj = snap.get("endpoint_error_counts")

    error_code_counts: dict[str, int] = {}
    if isinstance(error_code_counts_obj, dict):
        for k_obj, v_obj in cast(dict[object, object], error_code_counts_obj).items():
            k = str(k_obj or "").strip()
            if not k:
                continue
            try:
                if isinstance(v_obj, (int, float)) and not isinstance(v_obj, bool):
                    error_code_counts[k] = int(v_obj)
                elif isinstance(v_obj, str):
                    error_code_counts[k] = int(float(v_obj.strip() or "0"))
                else:
                    continue
            except Exception:
                continue

    endpoint_error_counts: dict[str, int] = {}
    if isinstance(endpoint_error_counts_obj, dict):
        for k_obj, v_obj in cast(dict[object, object], endpoint_error_counts_obj).items():
            k = str(k_obj or "").strip()
            if not k:
                continue
            try:
                if isinstance(v_obj, (int, float)) and not isinstance(v_obj, bool):
                    endpoint_error_counts[k] = int(v_obj)
                elif isinstance(v_obj, str):
                    endpoint_error_counts[k] = int(float(v_obj.strip() or "0"))
                else:
                    continue
            except Exception:
                continue

    lines: list[str] = []
    lines.append("# HELP baixing_ai_started_at_seconds Unix timestamp when AiMetrics started")
    lines.append("# TYPE baixing_ai_started_at_seconds gauge")
    lines.append(f"baixing_ai_started_at_seconds {started_at}")
    lines.append("# HELP baixing_ai_chat_requests_total Total /ai/chat requests")
    lines.append("# TYPE baixing_ai_chat_requests_total counter")
    lines.append(f"baixing_ai_chat_requests_total {chat_total}")
    lines.append("# HELP baixing_ai_chat_stream_requests_total Total /ai/chat_stream requests")
    lines.append("# TYPE baixing_ai_chat_stream_requests_total counter")
    lines.append(f"baixing_ai_chat_stream_requests_total {chat_stream_total}")
    lines.append("# HELP baixing_ai_errors_total Total AI errors")
    lines.append("# TYPE baixing_ai_errors_total counter")
    lines.append(f"baixing_ai_errors_total {errors_total}")

    lines.append("# HELP baixing_ai_error_code_total Total errors grouped by error_code")
    lines.append("# TYPE baixing_ai_error_code_total counter")
    for code in sorted(error_code_counts.keys()):
        v = int(error_code_counts.get(code) or 0)
        if v <= 0:
            continue
        lines.append(
            f"baixing_ai_error_code_total{{error_code=\"{_prom_escape_label_value(code)}\"}} {v}"
        )

    lines.append("# HELP baixing_ai_endpoint_error_total Total errors grouped by endpoint")
    lines.append("# TYPE baixing_ai_endpoint_error_total counter")
    for ep in sorted(endpoint_error_counts.keys()):
        v = int(endpoint_error_counts.get(ep) or 0)
        if v <= 0:
            continue
        lines.append(
            f"baixing_ai_endpoint_error_total{{endpoint=\"{_prom_escape_label_value(ep)}\"}} {v}"
        )

    body = "\n".join(lines) + "\n"
    return PlainTextResponse(content=body, media_type="text/plain; version=0.0.4")


@router.put("/configs/{key}")
async def update_config(
    key: str,
    data: ConfigItem,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    """更新配置项"""
    new_value = data.value
    if new_value is not None and (not str(new_value).strip()):
        new_value = None
    _validate_system_config_no_secrets(key, new_value)
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    config = result.scalar_one_or_none()
    
    if config:
        old_value = config.value
        config.value = new_value
        config.description = data.description or config.description
        config.updated_by = current_user.id
    else:
        config = SystemConfig(
            key=key,
            value=new_value,
            description=data.description,
            category=data.category,
            updated_by=current_user.id
        )
        db.add(config)
        old_value = None
    
    def _mask_value(key_name: str, value: str | None) -> str | None:
        if value is None:
            return None
        return _mask_config_value(key_name, value)

    masked_old = _mask_value(key, old_value)
    masked_new = _mask_value(key, new_value)

    # 记录日志
    await _log_action(
        db, current_user.id, LogAction.CONFIG, LogModule.SYSTEM,
        description=f"更新配置 {key}: {masked_old} -> {masked_new}",
        request=request
    )
    
    await db.commit()
    return {"message": "配置已更新", "key": key, "value": _mask_config_value(key, new_value)}


@router.post("/configs/batch")
async def batch_update_configs(
    data: ConfigBatchUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    """批量更新配置"""
    updated: list[str] = []
    for item in data.configs:
        new_value = item.value
        if new_value is not None and (not str(new_value).strip()):
            new_value = None
        _validate_system_config_no_secrets(item.key, new_value)
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == item.key)
        )
        config = result.scalar_one_or_none()
        
        if config:
            config.value = new_value
            config.updated_by = current_user.id
        else:
            config = SystemConfig(
                key=item.key,
                value=new_value,
                description=item.description,
                category=item.category,
                updated_by=current_user.id
            )
            db.add(config)
        updated.append(item.key)
    
    # 记录日志
    await _log_action(
        db, current_user.id, LogAction.CONFIG, LogModule.SYSTEM,
        description=f"批量更新配置: {', '.join(updated)}",
        request=request
    )
    
    await db.commit()
    return {"message": "配置已批量更新", "updated": updated}


# ============ 操作日志 ============

class LogResponse(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    action: str
    module: str
    target_id: int | None
    target_type: str | None
    description: str | None
    ip_address: str | None
    extra_data: dict[str, object] | None = None
    created_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class LogListResponse(BaseModel):
    items: list[LogResponse]
    total: int
    page: int
    page_size: int


@router.get("/logs", response_model=LogListResponse)
async def get_admin_logs(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    module: str | None = None,
    action: str | None = None,
    user_id: int | None = None,
):
    """获取操作日志列表"""
    query = select(AdminLog, User.nickname, User.username).outerjoin(User, User.id == AdminLog.user_id)
    
    if module:
        query = query.where(AdminLog.module == module)
    if action:
        query = query.where(AdminLog.action == action)
    if user_id:
        query = query.where(AdminLog.user_id == user_id)
    
    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 分页查询
    query = query.order_by(AdminLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = cast(list[tuple[AdminLog, str | None, str]], result.all())
    
    items: list[LogResponse] = []
    for log, nickname, username in rows:
        user_name: str | None = nickname or username
        parsed_extra: dict[str, object] | None = None
        if log.extra_data:
            try:
                value = cast(object, json.loads(log.extra_data))
                if isinstance(value, dict):
                    parsed_extra = cast(dict[str, object], value)
                else:
                    parsed_extra = {"value": value}
            except Exception:
                parsed_extra = {"raw": str(log.extra_data)}
        items.append(
            LogResponse(
                id=int(log.id),
                user_id=int(log.user_id),
                user_name=user_name,
                action=str(log.action),
                module=str(log.module),
                target_id=(int(log.target_id) if log.target_id is not None else None),
                target_type=log.target_type,
                description=log.description,
                ip_address=log.ip_address,
                extra_data=parsed_extra,
                created_at=log.created_at,
            )
        )
    
    return LogListResponse(items=items, total=total, page=page, page_size=page_size)


# ============ 辅助函数 ============

async def _log_action(
    db: AsyncSession,
    user_id: int,
    action: str,
    module: str,
    target_id: int | None = None,
    target_type: str | None = None,
    description: str | None = None,
    extra_data: dict[str, object] | None = None,
    request: Request | None = None,
):
    """记录操作日志"""
    ip_address = None
    user_agent = None
    
    if request:
        ip_address = get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")[:500]
    
    log = AdminLog(
        user_id=user_id,
        action=action,
        module=module,
        target_id=target_id,
        target_type=target_type,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        extra_data=json.dumps(extra_data, ensure_ascii=False) if extra_data else None
    )
    db.add(log)


# 导出日志函数供其他模块使用
async def log_admin_action(
    db: AsyncSession,
    user_id: int,
    action: str,
    module: str,
    target_id: int | None = None,
    description: str | None = None,
    request: Request | None = None,
):
    """供其他模块调用的日志记录函数"""
    await _log_action(db, user_id, action, module, target_id, None, description, None, request)


# ============ 数据统计 ============

from ..models.news import News
from ..models.forum import Post, Comment
from ..models.lawfirm import LawFirm, Lawyer
from ..models.consultation import Consultation, ChatMessage


class StatsOverview(BaseModel):
    """统计概览"""
    total_users: int = 0
    active_users_today: int = 0
    total_consultations: int = 0
    consultations_today: int = 0
    total_posts: int = 0
    posts_today: int = 0
    total_news: int = 0
    total_lawfirms: int = 0
    total_lawyers: int = 0


class DailyStats(BaseModel):
    """每日统计"""
    date: str
    users: int = 0
    consultations: int = 0
    posts: int = 0
    messages: int = 0


@router.get("/stats/overview", response_model=StatsOverview)
async def get_stats_overview(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取统计概览"""
    from datetime import date
    today = date.today()
    
    # 用户统计
    total_users = await db.scalar(select(func.count()).select_from(User))
    active_today = await db.scalar(
        select(func.count()).select_from(User).where(
            func.date(User.updated_at) == today
        )
    )
    
    # 咨询统计
    total_consultations = await db.scalar(select(func.count()).select_from(Consultation))
    consultations_today = await db.scalar(
        select(func.count()).select_from(Consultation).where(
            func.date(Consultation.created_at) == today
        )
    )
    
    # 帖子统计
    total_posts = await db.scalar(select(func.count()).select_from(Post))
    posts_today = await db.scalar(
        select(func.count()).select_from(Post).where(
            func.date(Post.created_at) == today
        )
    )
    
    # 其他统计
    total_news = await db.scalar(select(func.count()).select_from(News))
    total_lawfirms = await db.scalar(select(func.count()).select_from(LawFirm))
    total_lawyers = await db.scalar(select(func.count()).select_from(Lawyer))
    
    return StatsOverview(
        total_users=total_users or 0,
        active_users_today=active_today or 0,
        total_consultations=total_consultations or 0,
        consultations_today=consultations_today or 0,
        total_posts=total_posts or 0,
        posts_today=posts_today or 0,
        total_news=total_news or 0,
        total_lawfirms=total_lawfirms or 0,
        total_lawyers=total_lawyers or 0
    )


@router.get("/stats/daily", response_model=list[DailyStats])
async def get_daily_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=30)] = 7,
):
    """获取每日统计（最近N天）"""
    from datetime import date, timedelta
    
    results: list[DailyStats] = []
    today = date.today()
    
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        
        users = await db.scalar(
            select(func.count()).select_from(User).where(
                func.date(User.created_at) == day
            )
        )
        
        consultations = await db.scalar(
            select(func.count()).select_from(Consultation).where(
                func.date(Consultation.created_at) == day
            )
        )
        
        posts = await db.scalar(
            select(func.count()).select_from(Post).where(
                func.date(Post.created_at) == day
            )
        )
        
        messages = await db.scalar(
            select(func.count()).select_from(ChatMessage).where(
                func.date(ChatMessage.created_at) == day
            )
        )
        
        results.append(DailyStats(
            date=day.isoformat(),
            users=users or 0,
            consultations=consultations or 0,
            posts=posts or 0,
            messages=messages or 0
        ))
    
    return results


@router.get("/stats/ai-feedback")
async def get_ai_feedback_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=365, description="统计天数")] = 30,
    limit: Annotated[int, Query(ge=1, le=50, description="最近反馈条数")] = 20,
) -> dict[str, object]:
    """获取AI反馈统计"""
    since_dt = datetime.now(timezone.utc) - timedelta(days=int(days))

    def _as_int(value: object | None, default: int = 0) -> int:
        if value is None:
            return int(default)
        if isinstance(value, bool):
            return int(default)
        if isinstance(value, int):
            return int(value)
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return int(default)
            try:
                return int(float(s))
            except Exception:
                return int(default)
        return int(default)

    def _prompt_version_from_references(refs_text: object | None) -> str:
        raw = "" if refs_text is None else str(refs_text)
        s = raw.strip()
        if not s:
            return "v1"
        try:
            obj = cast(object, json.loads(s))
            if isinstance(obj, dict):
                obj_dict = cast(dict[str, object], obj)
                meta_obj = obj_dict.get("meta")
                if isinstance(meta_obj, dict):
                    meta = cast(dict[str, object], meta_obj)
                    pv_obj = meta.get("prompt_version")
                    if isinstance(pv_obj, str) and pv_obj.strip():
                        return pv_obj.strip()
                pv2_obj = obj_dict.get("prompt_version")
                if isinstance(pv2_obj, str) and pv2_obj.strip():
                    return pv2_obj.strip()
                return "v1"
            if isinstance(obj, list):
                return "v1"
        except Exception:
            return "v1"
        return "v1"

    consultations_total = await db.scalar(
        select(func.count()).select_from(Consultation).where(Consultation.created_at >= since_dt)
    )

    messages_total = await db.scalar(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.created_at >= since_dt)
    )

    assistant_messages_total = await db.scalar(
        select(func.count()).select_from(ChatMessage).where(
            and_(
                ChatMessage.created_at >= since_dt,
                ChatMessage.role == "assistant",
            )
        )
    )

    rated_filter = and_(
        ChatMessage.created_at >= since_dt,
        ChatMessage.role == "assistant",
        ChatMessage.rating.isnot(None),
    )

    total_rated = await db.scalar(
        select(func.count()).select_from(ChatMessage).where(rated_filter)
    )

    good_count = await db.scalar(
        select(func.count()).select_from(ChatMessage).where(and_(rated_filter, ChatMessage.rating == 3))
    )

    neutral_count = await db.scalar(
        select(func.count()).select_from(ChatMessage).where(and_(rated_filter, ChatMessage.rating == 2))
    )

    bad_count = await db.scalar(
        select(func.count()).select_from(ChatMessage).where(and_(rated_filter, ChatMessage.rating == 1))
    )

    pv_rows = await db.execute(
        select(ChatMessage.rating, ChatMessage.references).where(rated_filter)
    )
    pv_stats: dict[str, dict[str, int]] = {}
    for row in pv_rows.all():
        rating_any, references_any = row
        pv = _prompt_version_from_references(references_any)
        st = pv_stats.get(pv)
        if st is None:
            st = {"total_rated": 0, "good": 0, "neutral": 0, "bad": 0}
            pv_stats[pv] = st
        st["total_rated"] += 1
        r = _as_int(rating_any, 0)
        if r == 3:
            st["good"] += 1
        elif r == 2:
            st["neutral"] += 1
        elif r == 1:
            st["bad"] += 1

    by_prompt_version: list[dict[str, object]] = []
    for pv, st in pv_stats.items():
        total = int(st.get("total_rated", 0))
        good = int(st.get("good", 0))
        sr = round(good / max(total, 1) * 100, 1)
        by_prompt_version.append(
            {
                "prompt_version": str(pv),
                "total_rated": total,
                "good": good,
                "neutral": int(st.get("neutral", 0)),
                "bad": int(st.get("bad", 0)),
                "satisfaction_rate": float(sr),
            }
        )
    by_prompt_version = sorted(
        by_prompt_version,
        key=lambda x: (-_as_int(x.get("total_rated"), 0), str(x.get("prompt_version") or "")),
    )

    tag_scan_limit = max(200, min(2000, int(limit) * 50))
    tag_rows = await db.execute(
        select(ChatMessage.rating, ChatMessage.feedback)
        .where(and_(rated_filter, ChatMessage.feedback.isnot(None)))
        .order_by(desc(ChatMessage.created_at))
        .limit(tag_scan_limit)
    )

    def _extract_reason_tags(feedback: str) -> list[str]:
        s = str(feedback or "").strip()
        if not s:
            return []

        m = re.search(r"原因\s*[:：]\s*([^；\n\r]+)", s)
        if not m:
            return []

        raw = str(m.group(1) or "").strip()
        if not raw:
            return []

        parts = re.split(r"\s*(?:/|\||｜|、|,|，|;|；)\s*", raw)
        out: list[str] = []
        seen: set[str] = set()
        for p in parts:
            tag = str(p or "").strip()
            if not tag:
                continue
            if len(tag) > 30:
                tag = tag[:30]
            key = tag.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(tag)
            if len(out) >= 8:
                break
        return out

    tag_stats: dict[str, dict[str, int]] = {}
    scanned = 0
    for row in tag_rows.all():
        rating, feedback = row
        fb = str(feedback or "").strip()
        if not fb:
            continue
        scanned += 1
        tags = _extract_reason_tags(fb)
        if not tags:
            continue

        r = _as_int(rating, 0)
        for tag in tags:
            item = tag_stats.get(tag)
            if item is None:
                item = {"count": 0, "good": 0, "neutral": 0, "bad": 0}
                tag_stats[tag] = item
            item["count"] += 1
            if r == 3:
                item["good"] += 1
            elif r == 2:
                item["neutral"] += 1
            elif r == 1:
                item["bad"] += 1

    top_tags = sorted(
        (
            {
                "tag": tag,
                "count": counts.get("count", 0),
                "good": counts.get("good", 0),
                "neutral": counts.get("neutral", 0),
                "bad": counts.get("bad", 0),
            }
            for tag, counts in tag_stats.items()
        ),
        key=lambda x: (-int(x.get("count") or 0), str(x.get("tag") or "")),
    )
    top_tags = list(top_tags)[:20]

    suggestion_map: dict[str, dict[str, str]] = {
        "不准确": {
            "title": "提升准确性",
            "action": "检查检索/引用链路与回答模板：强化结论前的依据校验，必要时提示不确定并引导补充信息。",
        },
        "缺少依据": {
            "title": "补齐依据与引用",
            "action": "在回答模板中增加“依据/法条/裁判要旨”段落，优先给出可核验来源，并提示用户如何自查原文。",
        },
        "答非所问": {
            "title": "减少答非所问",
            "action": "在输出前做问题复述与意图确认；当信息不足时先输出澄清问题而不是直接下结论。",
        },
        "不够具体": {
            "title": "提升可执行性",
            "action": "增加“下一步行动清单/所需材料/时效期限”结构化输出，按场景给到可执行步骤。",
        },
        "太泛泛": {
            "title": "降低泛泛而谈",
            "action": "对常见问题引入更细分的场景模板（地区/金额/主体关系），并在输出中给出分支条件。",
        },
        "看不懂": {
            "title": "提升可读性",
            "action": "使用更短句+分点；对术语做括号解释；优先给出结论摘要，再展开细节与风险提示。",
        },
    }

    improvement_suggestions: list[dict[str, object]] = []
    scored_tags = sorted(
        tag_stats.items(),
        key=lambda kv: (-(kv[1].get("bad", 0) * 2 + kv[1].get("neutral", 0)), kv[0]),
    )
    for tag, counts in scored_tags:
        tpl = suggestion_map.get(tag)
        if tpl is None:
            continue
        if (counts.get("bad", 0) + counts.get("neutral", 0)) <= 0:
            continue
        improvement_suggestions.append(
            {
                "tag": tag,
                "count": int(counts.get("count", 0)),
                "good": int(counts.get("good", 0)),
                "neutral": int(counts.get("neutral", 0)),
                "bad": int(counts.get("bad", 0)),
                "title": str(tpl.get("title") or ""),
                "action": str(tpl.get("action") or ""),
            }
        )
        if len(improvement_suggestions) >= 6:
            break

    recent_rows = await db.execute(
        select(
            ChatMessage.id,
            ChatMessage.consultation_id,
            ChatMessage.rating,
            ChatMessage.feedback,
            ChatMessage.created_at,
            ChatMessage.references,
            Consultation.user_id,
        )
        .join(Consultation, ChatMessage.consultation_id == Consultation.id)
        .where(rated_filter)
        .order_by(desc(ChatMessage.created_at))
        .limit(int(limit))
    )

    recent_ratings: list[dict[str, object]] = []
    for row in recent_rows.all():
        message_id, consultation_id, rating, feedback, created_at, references, user_id = row
        created_at_iso = None
        if created_at is not None:
            try:
                created_at_iso = created_at.isoformat()
            except Exception:
                created_at_iso = str(created_at)
        pv = _prompt_version_from_references(references)
        recent_ratings.append(
            {
                "message_id": int(message_id),
                "consultation_id": int(consultation_id),
                "user_id": int(user_id) if user_id is not None else None,
                "rating": int(rating) if rating is not None else None,
                "feedback": str(feedback) if feedback is not None else None,
                "created_at": created_at_iso,
                "prompt_version": str(pv),
            }
        )

    total_rated_i = int(total_rated or 0)
    good_i = int(good_count or 0)
    assistant_total_i = int(assistant_messages_total or 0)
    satisfaction_rate = round(good_i / max(total_rated_i, 1) * 100, 1)
    rating_rate = round(total_rated_i / max(assistant_total_i, 1) * 100, 1)

    return {
        "days": int(days),
        "since": since_dt.isoformat(),
        "consultations_total": int(consultations_total or 0),
        "messages_total": int(messages_total or 0),
        "assistant_messages_total": assistant_total_i,
        "total_rated": total_rated_i,
        "good": int(good_count or 0),
        "neutral": int(neutral_count or 0),
        "bad": int(bad_count or 0),
        "satisfaction_rate": float(satisfaction_rate),
        "rating_rate": float(rating_rate),
        "by_prompt_version": by_prompt_version,
        "recent_ratings": recent_ratings,
        "top_tags": top_tags,
        "tag_messages_scanned": int(scanned),
        "improvement_suggestions": improvement_suggestions,
    }


# ============ FAQ 自动生成（最小可用）===========

FAQ_PUBLIC_ITEMS_KEY = "FAQ_PUBLIC_ITEMS_JSON"


class FaqItem(BaseModel):
    question: str
    answer: str


class FaqPublicResponse(BaseModel):
    items: list[FaqItem]
    updated_at: str | None = None


class FaqGenerateResponse(BaseModel):
    key: str
    generated: int
    saved: int
    items: list[FaqItem]


@router.get("/public/faq", response_model=FaqPublicResponse)
async def get_public_faq(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == FAQ_PUBLIC_ITEMS_KEY))
    config = result.scalar_one_or_none()

    items: list[FaqItem] = []
    updated_at: str | None = None
    if config is not None:
        try:
            updated_at = config.updated_at.isoformat()
        except Exception:
            try:
                updated_at = str(config.updated_at)
            except Exception:
                updated_at = None

        raw = str(config.value or "").strip()
        if raw:
            try:
                obj = cast(object, json.loads(raw))
                if isinstance(obj, list):
                    for row_obj in cast(list[object], obj):
                        if not isinstance(row_obj, dict):
                            continue
                        row = cast(dict[str, object], row_obj)
                        q = str(row.get("question") or "").strip()
                        a = str(row.get("answer") or "").strip()
                        if not q or not a:
                            continue
                        items.append(FaqItem(question=q, answer=a))
            except Exception:
                items = []

    return FaqPublicResponse(items=items, updated_at=updated_at)


@router.post("/faq/generate", response_model=FaqGenerateResponse)
async def generate_faq(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
    days: Annotated[int, Query(ge=1, le=365, description="从最近 N 天的好评消息生成")] = 30,
    max_items: Annotated[int, Query(ge=1, le=50, description="最多生成条数")] = 20,
    scan_limit: Annotated[int, Query(ge=1, le=500, description="最多扫描好评消息数")] = 200,
):
    since_dt = datetime.now(timezone.utc) - timedelta(days=int(days))

    top_rows = await db.execute(
        select(
            ChatMessage.consultation_id,
            ChatMessage.content,
            ChatMessage.created_at,
        )
        .where(
            and_(
                ChatMessage.created_at >= since_dt,
                ChatMessage.role == "assistant",
                ChatMessage.rating == 3,
            )
        )
        .order_by(desc(ChatMessage.created_at), desc(ChatMessage.id))
        .limit(int(scan_limit))
    )

    items: list[FaqItem] = []
    seen_questions: set[str] = set()
    for row in top_rows.all():
        consultation_id, answer, created_at = row

        ans = str(answer or "").strip()
        if not ans:
            continue

        created_at_dt = cast(datetime | None, created_at)
        if created_at_dt is None:
            continue

        q_res = await db.execute(
            select(ChatMessage.content)
            .where(
                and_(
                    ChatMessage.consultation_id == int(consultation_id),
                    ChatMessage.role == "user",
                    ChatMessage.created_at <= created_at_dt,
                )
            )
            .order_by(desc(ChatMessage.created_at), desc(ChatMessage.id))
            .limit(1)
        )
        q_val = q_res.scalar_one_or_none()
        q = str(q_val or "").strip()
        if not q:
            continue

        q_norm = re.sub(r"\s+", " ", q).strip().lower()
        if not q_norm:
            continue
        if q_norm in seen_questions:
            continue
        seen_questions.add(q_norm)

        items.append(FaqItem(question=q, answer=ans))
        if len(items) >= int(max_items):
            break

    value_json = json.dumps([it.model_dump() for it in items], ensure_ascii=False)
    _validate_system_config_no_secrets(FAQ_PUBLIC_ITEMS_KEY, value_json)

    cfg_res = await db.execute(select(SystemConfig).where(SystemConfig.key == FAQ_PUBLIC_ITEMS_KEY))
    cfg = cfg_res.scalar_one_or_none()
    if cfg is None:
        cfg = SystemConfig(
            key=FAQ_PUBLIC_ITEMS_KEY,
            value=value_json,
            description="Auto-generated public FAQ items",
            category="faq",
            updated_by=current_user.id,
        )
        db.add(cfg)
        log_action = LogAction.CREATE
    else:
        cfg.value = value_json
        cfg.description = "Auto-generated public FAQ items"
        cfg.category = "faq"
        cfg.updated_by = current_user.id
        log_action = LogAction.UPDATE

    await _log_action(
        db,
        current_user.id,
        log_action,
        LogModule.SYSTEM,
        description=f"生成FAQ: {len(items)} 条 (days={days}, scanned={scan_limit})",
        request=request,
    )

    await db.commit()

    return FaqGenerateResponse(
        key=FAQ_PUBLIC_ITEMS_KEY,
        generated=len(items),
        saved=len(items),
        items=items,
    )


# ============ 数据统计大屏 ============

from ..models.knowledge import LegalKnowledge


@router.get("/dashboard/overview", summary="仪表板概览数据")
async def get_dashboard_overview(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取仪表板概览统计数据"""
    from datetime import timedelta
    today = datetime.now().date()
    _yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    _month_ago = today - timedelta(days=30)
    
    # 用户统计
    total_users = await db.scalar(select(func.count()).select_from(User)) or 0
    new_users_today = await db.scalar(
        select(func.count()).select_from(User).where(func.date(User.created_at) == today)
    ) or 0
    new_users_week = await db.scalar(
        select(func.count()).select_from(User).where(func.date(User.created_at) >= week_ago)
    ) or 0
    active_users_week = await db.scalar(
        select(func.count(func.distinct(Consultation.user_id))).where(
            func.date(Consultation.created_at) >= week_ago
        )
    ) or 0
    
    # 内容统计
    total_posts = await db.scalar(select(func.count()).select_from(Post).where(Post.is_deleted == False)) or 0
    total_comments = await db.scalar(select(func.count()).select_from(Comment).where(Comment.is_deleted == False)) or 0
    total_news = await db.scalar(select(func.count()).select_from(News).where(News.is_published == True)) or 0
    
    # 咨询统计
    total_consultations = await db.scalar(select(func.count()).select_from(Consultation)) or 0
    consultations_today = await db.scalar(
        select(func.count()).select_from(Consultation).where(func.date(Consultation.created_at) == today)
    ) or 0
    total_messages = await db.scalar(select(func.count()).select_from(ChatMessage)) or 0
    
    # 律所统计
    total_lawfirms = await db.scalar(select(func.count()).select_from(LawFirm).where(LawFirm.is_active == True)) or 0
    total_lawyers = await db.scalar(select(func.count()).select_from(Lawyer).where(Lawyer.is_active == True)) or 0
    verified_lawyers = await db.scalar(select(func.count()).select_from(Lawyer).where(Lawyer.is_verified == True)) or 0
    
    # 知识库统计
    total_knowledge = await db.scalar(select(func.count()).select_from(LegalKnowledge).where(LegalKnowledge.is_active == True)) or 0
    vectorized_count = await db.scalar(select(func.count()).select_from(LegalKnowledge).where(LegalKnowledge.is_vectorized == True)) or 0
    
    return {
        "users": {
            "total": total_users,
            "new_today": new_users_today,
            "new_week": new_users_week,
            "active_week": active_users_week,
        },
        "content": {
            "posts": total_posts,
            "comments": total_comments,
            "news": total_news,
        },
        "consultations": {
            "total": total_consultations,
            "today": consultations_today,
            "messages": total_messages,
        },
        "lawfirms": {
            "firms": total_lawfirms,
            "lawyers": total_lawyers,
            "verified": verified_lawyers,
        },
        "knowledge": {
            "total": total_knowledge,
            "vectorized": vectorized_count,
            "vectorize_rate": round(vectorized_count / max(total_knowledge, 1) * 100, 1),
        }
    }


@router.get("/dashboard/trends", summary="趋势数据")
async def get_dashboard_trends(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=7, le=90, description="统计天数")] = 30,
):
    """获取近N天的趋势数据"""
    from datetime import timedelta
    today = datetime.now().date()
    
    trends: list[dict[str, object]] = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        
        users = await db.scalar(
            select(func.count()).select_from(User).where(func.date(User.created_at) == day)
        ) or 0
        
        consultations = await db.scalar(
            select(func.count()).select_from(Consultation).where(func.date(Consultation.created_at) == day)
        ) or 0
        
        posts = await db.scalar(
            select(func.count()).select_from(Post).where(func.date(Post.created_at) == day)
        ) or 0
        
        trends.append({
            "date": day.isoformat(),
            "users": users,
            "consultations": consultations,
            "posts": posts,
        })
    
    return {"trends": trends, "days": days}


@router.get("/dashboard/category-stats", summary="分类统计")
async def get_category_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取各类别统计数据"""
    # 帖子分类统计
    post_categories = await db.execute(
        select(Post.category, func.count(Post.id).label('count'))
        .where(Post.is_deleted == False, Post.category.isnot(None))
        .group_by(Post.category)
        .order_by(func.count(Post.id).desc())
        .limit(10)
    )
    post_cat_data: list[dict[str, object]] = [
        {"name": str(r[0] or ""), "value": int(r[1] or 0)} for r in post_categories.all()
    ]
    
    # 新闻分类统计
    news_categories = await db.execute(
        select(News.category, func.count(News.id).label('count'))
        .where(News.is_published == True, News.category.isnot(None))
        .group_by(News.category)
        .order_by(func.count(News.id).desc())
        .limit(10)
    )
    news_cat_data: list[dict[str, object]] = [
        {"name": str(r[0] or ""), "value": int(r[1] or 0)} for r in news_categories.all()
    ]
    
    # 知识库分类统计
    knowledge_categories = await db.execute(
        select(LegalKnowledge.category, func.count(LegalKnowledge.id).label('count'))
        .where(LegalKnowledge.is_active == True)
        .group_by(LegalKnowledge.category)
        .order_by(func.count(LegalKnowledge.id).desc())
        .limit(10)
    )
    knowledge_cat_data: list[dict[str, object]] = [
        {"name": str(r[0] or ""), "value": int(r[1] or 0)} for r in knowledge_categories.all()
    ]
    
    # 律所城市分布
    firm_cities = await db.execute(
        select(LawFirm.city, func.count(LawFirm.id).label('count'))
        .where(LawFirm.is_active == True, LawFirm.city.isnot(None))
        .group_by(LawFirm.city)
        .order_by(func.count(LawFirm.id).desc())
        .limit(10)
    )
    city_data: list[dict[str, object]] = [
        {"name": str(r[0] or ""), "value": int(r[1] or 0)} for r in firm_cities.all()
    ]
    
    return {
        "post_categories": post_cat_data,
        "news_categories": news_cat_data,
        "knowledge_categories": knowledge_cat_data,
        "firm_cities": city_data,
    }


@router.get("/dashboard/news-stats", summary="新闻统计")
async def get_dashboard_news_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=90)] = 7,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
):
    from datetime import timedelta

    today = datetime.now().date()

    total = await db.scalar(select(func.count()).select_from(News)) or 0
    published = await db.scalar(
        select(func.count()).select_from(News).where(News.is_published == True)
    ) or 0
    drafts = await db.scalar(
        select(func.count()).select_from(News).where(News.is_published == False)
    ) or 0

    trends: list[dict[str, object]] = []
    for i in range(int(days) - 1, -1, -1):
        day = today - timedelta(days=i)
        published_day = await db.scalar(
            select(func.count()).select_from(News).where(
                and_(
                    News.is_published == True,
                    func.date(func.coalesce(News.published_at, News.created_at)) == day,
                )
            )
        ) or 0
        trends.append({"date": day.isoformat(), "published": int(published_day)})

    cat_rows = await db.execute(
        select(News.category, func.count(News.id).label("count"))
        .where(News.is_published == True, News.category.isnot(None))
        .group_by(News.category)
        .order_by(func.count(News.id).desc())
        .limit(10)
    )
    categories: list[dict[str, object]] = [
        {"name": str(r[0] or ""), "value": int(r[1] or 0)} for r in cat_rows.all()
    ]

    hot_rows = await db.execute(
        select(News.id, News.title, News.category, News.view_count)
        .where(News.is_published == True)
        .order_by(desc(func.coalesce(News.view_count, 0)), desc(News.published_at), desc(News.created_at))
        .limit(limit)
    )
    hot_items = cast(list[tuple[int, str | None, str | None, int | None]], hot_rows.all())
    hot: list[dict[str, object]] = [
        {
            "id": int(r_id),
            "title": str(r_title or ""),
            "category": str(r_cat or ""),
            "views": int(r_views or 0),
        }
        for r_id, r_title, r_cat, r_views in hot_items
    ]

    return {
        "total": int(total),
        "published": int(published),
        "drafts": int(drafts),
        "days": int(days),
        "trends": trends,
        "categories": categories,
        "hot": hot,
    }


@router.get("/dashboard/realtime", summary="实时数据")
async def get_realtime_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取实时统计数据（最近1小时）"""
    from datetime import timedelta
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)
    
    # 最近1小时活跃数据
    new_users = await db.scalar(
        select(func.count()).select_from(User).where(User.created_at >= hour_ago)
    ) or 0
    
    new_consultations = await db.scalar(
        select(func.count()).select_from(Consultation).where(Consultation.created_at >= hour_ago)
    ) or 0
    
    new_messages = await db.scalar(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.created_at >= hour_ago)
    ) or 0
    
    new_posts = await db.scalar(
        select(func.count()).select_from(Post).where(Post.created_at >= hour_ago)
    ) or 0
    
    new_comments = await db.scalar(
        select(func.count()).select_from(Comment).where(Comment.created_at >= hour_ago)
    ) or 0
    
    # 最近活动
    recent_consultations = await db.execute(
        select(Consultation.id, Consultation.title, User.username, Consultation.created_at)
        .join(User, Consultation.user_id == User.id)
        .order_by(Consultation.created_at.desc())
        .limit(5)
    )
    recent_rows = cast(list[tuple[int, str | None, str | None, datetime]], recent_consultations.all())
    recent_list: list[dict[str, object]] = [
        {
            "id": int(r_id),
            "title": str(r_title or "AI法律咨询"),
            "user": str(r_user or ""),
            "time": r_created_at.isoformat(),
        }
        for r_id, r_title, r_user, r_created_at in recent_rows
    ]
    
    return {
        "hour_stats": {
            "users": new_users,
            "consultations": new_consultations,
            "messages": new_messages,
            "posts": new_posts,
            "comments": new_comments,
        },
        "recent_consultations": recent_list,
        "timestamp": now.isoformat(),
    }


@router.get("/dashboard/hot-content", summary="热门内容")
async def get_hot_content(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
):
    """获取热门内容（帖子 counting by view_count，新闻 counting by view_count）"""
    _ = _current_user

    post_rows = await db.execute(
        select(Post.id, Post.title, Post.view_count)
        .where(Post.is_deleted == False)
        .order_by(desc(func.coalesce(Post.view_count, 0)), desc(Post.created_at))
        .limit(limit)
    )
    post_items = cast(list[tuple[int, str | None, int | None]], post_rows.all())
    posts: list[dict[str, object]] = [
        {"type": "post", "id": int(r_id), "title": str(r_title or ""), "views": int(r_views or 0)}
        for r_id, r_title, r_views in post_items
    ]

    news_rows = await db.execute(
        select(News.id, News.title, News.view_count)
        .where(News.is_published == True)
        .order_by(desc(func.coalesce(News.view_count, 0)), desc(News.published_at), desc(News.created_at))
        .limit(limit)
    )
    news_items = cast(list[tuple[int, str | None, int | None]], news_rows.all())
    news: list[dict[str, object]] = [
        {"type": "news", "id": int(r_id), "title": str(r_title or ""), "views": int(r_views or 0)}
        for r_id, r_title, r_views in news_items
    ]

    def _views_of(item: dict[str, object]) -> int:
        v: object | None = item.get("views")
        if v is None:
            return 0
        if isinstance(v, bool):
            return 0
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return 0
            try:
                return int(float(s))
            except Exception:
                return 0
        return 0

    items = sorted(posts + news, key=_views_of, reverse=True)
    return {"items": items[:limit]}


# ============ 用户行为分析 ============

from ..models.system import UserActivity


class ActivityCreate(BaseModel):
    action: str  # page_view, click, search, etc.
    page: str | None = None
    target: str | None = None
    target_id: int | None = None
    referrer: str | None = None
    duration: int | None = None
    extra_data: str | None = None


@router.post("/analytics/track", summary="记录用户行为")
@rate_limit(*RateLimitConfig.ANALYTICS_TRACK, by_ip=True, by_user=False)
async def track_activity(
    data: ActivityCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
):
    """记录用户行为数据（前端调用）"""
    user_agent = request.headers.get("user-agent", "")
    
    # 解析设备类型
    device_type = "desktop"
    ua_lower = user_agent.lower()
    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        device_type = "mobile"
    elif "tablet" in ua_lower or "ipad" in ua_lower:
        device_type = "tablet"
    
    activity = UserActivity(
        user_id=current_user.id if current_user else None,
        session_id=(request.cookies.get("session_id") or "")[:200] or None,
        action=data.action,
        page=(data.page[:500] if data.page else None),
        target=(data.target[:500] if data.target else None),
        target_id=data.target_id,
        referrer=(data.referrer[:500] if data.referrer else None),
        user_agent=user_agent[:500] if user_agent else None,
        ip_address=get_client_ip(request),
        device_type=device_type,
        extra_data=(data.extra_data[:2000] if data.extra_data else None),
        duration=data.duration,
    )
    db.add(activity)
    await db.commit()
    
    return {"status": "ok"}


@router.get("/analytics/page-stats", summary="页面访问统计")
async def get_page_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=30)] = 7,
):
    """获取页面访问统计"""
    from datetime import timedelta
    start_date = datetime.now() - timedelta(days=days)
    
    # 按页面统计访问量
    page_stats = await db.execute(
        select(
            UserActivity.page,
            func.count(UserActivity.id).label('views'),
            func.count(func.distinct(UserActivity.user_id)).label('unique_users'),
            func.avg(UserActivity.duration).label('avg_duration')
        )
        .where(
            UserActivity.action == "page_view",
            UserActivity.created_at >= start_date,
            UserActivity.page.isnot(None)
        )
        .group_by(UserActivity.page)
        .order_by(func.count(UserActivity.id).desc())
        .limit(20)
    )
    
    pages: list[dict[str, object]] = []
    for row in page_stats.all():
        pages.append({
            "page": str(row[0] or ""),
            "views": int(row[1] or 0),
            "unique_users": int(row[2] or 0),
            "avg_duration": round(float(row[3] or 0), 1),
        })
    
    return {"pages": pages, "days": days}


@router.get("/analytics/user-behavior", summary="用户行为分析")
async def get_user_behavior(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=30)] = 7,
):
    """获取用户行为分析数据"""
    from datetime import timedelta
    start_date = datetime.now() - timedelta(days=days)
    
    # 按行为类型统计
    action_stats = await db.execute(
        select(
            UserActivity.action,
            func.count(UserActivity.id).label('count')
        )
        .where(UserActivity.created_at >= start_date)
        .group_by(UserActivity.action)
        .order_by(func.count(UserActivity.id).desc())
    )
    actions: list[dict[str, object]] = [
        {"action": str(r[0] or ""), "count": int(r[1] or 0)} for r in action_stats.all()
    ]
    
    # 按设备类型统计
    device_stats = await db.execute(
        select(
            UserActivity.device_type,
            func.count(UserActivity.id).label('count')
        )
        .where(
            UserActivity.created_at >= start_date,
            UserActivity.device_type.isnot(None)
        )
        .group_by(UserActivity.device_type)
    )
    devices: list[dict[str, object]] = [
        {"device": str(r[0] or ""), "count": int(r[1] or 0)} for r in device_stats.all()
    ]
    
    # 按小时统计活跃度
    hourly_stats = await db.execute(
        select(
            func.extract('hour', UserActivity.created_at).label('hour'),
            func.count(UserActivity.id).label('count')
        )
        .where(UserActivity.created_at >= start_date)
        .group_by(func.extract('hour', UserActivity.created_at))
        .order_by(func.extract('hour', UserActivity.created_at))
    )
    hourly: list[dict[str, object]] = [
        {"hour": int(cast(int | float, r[0] or 0)), "count": int(r[1] or 0)} for r in hourly_stats.all()
    ]
    
    return {
        "actions": actions,
        "devices": devices,
        "hourly_activity": hourly,
        "days": days,
    }


@router.get("/analytics/user-journey", summary="用户路径分析")
async def get_user_journey(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=10, le=500)] = 100,
):
    """获取用户访问路径（最近N条记录）"""
    result = await db.execute(
        select(
            UserActivity.page,
            UserActivity.referrer,
            func.count(UserActivity.id).label('count')
        )
        .where(
            UserActivity.action == "page_view",
            UserActivity.page.isnot(None)
        )
        .group_by(UserActivity.page, UserActivity.referrer)
        .order_by(func.count(UserActivity.id).desc())
        .limit(limit)
    )
    
    journeys: list[dict[str, object]] = []
    for row in result.all():
        journeys.append({
            "from": str(row[1] or "直接访问"),
            "to": str(row[0] or ""),
            "count": int(row[2] or 0),
        })
    
    return {"journeys": journeys}


@router.get("/analytics/retention", summary="用户留存分析")
async def get_retention_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取用户留存率数据"""
    from datetime import timedelta
    today = datetime.now().date()
    
    retention_data: list[dict[str, object]] = []
    for i in range(7):  # 近7天
        day = today - timedelta(days=i)
        next_day = day + timedelta(days=1)
        
        # 当天新注册用户
        new_users = await db.scalar(
            select(func.count(func.distinct(User.id)))
            .where(func.date(User.created_at) == day)
        ) or 0
        
        # 次日活跃用户(在次日有行为记录的新用户)
        if i > 0:  # 最后一天没有次日数据
            retained = await db.scalar(
                select(func.count(func.distinct(UserActivity.user_id)))
                .where(
                    UserActivity.user_id.in_(
                        select(User.id).where(func.date(User.created_at) == day)
                    ),
                    func.date(UserActivity.created_at) == next_day
                )
            ) or 0
        else:
            retained = 0
        
        retention_data.append({
            "date": day.isoformat(),
            "new_users": new_users,
            "retained": retained,
            "retention_rate": round(retained / max(new_users, 1) * 100, 1),
        })
    
    return {"retention": retention_data}


