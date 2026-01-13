"""合同审查API路由"""

import asyncio
import io
import json
import os
import tempfile
import time
import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import get_settings
from ..database import get_db
from ..models.system import SystemConfig
from ..models.user import User
from ..schemas.contracts import ContractReviewResponse
from ..services.contract_review_service import (
    call_openai_contract_review,
    apply_contract_review_rules,
    render_contract_review_markdown,
)
from ..services.quota_service import quota_service
from ..utils.deps import get_current_user_optional
from ..utils.pii import sanitize_pii
from ..utils.rate_limiter import RateLimitConfig, get_client_ip, rate_limit, rate_limiter

router = APIRouter(prefix="/contracts", tags=["合同审查"])

settings = get_settings()

ERROR_CONTRACT_NOT_CONFIGURED = "AI_NOT_CONFIGURED"
ERROR_CONTRACT_BAD_REQUEST = "CONTRACT_BAD_REQUEST"
ERROR_CONTRACT_INTERNAL_ERROR = "CONTRACT_INTERNAL_ERROR"

CONTRACT_REVIEW_RULES_KEY = "CONTRACT_REVIEW_RULES_JSON"


async def _load_contract_review_rules(db: AsyncSession) -> dict[str, object] | None:
    try:
        res = await db.execute(select(SystemConfig).where(SystemConfig.key == CONTRACT_REVIEW_RULES_KEY))
        cfg = res.scalar_one_or_none()
        raw = str(getattr(cfg, "value", "") or "").strip() if cfg is not None else ""
        if not raw:
            return None
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _get_int_env(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


GUEST_CONTRACT_REVIEW_LIMIT = _get_int_env("GUEST_CONTRACT_REVIEW_LIMIT", 1)
GUEST_CONTRACT_REVIEW_WINDOW_SECONDS = _get_int_env(
    "GUEST_CONTRACT_REVIEW_WINDOW_SECONDS", 60 * 60 * 24
)


def _make_error_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
    request_id: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    out_headers: dict[str, str] = {
        "X-Request-Id": str(request_id),
        "X-Error-Code": str(error_code),
    }
    if headers:
        for k, v in headers.items():
            out_headers[str(k)] = str(v)

    return JSONResponse(
        status_code=int(status_code),
        content={
            "error_code": str(error_code),
            "message": str(message),
            "detail": str(message),
            "request_id": str(request_id),
        },
        headers=out_headers,
    )


async def _enforce_guest_contract_quota(request: Request) -> None:
    if int(GUEST_CONTRACT_REVIEW_LIMIT) <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="合同审查需登录后使用",
        )

    key = f"contracts:guest:{get_client_ip(request)}"
    allowed, remaining, wait_time = await rate_limiter.check(
        key,
        int(GUEST_CONTRACT_REVIEW_LIMIT),
        int(GUEST_CONTRACT_REVIEW_WINDOW_SECONDS),
    )
    if allowed:
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"游客模式 24 小时内仅可试用 {int(GUEST_CONTRACT_REVIEW_LIMIT)} 次，请登录后继续",
        headers={
            "X-RateLimit-Limit": str(GUEST_CONTRACT_REVIEW_LIMIT),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(int(time.time() + wait_time)),
            "Retry-After": str(int(wait_time)),
        },
    )


@router.post("/review", response_model=ContractReviewResponse)
@rate_limit(*RateLimitConfig.AI_HEAVY, by_ip=True, by_user=False)
async def review_contract(
    request: Request,
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    request_id = str(getattr(request.state, "request_id", "") or "").strip() or uuid.uuid4().hex

    e2e_mock_enabled = bool(settings.debug) and str(request.headers.get("X-E2E-Mock-AI") or "").strip() == "1"

    try:
        content = await file.read()
    except Exception:
        if e2e_mock_enabled:
            content = b""
        else:
            return _make_error_response(
                status_code=400,
                error_code=ERROR_CONTRACT_BAD_REQUEST,
                message="读取文件失败",
                request_id=request_id,
            )

    filename = str(file.filename or "attachment").strip() or "attachment"
    content_type = str(file.content_type or "").strip() or None

    if not content and not e2e_mock_enabled:
        return _make_error_response(
            status_code=400,
            error_code=ERROR_CONTRACT_BAD_REQUEST,
            message="文件为空",
            request_id=request_id,
        )

    if len(content) > 10 * 1024 * 1024 and not e2e_mock_enabled:
        return _make_error_response(
            status_code=400,
            error_code=ERROR_CONTRACT_BAD_REQUEST,
            message="文件大小不能超过 10MB",
            request_id=request_id,
        )

    if e2e_mock_enabled:
        dummy = {
            "contract_type": "测试合同",
            "summary": "这是一个E2E mock 的合同审查结果",
            "overall_risk_level": "low",
            "risks": [],
            "missing_clauses": [],
            "recommended_edits": [],
            "questions_to_confirm": [],
        }
        res = ContractReviewResponse(
            filename=filename,
            content_type=content_type,
            text_chars=max(0, len(content)),
            text_preview="这是一个E2E mock 的文件内容",
            report_json=dummy,
            report_markdown="# 合同风险体检报告\n\n这是一个E2E mock 的合同审查结果\n",
            request_id=request_id,
        )
        _ = request  # silence unused warning in some linters
        headers = {"X-Request-Id": request_id}
        return JSONResponse(status_code=200, content=res.model_dump(), headers=headers)

    if current_user is None:
        await _enforce_guest_contract_quota(request)
    else:
        await quota_service.enforce_document_generate_quota(db, current_user)

    if not str(settings.openai_api_key or "").strip():
        return _make_error_response(
            status_code=503,
            error_code=ERROR_CONTRACT_NOT_CONFIGURED,
            message="AI服务未配置：请设置 OPENAI_API_KEY 后重试",
            request_id=request_id,
        )

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    def _extract_text_sync() -> str:
        if ext == "pdf" or (content_type or "").lower() == "application/pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            parts: list[str] = []
            for page in reader.pages:
                t = page.extract_text() or ""
                if t:
                    parts.append(t)
            return "\n".join(parts)

        if ext == "docx" or (content_type or "").lower() == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            import docx2txt

            tmp_path: str | None = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                return str(docx2txt.process(tmp_path) or "")
            finally:
                if tmp_path:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

        if ext in {"txt", "md", "csv", "json"} or (content_type or "").startswith("text/"):
            try:
                return content.decode("utf-8", errors="replace")
            except Exception:
                return str(content.decode(errors="replace"))

        raise ValueError("unsupported")

    try:
        extracted = await asyncio.to_thread(_extract_text_sync)
    except ValueError:
        return _make_error_response(
            status_code=400,
            error_code=ERROR_CONTRACT_BAD_REQUEST,
            message="不支持的文件类型",
            request_id=request_id,
        )
    except Exception:
        return _make_error_response(
            status_code=500,
            error_code=ERROR_CONTRACT_INTERNAL_ERROR,
            message="文件解析失败",
            request_id=request_id,
        )

    extracted_norm = str(extracted or "").strip()
    if not extracted_norm:
        return _make_error_response(
            status_code=400,
            error_code=ERROR_CONTRACT_BAD_REQUEST,
            message="无法从文件中提取文本",
            request_id=request_id,
        )

    max_chars = 200_000
    if len(extracted_norm) > max_chars:
        extracted_norm = extracted_norm[:max_chars]

    preview = extracted_norm[:4000]
    extracted_for_ai = sanitize_pii(extracted_norm)

    rules = await _load_contract_review_rules(db)

    try:
        report_json, report_md = await asyncio.to_thread(
            call_openai_contract_review, extracted_text=extracted_for_ai, rules=rules
        )
    except Exception:
        return _make_error_response(
            status_code=500,
            error_code=ERROR_CONTRACT_INTERNAL_ERROR,
            message="合同审查失败",
            request_id=request_id,
        )

    if current_user is not None:
        try:
            await quota_service.record_document_generate_usage(db, current_user)
        except Exception:
            pass

    merged = apply_contract_review_rules(
        cast(dict[str, object], report_json or {}),
        extracted_text=extracted_norm,
        rules=cast(dict[str, object] | None, rules),
    )
    merged_md = render_contract_review_markdown(cast(dict[str, object], merged))

    res = ContractReviewResponse(
        filename=filename,
        content_type=content_type,
        text_chars=len(extracted_norm),
        text_preview=preview,
        report_json=cast(dict[str, object], merged or {}),
        report_markdown=str(merged_md or "").strip() + "\n",
        request_id=request_id,
    )

    headers = {"X-Request-Id": request_id}
    return JSONResponse(status_code=200, content=res.model_dump(), headers=headers)
