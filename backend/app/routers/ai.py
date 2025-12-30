"""AI助手API路由"""
import uuid
import asyncio
import io
import tempfile
import json
import logging
import time
import urllib.parse
from typing import Annotated, cast
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, File, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, inspect, exists, or_

from ..database import get_db
from ..models.consultation import Consultation, ChatMessage
from ..models.user import User
from ..config import get_settings
from ..services.ai_metrics import ai_metrics
from ..services.report_generator import (
    build_consultation_report_from_export_data,
    generate_consultation_report_pdf,
)
from ..schemas.ai import (
    ChatRequest, 
    ChatResponse, 
    ConsultationResponse,
    ConsultationListItem,
    MessageResponse,
    RatingRequest,
    RatingResponse,
    QuickRepliesRequest,
    QuickRepliesResponse,
    TranscribeResponse,
    FileAnalyzeResponse,
)
from ..utils.deps import get_current_user, get_current_user_optional
from ..utils.rate_limiter import rate_limit, RateLimitConfig, rate_limiter, get_client_ip

router = APIRouter(prefix="/ai", tags=["AI法律助手"])

settings = get_settings()

logger = logging.getLogger(__name__)

GUEST_AI_LIMIT = 5
GUEST_AI_WINDOW_SECONDS = 60 * 60 * 24

SEED_HISTORY_MAX_MESSAGES = 20

ERROR_AI_NOT_CONFIGURED = "AI_NOT_CONFIGURED"
ERROR_AI_UNAVAILABLE = "AI_UNAVAILABLE"
ERROR_AI_RATE_LIMITED = "AI_RATE_LIMITED"
ERROR_AI_FORBIDDEN = "AI_FORBIDDEN"
ERROR_AI_UNAUTHORIZED = "AI_UNAUTHORIZED"
ERROR_AI_BAD_REQUEST = "AI_BAD_REQUEST"
ERROR_AI_INTERNAL_ERROR = "AI_INTERNAL_ERROR"


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


def _enforce_guest_ai_quota(request: Request) -> None:
    key = f"ai:guest:{get_client_ip(request)}"
    allowed, remaining = rate_limiter.is_allowed(key, GUEST_AI_LIMIT, GUEST_AI_WINDOW_SECONDS)
    if allowed:
        return

    wait_time = rate_limiter.get_wait_time(key, GUEST_AI_WINDOW_SECONDS)
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="游客模式 24 小时内仅可试用 5 次，请登录后继续",
        headers={
            "X-RateLimit-Limit": str(GUEST_AI_LIMIT),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(int(time.time() + wait_time)),
            "Retry-After": str(int(wait_time)),
        },
    )


def _try_get_ai_assistant():
    try:
        from ..services.ai_assistant import get_ai_assistant

        return get_ai_assistant()
    except Exception:
        return None


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
    request_id = uuid.uuid4().hex
    response.headers["X-Request-Id"] = request_id
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
            _enforce_guest_ai_quota(request)

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
            return _make_error_response(
                status_code=503,
                error_code=error_code,
                message=message,
                request_id=request_id,
            )

        session_id, answer, references = await assistant.chat(
            message=payload.message,
            session_id=payload.session_id,
            initial_history=seed_history,
        )

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
        
        refs_json = json.dumps([ref.model_dump() for ref in references], ensure_ascii=False)
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
                "duration_ms": int((time.time() - started_at) * 1000),
            },
        )
        
        return ChatResponse(
            session_id=session_id,
            answer=answer,
            references=references,
            assistant_message_id=assistant_message_id,
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
    request_id = uuid.uuid4().hex
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
            _enforce_guest_ai_quota(request)

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
            return _make_error_response(
                status_code=503,
                error_code=error_code,
                message=message,
                request_id=request_id,
            )

        async def event_generator():
            session_id: str | None = None
            references_payload: list[dict[str, object]] | None = None
            answer_parts: list[str] = []
            done_payload: dict[str, object] | None = None

            assistant_message_id: int | None = None
            persist_error: str | None = None

            try:
                async for event_type, data in assistant.chat_stream(
                    message=payload.message,
                    session_id=payload.session_id,
                    initial_history=seed_history,
                ):
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

                    refs_json = json.dumps(references_payload or [], ensure_ascii=False)
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
        sc = int(e.status_code)
        error_code = _error_code_for_http(sc)
        message = _extract_message(getattr(e, "detail", ""))
        ai_metrics.record_error(
            endpoint="chat_stream",
            request_id=request_id,
            error_code=error_code,
            status_code=sc,
            message=message,
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
                msg_data["references"] = cast(object, json.loads(msg_references))
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
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
):
    started_at = float(time.time())
    request_id = uuid.uuid4().hex
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
        response.headers["X-Request-Id"] = request_id
        return TranscribeResponse(text="这是一个E2E mock 的语音转写结果")

    try:
        if not settings.openai_api_key:
            error_code = ERROR_AI_NOT_CONFIGURED
            message = "AI服务未配置：请设置 OPENAI_API_KEY 后重试"
            ai_metrics.record_error(
                endpoint="transcribe",
                request_id=request_id,
                error_code=error_code,
                status_code=503,
                message=message,
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
            )

        if current_user is None:
            _enforce_guest_ai_quota(request)

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

        def _transcribe_sync() -> str:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
            buf = io.BytesIO(content)
            try:
                setattr(buf, "name", filename)
            except Exception:
                pass
            res = client.audio.transcriptions.create(model="whisper-1", file=buf)
            return str(getattr(res, "text", "") or "")

        text = await asyncio.to_thread(_transcribe_sync)
        if not str(text).strip():
            return _make_error_response(
                status_code=500,
                error_code=ERROR_AI_INTERNAL_ERROR,
                message="语音转写失败",
                request_id=request_id,
            )

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
        return TranscribeResponse(text=str(text))
    except HTTPException:
        raise
    except Exception:
        ai_metrics.record_error(
            endpoint="transcribe",
            request_id=request_id,
            error_code=ERROR_AI_INTERNAL_ERROR,
            status_code=500,
            message="transcribe_failed",
        )
        return _make_error_response(
            status_code=500,
            error_code=ERROR_AI_INTERNAL_ERROR,
            message="语音转写失败",
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
    request_id = uuid.uuid4().hex
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
        response.headers["X-Request-Id"] = request_id
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
        _enforce_guest_ai_quota(request)

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
                    "content": f"请分析以下文件内容：\n\n{extracted_norm}",
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
