"""AI助手API路由"""
import asyncio
import json
import time
from typing import Annotated, cast
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..database import get_db
from ..models.consultation import Consultation, ChatMessage
from ..models.user import User
from ..config import get_settings
from ..schemas.ai import (
    ChatRequest, 
    ChatResponse, 
    ConsultationResponse,
    ConsultationListItem,
    MessageResponse,
    RatingRequest,
    RatingResponse
)
from ..utils.deps import get_current_user, get_current_user_optional
from ..utils.rate_limiter import rate_limit, RateLimitConfig, rate_limiter, get_client_ip

router = APIRouter(prefix="/ai", tags=["AI法律助手"])

settings = get_settings()

GUEST_AI_LIMIT = 5
GUEST_AI_WINDOW_SECONDS = 60 * 60 * 24

SEED_HISTORY_MAX_MESSAGES = 20


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
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
):
    """
    与AI法律助手对话
    
    - **message**: 用户消息内容
    - **session_id**: 会话ID（可选，为空则创建新会话）
    - 如果已登录，咨询记录将绑定到用户账号
    """
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="AI服务未配置：请设置 OPENAI_API_KEY 后重试"
        )

    if current_user is None:
        _enforce_guest_ai_quota(request)

    seed_history: list[dict[str, str]] | None = None
    consultation: Consultation | None = None
    if payload.session_id:
        consultation, seed_history = await _load_seed_history(db, payload.session_id, current_user=current_user)

    assistant = _try_get_ai_assistant()
    if assistant is None:
        raise HTTPException(status_code=503, detail="AI服务不可用：缺少可选依赖或配置异常")

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
            user_id=current_user.id if current_user else None
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
        content=payload.message
    )
    db.add(user_message)
    
    refs_json = json.dumps([ref.model_dump() for ref in references], ensure_ascii=False)
    ai_message = ChatMessage(
        consultation_id=consultation.id,
        role="assistant",
        content=answer,
        references=refs_json
    )
    db.add(ai_message)

    await db.flush()
    assistant_message_id = cast(int | None, getattr(ai_message, "id", None))
    
    await db.commit()
    
    return ChatResponse(
        session_id=session_id,
        answer=answer,
        references=references,
        assistant_message_id=assistant_message_id,
        created_at=datetime.now()
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
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="AI服务未配置：请设置 OPENAI_API_KEY 后重试"
        )

    if current_user is None:
        _enforce_guest_ai_quota(request)

    seed_history: list[dict[str, str]] | None = None
    if payload.session_id:
        _, seed_history = await _load_seed_history(db, payload.session_id, current_user=current_user)

    assistant = _try_get_ai_assistant()
    if assistant is None:
        raise HTTPException(status_code=503, detail="AI服务不可用：缺少可选依赖或配置异常")
    
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
                    done_payload = cast(dict[str, object], data)
                    continue

                yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            raise
        except Exception:
            persist_error = "stream_failed"

        if session_id is None:
            return

        try:
            result = await db.execute(
                select(Consultation).where(Consultation.session_id == session_id)
            )
            consultation = result.scalar_one_or_none()

            if consultation is not None:
                consultation_user_id = cast(int | None, getattr(consultation, "user_id", None))
                if consultation_user_id is not None:
                    if current_user is None or consultation_user_id != current_user.id:
                        return

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

        yield f"event: done\ndata: {json.dumps(final_done, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "identity",
        }
    )


@router.get("/consultations", response_model=list[ConsultationListItem])
async def list_consultations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
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
    
    result = await db.execute(
        select(
            Consultation,
            func.coalesce(subquery.c.message_count, 0).label('message_count')
        )
        .outerjoin(subquery, Consultation.id == subquery.c.consultation_id)
        .where(Consultation.user_id == current_user.id)
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
