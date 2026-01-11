from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from ..models.system import SystemConfig
from ..models.user import User
from ..models.user_quota import UserQuotaDaily, UserQuotaPackBalance


def _get_int_env(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


FREE_AI_CHAT_DAILY_LIMIT = _get_int_env("FREE_AI_CHAT_DAILY_LIMIT", 5)
VIP_AI_CHAT_DAILY_LIMIT = _get_int_env("VIP_AI_CHAT_DAILY_LIMIT", 10**9)

FREE_DOCUMENT_GENERATE_DAILY_LIMIT = _get_int_env("FREE_DOCUMENT_GENERATE_DAILY_LIMIT", 10)
VIP_DOCUMENT_GENERATE_DAILY_LIMIT = _get_int_env("VIP_DOCUMENT_GENERATE_DAILY_LIMIT", 50)


async def _get_system_config_value(db: AsyncSession, key: str) -> str | None:
    res = await db.execute(select(SystemConfig.value).where(SystemConfig.key == str(key).strip()))
    v = res.scalar_one_or_none()
    return str(v) if isinstance(v, str) else None


async def _get_int_config(db: AsyncSession, key: str, default: int) -> int:
    raw = await _get_system_config_value(db, key)
    if raw is None:
        return int(default)
    try:
        return int(str(raw).strip())
    except Exception:
        return int(default)


def _is_vip_active(user: User | None) -> bool:
    if user is None:
        return False
    raw = getattr(user, "vip_expires_at", None)
    if not isinstance(raw, datetime):
        return False
    expires_at = raw
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > datetime.now(timezone.utc)


def _is_vip_active_on_day(user: User | None, day: date) -> bool:
    if user is None:
        return False
    raw = getattr(user, "vip_expires_at", None)
    if not isinstance(raw, datetime):
        return False
    expires_at = raw
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    day_start = datetime.combine(day, datetime.min.time()).replace(tzinfo=timezone.utc)
    return expires_at > day_start


class QuotaService:
    async def _get_or_create_today(self, db: AsyncSession, user_id: int) -> UserQuotaDaily:
        today = date.today()
        res = await db.execute(
            select(UserQuotaDaily).where(
                UserQuotaDaily.user_id == int(user_id),
                UserQuotaDaily.day == today,
            )
        )
        row = res.scalar_one_or_none()
        if row is not None:
            return row

        row = UserQuotaDaily(user_id=int(user_id), day=today, ai_chat_count=0, document_generate_count=0)
        db.add(row)
        try:
            await db.commit()
            await db.refresh(row)
            return row
        except IntegrityError:
            await db.rollback()
            res2 = await db.execute(
                select(UserQuotaDaily).where(
                    UserQuotaDaily.user_id == int(user_id),
                    UserQuotaDaily.day == today,
                )
            )
            row2 = res2.scalar_one_or_none()
            if row2 is None:
                raise
            return row2

    async def _get_or_create_pack_balance(
        self, db: AsyncSession, user_id: int
    ) -> UserQuotaPackBalance:
        res = await db.execute(
            select(UserQuotaPackBalance).where(UserQuotaPackBalance.user_id == int(user_id))
        )
        row = res.scalar_one_or_none()
        if row is not None:
            return row

        row = UserQuotaPackBalance(
            user_id=int(user_id),
            ai_chat_credits=0,
            document_generate_credits=0,
        )
        db.add(row)
        try:
            await db.commit()
            await db.refresh(row)
            return row
        except IntegrityError:
            await db.rollback()
            res2 = await db.execute(
                select(UserQuotaPackBalance).where(
                    UserQuotaPackBalance.user_id == int(user_id)
                )
            )
            row2 = res2.scalar_one_or_none()
            if row2 is None:
                raise
            return row2

    async def _ai_chat_limit_for_user(self, db: AsyncSession, user: User) -> int:
        if str(getattr(user, "role", "")).lower() in {"admin", "super_admin"}:
            return 10**9
        free_limit = await _get_int_config(db, "FREE_AI_CHAT_DAILY_LIMIT", FREE_AI_CHAT_DAILY_LIMIT)
        vip_limit = await _get_int_config(db, "VIP_AI_CHAT_DAILY_LIMIT", VIP_AI_CHAT_DAILY_LIMIT)
        return int(vip_limit) if _is_vip_active(user) else int(free_limit)

    async def _ai_chat_limit_for_user_on_day(self, db: AsyncSession, user: User, day: date) -> int:
        if str(getattr(user, "role", "")).lower() in {"admin", "super_admin"}:
            return 10**9
        free_limit = await _get_int_config(db, "FREE_AI_CHAT_DAILY_LIMIT", FREE_AI_CHAT_DAILY_LIMIT)
        vip_limit = await _get_int_config(db, "VIP_AI_CHAT_DAILY_LIMIT", VIP_AI_CHAT_DAILY_LIMIT)
        return int(vip_limit) if _is_vip_active_on_day(user, day) else int(free_limit)

    async def _doc_limit_for_user_on_day(self, db: AsyncSession, user: User, day: date) -> int:
        if str(getattr(user, "role", "")).lower() in {"admin", "super_admin"}:
            return 10**9
        free_limit = await _get_int_config(
            db, "FREE_DOCUMENT_GENERATE_DAILY_LIMIT", FREE_DOCUMENT_GENERATE_DAILY_LIMIT
        )
        vip_limit = await _get_int_config(
            db, "VIP_DOCUMENT_GENERATE_DAILY_LIMIT", VIP_DOCUMENT_GENERATE_DAILY_LIMIT
        )
        return int(vip_limit) if _is_vip_active_on_day(user, day) else int(free_limit)

    async def _doc_limit_for_user(self, db: AsyncSession, user: User) -> int:
        if str(getattr(user, "role", "")).lower() in {"admin", "super_admin"}:
            return 10**9
        free_limit = await _get_int_config(
            db, "FREE_DOCUMENT_GENERATE_DAILY_LIMIT", FREE_DOCUMENT_GENERATE_DAILY_LIMIT
        )
        vip_limit = await _get_int_config(
            db, "VIP_DOCUMENT_GENERATE_DAILY_LIMIT", VIP_DOCUMENT_GENERATE_DAILY_LIMIT
        )
        return int(vip_limit) if _is_vip_active(user) else int(free_limit)

    async def enforce_ai_chat_quota(self, db: AsyncSession, user: User) -> None:
        row = await self._get_or_create_today(db, int(user.id))
        limit = await self._ai_chat_limit_for_user(db, user)
        if int(row.ai_chat_count) >= int(limit):
            pack = await self._get_or_create_pack_balance(db, int(user.id))
            if int(getattr(pack, "ai_chat_credits", 0)) > 0:
                return
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="今日 AI 咨询次数已用尽，请开通 VIP 或明日再试",
            )

    async def record_ai_chat_usage(self, db: AsyncSession, user: User) -> None:
        row = await self._get_or_create_today(db, int(user.id))
        limit = await self._ai_chat_limit_for_user(db, user)
        if int(row.ai_chat_count) < int(limit):
            row.ai_chat_count = int(row.ai_chat_count) + 1
            db.add(row)
            await db.commit()
            return

        pack = await self._get_or_create_pack_balance(db, int(user.id))
        credits = int(getattr(pack, "ai_chat_credits", 0))
        if credits <= 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="今日 AI 咨询次数已用尽，请开通 VIP 或明日再试",
            )
        pack.ai_chat_credits = credits - 1
        db.add(pack)
        await db.commit()

    async def consume_ai_chat(self, db: AsyncSession, user: User) -> None:
        await self.enforce_ai_chat_quota(db, user)
        await self.record_ai_chat_usage(db, user)

    async def enforce_document_generate_quota(self, db: AsyncSession, user: User) -> None:
        row = await self._get_or_create_today(db, int(user.id))
        limit = await self._doc_limit_for_user(db, user)
        if int(row.document_generate_count) >= int(limit):
            pack = await self._get_or_create_pack_balance(db, int(user.id))
            if int(getattr(pack, "document_generate_credits", 0)) > 0:
                return
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="今日文书生成次数已用尽，请开通 VIP 或明日再试",
            )

    async def record_document_generate_usage(self, db: AsyncSession, user: User) -> None:
        row = await self._get_or_create_today(db, int(user.id))
        limit = await self._doc_limit_for_user(db, user)
        if int(row.document_generate_count) < int(limit):
            row.document_generate_count = int(row.document_generate_count) + 1
            db.add(row)
            await db.commit()
            return

        pack = await self._get_or_create_pack_balance(db, int(user.id))
        credits = int(getattr(pack, "document_generate_credits", 0))
        if credits <= 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="今日文书生成次数已用尽，请开通 VIP 或明日再试",
            )
        pack.document_generate_credits = credits - 1
        db.add(pack)
        await db.commit()

    async def consume_document_generate(self, db: AsyncSession, user: User) -> None:
        await self.enforce_document_generate_quota(db, user)
        await self.record_document_generate_usage(db, user)

    async def get_today_quota(self, db: AsyncSession, user: User) -> dict[str, object]:
        row = await self._get_or_create_today(db, int(user.id))
        pack = await self._get_or_create_pack_balance(db, int(user.id))
        ai_limit = await self._ai_chat_limit_for_user(db, user)
        doc_limit = await self._doc_limit_for_user(db, user)
        ai_used = int(row.ai_chat_count)
        doc_used = int(row.document_generate_count)
        return {
            "day": row.day,
            "ai_chat_limit": int(ai_limit),
            "ai_chat_used": ai_used,
            "ai_chat_remaining": max(0, int(ai_limit) - ai_used),
            "document_generate_limit": int(doc_limit),
            "document_generate_used": doc_used,
            "document_generate_remaining": max(0, int(doc_limit) - doc_used),
            "ai_chat_pack_remaining": max(0, int(getattr(pack, "ai_chat_credits", 0))),
            "document_generate_pack_remaining": max(
                0, int(getattr(pack, "document_generate_credits", 0))
            ),
            "is_vip_active": bool(_is_vip_active(user)),
        }

    async def list_quota_usage(
        self,
        db: AsyncSession,
        user: User,
        *,
        days: int = 30,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, object]:
        _ = await self._get_or_create_today(db, int(user.id))
        safe_days = max(1, min(int(days), 365))
        safe_page = max(1, int(page))
        safe_page_size = max(1, min(int(page_size), 100))

        day_from = date.today() - timedelta(days=safe_days - 1)

        base = select(UserQuotaDaily).where(
            UserQuotaDaily.user_id == int(user.id),
            UserQuotaDaily.day >= day_from,
        )
        count_q = select(func.count(UserQuotaDaily.id)).where(
            UserQuotaDaily.user_id == int(user.id),
            UserQuotaDaily.day >= day_from,
        )

        res_total = await db.execute(count_q)
        total = int(res_total.scalar() or 0)

        res = await db.execute(
            base.order_by(UserQuotaDaily.day.desc())
            .offset((safe_page - 1) * safe_page_size)
            .limit(safe_page_size)
        )
        rows = res.scalars().all()

        items: list[dict[str, object]] = []
        for r in rows:
            d = r.day
            ai_limit = await self._ai_chat_limit_for_user_on_day(db, user, d)
            doc_limit = await self._doc_limit_for_user_on_day(db, user, d)
            items.append(
                {
                    "day": d,
                    "ai_chat_limit": int(ai_limit),
                    "ai_chat_used": int(getattr(r, "ai_chat_count", 0) or 0),
                    "document_generate_limit": int(doc_limit),
                    "document_generate_used": int(getattr(r, "document_generate_count", 0) or 0),
                }
            )

        return {
            "items": items,
            "total": total,
            "page": safe_page,
            "page_size": safe_page_size,
        }


quota_service = QuotaService()
