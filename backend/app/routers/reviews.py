from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.consultation import Consultation
from ..models.consultation_review import ConsultationReviewTask, ConsultationReviewVersion
from ..models.payment import PaymentOrder, PaymentStatus
from ..models.user import User
from ..services.settlement_service import settlement_service
from ..schemas.consultation_review import (
    ConsultationReviewTaskDetailResponse,
    ConsultationReviewTaskItem,
    ConsultationReviewVersionItem,
    LawyerReviewSubmitRequest,
    LawyerReviewTaskListResponse,
)
from ..utils.deps import get_current_user, require_lawyer_verified

router = APIRouter(prefix="/reviews", tags=["律师复核"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_int(value: object | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except Exception:
            return None
    return None


async def _build_latest_versions(db: AsyncSession, task_ids: list[int]) -> dict[int, ConsultationReviewVersionItem]:
    if not task_ids:
        return {}

    res = await db.execute(
        select(ConsultationReviewVersion)
        .where(ConsultationReviewVersion.task_id.in_(task_ids))
        .order_by(
            ConsultationReviewVersion.task_id.asc(),
            ConsultationReviewVersion.created_at.desc(),
            ConsultationReviewVersion.id.desc(),
        )
    )
    rows = res.scalars().all()

    latest: dict[int, ConsultationReviewVersionItem] = {}
    for v in rows:
        tid = int(getattr(v, "task_id", 0) or 0)
        if tid <= 0 or tid in latest:
            continue
        latest[tid] = ConsultationReviewVersionItem.model_validate(v)
    return latest


@router.get(
    "/consultations/{consultation_id}",
    response_model=ConsultationReviewTaskDetailResponse,
    summary="用户-查询某次AI咨询的复核任务",
)
async def get_review_task_for_consultation(
    consultation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    res = await db.execute(
        select(Consultation).where(Consultation.id == int(consultation_id))
    )
    consultation = res.scalar_one_or_none()
    if consultation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="咨询不存在")

    owner_user_id = _as_int(getattr(consultation, "user_id", None))
    if owner_user_id != int(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该咨询")

    task_res = await db.execute(
        select(ConsultationReviewTask)
        .where(
            ConsultationReviewTask.consultation_id == int(consultation_id),
            ConsultationReviewTask.user_id == int(current_user.id),
        )
        .order_by(ConsultationReviewTask.created_at.desc(), ConsultationReviewTask.id.desc())
        .limit(1)
    )
    task = task_res.scalar_one_or_none()
    if task is None:
        return ConsultationReviewTaskDetailResponse(task=None)

    latest_versions = await _build_latest_versions(db, [int(task.id)])
    item = ConsultationReviewTaskItem.model_validate(task)
    latest = latest_versions.get(int(task.id))
    if latest is not None:
        item = item.model_copy(update={"latest_version": latest})

    return ConsultationReviewTaskDetailResponse(task=item)


@router.get(
    "/lawyer/tasks",
    response_model=LawyerReviewTaskListResponse,
    summary="律师-获取复核任务列表",
)
async def lawyer_list_review_tasks(
    current_user: Annotated[User, Depends(require_lawyer_verified)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    lawyer = await settlement_service.get_current_lawyer(db, int(current_user.id))
    if lawyer is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")
    if not bool(getattr(lawyer, "is_verified", False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="律师认证未通过")

    q = select(ConsultationReviewTask).where(
        or_(
            ConsultationReviewTask.lawyer_id.is_(None),
            ConsultationReviewTask.lawyer_id == int(lawyer.id),
        )
    )
    cq = select(func.count(ConsultationReviewTask.id)).where(
        or_(
            ConsultationReviewTask.lawyer_id.is_(None),
            ConsultationReviewTask.lawyer_id == int(lawyer.id),
        )
    )

    if status_filter:
        sf = str(status_filter).strip()
        q = q.where(ConsultationReviewTask.status == sf)
        cq = cq.where(ConsultationReviewTask.status == sf)

    total = int((await db.execute(cq)).scalar() or 0)
    res = await db.execute(
        q.order_by(ConsultationReviewTask.created_at.desc(), ConsultationReviewTask.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    tasks = res.scalars().all()

    task_ids = [int(t.id) for t in tasks]
    latest_versions = await _build_latest_versions(db, task_ids)

    items: list[ConsultationReviewTaskItem] = []
    for t in tasks:
        item = ConsultationReviewTaskItem.model_validate(t)
        latest = latest_versions.get(int(t.id))
        if latest is not None:
            item = item.model_copy(update={"latest_version": latest})
        items.append(item)

    return LawyerReviewTaskListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "/lawyer/tasks/{task_id}/claim",
    response_model=ConsultationReviewTaskItem,
    summary="律师-领取复核任务",
)
async def lawyer_claim_review_task(
    task_id: int,
    current_user: Annotated[User, Depends(require_lawyer_verified)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lawyer = await settlement_service.get_current_lawyer(db, int(current_user.id))
    if lawyer is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")
    if not bool(getattr(lawyer, "is_verified", False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="律师认证未通过")

    now = _now()

    upd = await db.execute(
        update(ConsultationReviewTask)
        .where(
            ConsultationReviewTask.id == int(task_id),
            ConsultationReviewTask.status == "pending",
            ConsultationReviewTask.lawyer_id.is_(None),
        )
        .values(
            lawyer_id=int(lawyer.id),
            status="claimed",
            claimed_at=now,
            updated_at=func.now(),
        )
    )
    if getattr(upd, "rowcount", 0) != 1:
        res = await db.execute(select(ConsultationReviewTask).where(ConsultationReviewTask.id == int(task_id)))
        task = res.scalar_one_or_none()
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
        cur_status = str(getattr(task, "status", "") or "")
        if str(getattr(task, "lawyer_id", None) or ""):
            raise HTTPException(status_code=400, detail="任务已被领取")
        raise HTTPException(status_code=400, detail=f"任务不可领取: {cur_status}")

    await db.commit()

    res2 = await db.execute(select(ConsultationReviewTask).where(ConsultationReviewTask.id == int(task_id)))
    task2 = res2.scalar_one()
    return ConsultationReviewTaskItem.model_validate(task2)


@router.post(
    "/lawyer/tasks/{task_id}/submit",
    response_model=ConsultationReviewTaskItem,
    summary="律师-提交复核结果",
)
async def lawyer_submit_review_task(
    task_id: int,
    data: LawyerReviewSubmitRequest,
    current_user: Annotated[User, Depends(require_lawyer_verified)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lawyer = await settlement_service.get_current_lawyer(db, int(current_user.id))
    if lawyer is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")
    if not bool(getattr(lawyer, "is_verified", False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="律师认证未通过")

    res = await db.execute(select(ConsultationReviewTask).where(ConsultationReviewTask.id == int(task_id)))
    task = res.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    if int(getattr(task, "lawyer_id", 0) or 0) != int(lawyer.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限处理该任务")

    if str(getattr(task, "status", "") or "") != "claimed":
        raise HTTPException(status_code=400, detail="仅已领取任务可提交")

    order_id = int(getattr(task, "order_id", 0) or 0)

    order: PaymentOrder | None = None
    if order_id > 0:
        order_res = await db.execute(select(PaymentOrder).where(PaymentOrder.id == int(order_id)))
        order = order_res.scalar_one_or_none()

    if order is None:
        raise HTTPException(status_code=500, detail="订单信息缺失")

    if getattr(order, "status", None) != PaymentStatus.PAID:
        raise HTTPException(status_code=400, detail="订单未支付，无法提交")

    now = _now()

    version = ConsultationReviewVersion(
        task_id=int(task.id),
        editor_user_id=int(current_user.id),
        editor_role="lawyer",
        content_markdown=str(data.content_markdown),
    )
    db.add(version)

    task.status = "submitted"
    task.result_markdown = str(data.content_markdown)
    task.submitted_at = now
    task.updated_at = now
    db.add(task)

    await settlement_service.ensure_income_record_for_paid_review_order(
        db,
        lawyer_id=int(lawyer.id),
        order=order,
    )

    await db.commit()

    refreshed = await db.execute(select(ConsultationReviewTask).where(ConsultationReviewTask.id == int(task.id)))
    out_task = refreshed.scalar_one()

    latest = ConsultationReviewVersionItem.model_validate(version)
    out_item = ConsultationReviewTaskItem.model_validate(out_task).model_copy(update={"latest_version": latest})
    return out_item
