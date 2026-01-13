from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.consultation import Consultation
from ..models.consultation_review import ConsultationReviewTask, ConsultationReviewVersion
from ..models.payment import PaymentOrder, PaymentStatus
from ..models.system import SystemConfig
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

CONSULT_REVIEW_SLA_CONFIG_KEY = "CONSULT_REVIEW_SLA_JSON"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_int(value: object | None, default: int) -> int:
    try:
        if value is None:
            return int(default)
        if isinstance(value, bool):
            return int(default)
        if isinstance(value, int):
            return int(value)
        if isinstance(value, float):
            return int(value)
        s = str(value).strip()
        if not s:
            return int(default)
        return int(float(s))
    except Exception:
        return int(default)


async def _load_review_sla_config(db: AsyncSession) -> dict[str, object]:
    raw = ""
    try:
        res = await db.execute(select(SystemConfig).where(SystemConfig.key == CONSULT_REVIEW_SLA_CONFIG_KEY))
        cfg = res.scalar_one_or_none()
        raw = str(getattr(cfg, "value", "") or "").strip() if cfg is not None else ""
    except Exception:
        raw = ""

    if not raw:
        raw = str(os.getenv(CONSULT_REVIEW_SLA_CONFIG_KEY, "") or "").strip()

    if raw:
        try:
            obj_raw: object = json.loads(raw)
            if isinstance(obj_raw, dict):
                return dict(obj_raw)
        except Exception:
            pass

    return {
        "pending_sla_minutes": 24 * 60,
        "claimed_sla_minutes": 12 * 60,
        "remind_before_minutes": 60,
    }


def _compute_review_due_at(task: ConsultationReviewTask, cfg: dict[str, object]) -> datetime | None:
    status = str(getattr(task, "status", "") or "").strip().lower()
    if status == "submitted":
        return None

    created_at = getattr(task, "created_at", None)
    claimed_at = getattr(task, "claimed_at", None)
    base: datetime | None = None
    if status == "claimed" and isinstance(claimed_at, datetime):
        base = claimed_at
    elif isinstance(created_at, datetime):
        base = created_at

    if base is None:
        return None
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)

    pending_minutes = _parse_int(cfg.get("pending_sla_minutes"), 24 * 60)
    claimed_minutes = _parse_int(cfg.get("claimed_sla_minutes"), 12 * 60)
    minutes = claimed_minutes if status == "claimed" else pending_minutes
    minutes = max(1, int(minutes))
    return base + timedelta(minutes=int(minutes))


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

    cfg = await _load_review_sla_config(db)
    due_at = _compute_review_due_at(task, cfg)
    now = _now()
    is_overdue = bool(due_at is not None and now > due_at)

    latest_versions = await _build_latest_versions(db, [int(task.id)])
    item = ConsultationReviewTaskItem.model_validate(task).model_copy(update={"due_at": due_at, "is_overdue": is_overdue})
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

    cfg = await _load_review_sla_config(db)
    now = _now()

    task_ids = [int(t.id) for t in tasks]
    latest_versions = await _build_latest_versions(db, task_ids)

    items: list[ConsultationReviewTaskItem] = []
    for t in tasks:
        due_at = _compute_review_due_at(t, cfg)
        is_overdue = bool(due_at is not None and now > due_at)
        item = ConsultationReviewTaskItem.model_validate(t).model_copy(update={"due_at": due_at, "is_overdue": is_overdue})
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
    cfg = await _load_review_sla_config(db)
    due_at = _compute_review_due_at(task2, cfg)
    is_overdue = bool(due_at is not None and _now() > due_at)
    return ConsultationReviewTaskItem.model_validate(task2).model_copy(update={"due_at": due_at, "is_overdue": is_overdue})


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
    cfg = await _load_review_sla_config(db)
    due_at = _compute_review_due_at(out_task, cfg)
    is_overdue = bool(due_at is not None and _now() > due_at)
    out_item = ConsultationReviewTaskItem.model_validate(out_task).model_copy(
        update={"latest_version": latest, "due_at": due_at, "is_overdue": is_overdue}
    )
    return out_item
