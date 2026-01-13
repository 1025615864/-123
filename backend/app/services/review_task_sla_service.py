from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.consultation_review import ConsultationReviewTask
from ..models.lawfirm import Lawyer
from ..models.notification import Notification, NotificationType
from ..models.system import SystemConfig

logger = logging.getLogger(__name__)

CONSULT_REVIEW_SLA_CONFIG_KEY = "CONSULT_REVIEW_SLA_JSON"
ENABLE_NOTIFICATIONS_CONFIG_KEY = "enable_notifications"


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


async def load_review_sla_config(db: AsyncSession) -> dict[str, object]:
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


def compute_review_due_at(task: ConsultationReviewTask, cfg: dict[str, object]) -> datetime | None:
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


async def scan_and_notify_review_task_sla(db: AsyncSession) -> dict[str, int]:
    try:
        en_res = await db.execute(
            select(SystemConfig.value).where(SystemConfig.key == ENABLE_NOTIFICATIONS_CONFIG_KEY)
        )
        en_val = en_res.scalar_one_or_none()
        if isinstance(en_val, str) and en_val.strip() and en_val.strip().lower() in {"0", "false", "no", "off"}:
            return {"scanned": 0, "candidates": 0, "inserted": 0, "due_soon": 0, "overdue": 0, "skipped": 1}
    except Exception:
        pass

    cfg = await load_review_sla_config(db)

    now = datetime.now(timezone.utc)
    remind_before_minutes = _parse_int(cfg.get("remind_before_minutes"), 60)
    remind_before = timedelta(minutes=max(0, int(remind_before_minutes)))

    res = await db.execute(
        select(ConsultationReviewTask, Lawyer.user_id)
        .join(Lawyer, Lawyer.id == ConsultationReviewTask.lawyer_id)
        .where(ConsultationReviewTask.status.in_(["pending", "claimed"]))
        .where(ConsultationReviewTask.lawyer_id.is_not(None))
        .order_by(ConsultationReviewTask.created_at.desc(), ConsultationReviewTask.id.desc())
        .limit(500)
    )

    rows = cast(list[tuple[ConsultationReviewTask, int | None]], list(res.all()))

    scanned = len(rows)
    values: list[dict[str, object]] = []
    due_soon = 0
    overdue = 0

    for task, lawyer_user_id in rows:
        if lawyer_user_id is None:
            continue

        due_at = compute_review_due_at(task, cfg)
        if due_at is None:
            continue
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)

        kind: str | None = None
        remaining = due_at - now
        if now > due_at:
            kind = "overdue"
        elif remaining <= remind_before:
            kind = "due_soon"

        if kind is None:
            continue

        if kind == "overdue":
            overdue += 1
            title = "复核任务已超时"
        else:
            due_soon += 1
            title = "复核任务即将到期"

        content_lines: list[str] = [
            f"复核任务 #{int(getattr(task, 'id', 0) or 0)}",
            f"咨询ID：{int(getattr(task, 'consultation_id', 0) or 0)}",
            f"订单号：{str(getattr(task, 'order_no', '') or '')}",
            f"状态：{str(getattr(task, 'status', '') or '')}",
            f"到期时间：{due_at.isoformat()}",
        ]
        if kind == "due_soon":
            mins_left = int(max(0.0, remaining.total_seconds()) // 60)
            content_lines.append(f"剩余时间：约 {mins_left} 分钟")

        dedupe_key = f"review_task:{int(getattr(task, 'id', 0) or 0)}:{kind}:{due_at.isoformat()}"

        values.append(
            {
                "user_id": int(lawyer_user_id),
                "type": NotificationType.SYSTEM,
                "title": title,
                "content": "\n".join(content_lines) if content_lines else None,
                "link": "/lawyer?tab=reviews",
                "dedupe_key": dedupe_key,
                "is_read": False,
            }
        )

    if not values:
        return {
            "scanned": int(scanned),
            "candidates": 0,
            "inserted": 0,
            "due_soon": int(due_soon),
            "overdue": int(overdue),
            "skipped": 0,
        }

    bind = db.get_bind()
    dialect_name = str(getattr(getattr(bind, "dialect", None), "name", "") or "")

    if dialect_name == "postgresql":
        stmt = (
            pg_insert(Notification)
            .values(values)
            .on_conflict_do_nothing(index_elements=["user_id", "type", "dedupe_key"])
            .returning(Notification.user_id, Notification.title, Notification.content, Notification.link, Notification.dedupe_key)
        )
    else:
        stmt = sqlite_insert(Notification).values(values).on_conflict_do_nothing(
            index_elements=["user_id", "type", "dedupe_key"]
        )

    result = await db.execute(stmt)
    await db.commit()

    inserted_rows: list[tuple[object, object, object, object, object]] = []
    if dialect_name == "postgresql":
        inserted_rows = cast(list[tuple[object, object, object, object, object]], list(result.all()))
        inserted = int(len(inserted_rows))
    else:
        inserted = int(getattr(result, "rowcount", 0) or 0)

    logger.info(
        "review_task_sla scan done scanned=%s candidates=%s inserted=%s due_soon=%s overdue=%s",
        scanned,
        len(values),
        inserted,
        due_soon,
        overdue,
    )

    if inserted > 0:
        try:
            from . import websocket_service

            if inserted_rows:
                for user_id, title, content, link, dedupe_key in inserted_rows:
                    uid = _parse_int(user_id, 0)
                    if uid <= 0:
                        continue
                    _ = await websocket_service.notify_user(
                        uid,
                        websocket_service.MessageType.NOTIFICATION,
                        str(title or ""),
                        str(content or ""),
                        data={"link": str(link or ""), "dedupe_key": str(dedupe_key or "")},
                    )
            else:
                for v in values:
                    uid = _parse_int(v.get("user_id"), 0)
                    if uid <= 0:
                        continue
                    _ = await websocket_service.notify_user(
                        uid,
                        websocket_service.MessageType.NOTIFICATION,
                        str(v.get("title") or ""),
                        str(v.get("content") or ""),
                        data={"link": str(v.get("link") or ""), "dedupe_key": str(v.get("dedupe_key") or "")},
                    )
        except Exception:
            logger.exception("review_task_sla websocket notify failed")

    return {
        "scanned": int(scanned),
        "candidates": int(len(values)),
        "inserted": int(inserted),
        "due_soon": int(due_soon),
        "overdue": int(overdue),
        "skipped": 0,
    }
