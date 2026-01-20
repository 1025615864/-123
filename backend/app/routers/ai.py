"""AI助手API路由"""
import uuid
import asyncio
import hashlib
import io
import tempfile
import json
import logging
import time
import os
import inspect as py_inspect
import urllib.parse
from collections.abc import Callable
from typing import Annotated, Any, cast
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, File, Form, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, inspect, exists, or_

from ..database import get_db
from ..models.consultation import Consultation, ChatMessage
from ..models.user import User
from ..config import get_settings
from ..services.ai_metrics import ai_metrics
from ..services.critical_event_reporter import critical_event_reporter
from ..services.quota_service import quota_service
from ..services.report_generator import (
    build_consultation_report_from_export_data,
    generate_consultation_report_pdf,
)
from ..schemas.ai import (
    ChatRequest, 
    ChatResponse, 
    SearchQualityInfo,
    ConsultationResponse,
    ConsultationListItem,
    MessageResponse,
    ShareLinkResponse,
    SharedConsultationResponse,
    SharedMessageResponse,
    RatingRequest,
    RatingResponse,
    QuickRepliesRequest,
    QuickRepliesResponse,
    TranscribeResponse,
    FileAnalyzeResponse,
)
from ..utils.deps import get_current_user, get_current_user_optional
from ..utils.security import create_access_token, decode_token
from ..utils.rate_limiter import rate_limit, RateLimitConfig, rate_limiter, get_client_ip
from ..utils.pii import sanitize_pii

router = APIRouter(prefix="/ai", tags=["AI法律助手"])

settings = get_settings()

logger = logging.getLogger(__name__)

def _get_int_env(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


GUEST_AI_LIMIT = _get_int_env("GUEST_AI_LIMIT", 3)
GUEST_AI_WINDOW_SECONDS = _get_int_env("GUEST_AI_WINDOW_SECONDS", 60 * 60 * 24)

SEED_HISTORY_MAX_MESSAGES = 20

ERROR_AI_NOT_CONFIGURED = "AI_NOT_CONFIGURED"
ERROR_AI_UNAVAILABLE = "AI_UNAVAILABLE"
ERROR_AI_RATE_LIMITED = "AI_RATE_LIMITED"
ERROR_AI_FORBIDDEN = "AI_FORBIDDEN"
ERROR_AI_UNAUTHORIZED = "AI_UNAUTHORIZED"
ERROR_AI_BAD_REQUEST = "AI_BAD_REQUEST"
ERROR_AI_INTERNAL_ERROR = "AI_INTERNAL_ERROR"


def _coerce_int(value: object, default: int = 0) -> int:
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


def _stable_bucket(seed: str) -> int:
    s = str(seed or "").strip()
    if not s:
        return 0
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    try:
        return int(h[:8], 16) % 100
    except Exception:
        return 0


async def _get_system_config_value(db: AsyncSession, key: str) -> str | None:
    from ..models.system import SystemConfig

    k = str(key or "").strip()
    if not k:
        return None
    res = await db.execute(select(SystemConfig.value).where(SystemConfig.key == k))
    v = res.scalar_one_or_none()
    return str(v) if isinstance(v, str) else None


async def _select_prompt_version(db: AsyncSession, *, bucket_seed: str) -> str:
    default_pv = str((await _get_system_config_value(db, "AI_PROMPT_VERSION_DEFAULT")) or "v1").strip() or "v1"
    v2_pv = str((await _get_system_config_value(db, "AI_PROMPT_VERSION_V2")) or "v2").strip() or "v2"

    percent_raw = await _get_system_config_value(db, "AI_PROMPT_VERSION_V2_PERCENT")
    percent = _coerce_int(percent_raw, 0)
    percent = max(0, min(100, int(percent)))

    if percent <= 0:
        return default_pv
    if percent >= 100:
        return v2_pv or default_pv

    bucket = _stable_bucket(bucket_seed)
    return v2_pv if bucket < percent else default_pv


def _audit_event(event: str, payload: dict[str, object]) -> None:
    try:
        logger.info("ai_audit event=%s payload=%s", str(event), json.dumps(payload, ensure_ascii=False))
    except Exception:
        logger.info("ai_audit event=%s", str(event))


def _error_code_for_http(status_code: int) -> str:
    sc = int(status_code)
    if sc == 400:
        return ERROR_AI_BAD_REQUEST
    if sc == 401:
        return ERROR_AI_UNAUTHORIZED
    if sc == 403:
        return ERROR_AI_FORBIDDEN
    if sc == 429:
        return ERROR_AI_RATE_LIMITED
    if sc == 503:
        return ERROR_AI_UNAVAILABLE
    return ERROR_AI_INTERNAL_ERROR


def _extract_message(detail: object) -> str:
    if detail is None:
        return ""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        detail_dict = cast(dict[str, object], detail)
        msg_obj = detail_dict.get("message")
        if isinstance(msg_obj, str):
            return msg_obj
        msg2_obj = detail_dict.get("detail")
        if isinstance(msg2_obj, str):
            return msg2_obj
    return str(detail)


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


def _audit_text(value: str | None, *, limit: int = 500) -> str:
    s = str(value or "")
    s = s.replace("\r", " ").replace("\n", " ")
    s = s[: max(0, limit)]
    s = s.strip()
    s = s.replace("\t", " ")
    s = s.replace("  ", " ")
    return s


async def _enforce_guest_ai_quota(request: Request) -> None:
    key = f"ai:guest:{get_client_ip(request)}"
    allowed, remaining, wait_time = await rate_limiter.check(key, GUEST_AI_LIMIT, GUEST_AI_WINDOW_SECONDS)
    if allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"游客模式 24 小时内仅可试用 {int(GUEST_AI_LIMIT)} 次，请登录后继续",
        headers={
            "X-RateLimit-Limit": str(GUEST_AI_LIMIT),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(int(time.time() + wait_time)),
            "Retry-After": str(int(wait_time)),
        },
    )


def _try_get_ai_assistant() -> Any | None:
    try:
        from ..services.ai_assistant import get_ai_assistant

        return get_ai_assistant()
    except Exception:
        return None


def _supports_kwarg(func: Callable[..., Any] | None, name: str) -> bool:
    if func is None:
        return False
    try:
        sig = py_inspect.signature(func)
        params = sig.parameters
        for p in params.values():
            if p.kind == py_inspect.Parameter.VAR_KEYWORD:
                return True
        return name in params
    except Exception:
        return False


def _build_user_profile(current_user: User | None) -> str:
    if current_user is None:
        return ""

    nickname = str(getattr(current_user, "nickname", "") or "").strip()
    username = str(getattr(current_user, "username", "") or "").strip()
    role = str(getattr(current_user, "role", "") or "").strip()

    parts: list[str] = []
    if nickname:
        parts.append(f"昵称：{nickname}")
    if username:
        parts.append(f"用户名：{username}")
    if role:
        parts.append(f"身份：{role}")
    return "\n".join(parts)


async def _load_seed_history(
    db: AsyncSession,
    session_id: str,
    *,
    current_user: User | None,
) -> tuple[Consultation | None, list[dict[str, str]]]:
    """Load DB-backed conversation history for a given session.

    Returns:
        (consultation, history)
    """
    result = await db.execute(
        select(Consultation).where(Consultation.session_id == session_id)
    )
    consultation = result.scalar_one_or_none()

    if consultation is None:
        return None, []

    consultation_user_id = cast(int | None, getattr(consultation, "user_id", None))
    if consultation_user_id is not None:
        if current_user is None or consultation_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权限访问该咨询会话")

    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.consultation_id == consultation.id)
        .order_by(ChatMessage.created_at)
    )
    messages = messages_result.scalars().all()

    history = [
        {"role": cast(str, cast(object, m.role)), "content": cast(str, cast(object, m.content))}
        for m in messages
    ]
    if len(history) > SEED_HISTORY_MAX_MESSAGES:
        history = history[-SEED_HISTORY_MAX_MESSAGES:]
    return consultation, history


@router.post("/chat", response_model=ChatResponse)
@rate_limit(*RateLimitConfig.AI_CHAT, by_ip=True, by_user=False)
async def chat_with_ai(
    payload: ChatRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
):
    """
    与AI法律助手对话
    
    - **message**: 用户消息内容
    - **session_id**: 会话ID（可选，为空则创建新会话）
    - 如果已登录，咨询记录将绑定到用户账号
    """
    started_at = float(time.time())
    request_id = str(getattr(request.state, "request_id", "") or "").strip() or uuid.uuid4().hex
    _ = response.headers.setdefault("X-Request-Id", request_id)
    ai_metrics.record_request("chat")
    client_ip = get_client_ip(request)
    user_id_str = str(current_user.id) if current_user else "guest"

    try:
        if not settings.openai_api_key:
            error_code = ERROR_AI_NOT_CONFIGURED
            message = "AI服务未配置：请设置 OPENAI_API_KEY 后重试"
            ai_metrics.record_error(
                endpoint="chat",
                request_id=request_id,
                error_code=error_code,
                status_code=503,
                message=message,
            )
            critical_event_reporter.fire_and_forget(
                event="ai_not_configured",
                severity="warning",
                request_id=request_id,
                title="AI服务未配置",
                message=message,
                data={
                    "endpoint": "chat",
                    "user_id": user_id_str,
                    "ip": client_ip,
                },
                dedup_key="ai_not_configured",
            )
            _audit_event(
                "chat_error",
                {
                    "request_id": request_id,
                    "endpoint": "chat",
                    "user_id": user_id_str,
                    "ip": client_ip,
                    "session_id": str(payload.session_id or ""),
                    "status_code": 503,
                    "error_code": error_code,
                    "duration_ms": int((time.time() - started_at) * 1000),
                },
            )
            return _make_error_response(
                status_code=503,
                error_code=error_code,
                message=message,
                request_id=request_id,
            )

        if current_user is None:
            await _enforce_guest_ai_quota(request)
        else:
            await quota_service.enforce_ai_chat_quota(db, current_user)

        logger.info(
            "ai_chat_request request_id=%s user_id=%s session_id=%s message=%s",
            request_id,
            user_id_str,
            str(payload.session_id) if payload.session_id else "",
            _audit_text(payload.message),
        )
        _audit_event(
            "chat_request",
            {
                "request_id": request_id,
                "endpoint": "chat",
                "user_id": user_id_str,
                "ip": client_ip,
                "session_id": str(payload.session_id or ""),
            },
        )

        seed_history: list[dict[str, str]] | None = None
        consultation: Consultation | None = None
        if payload.session_id:
            consultation, seed_history = await _load_seed_history(db, payload.session_id, current_user=current_user)

        bucket_seed = f"u:{current_user.id}" if current_user is not None else f"g:{client_ip or request_id}"
        prompt_version = await _select_prompt_version(db, bucket_seed=bucket_seed)

        assistant = _try_get_ai_assistant()
        if assistant is None:
            error_code = ERROR_AI_UNAVAILABLE
            message = "AI服务不可用：缺少可选依赖或配置异常"
            ai_metrics.record_error(
                endpoint="chat",
                request_id=request_id,
                error_code=error_code,
                status_code=503,
                message=message,
            )
            critical_event_reporter.fire_and_forget(
                event="ai_unavailable",
                severity="warning",
                request_id=request_id,
                title="AI服务不可用",
                message=message,
                data={
                    "endpoint": "chat",
                    "user_id": user_id_str,
                    "ip": client_ip,
                },
                dedup_key="ai_unavailable",
            )
            return _make_error_response(
                status_code=503,
                error_code=error_code,
                message=message,
                request_id=request_id,
            )

        user_profile = _build_user_profile(current_user)
        chat_kwargs: dict[str, Any] = {
            "message": payload.message,
            "session_id": payload.session_id,
            "initial_history": seed_history,
        }
        if user_profile and _supports_kwarg(getattr(assistant, "chat", None), "user_profile"):
            chat_kwargs["user_profile"] = user_profile
        if _supports_kwarg(getattr(assistant, "chat", None), "prompt_version"):
            chat_kwargs["prompt_version"] = prompt_version

        chat_result: object = await cast(Any, assistant).chat(**chat_kwargs)

        meta: dict[str, Any] = {}
        if not isinstance(chat_result, tuple):
            raise RuntimeError("invalid assistant.chat result")

        if len(chat_result) == 3:
            session_id_obj, answer_obj, references_obj = chat_result
        elif len(chat_result) == 4:
            session_id_obj, answer_obj, references_obj, meta_obj = chat_result
            if isinstance(meta_obj, dict):
                meta = cast(dict[str, Any], meta_obj)
        else:
            raise RuntimeError("invalid assistant.chat result")

        session_id = cast(str, session_id_obj) if isinstance(session_id_obj, str) else str(session_id_obj)
        answer = cast(str, answer_obj) if isinstance(answer_obj, str) else str(answer_obj)
        references: list[Any] = cast(list[Any], references_obj) if isinstance(references_obj, list) else []

        if consultation is None:
            result = await db.execute(
                select(Consultation).where(Consultation.session_id == session_id)
            )
            consultation = result.scalar_one_or_none()

            if consultation is not None:
                consultation_user_id = cast(int | None, getattr(consultation, "user_id", None))
                if consultation_user_id is not None:
                    if current_user is None or consultation_user_id != current_user.id:
                        raise HTTPException(status_code=403, detail="无权限访问该咨询会话")

        if not consultation:
            consultation = Consultation(
                session_id=session_id,
                title=payload.message[:50] + "..." if len(payload.message) > 50 else payload.message,
                user_id=current_user.id if current_user else None,
            )
            db.add(consultation)
            await db.flush()
        else:
            consultation_user_id = cast(int | None, getattr(consultation, "user_id", None))
            if current_user is not None and consultation_user_id is None:
                setattr(consultation, "user_id", current_user.id)
        
        user_message = ChatMessage(
            consultation_id=consultation.id,
            role="user",
            content=payload.message,
        )
        db.add(user_message)
        
        references_list = [ref.model_dump() for ref in references]
        meta_to_save: dict[str, object] = {}
        if isinstance(meta, dict):
            meta_to_save.update(meta)
        meta_to_save.setdefault("prompt_version", str(prompt_version or "v1"))
        meta_to_save.setdefault("duration_ms", int((time.time() - started_at) * 1000))
        meta_to_save.setdefault("request_id", str(request_id))

        refs_json = json.dumps(
            {"references": references_list, "meta": meta_to_save},
            ensure_ascii=False,
        )
        ai_message = ChatMessage(
            consultation_id=consultation.id,
            role="assistant",
            content=answer,
            references=refs_json,
        )
        db.add(ai_message)

        await db.flush()
        assistant_message_id = cast(int | None, getattr(ai_message, "id", None))
        
        await db.commit()

        if current_user is not None:
            try:
                await quota_service.record_ai_chat_usage(db, current_user)
            except Exception:
                logger.exception("quota_consume_failed request_id=%s", request_id)

        logger.info(
            "ai_chat_response request_id=%s user_id=%s session_id=%s assistant_message_id=%s",
            request_id,
            user_id_str,
            str(session_id),
            str(assistant_message_id) if assistant_message_id is not None else "",
        )

        _audit_event(
            "chat_done",
            {
                "request_id": request_id,
                "endpoint": "chat",
                "user_id": user_id_str,
                "ip": client_ip,
                "session_id": str(session_id),
                "assistant_message_id": int(assistant_message_id) if assistant_message_id is not None else None,
                "strategy_used": meta.get("strategy_used"),
                "risk_level": meta.get("risk_level"),
                "duration_ms": int((time.time() - started_at) * 1000),
            },
        )

        search_quality_raw = meta.get("search_quality")
        search_quality = (
            SearchQualityInfo.model_validate(search_quality_raw)
            if isinstance(search_quality_raw, dict)
            else None
        )

        return ChatResponse(
            session_id=session_id,
            answer=answer,
            references=references,
            assistant_message_id=assistant_message_id,
            strategy_used=cast(str | None, meta.get("strategy_used")) if isinstance(meta.get("strategy_used"), str) else None,
            strategy_reason=cast(str | None, meta.get("strategy_reason")) if isinstance(meta.get("strategy_reason"), str) else None,
            confidence=cast(str | None, meta.get("confidence")) if isinstance(meta.get("confidence"), str) else None,
            risk_level=cast(str | None, meta.get("risk_level")) if isinstance(meta.get("risk_level"), str) else None,
            search_quality=search_quality,
            disclaimer=cast(str | None, meta.get("disclaimer")) if isinstance(meta.get("disclaimer"), str) else None,
            model_used=cast(str | None, meta.get("model_used")) if isinstance(meta.get("model_used"), str) else None,
            fallback_used=cast(bool | None, meta.get("fallback_used")) if isinstance(meta.get("fallback_used"), bool) else None,
            model_attempts=cast(list[str] | None, meta.get("model_attempts"))
            if isinstance(meta.get("model_attempts"), list)
            else None,
            intent=cast(str | None, meta.get("intent")) if isinstance(meta.get("intent"), str) else None,
            needs_clarification=cast(bool | None, meta.get("needs_clarification")) if isinstance(meta.get("needs_clarification"), bool) else None,
            clarifying_questions=cast(list[str] | None, meta.get("clarifying_questions"))
            if isinstance(meta.get("clarifying_questions"), list)
            else None,
            created_at=datetime.now(),
        )
    except HTTPException as e:
        sc = int(e.status_code)
        error_code = _error_code_for_http(sc)
        message = _extract_message(getattr(e, "detail", ""))
        ai_metrics.record_error(
            endpoint="chat",
            request_id=request_id,
            error_code=error_code,
            status_code=sc,
            message=message,
        )
        if sc >= 500:
            critical_event_reporter.fire_and_forget(
                event="ai_http_exception",
                severity="error",
                request_id=request_id,
                title="AI接口异常",
                message=message,
                data={
                    "endpoint": "chat",
                    "user_id": user_id_str,
                    "ip": client_ip,
                },
                dedup_key="ai_http_exception|chat",
            )
        _audit_event(
            "chat_error",
            {
                "request_id": request_id,
                "endpoint": "chat",
                "user_id": user_id_str,
                "ip": client_ip,
                "session_id": str(payload.session_id or ""),
                "status_code": sc,
                "error_code": error_code,
                "duration_ms": int((time.time() - started_at) * 1000),
            },
        )
        extra_headers = cast(dict[str, str] | None, getattr(e, "headers", None))
        return _make_error_response(
            status_code=sc,
            error_code=error_code,
            message=message,
            request_id=request_id,
            headers=extra_headers,
        )
    except Exception as e:
        logger.exception("ai_chat_unhandled request_id=%s", request_id)
        error_code = ERROR_AI_INTERNAL_ERROR
        message = "AI服务异常，请稍后重试"
        ai_metrics.record_error(
            endpoint="chat",
            request_id=request_id,
            error_code=error_code,
            status_code=500,
            message=str(e),
        )
        critical_event_reporter.fire_and_forget(
            event="ai_unhandled_exception",
            severity="error",
            request_id=request_id,
            title="AI未处理异常",
            message=str(e),
            data={
                "endpoint": "chat",
                "user_id": user_id_str,
                "ip": client_ip,
            },
            dedup_key="ai_unhandled_exception|chat",
        )
        _audit_event(
            "chat_error",
            {
                "request_id": request_id,
                "endpoint": "chat",
                "user_id": user_id_str,
                "ip": client_ip,
                "session_id": str(payload.session_id or ""),
                "status_code": 500,
                "error_code": error_code,
                "duration_ms": int((time.time() - started_at) * 1000),
            },
        )
        return _make_error_response(
            status_code=500,
            error_code=error_code,
            message=message,
            request_id=request_id,
        )


@router.post("/chat/stream")
@rate_limit(*RateLimitConfig.AI_CHAT, by_ip=True, by_user=False)
async def chat_with_ai_stream(
    payload: ChatRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
):
    """
    流式对话（SSE）
    
    返回Server-Sent Events流，包含：
    - session: 会话ID
    - references: 法律引用
    - content: 回答内容片段
    - done: 完成信号
    """
    started_at = float(time.time())
    request_id = str(getattr(request.state, "request_id", "") or "").strip() or uuid.uuid4().hex
    ai_metrics.record_request("chat_stream")
    client_ip = get_client_ip(request)

    current_user_id: int | None = None
    if current_user is not None:
        try:
            identity = inspect(current_user).identity
            if identity:
                current_user_id = cast(int | None, identity[0])
        except Exception:
            current_user_id = None

    user_id_str = str(current_user_id) if current_user_id is not None else "guest"

    e2e_mock_enabled = bool(settings.debug) and str(request.headers.get("X-E2E-Mock-AI") or "").strip() == "1"
    if e2e_mock_enabled:
        forced_persist_error = str(request.headers.get("X-E2E-Force-Persist-Error") or "").strip()
        e2e_stream_scenario = str(request.headers.get("X-E2E-Stream-Scenario") or "").strip().lower()

        async def event_generator():
            session_id = str(payload.session_id or "").strip() or f"e2e_{uuid.uuid4().hex}"
            yield f"event: session\ndata: {json.dumps({'session_id': session_id}, ensure_ascii=False)}\n\n"

            thinking_steps = [
                {
                    "type": "intent",
                    "title": "识别用户意图",
                    "content": "理解用户的问题类型与诉求重点。",
                },
                {
                    "type": "retrieval",
                    "title": "检索相关法条",
                    "content": "匹配可能适用的法律条文与关键词。",
                },
                {
                    "type": "analysis",
                    "title": "归纳要点并分析",
                    "content": "梳理事实要点，给出可执行的建议路径。",
                },
                {
                    "type": "generation",
                    "title": "生成回复",
                    "content": "输出结构化答复与注意事项。",
                },
            ]
            yield f"event: thinking\ndata: {json.dumps({'steps': thinking_steps, 'is_thinking': True}, ensure_ascii=False)}\n\n"

            refs = [
                {
                    "law_name": "民法典",
                    "article": "第1条",
                    "content": "为了保护民事主体的合法权益，调整民事关系，维护社会和经济秩序，适应中国特色社会主义发展要求，弘扬社会主义核心价值观，根据宪法，制定本法。",
                    "relevance": 0.92,
                }
            ]
            yield f"event: references\ndata: {json.dumps({'references': refs}, ensure_ascii=False)}\n\n"

            if e2e_stream_scenario == "scroll":
                scroll_intro = "根据《民法典》第1条，以下为滚动测试内容：\n"
                yield f"event: content\ndata: {json.dumps({'text': scroll_intro}, ensure_ascii=False)}\n\n"

                lines = [f"{i}-内容\n" for i in range(1, 201)]
                batch_size = 12
                for batch_start in range(0, len(lines), batch_size):
                    batch_text = "".join(lines[batch_start : batch_start + batch_size])
                    yield f"event: content\ndata: {json.dumps({'text': batch_text}, ensure_ascii=False)}\n\n"

                    if batch_start == batch_size * 4:
                        await asyncio.sleep(0.9)
                    else:
                        await asyncio.sleep(0.02)
            else:
                yield f"event: content\ndata: {json.dumps({'text': '根据《民法典》第1条，给您一个示例回复。'}, ensure_ascii=False)}\n\n"

            final_done: dict[str, object] = {
                "session_id": session_id,
                "assistant_message_id": 1,
                "request_id": request_id,
            }

            if forced_persist_error:
                final_done["persist_error"] = forced_persist_error

            persist_error_code: str | None = None
            if forced_persist_error == "stream_failed":
                persist_error_code = "AI_STREAM_FAILED"
            elif forced_persist_error == "persist_failed":
                persist_error_code = "AI_PERSIST_FAILED"
            elif forced_persist_error == "persist_forbidden":
                persist_error_code = "AI_PERSIST_FORBIDDEN"
            if persist_error_code is not None:
                final_done["error_code"] = persist_error_code

            yield f"event: done\ndata: {json.dumps(final_done, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Encoding": "identity",
                "X-Request-Id": request_id,
            },
        )

    try:
        if not settings.openai_api_key:
            error_code = ERROR_AI_NOT_CONFIGURED
            message = "AI服务未配置：请设置 OPENAI_API_KEY 后重试"
            ai_metrics.record_error(
                endpoint="chat_stream",
                request_id=request_id,
                error_code=error_code,
                status_code=503,
                message=message,
            )
            critical_event_reporter.fire_and_forget(
                event="ai_not_configured",
                severity="warning",
                request_id=request_id,
                title="AI服务未配置",
                message=message,
                data={
                    "endpoint": "chat_stream",
                    "user_id": user_id_str,
                    "ip": client_ip,
                },
                dedup_key="ai_not_configured",
            )
            _audit_event(
                "chat_stream_error",
                {
                    "request_id": request_id,
                    "endpoint": "chat_stream",
                    "user_id": user_id_str,
                    "ip": client_ip,
                    "session_id": str(payload.session_id or ""),
                    "status_code": 503,
                    "error_code": error_code,
                    "duration_ms": int((time.time() - started_at) * 1000),
                },
            )
            return _make_error_response(
                status_code=503,
                error_code=error_code,
                message=message,
                request_id=request_id,
            )

        if current_user is None:
            await _enforce_guest_ai_quota(request)
        else:
            await quota_service.enforce_ai_chat_quota(db, current_user)

        logger.info(
            "ai_chat_stream_request request_id=%s user_id=%s session_id=%s message=%s",
            request_id,
            user_id_str,
            str(payload.session_id) if payload.session_id else "",
            _audit_text(payload.message),
        )
        _audit_event(
            "chat_stream_request",
            {
                "request_id": request_id,
                "endpoint": "chat_stream",
                "user_id": user_id_str,
                "ip": client_ip,
                "session_id": str(payload.session_id or ""),
            },
        )

        bucket_seed = f"u:{current_user_id}" if current_user_id is not None else f"g:{client_ip or request_id}"
        prompt_version = await _select_prompt_version(db, bucket_seed=bucket_seed)

        seed_history: list[dict[str, str]] | None = None
        if payload.session_id:
            _, seed_history = await _load_seed_history(db, payload.session_id, current_user=current_user)

        assistant = _try_get_ai_assistant()
        if assistant is None:
            error_code = ERROR_AI_UNAVAILABLE
            message = "AI服务不可用：缺少可选依赖或配置异常"
            ai_metrics.record_error(
                endpoint="chat_stream",
                request_id=request_id,
                error_code=error_code,
                status_code=503,
                message=message,
            )
            critical_event_reporter.fire_and_forget(
                event="ai_unavailable",
                severity="warning",
                request_id=request_id,
                title="AI服务不可用",
                message=message,
                data={
                    "endpoint": "chat_stream",
                    "user_id": user_id_str,
                    "ip": client_ip,
                },
                dedup_key="ai_unavailable",
            )
            return _make_error_response(
                status_code=503,
                error_code=error_code,
                message=message,
                request_id=request_id,
            )

        if current_user is not None:
            try:
                await quota_service.record_ai_chat_usage(db, current_user)
            except Exception:
                logger.exception("quota_consume_failed request_id=%s", request_id)

        async def event_generator():
            session_id: str | None = None
            references_payload: list[dict[str, object]] | None = None
            answer_parts: list[str] = []
            done_payload: dict[str, object] | None = None

            assistant_message_id: int | None = None
            persist_error: str | None = None

            try:
                user_profile = _build_user_profile(current_user)
                stream_kwargs: dict[str, object] = {
                    "message": payload.message,
                    "session_id": payload.session_id,
                    "initial_history": seed_history,
                }
                if user_profile and _supports_kwarg(getattr(assistant, "chat_stream", None), "user_profile"):
                    stream_kwargs["user_profile"] = user_profile
                if _supports_kwarg(getattr(assistant, "chat_stream", None), "prompt_version"):
                    stream_kwargs["prompt_version"] = prompt_version

                async for event_type, data in assistant.chat_stream(**cast(dict, stream_kwargs)):
                    if event_type == "session":
                        session_id = cast(str | None, data.get("session_id"))
                    elif event_type == "references":
                        references_payload = cast(list[dict[str, object]] | None, data.get("references"))
                    elif event_type == "content":
                        chunk = cast(str | None, data.get("text"))
                        if chunk:
                            answer_parts.append(chunk)

                    if event_type == "done":
                        done_payload = data
                        continue

                    yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            except asyncio.CancelledError:
                raise
            except Exception:
                persist_error = "stream_failed"

            if session_id is None:
                session_id = payload.session_id

            if session_id is None:
                if persist_error is None:
                    persist_error = "stream_failed"
            else:
                try:
                    result = await db.execute(
                        select(Consultation).where(Consultation.session_id == session_id)
                    )
                    consultation = result.scalar_one_or_none()

                    if consultation is not None:
                        consultation_user_id = cast(int | None, getattr(consultation, "user_id", None))
                        if consultation_user_id is not None:
                            if current_user_id is None or consultation_user_id != current_user_id:
                                if persist_error is None:
                                    persist_error = "persist_forbidden"
                                raise PermissionError("persist forbidden")

                    if not consultation:
                        consultation = Consultation(
                            session_id=session_id,
                            title=payload.message[:50] + "..." if len(payload.message) > 50 else payload.message,
                            user_id=current_user_id,
                        )
                        db.add(consultation)
                        await db.flush()
                    else:
                        consultation_user_id = cast(int | None, getattr(consultation, "user_id", None))
                        if current_user_id is not None and consultation_user_id is None:
                            setattr(consultation, "user_id", current_user_id)

                    user_message = ChatMessage(
                        consultation_id=consultation.id,
                        role="user",
                        content=payload.message,
                    )
                    db.add(user_message)

                    meta_to_save: dict[str, object] = {}
                    if isinstance(done_payload, dict):
                        for k in (
                            "strategy_used",
                            "strategy_reason",
                            "confidence",
                            "risk_level",
                            "prompt_version",
                            "intent",
                            "needs_clarification",
                            "model_used",
                            "fallback_used",
                            "model_attempts",
                            "prompt_tokens",
                            "completion_tokens",
                            "total_tokens",
                            "estimated_cost_usd",
                        ):
                            if k in done_payload:
                                meta_to_save[k] = cast(object, done_payload.get(k))
                    meta_to_save.setdefault("prompt_version", str(prompt_version or "v1"))
                    meta_to_save.setdefault("duration_ms", int((time.time() - started_at) * 1000))
                    meta_to_save.setdefault("request_id", str(request_id))

                    refs_json = json.dumps(
                        {"references": references_payload or [], "meta": meta_to_save},
                        ensure_ascii=False,
                    )
                    ai_message = ChatMessage(
                        consultation_id=consultation.id,
                        role="assistant",
                        content="".join(answer_parts),
                        references=refs_json,
                    )
                    db.add(ai_message)

                    await db.flush()
                    assistant_message_id = cast(int | None, getattr(ai_message, "id", None))

                    await db.commit()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    await db.rollback()
                    if persist_error is None:
                        persist_error = "persist_failed"

            final_done: dict[str, object] = {}
            if done_payload:
                final_done.update(done_payload)
            final_done["session_id"] = session_id
            if assistant_message_id is not None:
                final_done["assistant_message_id"] = assistant_message_id
            if persist_error is not None:
                final_done["persist_error"] = persist_error

            final_done["request_id"] = request_id

            persist_error_code: str | None = None
            if persist_error == "stream_failed":
                persist_error_code = "AI_STREAM_FAILED"
            elif persist_error == "persist_failed":
                persist_error_code = "AI_PERSIST_FAILED"
            elif persist_error == "persist_forbidden":
                persist_error_code = "AI_PERSIST_FORBIDDEN"
            if persist_error_code is not None:
                final_done["error_code"] = persist_error_code
                ai_metrics.record_error(
                    endpoint="chat_stream",
                    request_id=request_id,
                    error_code=persist_error_code,
                    status_code=200,
                    message=persist_error,
                )

            logger.info(
                "ai_chat_stream_done request_id=%s user_id=%s session_id=%s assistant_message_id=%s persist_error=%s",
                request_id,
                user_id_str,
                str(session_id) if session_id is not None else "",
                str(assistant_message_id) if assistant_message_id is not None else "",
                str(persist_error) if persist_error is not None else "",
            )

            _audit_event(
                "chat_stream_done",
                {
                    "request_id": request_id,
                    "endpoint": "chat_stream",
                    "user_id": user_id_str,
                    "ip": client_ip,
                    "session_id": str(session_id) if session_id is not None else "",
                    "assistant_message_id": int(assistant_message_id) if assistant_message_id is not None else None,
                    "persist_error": str(persist_error) if persist_error is not None else None,
                    "persist_error_code": persist_error_code,
                    "duration_ms": int((time.time() - started_at) * 1000),
                },
            )

            yield f"event: done\ndata: {json.dumps(final_done, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Encoding": "identity",
                "X-Request-Id": request_id,
            },
        )
    except HTTPException as e:
        sc = int(getattr(e, "status_code", 500) or 500)
        error_code = _error_code_for_http(sc)
        message = _extract_message(getattr(e, "detail", ""))
        ai_metrics.record_error(
            endpoint="chat_stream",
            request_id=request_id,
            error_code=error_code,
            status_code=sc,
            message=message,
        )
        if sc >= 500:
            critical_event_reporter.fire_and_forget(
                event="ai_http_exception",
                severity="error",
                request_id=request_id,
                title="AI接口异常",
                message=message,
                data={
                    "endpoint": "chat_stream",
                    "status_code": sc,
                    "error_code": error_code,
                    "user_id": user_id_str,
                    "ip": client_ip,
                },
                dedup_key=f"ai_http_exception|chat_stream|{sc}|{error_code}",
            )
        _audit_event(
            "chat_stream_error",
            {
                "request_id": request_id,
                "endpoint": "chat_stream",
                "user_id": user_id_str,
                "ip": client_ip,
                "session_id": str(payload.session_id or ""),
                "status_code": sc,
                "error_code": error_code,
                "duration_ms": int((time.time() - started_at) * 1000),
            },
        )
        extra_headers = cast(dict[str, str] | None, getattr(e, "headers", None))
        return _make_error_response(
            status_code=sc,
            error_code=error_code,
            message=message,
            request_id=request_id,
            headers=extra_headers,
        )
    except Exception as e:
        logger.exception("ai_chat_stream_unhandled request_id=%s", request_id)
        error_code = ERROR_AI_INTERNAL_ERROR
        message = "AI服务异常，请稍后重试"
        ai_metrics.record_error(
            endpoint="chat_stream",
            request_id=request_id,
            error_code=error_code,
            status_code=500,
            message=str(e),
        )
        critical_event_reporter.fire_and_forget(
            event="ai_unhandled_exception",
            severity="error",
            request_id=request_id,
            title="AI未处理异常",
            message=str(e),
            data={
                "endpoint": "chat_stream",
                "user_id": user_id_str,
                "ip": client_ip,
            },
            dedup_key="ai_unhandled_exception|chat_stream",
        )
        _audit_event(
            "chat_stream_error",
            {
                "request_id": request_id,
                "endpoint": "chat_stream",
                "user_id": user_id_str,
                "ip": client_ip,
                "session_id": str(payload.session_id or ""),
                "status_code": 500,
                "error_code": error_code,
                "duration_ms": int((time.time() - started_at) * 1000),
            },
        )
        return _make_error_response(
            status_code=500,
            error_code=error_code,
            message=message,
            request_id=request_id,
        )


@router.get("/consultations", response_model=list[ConsultationListItem])
async def list_consultations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(max_length=200)] = None,
):
    """
    获取咨询历史列表
    
    - **skip**: 跳过记录数
    - **limit**: 返回记录数限制
    """
    subquery = (
        select(
            ChatMessage.consultation_id,
            func.count(ChatMessage.id).label('message_count')
        )
        .group_by(ChatMessage.consultation_id)
        .subquery()
    )
    
    query = (
        select(
            Consultation,
            func.coalesce(subquery.c.message_count, 0).label('message_count')
        )
        .outerjoin(subquery, Consultation.id == subquery.c.consultation_id)
        .where(Consultation.user_id == current_user.id)
    )

    q_norm = str(q or "").strip()
    if q_norm:
        q_lower = q_norm.lower()
        pattern = f"%{q_lower}%"
        title_match = func.lower(func.coalesce(Consultation.title, "")).like(pattern)
        message_match = exists(
            select(1)
            .where(ChatMessage.consultation_id == Consultation.id)
            .where(func.lower(ChatMessage.content).like(pattern))
        )
        query = query.where(or_(title_match, message_match))

    result = await db.execute(
        query
        .order_by(Consultation.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    rows = cast(list[tuple[Consultation, int]], result.all())
    items: list[ConsultationListItem] = []
    for consultation, message_count in rows:
        items.append(
            ConsultationListItem(
                id=cast(int, cast(object, consultation.id)),
                session_id=cast(str, cast(object, consultation.session_id)),
                title=cast(str | None, cast(object, consultation.title)),
                created_at=cast(datetime, cast(object, consultation.created_at)),
                message_count=int(message_count),
            )
        )

    return items


@router.get("/consultations/{session_id}", response_model=ConsultationResponse)
async def get_consultation(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    获取单次咨询详情
    
    - **session_id**: 会话ID
    """
    result = await db.execute(
        select(Consultation).where(Consultation.session_id == session_id)
    )
    consultation = result.scalar_one_or_none()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="咨询记录不存在")

    consultation_user_id = cast(int | None, getattr(consultation, "user_id", None))
    if consultation_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问该咨询记录")
    
    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.consultation_id == consultation.id)
        .order_by(ChatMessage.created_at)
    )
    messages = messages_result.scalars().all()
    
    return ConsultationResponse(
        id=cast(int, cast(object, consultation.id)),
        session_id=cast(str, cast(object, consultation.session_id)),
        title=cast(str | None, cast(object, consultation.title)),
        created_at=cast(datetime, cast(object, consultation.created_at)),
        updated_at=cast(datetime, cast(object, consultation.updated_at)),
        messages=[MessageResponse.model_validate(msg) for msg in messages]
    )


@router.post("/consultations/{session_id}/share", response_model=ShareLinkResponse)
async def create_consultation_share_link(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    expires_days: Annotated[int, Query(ge=1, le=30, description="分享链接有效期（天）")] = 7,
):
    result = await db.execute(select(Consultation).where(Consultation.session_id == session_id))
    consultation = result.scalar_one_or_none()
    if not consultation:
        raise HTTPException(status_code=404, detail="咨询记录不存在")

    consultation_user_id = cast(int | None, getattr(consultation, "user_id", None))
    if consultation_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限分享该咨询记录")

    exp_delta = timedelta(days=int(expires_days))
    expires_at = datetime.now(timezone.utc) + exp_delta

    token = create_access_token(
        {
            "type": "consultation_share",
            "session_id": str(session_id),
        },
        expires_delta=exp_delta,
    )

    return ShareLinkResponse(
        token=token,
        share_path=f"/share/{token}",
        expires_at=expires_at,
    )


@router.get("/share/{token}", response_model=SharedConsultationResponse)
async def get_shared_consultation(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    payload = decode_token(str(token or ""))
    if payload is None:
        raise HTTPException(status_code=401, detail="无效或已过期的分享链接")

    token_type = str(payload.get("type") or "").strip()
    if token_type != "consultation_share":
        raise HTTPException(status_code=401, detail="无效的分享链接")

    sid = str(payload.get("session_id") or "").strip()
    if not sid:
        raise HTTPException(status_code=401, detail="无效的分享链接")

    result = await db.execute(select(Consultation).where(Consultation.session_id == sid))
    consultation = result.scalar_one_or_none()
    if not consultation:
        raise HTTPException(status_code=404, detail="咨询记录不存在")

    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.consultation_id == consultation.id)
        .order_by(ChatMessage.created_at)
    )
    messages = messages_result.scalars().all()

    shared_messages: list[SharedMessageResponse] = []
    for msg in messages:
        shared_messages.append(
            SharedMessageResponse(
                role=cast(str, cast(object, msg.role)),
                content=cast(str, cast(object, msg.content)),
                references=cast(str | None, getattr(msg, "references", None)),
                created_at=cast(datetime, cast(object, msg.created_at)),
            )
        )

    return SharedConsultationResponse(
        session_id=cast(str, cast(object, consultation.session_id)),
        title=cast(str | None, cast(object, consultation.title)),
        created_at=cast(datetime, cast(object, consultation.created_at)),
        messages=shared_messages,
    )


@router.delete("/consultations/{session_id}")
async def delete_consultation(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    删除咨询记录
    
    - **session_id**: 会话ID
    """
    result = await db.execute(
        select(Consultation).where(Consultation.session_id == session_id)
    )
    consultation = result.scalar_one_or_none()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="咨询记录不存在")
    
    consultation_user_id = cast(int | None, getattr(consultation, "user_id", None))
    if consultation_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限删除该咨询记录")
    
    await db.delete(consultation)
    await db.commit()
    
    try:
        assistant = _try_get_ai_assistant()
        if assistant is not None:
            assistant.clear_session(session_id)
    except Exception:
        pass
    
    return {"message": "删除成功"}


@router.get("/consultations/{session_id}/export")
async def export_consultation(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    导出咨询记录为结构化数据（用于前端生成PDF）
    
    - **session_id**: 会话ID
    """
    result = await db.execute(
        select(Consultation).where(Consultation.session_id == session_id)
    )
    consultation = result.scalar_one_or_none()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="咨询记录不存在")

    consultation_user_id = cast(int | None, getattr(consultation, "user_id", None))
    if consultation_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问该咨询记录")
    
    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.consultation_id == consultation.id)
        .order_by(ChatMessage.created_at)
    )
    messages = messages_result.scalars().all()
    
    consultation_created_at = cast(datetime | None, getattr(consultation, "created_at", None))
    export_data: dict[str, object] = {
        "title": cast(str | None, cast(object, consultation.title)),
        "session_id": cast(str, cast(object, consultation.session_id)),
        "created_at": consultation_created_at.isoformat() if consultation_created_at else None,
        "messages": [],
    }
    export_messages = cast(list[dict[str, object]], export_data["messages"])
    
    for msg in messages:
        msg_created_at = cast(datetime | None, getattr(msg, "created_at", None))
        msg_references = cast(str | None, getattr(msg, "references", None))
        msg_data: dict[str, object] = {
            "role": cast(str, cast(object, msg.role)),
            "content": cast(str, cast(object, msg.content)),
            "created_at": msg_created_at.isoformat() if msg_created_at else None,
        }
        if msg_references:
            try:
                parsed = cast(object, json.loads(msg_references))
                if isinstance(parsed, list):
                    msg_data["references"] = cast(object, parsed)
                elif isinstance(parsed, dict):
                    parsed_dict = cast(dict[str, object], parsed)
                    refs = parsed_dict.get("references")
                    if isinstance(refs, list):
                        msg_data["references"] = cast(object, refs)
                    else:
                        msg_data["references"] = []
                    meta_obj = parsed_dict.get("meta")
                    if isinstance(meta_obj, dict):
                        msg_data["references_meta"] = cast(object, meta_obj)
                else:
                    msg_data["references"] = []
            except json.JSONDecodeError:
                msg_data["references"] = []
        export_messages.append(msg_data)
    
    return export_data


@router.get("/consultations/{session_id}/report")
async def consultation_report(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    format: str = Query("pdf", max_length=10),
):
    fmt = str(format or "").strip().lower()
    if fmt != "pdf":
        raise HTTPException(status_code=400, detail="暂不支持该格式")

    export_data = await export_consultation(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )

    user_name = str(getattr(current_user, "nickname", None) or "") or str(
        getattr(current_user, "username", None) or "用户"
    )

    report = build_consultation_report_from_export_data(
        cast(dict[str, object], export_data),
        user_name=user_name,
    )

    try:
        pdf_bytes = generate_consultation_report_pdf(report)
    except RuntimeError as e:
        if str(e) == "PDF_DEPENDENCY_MISSING":
            raise HTTPException(status_code=501, detail="PDF 报告生成依赖未安装")
        raise

    safe_sid = "".join(
        ch
        if (ch.isascii() and (ch.isalnum() or ch in ("-", "_")))
        else "_"
        for ch in str(session_id or "")
    )
    ascii_filename = f"report_{safe_sid or 'session'}.pdf"
    utf8_filename = f"法律咨询报告_{session_id}.pdf"
    quoted_utf8 = urllib.parse.quote(utf8_filename, safe="")
    content_disposition = (
        f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{quoted_utf8}"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": content_disposition,
        },
    )


@router.post("/transcribe", response_model=TranscribeResponse)
@rate_limit(*RateLimitConfig.AI_CHAT, by_ip=True, by_user=False)
async def transcribe(
    request: Request,
    response: Response,
    file: Annotated[UploadFile, File(...)],
    segment_index: Annotated[int | None, Form()] = None,
    is_final: Annotated[bool | None, Form()] = None,
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Annotated[AsyncSession | None, Depends(get_db)] = None,
):
    started_at = float(time.time())
    request_id = str(getattr(request.state, "request_id", "") or "").strip() or uuid.uuid4().hex
    ai_metrics.record_request("transcribe")
    client_ip = get_client_ip(request)

    current_user_id: int | None = None
    if current_user is not None:
        try:
            identity = inspect(current_user).identity
            if identity:
                current_user_id = cast(int | None, identity[0])
        except Exception:
            current_user_id = None

    user_id_str = str(current_user_id) if current_user_id is not None else "guest"

    e2e_mock_enabled = bool(settings.debug) and str(request.headers.get("X-E2E-Mock-AI") or "").strip() == "1"
    if e2e_mock_enabled:
        try:
            _ = await file.read()
        except Exception:
            pass
        _ = response.headers.setdefault("X-Request-Id", request_id)
        return TranscribeResponse(
            text="这是一个E2E mock 的语音转写结果",
            segment_index=segment_index,
            is_final=is_final,
        )

    try:
        from ..services.sherpa_asr_service import sherpa_is_ready, sherpa_transcribe
        from ..services.voice_config_service import get_effective_voice_settings

        effective_settings = settings
        voice_cfg_overrides: dict[str, str] = {}
        voice_forced = False
        if db is not None:
            try:
                effective_settings, voice_cfg_overrides, voice_forced = await get_effective_voice_settings(db, settings)
            except Exception:
                effective_settings = settings
                voice_cfg_overrides = {}
                voice_forced = False

        if voice_forced:
            response.headers.setdefault("X-Voice-Config-Forced", "1")

        provider_raw = str(getattr(effective_settings, "voice_transcribe_provider", "auto") or "").strip().lower()
        provider = provider_raw if provider_raw in {"auto", "openai", "sherpa"} else "auto"

        transcribe_api_key = str(getattr(settings, "openai_transcribe_api_key", "") or "").strip()
        transcribe_base_url = str(getattr(settings, "openai_transcribe_base_url", "") or "").strip()
        default_api_key = str(settings.openai_api_key or "").strip()
        default_base_url = str(settings.openai_base_url or "").strip()

        api_key_to_use = transcribe_api_key or default_api_key
        base_url_to_use = transcribe_base_url or default_base_url

        sherpa_ready = False
        try:
            sherpa_ready = bool(sherpa_is_ready(effective_settings))
        except Exception:
            sherpa_ready = False

        openai_ready = bool(api_key_to_use)

        sherpa_enabled_flag = bool(getattr(effective_settings, "sherpa_asr_enabled", False))
        sherpa_mode_raw = str(getattr(effective_settings, "sherpa_asr_mode", "off") or "").strip().lower()
        sherpa_mode = sherpa_mode_raw if sherpa_mode_raw in {"off", "local", "remote"} else "off"

        diag_headers: dict[str, str] = {
            "X-AI-Voice-Provider-Configured": str(provider),
            "X-AI-Voice-OpenAI-Ready": "1" if openai_ready else "0",
            "X-AI-Voice-Sherpa-Enabled": "1" if sherpa_enabled_flag else "0",
            "X-AI-Voice-Sherpa-Mode": str(sherpa_mode),
            "X-AI-Voice-Sherpa-Ready": "1" if sherpa_ready else "0",
        }
        if voice_forced:
            diag_headers["X-Voice-Config-Forced"] = "1"

        if provider == "openai" and not openai_ready:
            error_code = ERROR_AI_NOT_CONFIGURED
            message = "AI服务未配置：请设置 OPENAI_TRANSCRIBE_API_KEY 或 OPENAI_API_KEY 后重试"
            ai_metrics.record_error(
                endpoint="transcribe",
                request_id=request_id,
                error_code=error_code,
                status_code=503,
                message=message,
            )
            critical_event_reporter.fire_and_forget(
                event="ai_not_configured",
                severity="warning",
                request_id=request_id,
                title="AI服务未配置",
                message=message,
                data={
                    "endpoint": "transcribe",
                    "user_id": user_id_str,
                    "ip": client_ip,
                },
                dedup_key="ai_not_configured",
            )
            _audit_event(
                "transcribe_error",
                {
                    "request_id": request_id,
                    "endpoint": "transcribe",
                    "user_id": user_id_str,
                    "ip": client_ip,
                    "status_code": 503,
                    "error_code": error_code,
                    "duration_ms": int((time.time() - started_at) * 1000),
                },
            )
            return _make_error_response(
                status_code=503,
                error_code=error_code,
                message=message,
                request_id=request_id,
                headers=diag_headers,
            )

        if provider == "sherpa" and not sherpa_ready:
            error_code = ERROR_AI_NOT_CONFIGURED
            message = (
                "AI服务未配置：Sherpa 未就绪。"
                " 请确认：1) SHERPA_ASR_ENABLED=1；2) SHERPA_ASR_MODE=local/remote（当前为 %s）；"
                " 3) remote 模式需配置 SHERPA_ASR_REMOTE_URL，local 模式需配置 tokens+model 路径。"
            ) % (sherpa_mode,)
            ai_metrics.record_error(
                endpoint="transcribe",
                request_id=request_id,
                error_code=error_code,
                status_code=503,
                message=message,
            )
            return _make_error_response(
                status_code=503,
                error_code=error_code,
                message=message,
                request_id=request_id,
                headers=diag_headers,
            )

        if provider == "auto" and not openai_ready and not sherpa_ready:
            error_code = ERROR_AI_NOT_CONFIGURED
            message = "AI服务未配置：请设置 OPENAI_TRANSCRIBE_API_KEY/OPENAI_API_KEY 或启用 Sherpa-ONNX 后重试"
            ai_metrics.record_error(
                endpoint="transcribe",
                request_id=request_id,
                error_code=error_code,
                status_code=503,
                message=message,
            )
            return _make_error_response(
                status_code=503,
                error_code=error_code,
                message=message,
                request_id=request_id,
                headers=diag_headers,
            )

        if current_user is None:
            await _enforce_guest_ai_quota(request)

        content = await file.read()
        if not content:
            return _make_error_response(
                status_code=400,
                error_code=ERROR_AI_BAD_REQUEST,
                message="音频文件为空",
                request_id=request_id,
            )

        if len(content) > 10 * 1024 * 1024:
            return _make_error_response(
                status_code=400,
                error_code=ERROR_AI_BAD_REQUEST,
                message="音频文件大小不能超过 10MB",
                request_id=request_id,
            )

        filename = str(file.filename or "audio").strip() or "audio"
        safe_filename = "".join(
            ch if ("0" <= ch <= "9") or ("A" <= ch <= "Z") or ("a" <= ch <= "z") or ch in ("-", "_", ".") else "_"
            for ch in filename
        ).strip("._")
        if not safe_filename:
            safe_filename = "audio"
        filename = safe_filename

        ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower().strip()
        allowed_ext = {"wav", "mp3", "m4a", "ogg", "webm", "opus", "mp4", "aac", "mpeg"}
        if ext and ext not in allowed_ext:
            return _make_error_response(
                status_code=400,
                error_code=ERROR_AI_BAD_REQUEST,
                message="音频格式不支持",
                request_id=request_id,
            )

        openai_error: Exception | None = None
        if provider in {"auto", "openai"} and openai_ready:
            try:
                def _transcribe_sync() -> tuple[str, str | None, bool]:
                    from openai import OpenAI

                    primary_base = str(base_url_to_use or "").strip() or "https://api.openai.com/v1"
                    official_base = "https://api.openai.com/v1"
                    bases: list[str] = [primary_base]
                    allow_official_fallback = bool(transcribe_api_key) and primary_base.rstrip("/") != official_base
                    if allow_official_fallback:
                        bases.append(official_base)

                    last_err: Exception | None = None

                    used_base: str | None = None
                    used_fallback: bool = False

                    for base_url in bases:
                        try:
                            used_base = base_url
                            used_fallback = base_url.rstrip("/") == official_base and primary_base.rstrip("/") != official_base
                            client = OpenAI(api_key=api_key_to_use, base_url=base_url)
                            buf = io.BytesIO(content)
                            try:
                                setattr(buf, "name", filename)
                            except Exception:
                                pass
                            res = client.audio.transcriptions.create(model="whisper-1", file=buf)
                            return str(getattr(res, "text", "") or ""), used_base, used_fallback
                        except Exception as e:
                            last_err = e

                    if last_err is not None:
                        raise last_err
                    return "", used_base, used_fallback

                text, used_base, used_fallback = await asyncio.to_thread(_transcribe_sync)
                response.headers.setdefault("X-AI-Transcribe-Provider", "openai")
                if used_base:
                    response.headers.setdefault("X-AI-Transcribe-Base-Url", str(used_base))
                    response.headers.setdefault("X-AI-Transcribe-Fallback", "1" if used_fallback else "0")
                if not str(text).strip():
                    response.headers["X-Request-Id"] = request_id
                    return TranscribeResponse(text="", segment_index=segment_index, is_final=is_final)

                _audit_event(
                    "transcribe_ok",
                    {
                        "request_id": request_id,
                        "endpoint": "transcribe",
                        "user_id": user_id_str,
                        "ip": client_ip,
                        "duration_ms": int((time.time() - started_at) * 1000),
                        "text_len": len(str(text)),
                    },
                )

                response.headers["X-Request-Id"] = request_id
                return TranscribeResponse(
                    text=str(text),
                    segment_index=segment_index,
                    is_final=is_final,
                )
            except Exception as e:
                openai_error = e
                if provider == "openai":
                    raise

        if provider in {"auto", "sherpa"} and sherpa_ready:
            try:
                text, sherpa_kind, sherpa_url = await sherpa_transcribe(
                    content=content,
                    filename=filename,
                    settings=effective_settings,
                    segment_index=segment_index,
                    is_final=is_final,
                )
                response.headers.setdefault("X-AI-Transcribe-Provider", sherpa_kind)
                if sherpa_url:
                    response.headers.setdefault("X-AI-Transcribe-Remote-Url", str(sherpa_url))
                if not str(text).strip():
                    response.headers["X-Request-Id"] = request_id
                    return TranscribeResponse(text="", segment_index=segment_index, is_final=is_final)

                _audit_event(
                    "transcribe_ok",
                    {
                        "request_id": request_id,
                        "endpoint": "transcribe",
                        "user_id": user_id_str,
                        "ip": client_ip,
                        "duration_ms": int((time.time() - started_at) * 1000),
                        "text_len": len(str(text)),
                    },
                )

                response.headers["X-Request-Id"] = request_id
                return TranscribeResponse(
                    text=str(text),
                    segment_index=segment_index,
                    is_final=is_final,
                )
            except Exception:
                if openai_error is not None:
                    raise openai_error
                raise

        if openai_error is not None:
            if provider == "auto" and not sherpa_ready:
                msg = (
                    "语音转写失败：OpenAI Whisper 调用失败，且 Sherpa 未就绪，无法回退。"
                    " 请到管理后台【系统设置 -> AI 咨询 -> 语音管理】开启强制模式，"
                    "并将 SHERPA_ASR_MODE 设置为 local/remote（不要是 off），"
                    "再配置 remote_url 或本地模型路径；或者改用 provider=openai 并确保转写网关支持 Whisper。"
                )
                return _make_error_response(
                    status_code=503,
                    error_code=ERROR_AI_UNAVAILABLE,
                    message=msg,
                    request_id=request_id,
                    headers=diag_headers,
                )
            raise openai_error

        error_code = ERROR_AI_UNAVAILABLE
        message = "AI服务不可用：请稍后再试"
        return _make_error_response(
            status_code=503,
            error_code=error_code,
            message=message,
            request_id=request_id,
        )
    except HTTPException as e:
        sc = int(getattr(e, "status_code", 500) or 500)
        error_code = _error_code_for_http(sc)
        message = _extract_message(getattr(e, "detail", ""))
        raw_headers = getattr(e, "headers", None)
        out_headers: dict[str, str] | None = None
        if isinstance(raw_headers, dict) and raw_headers:
            out_headers = {str(k): str(v) for k, v in raw_headers.items()}
        ai_metrics.record_error(
            endpoint="transcribe",
            request_id=request_id,
            error_code=error_code,
            status_code=sc,
            message=message or "transcribe_http_error",
        )
        return _make_error_response(
            status_code=sc,
            error_code=error_code,
            message=message or "语音转写失败",
            request_id=request_id,
            headers=out_headers,
        )
    except Exception as e:
        sc = int(getattr(getattr(e, "status_code", None), "__int__", lambda: 0)() or 0)
        if not sc:
            try:
                sc = int(getattr(getattr(e, "response", None), "status_code", 0) or 0)
            except Exception:
                sc = 0
        if sc <= 0:
            sc = 500
        error_code = _error_code_for_http(sc)
        ai_metrics.record_error(
            endpoint="transcribe",
            request_id=request_id,
            error_code=error_code,
            status_code=sc,
            message="transcribe_failed",
        )
        logger.exception("ai_transcribe_failed request_id=%s", request_id)
        critical_event_reporter.fire_and_forget(
            event="ai_transcribe_failed",
            severity="error",
            request_id=request_id,
            title="语音转写失败",
            message="transcribe_failed",
            data={
                "endpoint": "transcribe",
            },
            dedup_key="ai_transcribe_failed",
        )
        msg = "语音转写失败：请确认 OPENAI_TRANSCRIBE_BASE_URL 指向支持 Whisper 的服务，且 OPENAI_TRANSCRIBE_API_KEY 有效"
        if sc == 401:
            msg = "AI鉴权失败：TRANSCRIBE_API_KEY 无效或与 TRANSCRIBE_BASE_URL 不匹配"
        elif sc == 403:
            msg = "AI服务拒绝访问：权限不足或账号未开通语音转写能力"
        elif sc == 429:
            msg = "AI服务限流：请求过于频繁，请稍后再试"
        elif sc == 503:
            msg = "AI服务不可用：请稍后再试"
        return _make_error_response(
            status_code=sc,
            error_code=error_code,
            message=msg,
            request_id=request_id,
        )


@router.post("/files/analyze", response_model=FileAnalyzeResponse)
@rate_limit(*RateLimitConfig.AI_CHAT, by_ip=True, by_user=False)
async def analyze_file(
    request: Request,
    response: Response,
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
):
    started_at = float(time.time())
    request_id = str(getattr(request.state, "request_id", "") or "").strip() or uuid.uuid4().hex
    ai_metrics.record_request("file_analyze")
    client_ip = get_client_ip(request)

    current_user_id: int | None = None
    if current_user is not None:
        try:
            identity = inspect(current_user).identity
            if identity:
                current_user_id = cast(int | None, identity[0])
        except Exception:
            current_user_id = None

    user_id_str = str(current_user_id) if current_user_id is not None else "guest"

    e2e_mock_enabled = bool(settings.debug) and str(request.headers.get("X-E2E-Mock-AI") or "").strip() == "1"
    if e2e_mock_enabled:
        try:
            _ = await file.read()
        except Exception:
            pass
        _ = response.headers.setdefault("X-Request-Id", request_id)
        return FileAnalyzeResponse(
            filename=str(file.filename or "attachment"),
            content_type=str(file.content_type or "") or None,
            text_chars=12,
            text_preview="这是一个E2E mock 的文件内容",
            summary="这是一个E2E mock 的文件分析结果",
        )

    if not settings.openai_api_key:
        error_code = ERROR_AI_NOT_CONFIGURED
        message = "AI服务未配置：请设置 OPENAI_API_KEY 后重试"
        ai_metrics.record_error(
            endpoint="file_analyze",
            request_id=request_id,
            error_code=error_code,
            status_code=503,
            message=message,
        )
        critical_event_reporter.fire_and_forget(
            event="ai_not_configured",
            severity="warning",
            request_id=request_id,
            title="AI服务未配置",
            message=message,
            data={
                "endpoint": "file_analyze",
                "user_id": user_id_str,
                "ip": client_ip,
            },
            dedup_key="ai_not_configured",
        )
        _audit_event(
            "file_analyze_error",
            {
                "request_id": request_id,
                "endpoint": "file_analyze",
                "user_id": user_id_str,
                "ip": client_ip,
                "status_code": 503,
                "error_code": error_code,
                "duration_ms": int((time.time() - started_at) * 1000),
            },
        )
        return _make_error_response(
            status_code=503,
            error_code=error_code,
            message=message,
            request_id=request_id,
        )

    if current_user is None:
        await _enforce_guest_ai_quota(request)

    try:
        content = await file.read()
    except Exception:
        return _make_error_response(
            status_code=400,
            error_code=ERROR_AI_BAD_REQUEST,
            message="读取文件失败",
            request_id=request_id,
        )

    if not content:
        return _make_error_response(
            status_code=400,
            error_code=ERROR_AI_BAD_REQUEST,
            message="文件为空",
            request_id=request_id,
        )

    if len(content) > 10 * 1024 * 1024:
        return _make_error_response(
            status_code=400,
            error_code=ERROR_AI_BAD_REQUEST,
            message="文件大小不能超过 10MB",
            request_id=request_id,
        )

    filename = str(file.filename or "attachment").strip() or "attachment"
    content_type = str(file.content_type or "").strip() or None
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
            import os
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
            error_code=ERROR_AI_BAD_REQUEST,
            message="不支持的文件类型",
            request_id=request_id,
        )
    except Exception:
        return _make_error_response(
            status_code=500,
            error_code=ERROR_AI_INTERNAL_ERROR,
            message="文件解析失败",
            request_id=request_id,
        )

    extracted_norm = str(extracted or "").strip()
    if not extracted_norm:
        return _make_error_response(
            status_code=400,
            error_code=ERROR_AI_BAD_REQUEST,
            message="无法从文件中提取文本",
            request_id=request_id,
        )

    max_chars = 200_000
    if len(extracted_norm) > max_chars:
        extracted_norm = extracted_norm[:max_chars]

    preview = extracted_norm[:4000]

    extracted_for_ai = sanitize_pii(extracted_norm)

    def _summarize_sync() -> str:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        res = client.chat.completions.create(
            model=str(settings.ai_model or "").strip() or "gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "你是法律文书/材料分析助手。请用简洁中文输出：1) 摘要 2) 关键信息要点 3) 风险与建议。",
                },
                {
                    "role": "user",
                    "content": f"请分析以下文件内容：\n\n{extracted_for_ai}",
                },
            ],
            temperature=0.2,
            max_tokens=800,
        )
        choices = getattr(res, "choices", None)
        if not choices:
            return ""
        msg = getattr(choices[0], "message", None)
        return str(getattr(msg, "content", "") or "")

    try:
        summary = await asyncio.to_thread(_summarize_sync)
    except Exception:
        ai_metrics.record_error(
            endpoint="file_analyze",
            request_id=request_id,
            error_code=ERROR_AI_INTERNAL_ERROR,
            status_code=500,
            message="summarize_failed",
        )
        critical_event_reporter.fire_and_forget(
            event="ai_file_analyze_failed",
            severity="error",
            request_id=request_id,
            title="文件分析失败",
            message="summarize_failed",
            data={
                "endpoint": "file_analyze",
            },
            dedup_key="ai_file_analyze_failed",
        )
        return _make_error_response(
            status_code=500,
            error_code=ERROR_AI_INTERNAL_ERROR,
            message="文件分析失败",
            request_id=request_id,
        )

    summary_norm = str(summary or "").strip()
    if not summary_norm:
        return _make_error_response(
            status_code=500,
            error_code=ERROR_AI_INTERNAL_ERROR,
            message="文件分析失败",
            request_id=request_id,
        )

    _audit_event(
        "file_analyze_ok",
        {
            "request_id": request_id,
            "endpoint": "file_analyze",
            "user_id": user_id_str,
            "ip": client_ip,
            "duration_ms": int((time.time() - started_at) * 1000),
            "text_len": len(extracted_norm),
        },
    )

    response.headers["X-Request-Id"] = request_id
    return FileAnalyzeResponse(
        filename=filename,
        content_type=content_type,
        text_chars=len(extracted_norm),
        text_preview=preview,
        summary=summary_norm,
    )


@router.post("/quick-replies", response_model=QuickRepliesResponse)
@rate_limit(*RateLimitConfig.AI_CHAT, by_ip=True, by_user=False)
async def quick_replies(
    payload: QuickRepliesRequest,
    request: Request,
):
    _ = request
    user_text = str(payload.user_message or "")
    answer_text = str(payload.assistant_answer or "")
    haystack = (user_text + "\n" + answer_text).lower()

    replies: list[str] = []

    refs = payload.references or []
    if refs:
        ref0 = refs[0]
        law_name = str(getattr(ref0, "law_name", "") or "").strip()
        article = str(getattr(ref0, "article", "") or "").strip()
        if law_name and article:
            replies.append(f"《{law_name}》{article}的适用范围是什么？")

    if "离婚" in haystack or "婚姻" in haystack:
        replies.extend([
            "双方是否有子女？抚养权/抚养费怎么安排？",
            "有哪些共同财产与共同债务？请列一下金额与证据。",
            "是否有家暴/出轨/分居等情形？对应证据有哪些？",
        ])
    elif "劳动" in haystack or "工资" in haystack or "社保" in haystack:
        replies.extend([
            "是否签订劳动合同？入职时间、岗位、工资是多少？",
            "有没有考勤、聊天记录、工资条或转账记录？",
            "你希望的诉求是补发工资、赔偿还是恢复劳动关系？",
        ])
    elif "合同" in haystack or "违约" in haystack or "定金" in haystack:
        replies.extend([
            "合同是否书面？关键条款（金额/期限/违约责任）是什么？",
            "对方的违约行为具体是什么？造成了哪些损失？",
            "你现在掌握的证据有哪些（合同、付款凭证、聊天记录）？",
        ])
    elif "借" in haystack or "借款" in haystack or "欠" in haystack:
        replies.extend([
            "是否有借条/转账记录/聊天记录能证明借款关系？",
            "约定的还款期限与利息是多少？是否逾期？",
            "对方目前是否有可执行财产线索？",
        ])
    else:
        replies.extend([
            "需要准备哪些证据？",
            "请给出可操作的处理步骤（先协商/调解/仲裁/起诉）。",
            "这个问题的诉讼/仲裁时效一般是多久？",
        ])

    seen: set[str] = set()
    out: list[str] = []
    for r in replies:
        s = str(r).strip()
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= 6:
            break

    return QuickRepliesResponse(replies=out)


@router.post("/messages/rate", response_model=RatingResponse)
async def rate_message(
    request: RatingRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    评价AI回复
    
    - **message_id**: 消息ID（必须是assistant角色的消息）
    - **rating**: 评分 1=差评, 2=一般, 3=好评
    - **feedback**: 反馈内容（可选）
    """
    result = await db.execute(
        select(ChatMessage, Consultation.user_id)
        .join(Consultation, ChatMessage.consultation_id == Consultation.id)
        .where(ChatMessage.id == request.message_id)
    )
    row = cast(tuple[ChatMessage, int | None] | None, result.first())
    if row is None:
        message = None
        owner_user_id = None
    else:
        message, owner_user_id = row
    
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")

    if owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限评价该消息")
    
    message_role = cast(str, cast(object, getattr(message, "role", "")))
    if message_role != "assistant":
        raise HTTPException(status_code=400, detail="只能评价AI回复")
    
    setattr(message, "rating", request.rating)
    setattr(message, "feedback", request.feedback)
    await db.commit()
    
    rating_text = {1: "差评", 2: "一般", 3: "好评"}.get(request.rating, "")
    return RatingResponse(message=f"感谢您的{rating_text}反馈！")
