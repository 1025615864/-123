from datetime import datetime, timezone
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.calendar import CalendarReminder
from ..models.user import User
from ..schemas.calendar import (
    CalendarReminderCreate,
    CalendarReminderListResponse,
    CalendarReminderResponse,
    CalendarReminderUpdate,
)
from ..utils.deps import get_current_user

router = APIRouter(prefix="/calendar", tags=["法律日历"])


@router.post("/reminders", response_model=CalendarReminderResponse)
async def create_reminder(
    payload: CalendarReminderCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    reminder = CalendarReminder(
        user_id=current_user.id,
        title=str(payload.title),
        note=payload.note,
        due_at=payload.due_at,
        remind_at=payload.remind_at,
        is_done=False,
        done_at=None,
    )
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    return CalendarReminderResponse.model_validate(reminder)


@router.get("/reminders", response_model=CalendarReminderListResponse)
async def list_reminders(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    done: bool | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
):
    query = select(CalendarReminder).where(CalendarReminder.user_id == current_user.id)
    if done is not None:
        query = query.where(CalendarReminder.is_done == bool(done))
    if from_at is not None:
        query = query.where(CalendarReminder.due_at >= from_at)
    if to_at is not None:
        query = query.where(CalendarReminder.due_at <= to_at)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = int(total_result.scalar() or 0)

    query = query.order_by(CalendarReminder.due_at.asc(), CalendarReminder.id.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(query)
    items = cast(list[CalendarReminder], res.scalars().all())

    return CalendarReminderListResponse(
        items=[CalendarReminderResponse.model_validate(x) for x in items],
        total=total,
    )


async def _get_owned_reminder(db: AsyncSession, reminder_id: int, user_id: int) -> CalendarReminder | None:
    res = await db.execute(
        select(CalendarReminder).where(
            CalendarReminder.id == int(reminder_id),
            CalendarReminder.user_id == int(user_id),
        )
    )
    return res.scalar_one_or_none()


@router.put("/reminders/{reminder_id}", response_model=CalendarReminderResponse)
async def update_reminder(
    reminder_id: int,
    payload: CalendarReminderUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    reminder = await _get_owned_reminder(db, reminder_id, current_user.id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提醒不存在")

    if payload.title is not None:
        reminder.title = str(payload.title)
    if payload.note is not None:
        reminder.note = payload.note
    if payload.due_at is not None:
        reminder.due_at = payload.due_at
    if payload.remind_at is not None:
        reminder.remind_at = payload.remind_at

    if payload.is_done is not None:
        next_done = bool(payload.is_done)
        reminder.is_done = next_done
        if next_done:
            if reminder.done_at is None:
                reminder.done_at = datetime.now(timezone.utc)
        else:
            reminder.done_at = None

    await db.commit()
    await db.refresh(reminder)
    return CalendarReminderResponse.model_validate(reminder)


@router.delete("/reminders/{reminder_id}")
async def delete_reminder(
    reminder_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    reminder = await _get_owned_reminder(db, reminder_id, current_user.id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提醒不存在")

    await db.delete(reminder)
    await db.commit()
    return {"message": "删除成功"}
