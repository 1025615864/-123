from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.feedback import FeedbackTicket
from ..models.user import User
from ..schemas.feedback import (
    AdminFeedbackTicketUpdate,
    FeedbackTicketCreate,
    FeedbackTicketItem,
    FeedbackTicketListResponse,
)
from ..utils.deps import get_current_user, require_admin

router = APIRouter(prefix="/feedback", tags=["客服反馈"])


ALLOWED_TICKET_STATUS = {"open", "processing", "closed"}


@router.post("", response_model=FeedbackTicketItem, summary="提交反馈工单")
async def create_ticket(
    data: FeedbackTicketCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ticket = FeedbackTicket(
        user_id=int(current_user.id),
        subject=str(data.subject).strip(),
        content=str(data.content).strip(),
        status="open",
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return FeedbackTicketItem.model_validate(ticket)


@router.get("", response_model=FeedbackTicketListResponse, summary="获取我的反馈工单")
async def list_my_tickets(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    base = select(FeedbackTicket).where(FeedbackTicket.user_id == int(current_user.id))
    count_q = select(func.count(FeedbackTicket.id)).where(
        FeedbackTicket.user_id == int(current_user.id)
    )

    res_total = await db.execute(count_q)
    total = int(res_total.scalar() or 0)

    res = await db.execute(
        base.order_by(FeedbackTicket.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = res.scalars().all()

    return FeedbackTicketListResponse(
        items=[FeedbackTicketItem.model_validate(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/admin/tickets", response_model=FeedbackTicketListResponse, summary="管理员-获取反馈工单列表")
async def admin_list_tickets(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    keyword: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    _ = current_user

    q = select(FeedbackTicket)
    count_q = select(func.count(FeedbackTicket.id))

    if status_filter:
        q = q.where(FeedbackTicket.status == str(status_filter).strip())
        count_q = count_q.where(FeedbackTicket.status == str(status_filter).strip())

    if keyword:
        kw = f"%{keyword.strip()}%"
        q = q.where(
            (FeedbackTicket.subject.ilike(kw))
            | (FeedbackTicket.content.ilike(kw))
            | (FeedbackTicket.admin_reply.ilike(kw))
        )
        count_q = count_q.where(
            (FeedbackTicket.subject.ilike(kw))
            | (FeedbackTicket.content.ilike(kw))
            | (FeedbackTicket.admin_reply.ilike(kw))
        )

    total_res = await db.execute(count_q)
    total = int(total_res.scalar() or 0)

    res = await db.execute(
        q.order_by(FeedbackTicket.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = res.scalars().all()

    return FeedbackTicketListResponse(
        items=[FeedbackTicketItem.model_validate(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put(
    "/admin/tickets/{ticket_id}",
    response_model=FeedbackTicketItem,
    summary="管理员-更新反馈工单（回复/状态）",
)
async def admin_update_ticket(
    ticket_id: int,
    data: AdminFeedbackTicketUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    res = await db.execute(select(FeedbackTicket).where(FeedbackTicket.id == int(ticket_id)))
    ticket = res.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")

    if data.status is not None:
        next_status = str(data.status).strip()
        if next_status not in ALLOWED_TICKET_STATUS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效状态：{next_status}",
            )
        ticket.status = next_status

    if data.admin_reply is not None:
        ticket.admin_reply = str(data.admin_reply).strip() or None
        ticket.admin_id = int(current_user.id)

    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return FeedbackTicketItem.model_validate(ticket)
