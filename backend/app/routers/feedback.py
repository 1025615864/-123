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
    AdminFeedbackTicketStatsResponse,
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


@router.get(
    "/admin/tickets/stats",
    response_model=AdminFeedbackTicketStatsResponse,
    summary="管理员-反馈工单统计",
)
async def admin_ticket_stats(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = current_user

    res = await db.execute(select(FeedbackTicket.status, func.count(FeedbackTicket.id)).group_by(FeedbackTicket.status))
    rows = res.all()
    by_status: dict[str, int] = {}
    for s, c in rows:
        by_status[str(s or "").strip()] = int(c or 0)

    total = sum(by_status.values())
    unassigned_res = await db.execute(
        select(func.count(FeedbackTicket.id)).where(FeedbackTicket.admin_id.is_(None))
    )
    unassigned = int(unassigned_res.scalar() or 0)

    return AdminFeedbackTicketStatsResponse(
        total=int(total),
        open=int(by_status.get("open", 0)),
        processing=int(by_status.get("processing", 0)),
        closed=int(by_status.get("closed", 0)),
        unassigned=int(unassigned),
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

    fields_set = getattr(data, "model_fields_set", set())

    if ("status" in fields_set) and (data.status is not None):
        next_status = str(data.status).strip()
        if next_status not in ALLOWED_TICKET_STATUS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效状态：{next_status}",
            )
        ticket.status = next_status

    if "admin_reply" in fields_set:
        next_reply = str(data.admin_reply or "").strip() if data.admin_reply is not None else ""
        ticket.admin_reply = next_reply or None
        if next_reply:
            ticket.admin_id = int(current_user.id)

    if "admin_id" in fields_set:
        if data.admin_id is None:
            ticket.admin_id = None
        else:
            if int(data.admin_id) != int(current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="目前仅支持指派给自己",
                )
            ticket.admin_id = int(current_user.id)

    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return FeedbackTicketItem.model_validate(ticket)
