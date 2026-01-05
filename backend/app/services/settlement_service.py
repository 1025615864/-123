from __future__ import annotations

import json
import os
import uuid
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models.lawfirm import Lawyer, LawyerConsultation
from ..models.payment import PaymentOrder, PaymentStatus
from ..models.settlement import LawyerBankAccount, LawyerIncomeRecord, LawyerWallet, WithdrawalRequest


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _quantize_amount(amount: float) -> Decimal:
    return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _decimal_to_cents(amount: Decimal) -> int:
    return int(amount * 100)


def _get_float_env(key: str, default: float) -> float:
    raw = os.getenv(key, "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _get_int_env(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _get_int_set_env(key: str) -> set[int]:
    raw = os.getenv(key, "").strip()
    if not raw:
        return set()
    out: set[int] = set()
    for part in raw.split(","):
        p = str(part).strip()
        if not p:
            continue
        try:
            out.add(int(p))
        except Exception:
            continue
    return out


SETTLEMENT_PLATFORM_FEE_RATE = _get_float_env("SETTLEMENT_PLATFORM_FEE_RATE", 0.15)
SETTLEMENT_FREEZE_DAYS = _get_int_env("SETTLEMENT_FREEZE_DAYS", 7)
SETTLEMENT_WITHDRAW_MIN_AMOUNT = _get_float_env("SETTLEMENT_WITHDRAW_MIN_AMOUNT", 100.0)
SETTLEMENT_WITHDRAW_MAX_AMOUNT = _get_float_env("SETTLEMENT_WITHDRAW_MAX_AMOUNT", 50000.0)
SETTLEMENT_WITHDRAW_FEE = _get_float_env("SETTLEMENT_WITHDRAW_FEE", 0.0)

SETTLEMENT_VERIFIED_MIN_COMPLETED = _get_int_env("SETTLEMENT_VERIFIED_MIN_COMPLETED", 10)
SETTLEMENT_VERIFIED_MIN_RATING = _get_float_env("SETTLEMENT_VERIFIED_MIN_RATING", 4.5)
SETTLEMENT_VERIFIED_PLATFORM_FEE_RATE = _get_float_env(
    "SETTLEMENT_VERIFIED_PLATFORM_FEE_RATE", 0.13
)

SETTLEMENT_GOLD_MIN_COMPLETED = _get_int_env("SETTLEMENT_GOLD_MIN_COMPLETED", 50)
SETTLEMENT_GOLD_MIN_RATING = _get_float_env("SETTLEMENT_GOLD_MIN_RATING", 4.8)
SETTLEMENT_GOLD_PLATFORM_FEE_RATE = _get_float_env("SETTLEMENT_GOLD_PLATFORM_FEE_RATE", 0.10)

SETTLEMENT_PARTNER_LAWYER_IDS = _get_int_set_env("SETTLEMENT_PARTNER_LAWYER_IDS")
SETTLEMENT_PARTNER_PLATFORM_FEE_RATE = _get_float_env(
    "SETTLEMENT_PARTNER_PLATFORM_FEE_RATE", 0.08
)


def _mask_account_no(account_no: str) -> str:
    s = str(account_no or "").strip()
    if len(s) <= 4:
        return "****"
    return f"****{s[-4:]}"


_ENC_PREFIX = "enc:"


def _get_fernet() -> Fernet:
    secret = str(get_settings().secret_key or "")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _recalc_wallet_fields(wallet: LawyerWallet) -> None:
    total = _quantize_amount(float(wallet.total_income or 0.0))
    withdrawn = _quantize_amount(float(wallet.withdrawn_amount or 0.0))
    pending = _quantize_amount(float(wallet.pending_amount or 0.0))
    frozen = _quantize_amount(float(wallet.frozen_amount or 0.0))

    available = total - withdrawn - pending - frozen
    if available < Decimal("0"):
        available = Decimal("0")

    wallet.available_amount = float(available)
    wallet.total_income_cents = _decimal_to_cents(total)
    wallet.withdrawn_amount_cents = _decimal_to_cents(withdrawn)
    wallet.pending_amount_cents = _decimal_to_cents(pending)
    wallet.frozen_amount_cents = _decimal_to_cents(frozen)
    wallet.available_amount_cents = _decimal_to_cents(available)


class SettlementService:
    def encrypt_secret(self, raw: str) -> str:
        s = str(raw or "").strip()
        if not s:
            return ""
        if s.startswith(_ENC_PREFIX):
            return s
        token = _get_fernet().encrypt(s.encode("utf-8")).decode("utf-8")
        return f"{_ENC_PREFIX}{token}"

    def decrypt_secret(self, value: str) -> str:
        s = str(value or "").strip()
        if not s:
            return ""
        if not s.startswith(_ENC_PREFIX):
            return s
        token = s[len(_ENC_PREFIX) :]
        try:
            return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            return ""
        except Exception:
            return ""

    def choose_platform_fee_rate(self, lawyer_id: int, rating: float, completed: int) -> float:
        if int(lawyer_id) in SETTLEMENT_PARTNER_LAWYER_IDS:
            return float(SETTLEMENT_PARTNER_PLATFORM_FEE_RATE)

        if completed >= int(SETTLEMENT_GOLD_MIN_COMPLETED) and rating >= float(SETTLEMENT_GOLD_MIN_RATING):
            return float(SETTLEMENT_GOLD_PLATFORM_FEE_RATE)
        if completed >= int(SETTLEMENT_VERIFIED_MIN_COMPLETED) and rating >= float(
            SETTLEMENT_VERIFIED_MIN_RATING
        ):
            return float(SETTLEMENT_VERIFIED_PLATFORM_FEE_RATE)

        return float(SETTLEMENT_PLATFORM_FEE_RATE)

    async def get_platform_fee_rate(self, db: AsyncSession, lawyer_id: int) -> float:
        res = await db.execute(select(Lawyer).where(Lawyer.id == int(lawyer_id)))
        lawyer = res.scalar_one_or_none()
        if lawyer is None:
            return float(SETTLEMENT_PLATFORM_FEE_RATE)

        rating = float(getattr(lawyer, "rating", 0.0) or 0.0)
        completed_res = await db.execute(
            select(func.count(LawyerConsultation.id)).where(
                LawyerConsultation.lawyer_id == int(lawyer_id),
                LawyerConsultation.status == "completed",
            )
        )
        completed = int(completed_res.scalar() or 0)

        return self.choose_platform_fee_rate(int(lawyer_id), float(rating), int(completed))

    async def get_current_lawyer(self, db: AsyncSession, user_id: int) -> Lawyer | None:
        res = await db.execute(
            select(Lawyer).where(
                Lawyer.user_id == int(user_id),
                Lawyer.is_active == True,
            )
        )
        return res.scalar_one_or_none()

    async def get_or_create_wallet(self, db: AsyncSession, lawyer_id: int) -> LawyerWallet:
        res = await db.execute(select(LawyerWallet).where(LawyerWallet.lawyer_id == int(lawyer_id)))
        wallet = res.scalar_one_or_none()
        if wallet is not None:
            _recalc_wallet_fields(wallet)
            return wallet

        wallet = LawyerWallet(lawyer_id=int(lawyer_id))
        _recalc_wallet_fields(wallet)
        db.add(wallet)
        await db.commit()
        await db.refresh(wallet)
        return wallet

    async def ensure_income_record_for_completed_consultation(
        self,
        db: AsyncSession,
        consultation: LawyerConsultation,
        order: PaymentOrder | None,
    ) -> LawyerIncomeRecord | None:
        if order is None:
            return None
        if str(order.status or "").lower() != str(PaymentStatus.PAID.value).lower():
            return None

        res = await db.execute(
            select(LawyerIncomeRecord).where(
                LawyerIncomeRecord.consultation_id == int(consultation.id),
                LawyerIncomeRecord.lawyer_id == int(consultation.lawyer_id),
            )
        )
        existing = res.scalar_one_or_none()
        if existing is not None:
            return existing

        paid_amount = _quantize_amount(float(order.actual_amount or 0.0))
        platform_fee_rate = await self.get_platform_fee_rate(db, int(consultation.lawyer_id))
        if platform_fee_rate < 0:
            platform_fee_rate = 0.0
        if platform_fee_rate > 1:
            platform_fee_rate = 1.0

        platform_fee = (paid_amount * Decimal(str(platform_fee_rate))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if platform_fee < Decimal("0"):
            platform_fee = Decimal("0")
        if platform_fee > paid_amount:
            platform_fee = paid_amount
        lawyer_income = paid_amount - platform_fee

        settle_time = _now() + timedelta(days=int(SETTLEMENT_FREEZE_DAYS))

        record = LawyerIncomeRecord(
            lawyer_id=int(consultation.lawyer_id),
            consultation_id=int(consultation.id),
            order_no=str(order.order_no or "").strip() or None,
            user_paid_amount=float(paid_amount),
            platform_fee=float(platform_fee),
            lawyer_income=float(lawyer_income),
            user_paid_amount_cents=_decimal_to_cents(paid_amount),
            platform_fee_cents=_decimal_to_cents(platform_fee),
            lawyer_income_cents=_decimal_to_cents(lawyer_income),
            withdrawn_amount=0.0,
            withdrawn_amount_cents=0,
            status="pending",
            settle_time=settle_time,
        )
        db.add(record)

        wallet = await self.get_or_create_wallet(db, int(consultation.lawyer_id))
        wallet.total_income = float(_quantize_amount(float(wallet.total_income or 0.0)) + lawyer_income)
        wallet.pending_amount = float(_quantize_amount(float(wallet.pending_amount or 0.0)) + lawyer_income)
        _recalc_wallet_fields(wallet)
        db.add(wallet)

        await db.commit()
        await db.refresh(record)
        return record

    async def settle_due_income_records(self, db: AsyncSession) -> dict[str, int]:
        now = _now()
        res = await db.execute(
            select(LawyerIncomeRecord).where(
                LawyerIncomeRecord.status == "pending",
                LawyerIncomeRecord.settle_time.is_not(None),
                LawyerIncomeRecord.settle_time <= now,
            )
        )
        records = res.scalars().all()
        settled = 0

        for r in records:
            amount = _quantize_amount(float(r.lawyer_income or 0.0))
            if amount <= Decimal("0"):
                r.status = "settled"
                db.add(r)
                settled += 1
                continue

            wallet = await self.get_or_create_wallet(db, int(r.lawyer_id))
            wallet.pending_amount = float(_quantize_amount(float(wallet.pending_amount or 0.0)) - amount)
            if float(wallet.pending_amount) < 0:
                wallet.pending_amount = 0.0
            _recalc_wallet_fields(wallet)

            r.status = "settled"
            db.add_all([wallet, r])
            settled += 1

        await db.commit()
        return {"settled": int(settled)}

    async def create_withdrawal_request(
        self,
        db: AsyncSession,
        *,
        lawyer_id: int,
        amount: float,
        withdraw_method: str,
        bank_account_id: int,
    ) -> WithdrawalRequest:
        wallet = await self.get_or_create_wallet(db, int(lawyer_id))
        _recalc_wallet_fields(wallet)

        amt = _quantize_amount(float(amount))
        if amt <= Decimal("0"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="金额不合法")

        if float(amt) > float(SETTLEMENT_WITHDRAW_MAX_AMOUNT):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"单次最高提现金额为 {SETTLEMENT_WITHDRAW_MAX_AMOUNT}",
            )

        if float(amt) < float(SETTLEMENT_WITHDRAW_MIN_AMOUNT):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"最低提现金额为 {SETTLEMENT_WITHDRAW_MIN_AMOUNT}",
            )

        if _quantize_amount(float(wallet.available_amount or 0.0)) < amt:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="可提现余额不足")

        fee = _quantize_amount(float(SETTLEMENT_WITHDRAW_FEE))
        if fee < Decimal("0"):
            fee = Decimal("0")
        if fee > amt:
            fee = amt
        actual = amt - fee

        bank_res = await db.execute(
            select(LawyerBankAccount).where(
                LawyerBankAccount.id == int(bank_account_id),
                LawyerBankAccount.lawyer_id == int(lawyer_id),
                LawyerBankAccount.is_active == True,
            )
        )
        bank = bank_res.scalar_one_or_none()
        if bank is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="收款账户不存在")

        request_no = f"W{_now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"

        raw_account_no = self.decrypt_secret(str(bank.account_no))
        encrypted_account_no = self.encrypt_secret(raw_account_no)

        account_info = {
            "account_type": str(bank.account_type),
            "bank_name": str(bank.bank_name or ""),
            "account_no": str(encrypted_account_no),
            "account_holder": str(bank.account_holder),
            "masked": {
                "account_no": _mask_account_no(str(raw_account_no)),
            },
        }

        wr = WithdrawalRequest(
            request_no=request_no,
            lawyer_id=int(lawyer_id),
            amount=float(amt),
            fee=float(fee),
            actual_amount=float(actual),
            amount_cents=_decimal_to_cents(amt),
            fee_cents=_decimal_to_cents(fee),
            actual_amount_cents=_decimal_to_cents(actual),
            withdraw_method=str(withdraw_method or "bank_card"),
            account_info=json.dumps(account_info, ensure_ascii=False),
            status="pending",
        )

        wallet.available_amount = float(_quantize_amount(float(wallet.available_amount or 0.0)) - amt)
        wallet.frozen_amount = float(_quantize_amount(float(wallet.frozen_amount or 0.0)) + amt)
        _recalc_wallet_fields(wallet)

        db.add_all([wr, wallet])
        await db.commit()
        await db.refresh(wr)
        return wr

    async def admin_set_withdrawal_status(
        self,
        db: AsyncSession,
        *,
        withdrawal_id: int,
        action: str,
        admin_id: int,
        reject_reason: str | None = None,
        remark: str | None = None,
    ) -> WithdrawalRequest:
        res = await db.execute(select(WithdrawalRequest).where(WithdrawalRequest.id == int(withdrawal_id)))
        wr = res.scalar_one_or_none()
        if wr is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提现申请不存在")

        now = _now()
        cur = str(wr.status or "").lower()
        action_l = str(action).lower()

        wallet = await self.get_or_create_wallet(db, int(wr.lawyer_id))
        _recalc_wallet_fields(wallet)

        amt = _quantize_amount(float(wr.amount or 0.0))

        if action_l == "approve":
            if cur != "pending":
                raise HTTPException(status_code=400, detail="仅待审核可通过")
            wr.status = "approved"
            wr.admin_id = int(admin_id)
            wr.reviewed_at = now
            wr.remark = remark
        elif action_l == "reject":
            if cur != "pending":
                raise HTTPException(status_code=400, detail="仅待审核可驳回")
            wr.status = "rejected"
            wr.reject_reason = str(reject_reason or "").strip() or "驳回"
            wr.admin_id = int(admin_id)
            wr.reviewed_at = now
            wr.remark = remark

            wallet.frozen_amount = float(_quantize_amount(float(wallet.frozen_amount or 0.0)) - amt)
            if float(wallet.frozen_amount) < 0:
                wallet.frozen_amount = 0.0
            wallet.available_amount = float(_quantize_amount(float(wallet.available_amount or 0.0)) + amt)
        elif action_l == "complete":
            if cur != "approved":
                raise HTTPException(status_code=400, detail="仅已通过可标记完成")
            wr.status = "completed"
            wr.admin_id = int(admin_id)
            wr.completed_at = now
            wr.remark = remark

            wallet.frozen_amount = float(_quantize_amount(float(wallet.frozen_amount or 0.0)) - amt)
            if float(wallet.frozen_amount) < 0:
                wallet.frozen_amount = 0.0
            wallet.withdrawn_amount = float(_quantize_amount(float(wallet.withdrawn_amount or 0.0)) + amt)

            try:
                remaining = amt
                income_res = await db.execute(
                    select(LawyerIncomeRecord)
                    .where(
                        LawyerIncomeRecord.lawyer_id == int(wr.lawyer_id),
                        LawyerIncomeRecord.status.in_(["settled", "withdrawn"]),
                    )
                    .order_by(
                        func.coalesce(LawyerIncomeRecord.settle_time, LawyerIncomeRecord.created_at).asc(),
                        LawyerIncomeRecord.created_at.asc(),
                    )
                )
                records = income_res.scalars().all()
                for r in records:
                    if remaining <= Decimal("0"):
                        break

                    total_income = _quantize_amount(float(r.lawyer_income or 0.0))
                    already = _quantize_amount(float(r.withdrawn_amount or 0.0))
                    can_take = total_income - already
                    if can_take <= Decimal("0"):
                        if str(r.status or "").lower() == "settled":
                            r.status = "withdrawn"
                            db.add(r)
                        continue

                    take = can_take if can_take <= remaining else remaining
                    new_withdrawn = already + take
                    r.withdrawn_amount = float(new_withdrawn)
                    r.withdrawn_amount_cents = _decimal_to_cents(new_withdrawn)
                    if new_withdrawn >= total_income:
                        r.status = "withdrawn"
                    else:
                        r.status = "settled"
                    db.add(r)

                    remaining = remaining - take
            except Exception:
                pass
        elif action_l == "fail":
            if cur != "approved":
                raise HTTPException(status_code=400, detail="仅已通过可标记失败")
            wr.status = "failed"
            wr.admin_id = int(admin_id)
            wr.completed_at = now
            wr.remark = remark

            wallet.frozen_amount = float(_quantize_amount(float(wallet.frozen_amount or 0.0)) - amt)
            if float(wallet.frozen_amount) < 0:
                wallet.frozen_amount = 0.0
            wallet.available_amount = float(_quantize_amount(float(wallet.available_amount or 0.0)) + amt)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的操作: {action}")

        _recalc_wallet_fields(wallet)
        db.add_all([wr, wallet])
        await db.commit()
        await db.refresh(wr)
        return wr


settlement_service = SettlementService()
