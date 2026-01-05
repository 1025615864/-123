from __future__ import annotations

import csv
import io
import json
from collections.abc import AsyncIterator, Mapping
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import Integer, cast as sa_cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.lawfirm import Lawyer, LawyerConsultation
from ..models.settlement import LawyerBankAccount, LawyerIncomeRecord, LawyerWallet, WithdrawalRequest
from ..models.user import User
from ..schemas.settlement import (
    AdminSettlementStatsResponse,
    AdminWithdrawalDetailResponse,
    LawyerBankAccountCreate,
    LawyerBankAccountItem,
    LawyerBankAccountListResponse,
    LawyerBankAccountUpdate,
    LawyerIncomeRecordItem,
    LawyerIncomeRecordListResponse,
    LawyerWalletResponse,
    SettlementStatsTopLawyerItem,
    SettlementStatsWalletSummary,
    SettlementStatsWithdrawalSummary,
    WithdrawalAdminActionRequest,
    WithdrawalCreateRequest,
    WithdrawalItem,
    WithdrawalListResponse,
    WithdrawalRejectRequest,
)
from ..services.settlement_service import settlement_service
from ..utils.deps import require_admin, require_lawyer

router = APIRouter(tags=["律师结算"])


def _mask_account_no(account_no: str) -> str:
    s = str(account_no or "").strip()
    if len(s) <= 4:
        return "****"
    return f"****{s[-4:]}"


def _mask_account_info(raw: str) -> str:
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            masked = obj.get("masked")
            if isinstance(masked, dict) and isinstance(masked.get("account_no"), str):
                obj["account_no"] = str(masked.get("account_no") or "")
            elif isinstance(obj.get("account_no"), str):
                raw_no = settlement_service.decrypt_secret(str(obj.get("account_no") or ""))
                obj["account_no"] = _mask_account_no(raw_no)
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return "***"


async def _generate_csv_stream(fieldnames: list[str], rows_iter: AsyncIterator[Mapping[str, object]]):
    header_out = io.StringIO()
    _ = header_out.write("\ufeff")
    header_writer = csv.DictWriter(header_out, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
    header_writer.writeheader()
    yield header_out.getvalue()

    async for row in rows_iter:
        processed: dict[str, object] = {}
        for k, v in row.items():
            if isinstance(v, datetime):
                processed[k] = v.strftime("%Y-%m-%d %H:%M:%S")
            else:
                processed[k] = v

        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writerow(processed)
        yield out.getvalue()


@router.get("/lawyer/wallet", response_model=LawyerWalletResponse, summary="律师-获取钱包")
async def lawyer_get_wallet(
    current_user: Annotated[User, Depends(require_lawyer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lawyer = await settlement_service.get_current_lawyer(db, int(current_user.id))
    if lawyer is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")

    wallet = await settlement_service.get_or_create_wallet(db, int(lawyer.id))
    return LawyerWalletResponse.model_validate(wallet)


@router.get(
    "/lawyer/income-records",
    response_model=LawyerIncomeRecordListResponse,
    summary="律师-获取收入记录",
)
async def lawyer_list_income_records(
    current_user: Annotated[User, Depends(require_lawyer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    lawyer = await settlement_service.get_current_lawyer(db, int(current_user.id))
    if lawyer is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")

    q = select(LawyerIncomeRecord).where(LawyerIncomeRecord.lawyer_id == int(lawyer.id))
    cq = select(func.count(LawyerIncomeRecord.id)).where(LawyerIncomeRecord.lawyer_id == int(lawyer.id))

    if status_filter:
        q = q.where(LawyerIncomeRecord.status == str(status_filter).strip())
        cq = cq.where(LawyerIncomeRecord.status == str(status_filter).strip())

    total = int((await db.execute(cq)).scalar() or 0)
    res = await db.execute(
        q.order_by(LawyerIncomeRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )

    records = res.scalars().all()
    consultation_ids = [int(x.consultation_id) for x in records if x.consultation_id is not None]
    subject_by_id: dict[int, str] = {}
    if consultation_ids:
        sub_res = await db.execute(
            select(LawyerConsultation.id, LawyerConsultation.subject).where(
                LawyerConsultation.id.in_(consultation_ids)
            )
        )
        for cid, subj in sub_res.all():
            if isinstance(cid, int) and isinstance(subj, str):
                subject_by_id[int(cid)] = subj

    items: list[LawyerIncomeRecordItem] = []
    for r in records:
        item = LawyerIncomeRecordItem.model_validate(r)
        subj = subject_by_id.get(int(r.consultation_id)) if r.consultation_id is not None else None
        items.append(item.model_copy(update={"consultation_subject": subj}))

    return LawyerIncomeRecordListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/lawyer/income-records/export",
    summary="律师-导出收入记录",
)
async def lawyer_export_income_records(
    current_user: Annotated[User, Depends(require_lawyer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
):
    lawyer = await settlement_service.get_current_lawyer(db, int(current_user.id))
    if lawyer is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")

    fieldnames = [
        "id",
        "consultation_id",
        "consultation_subject",
        "order_no",
        "user_paid_amount",
        "platform_fee",
        "lawyer_income",
        "withdrawn_amount",
        "status",
        "settle_time",
        "created_at",
    ]

    async def row_generator():
        batch_size = 1000
        offset = 0
        while True:
            stmt = (
                select(LawyerIncomeRecord, LawyerConsultation.subject)
                .outerjoin(LawyerConsultation, LawyerConsultation.id == LawyerIncomeRecord.consultation_id)
                .where(LawyerIncomeRecord.lawyer_id == int(lawyer.id))
            )
            if status_filter:
                stmt = stmt.where(LawyerIncomeRecord.status == str(status_filter).strip())

            stmt = (
                stmt.order_by(LawyerIncomeRecord.created_at.desc(), LawyerIncomeRecord.id.desc())
                .offset(offset)
                .limit(batch_size)
            )

            res = await db.execute(stmt)
            rows = res.all()
            if not rows:
                break

            for record, subject in rows:
                yield {
                    "id": int(record.id),
                    "consultation_id": int(record.consultation_id)
                    if record.consultation_id is not None
                    else "",
                    "consultation_subject": str(subject) if isinstance(subject, str) else "",
                    "order_no": str(record.order_no or ""),
                    "user_paid_amount": float(record.user_paid_amount or 0.0),
                    "platform_fee": float(record.platform_fee or 0.0),
                    "lawyer_income": float(record.lawyer_income or 0.0),
                    "withdrawn_amount": float(record.withdrawn_amount or 0.0),
                    "status": str(record.status or ""),
                    "settle_time": record.settle_time,
                    "created_at": record.created_at,
                }

            offset += batch_size

    filename = f"income_records_{int(lawyer.id)}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        _generate_csv_stream(fieldnames, row_generator()),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/lawyer/bank-accounts",
    response_model=LawyerBankAccountListResponse,
    summary="律师-获取收款账户",
)
async def lawyer_list_bank_accounts(
    current_user: Annotated[User, Depends(require_lawyer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lawyer = await settlement_service.get_current_lawyer(db, int(current_user.id))
    if lawyer is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")

    res = await db.execute(
        select(LawyerBankAccount)
        .where(LawyerBankAccount.lawyer_id == int(lawyer.id))
        .order_by(LawyerBankAccount.is_default.desc(), LawyerBankAccount.created_at.desc())
    )
    rows = res.scalars().all()

    items: list[LawyerBankAccountItem] = []
    for r in rows:
        raw_no = settlement_service.decrypt_secret(str(r.account_no))
        items.append(
            LawyerBankAccountItem(
                id=int(r.id),
                lawyer_id=int(r.lawyer_id),
                account_type=str(r.account_type),
                bank_name=str(r.bank_name) if r.bank_name is not None else None,
                account_no_masked=_mask_account_no(str(raw_no)),
                account_holder=str(r.account_holder),
                is_default=bool(r.is_default),
                is_active=bool(r.is_active),
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )

    return LawyerBankAccountListResponse(items=items, total=len(items))


@router.post(
    "/lawyer/bank-accounts",
    response_model=LawyerBankAccountItem,
    summary="律师-添加收款账户",
)
async def lawyer_create_bank_account(
    data: LawyerBankAccountCreate,
    current_user: Annotated[User, Depends(require_lawyer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lawyer = await settlement_service.get_current_lawyer(db, int(current_user.id))
    if lawyer is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")

    row = LawyerBankAccount(
        lawyer_id=int(lawyer.id),
        account_type=str(data.account_type or "bank_card"),
        bank_name=(str(data.bank_name).strip() if data.bank_name else None),
        account_no=settlement_service.encrypt_secret(str(data.account_no).strip()),
        account_holder=str(data.account_holder).strip(),
        is_default=bool(data.is_default),
        is_active=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    if bool(data.is_default):
        _ = await db.execute(
            select(LawyerBankAccount)
            .where(
                LawyerBankAccount.lawyer_id == int(lawyer.id),
                LawyerBankAccount.id != int(row.id),
            )
        )
        await db.execute(
            LawyerBankAccount.__table__.update()
            .where(
                LawyerBankAccount.lawyer_id == int(lawyer.id),
                LawyerBankAccount.id != int(row.id),
            )
            .values(is_default=False)
        )
        await db.commit()

    return LawyerBankAccountItem(
        id=int(row.id),
        lawyer_id=int(row.lawyer_id),
        account_type=str(row.account_type),
        bank_name=str(row.bank_name) if row.bank_name is not None else None,
        account_no_masked=_mask_account_no(str(data.account_no)),
        account_holder=str(row.account_holder),
        is_default=bool(row.is_default),
        is_active=bool(row.is_active),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.put(
    "/lawyer/bank-accounts/{account_id}",
    response_model=LawyerBankAccountItem,
    summary="律师-更新收款账户",
)
async def lawyer_update_bank_account(
    account_id: int,
    data: LawyerBankAccountUpdate,
    current_user: Annotated[User, Depends(require_lawyer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lawyer = await settlement_service.get_current_lawyer(db, int(current_user.id))
    if lawyer is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")

    res = await db.execute(
        select(LawyerBankAccount).where(
            LawyerBankAccount.id == int(account_id),
            LawyerBankAccount.lawyer_id == int(lawyer.id),
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账户不存在")

    if data.bank_name is not None:
        row.bank_name = str(data.bank_name).strip() or None
    if data.account_no is not None:
        row.account_no = settlement_service.encrypt_secret(str(data.account_no).strip())
    if data.account_holder is not None:
        row.account_holder = str(data.account_holder).strip()
    if data.is_active is not None:
        row.is_active = bool(data.is_active)
    if data.is_default is not None:
        row.is_default = bool(data.is_default)

    db.add(row)
    await db.commit()
    await db.refresh(row)

    if bool(row.is_default):
        await db.execute(
            LawyerBankAccount.__table__.update()
            .where(
                LawyerBankAccount.lawyer_id == int(lawyer.id),
                LawyerBankAccount.id != int(row.id),
            )
            .values(is_default=False)
        )
        await db.commit()

    raw_no = settlement_service.decrypt_secret(str(row.account_no))
    return LawyerBankAccountItem(
        id=int(row.id),
        lawyer_id=int(row.lawyer_id),
        account_type=str(row.account_type),
        bank_name=str(row.bank_name) if row.bank_name is not None else None,
        account_no_masked=_mask_account_no(str(raw_no)),
        account_holder=str(row.account_holder),
        is_default=bool(row.is_default),
        is_active=bool(row.is_active),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.delete("/lawyer/bank-accounts/{account_id}", summary="律师-删除收款账户")
async def lawyer_delete_bank_account(
    account_id: int,
    current_user: Annotated[User, Depends(require_lawyer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lawyer = await settlement_service.get_current_lawyer(db, int(current_user.id))
    if lawyer is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")

    res = await db.execute(
        select(LawyerBankAccount).where(
            LawyerBankAccount.id == int(account_id),
            LawyerBankAccount.lawyer_id == int(lawyer.id),
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账户不存在")

    await db.delete(row)
    await db.commit()

    return {"message": "删除成功"}


@router.put(
    "/lawyer/bank-accounts/{account_id}/default",
    summary="律师-设为默认收款账户",
)
async def lawyer_set_default_bank_account(
    account_id: int,
    current_user: Annotated[User, Depends(require_lawyer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lawyer = await settlement_service.get_current_lawyer(db, int(current_user.id))
    if lawyer is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")

    res = await db.execute(
        select(LawyerBankAccount).where(
            LawyerBankAccount.id == int(account_id),
            LawyerBankAccount.lawyer_id == int(lawyer.id),
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账户不存在")

    await db.execute(
        LawyerBankAccount.__table__.update()
        .where(LawyerBankAccount.lawyer_id == int(lawyer.id))
        .values(is_default=False)
    )
    await db.execute(
        LawyerBankAccount.__table__.update()
        .where(LawyerBankAccount.id == int(row.id))
        .values(is_default=True)
    )
    await db.commit()

    return {"message": "已设为默认"}


@router.get(
    "/lawyer/withdrawals",
    response_model=WithdrawalListResponse,
    summary="律师-提现记录",
)
async def lawyer_list_withdrawals(
    current_user: Annotated[User, Depends(require_lawyer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    lawyer = await settlement_service.get_current_lawyer(db, int(current_user.id))
    if lawyer is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")

    q = select(WithdrawalRequest).where(WithdrawalRequest.lawyer_id == int(lawyer.id))
    cq = select(func.count(WithdrawalRequest.id)).where(WithdrawalRequest.lawyer_id == int(lawyer.id))

    if status_filter:
        q = q.where(WithdrawalRequest.status == str(status_filter).strip())
        cq = cq.where(WithdrawalRequest.status == str(status_filter).strip())

    total = int((await db.execute(cq)).scalar() or 0)
    res = await db.execute(
        q.order_by(WithdrawalRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )

    rows = res.scalars().all()

    lawyer_ids = sorted({int(x.lawyer_id) for x in rows if x.lawyer_id is not None})
    lawyer_name_by_id: dict[int, str] = {}
    lawyer_rating_by_id: dict[int, float] = {}
    lawyer_completed_by_id: dict[int, int] = {}
    if lawyer_ids:
        lr = await db.execute(select(Lawyer).where(Lawyer.id.in_(lawyer_ids)))
        for l in lr.scalars().all():
            lid = int(l.id)
            lawyer_name_by_id[lid] = str(getattr(l, "name", "") or "")
            lawyer_rating_by_id[lid] = float(getattr(l, "rating", 0.0) or 0.0)

        cnt_res = await db.execute(
            select(LawyerConsultation.lawyer_id, func.count(LawyerConsultation.id))
            .where(
                LawyerConsultation.lawyer_id.in_(lawyer_ids),
                LawyerConsultation.status == "completed",
            )
            .group_by(LawyerConsultation.lawyer_id)
        )
        for lid, cnt in cnt_res.all():
            if lid is None:
                continue
            lawyer_completed_by_id[int(lid)] = int(cnt or 0)

    items: list[WithdrawalItem] = []
    for w in rows:
        lid = int(w.lawyer_id)
        rating = float(lawyer_rating_by_id.get(lid, 0.0))
        completed = int(lawyer_completed_by_id.get(lid, 0))
        platform_fee_rate = settlement_service.choose_platform_fee_rate(lid, rating, completed)

        items.append(
            WithdrawalItem(
                id=int(w.id),
                request_no=str(w.request_no),
                lawyer_id=int(w.lawyer_id),
                lawyer_name=str(lawyer_name_by_id.get(lid) or "") or None,
                lawyer_rating=rating,
                lawyer_completed_count=completed,
                platform_fee_rate=float(platform_fee_rate),
                amount=float(w.amount),
                fee=float(w.fee),
                actual_amount=float(w.actual_amount),
                withdraw_method=str(w.withdraw_method),
                account_info_masked=_mask_account_info(str(w.account_info)),
                status=str(w.status),
                reject_reason=str(w.reject_reason) if w.reject_reason is not None else None,
                admin_id=int(w.admin_id) if w.admin_id is not None else None,
                reviewed_at=w.reviewed_at,
                completed_at=w.completed_at,
                remark=str(w.remark) if w.remark is not None else None,
                created_at=w.created_at,
                updated_at=w.updated_at,
            )
        )

    return WithdrawalListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/lawyer/withdrawals/{withdrawal_id}",
    response_model=WithdrawalItem,
    summary="律师-提现详情",
)
async def lawyer_get_withdrawal(
    withdrawal_id: int,
    current_user: Annotated[User, Depends(require_lawyer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lawyer = await settlement_service.get_current_lawyer(db, int(current_user.id))
    if lawyer is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")

    res = await db.execute(
        select(WithdrawalRequest).where(
            WithdrawalRequest.id == int(withdrawal_id),
            WithdrawalRequest.lawyer_id == int(lawyer.id),
        )
    )
    w = res.scalar_one_or_none()
    if w is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提现申请不存在")

    return WithdrawalItem(
        id=int(w.id),
        request_no=str(w.request_no),
        lawyer_id=int(w.lawyer_id),
        amount=float(w.amount),
        fee=float(w.fee),
        actual_amount=float(w.actual_amount),
        withdraw_method=str(w.withdraw_method),
        account_info_masked=_mask_account_info(str(w.account_info)),
        status=str(w.status),
        reject_reason=str(w.reject_reason) if w.reject_reason is not None else None,
        admin_id=int(w.admin_id) if w.admin_id is not None else None,
        reviewed_at=w.reviewed_at,
        completed_at=w.completed_at,
        remark=str(w.remark) if w.remark is not None else None,
        created_at=w.created_at,
        updated_at=w.updated_at,
    )


@router.post(
    "/lawyer/withdrawals",
    response_model=WithdrawalItem,
    summary="律师-提交提现申请",
)
async def lawyer_create_withdrawal(
    data: WithdrawalCreateRequest,
    current_user: Annotated[User, Depends(require_lawyer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lawyer = await settlement_service.get_current_lawyer(db, int(current_user.id))
    if lawyer is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")

    wr = await settlement_service.create_withdrawal_request(
        db,
        lawyer_id=int(lawyer.id),
        amount=float(data.amount),
        withdraw_method=str(data.withdraw_method),
        bank_account_id=int(data.bank_account_id),
    )

    return WithdrawalItem(
        id=int(wr.id),
        request_no=str(wr.request_no),
        lawyer_id=int(wr.lawyer_id),
        amount=float(wr.amount),
        fee=float(wr.fee),
        actual_amount=float(wr.actual_amount),
        withdraw_method=str(wr.withdraw_method),
        account_info_masked=_mask_account_info(str(wr.account_info)),
        status=str(wr.status),
        reject_reason=str(wr.reject_reason) if wr.reject_reason is not None else None,
        admin_id=int(wr.admin_id) if wr.admin_id is not None else None,
        reviewed_at=wr.reviewed_at,
        completed_at=wr.completed_at,
        remark=str(wr.remark) if wr.remark is not None else None,
        created_at=wr.created_at,
        updated_at=wr.updated_at,
    )


@router.get(
    "/admin/withdrawals",
    response_model=WithdrawalListResponse,
    summary="管理员-提现申请列表",
)
async def admin_list_withdrawals(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    keyword: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    _ = current_user

    q = select(WithdrawalRequest)
    cq = select(func.count(WithdrawalRequest.id))

    if status_filter:
        q = q.where(WithdrawalRequest.status == str(status_filter).strip())
        cq = cq.where(WithdrawalRequest.status == str(status_filter).strip())

    if keyword:
        kw = f"%{keyword.strip()}%"
        q = q.where(WithdrawalRequest.request_no.ilike(kw))
        cq = cq.where(WithdrawalRequest.request_no.ilike(kw))

    total = int((await db.execute(cq)).scalar() or 0)
    res = await db.execute(
        q.order_by(WithdrawalRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )

    rows = res.scalars().all()

    lawyer_ids = sorted({int(x.lawyer_id) for x in rows if x.lawyer_id is not None})
    lawyer_name_by_id: dict[int, str] = {}
    lawyer_rating_by_id: dict[int, float] = {}
    lawyer_completed_by_id: dict[int, int] = {}
    if lawyer_ids:
        lr = await db.execute(select(Lawyer).where(Lawyer.id.in_(lawyer_ids)))
        for l in lr.scalars().all():
            lid = int(l.id)
            lawyer_name_by_id[lid] = str(getattr(l, "name", "") or "")
            lawyer_rating_by_id[lid] = float(getattr(l, "rating", 0.0) or 0.0)

        cnt_res = await db.execute(
            select(LawyerConsultation.lawyer_id, func.count(LawyerConsultation.id))
            .where(
                LawyerConsultation.lawyer_id.in_(lawyer_ids),
                LawyerConsultation.status == "completed",
            )
            .group_by(LawyerConsultation.lawyer_id)
        )
        for lid, cnt in cnt_res.all():
            if lid is None:
                continue
            lawyer_completed_by_id[int(lid)] = int(cnt or 0)

    items: list[WithdrawalItem] = []
    for w in rows:
        lid = int(w.lawyer_id)
        rating = float(lawyer_rating_by_id.get(lid, 0.0))
        completed = int(lawyer_completed_by_id.get(lid, 0))
        platform_fee_rate = settlement_service.choose_platform_fee_rate(lid, rating, completed)

        items.append(
            WithdrawalItem(
                id=int(w.id),
                request_no=str(w.request_no),
                lawyer_id=int(w.lawyer_id),
                lawyer_name=str(lawyer_name_by_id.get(lid) or "") or None,
                lawyer_rating=float(rating),
                lawyer_completed_count=int(completed),
                platform_fee_rate=float(platform_fee_rate),
                amount=float(w.amount),
                fee=float(w.fee),
                actual_amount=float(w.actual_amount),
                withdraw_method=str(w.withdraw_method),
                account_info_masked=_mask_account_info(str(w.account_info)),
                status=str(w.status),
                reject_reason=str(w.reject_reason) if w.reject_reason is not None else None,
                admin_id=int(w.admin_id) if w.admin_id is not None else None,
                reviewed_at=w.reviewed_at,
                completed_at=w.completed_at,
                remark=str(w.remark) if w.remark is not None else None,
                created_at=w.created_at,
                updated_at=w.updated_at,
            )
        )

    return WithdrawalListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/admin/withdrawals/export",
    summary="管理员-导出提现申请",
)
async def admin_export_withdrawals(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    keyword: Annotated[str | None, Query()] = None,
):
    _ = current_user

    fieldnames = [
        "id",
        "request_no",
        "lawyer_id",
        "lawyer_name",
        "amount",
        "fee",
        "actual_amount",
        "withdraw_method",
        "account_info_masked",
        "status",
        "reject_reason",
        "admin_id",
        "reviewed_at",
        "completed_at",
        "remark",
        "created_at",
    ]

    async def row_generator():
        batch_size = 1000
        offset = 0
        while True:
            q = select(WithdrawalRequest)
            if status_filter:
                q = q.where(WithdrawalRequest.status == str(status_filter).strip())
            if keyword:
                kw = f"%{keyword.strip()}%"
                q = q.where(WithdrawalRequest.request_no.ilike(kw))

            res = await db.execute(
                q.order_by(WithdrawalRequest.created_at.desc(), WithdrawalRequest.id.desc())
                .offset(offset)
                .limit(batch_size)
            )
            rows = res.scalars().all()
            if not rows:
                break

            lawyer_ids = sorted({int(x.lawyer_id) for x in rows if x.lawyer_id is not None})
            lawyer_name_by_id: dict[int, str] = {}
            if lawyer_ids:
                lr = await db.execute(select(Lawyer.id, Lawyer.name).where(Lawyer.id.in_(lawyer_ids)))
                for lid, name in lr.all():
                    if lid is None:
                        continue
                    lawyer_name_by_id[int(lid)] = str(name or "")

            for w in rows:
                lid = int(w.lawyer_id)
                yield {
                    "id": int(w.id),
                    "request_no": str(w.request_no),
                    "lawyer_id": lid,
                    "lawyer_name": str(lawyer_name_by_id.get(lid) or "") or "",
                    "amount": float(w.amount),
                    "fee": float(w.fee),
                    "actual_amount": float(w.actual_amount),
                    "withdraw_method": str(w.withdraw_method),
                    "account_info_masked": _mask_account_info(str(w.account_info)),
                    "status": str(w.status),
                    "reject_reason": str(w.reject_reason or ""),
                    "admin_id": int(w.admin_id) if w.admin_id is not None else "",
                    "reviewed_at": w.reviewed_at,
                    "completed_at": w.completed_at,
                    "remark": str(w.remark or ""),
                    "created_at": w.created_at,
                }

            offset += batch_size

    filename = f"withdrawals_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        _generate_csv_stream(fieldnames, row_generator()),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/admin/withdrawals/{withdrawal_id}",
    response_model=AdminWithdrawalDetailResponse,
    summary="管理员-提现详情",
)
async def admin_get_withdrawal(
    withdrawal_id: int,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = current_user
    res = await db.execute(select(WithdrawalRequest).where(WithdrawalRequest.id == int(withdrawal_id)))
    wr = res.scalar_one_or_none()
    if wr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提现申请不存在")

    lawyer_res = await db.execute(select(Lawyer).where(Lawyer.id == int(wr.lawyer_id)))
    lawyer = lawyer_res.scalar_one_or_none()
    lawyer_name = str(getattr(lawyer, "name", "") or "") if lawyer is not None else ""
    lawyer_rating = float(getattr(lawyer, "rating", 0.0) or 0.0) if lawyer is not None else 0.0

    completed_res = await db.execute(
        select(func.count(LawyerConsultation.id)).where(
            LawyerConsultation.lawyer_id == int(wr.lawyer_id),
            LawyerConsultation.status == "completed",
        )
    )
    completed = int(completed_res.scalar() or 0)
    platform_fee_rate = settlement_service.choose_platform_fee_rate(int(wr.lawyer_id), lawyer_rating, completed)

    base = AdminWithdrawalDetailResponse.model_validate(wr)
    return base.model_copy(
        update={
            "lawyer_name": lawyer_name or None,
            "lawyer_rating": float(lawyer_rating),
            "lawyer_completed_count": int(completed),
            "platform_fee_rate": float(platform_fee_rate),
            "account_info": _mask_account_info(str(getattr(wr, "account_info", "") or "")),
        }
    )


@router.get(
    "/admin/income-records/export",
    summary="管理员-导出收入记录",
)
async def admin_export_income_records(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    lawyer_id: Annotated[int | None, Query(ge=1)] = None,
    start_at: Annotated[datetime | None, Query(alias="from")] = None,
    end_at: Annotated[datetime | None, Query(alias="to")] = None,
):
    _ = current_user

    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        month_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        month_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)

    s = start_at or month_start
    e = end_at or month_end

    fieldnames = [
        "id",
        "lawyer_id",
        "lawyer_name",
        "consultation_id",
        "consultation_subject",
        "order_no",
        "user_paid_amount",
        "platform_fee",
        "lawyer_income",
        "withdrawn_amount",
        "status",
        "settle_time",
        "created_at",
    ]

    async def row_generator():
        batch_size = 2000
        offset = 0
        while True:
            stmt = (
                select(LawyerIncomeRecord, Lawyer.name, LawyerConsultation.subject)
                .join(Lawyer, Lawyer.id == LawyerIncomeRecord.lawyer_id)
                .outerjoin(LawyerConsultation, LawyerConsultation.id == LawyerIncomeRecord.consultation_id)
                .where(LawyerIncomeRecord.created_at >= s, LawyerIncomeRecord.created_at < e)
            )
            if status_filter:
                stmt = stmt.where(LawyerIncomeRecord.status == str(status_filter).strip())
            if lawyer_id:
                stmt = stmt.where(LawyerIncomeRecord.lawyer_id == int(lawyer_id))

            stmt = (
                stmt.order_by(LawyerIncomeRecord.created_at.desc(), LawyerIncomeRecord.id.desc())
                .offset(offset)
                .limit(batch_size)
            )

            res = await db.execute(stmt)
            rows = res.all()
            if not rows:
                break

            for record, lawyer_name, subject in rows:
                yield {
                    "id": int(record.id),
                    "lawyer_id": int(record.lawyer_id),
                    "lawyer_name": str(lawyer_name or ""),
                    "consultation_id": int(record.consultation_id) if record.consultation_id is not None else "",
                    "consultation_subject": str(subject) if isinstance(subject, str) else "",
                    "order_no": str(record.order_no or ""),
                    "user_paid_amount": float(record.user_paid_amount or 0.0),
                    "platform_fee": float(record.platform_fee or 0.0),
                    "lawyer_income": float(record.lawyer_income or 0.0),
                    "withdrawn_amount": float(record.withdrawn_amount or 0.0),
                    "status": str(record.status or ""),
                    "settle_time": record.settle_time,
                    "created_at": record.created_at,
                }

            offset += batch_size

    filename = f"income_records_{s.strftime('%Y%m%d')}_{e.strftime('%Y%m%d')}_{datetime.now(timezone.utc).strftime('%H%M%S')}.csv"
    return StreamingResponse(
        _generate_csv_stream(fieldnames, row_generator()),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post(
    "/admin/withdrawals/{withdrawal_id}/approve",
    response_model=AdminWithdrawalDetailResponse,
    summary="管理员-通过提现",
)
async def admin_approve_withdrawal(
    withdrawal_id: int,
    data: WithdrawalAdminActionRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    wr = await settlement_service.admin_set_withdrawal_status(
        db,
        withdrawal_id=int(withdrawal_id),
        action="approve",
        admin_id=int(current_user.id),
        remark=str(data.remark).strip() if data.remark else None,
    )
    return AdminWithdrawalDetailResponse.model_validate(wr)


@router.get(
    "/admin/settlement-stats",
    response_model=AdminSettlementStatsResponse,
    summary="管理员-结算统计",
)
async def admin_settlement_stats(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = current_user

    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        month_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        month_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)

    def _sum_cents_expr(col_cents, col_float):
        return func.coalesce(
            col_cents,
            sa_cast(func.round(func.coalesce(col_float, 0) * 100), Integer),
        )

    def _cents_to_amount(cents: int | None) -> float:
        c = int(cents or 0)
        return float((Decimal(c) / 100).quantize(Decimal("0.01")))

    wallet_total_income_cents = func.sum(_sum_cents_expr(LawyerWallet.total_income_cents, LawyerWallet.total_income))
    wallet_withdrawn_cents = func.sum(
        _sum_cents_expr(LawyerWallet.withdrawn_amount_cents, LawyerWallet.withdrawn_amount)
    )
    wallet_pending_cents = func.sum(_sum_cents_expr(LawyerWallet.pending_amount_cents, LawyerWallet.pending_amount))
    wallet_frozen_cents = func.sum(_sum_cents_expr(LawyerWallet.frozen_amount_cents, LawyerWallet.frozen_amount))
    wallet_available_cents = func.sum(
        _sum_cents_expr(LawyerWallet.available_amount_cents, LawyerWallet.available_amount)
    )

    wallet_row = await db.execute(
        select(
            wallet_total_income_cents,
            wallet_withdrawn_cents,
            wallet_pending_cents,
            wallet_frozen_cents,
            wallet_available_cents,
        ).select_from(LawyerWallet)
    )
    wallet_vals = wallet_row.first() or (0, 0, 0, 0, 0)
    wallet_summary = SettlementStatsWalletSummary(
        total_income=_cents_to_amount(wallet_vals[0]),
        withdrawn_amount=_cents_to_amount(wallet_vals[1]),
        pending_amount=_cents_to_amount(wallet_vals[2]),
        frozen_amount=_cents_to_amount(wallet_vals[3]),
        available_amount=_cents_to_amount(wallet_vals[4]),
    )

    withdraw_amount_cents_expr = _sum_cents_expr(WithdrawalRequest.amount_cents, WithdrawalRequest.amount)

    pending_count = int(
        (await db.execute(select(func.count(WithdrawalRequest.id)).where(WithdrawalRequest.status == "pending"))).scalar()
        or 0
    )
    pending_amount_cents = int(
        (
            await db.execute(
                select(func.sum(withdraw_amount_cents_expr)).where(WithdrawalRequest.status == "pending")
            )
        ).scalar()
        or 0
    )

    approved_count = int(
        (await db.execute(select(func.count(WithdrawalRequest.id)).where(WithdrawalRequest.status == "approved"))).scalar()
        or 0
    )
    approved_amount_cents = int(
        (
            await db.execute(
                select(func.sum(withdraw_amount_cents_expr)).where(WithdrawalRequest.status == "approved")
            )
        ).scalar()
        or 0
    )

    completed_month_count = int(
        (
            await db.execute(
                select(func.count(WithdrawalRequest.id)).where(
                    WithdrawalRequest.status == "completed",
                    WithdrawalRequest.completed_at.is_not(None),
                    WithdrawalRequest.completed_at >= month_start,
                    WithdrawalRequest.completed_at < month_end,
                )
            )
        ).scalar()
        or 0
    )
    completed_month_amount_cents = int(
        (
            await db.execute(
                select(func.sum(withdraw_amount_cents_expr)).where(
                    WithdrawalRequest.status == "completed",
                    WithdrawalRequest.completed_at.is_not(None),
                    WithdrawalRequest.completed_at >= month_start,
                    WithdrawalRequest.completed_at < month_end,
                )
            )
        ).scalar()
        or 0
    )

    withdrawal_summary = SettlementStatsWithdrawalSummary(
        pending_count=int(pending_count),
        pending_amount=_cents_to_amount(pending_amount_cents),
        approved_count=int(approved_count),
        approved_amount=_cents_to_amount(approved_amount_cents),
        completed_month_count=int(completed_month_count),
        completed_month_amount=_cents_to_amount(completed_month_amount_cents),
    )

    income_fee_cents_expr = _sum_cents_expr(LawyerIncomeRecord.platform_fee_cents, LawyerIncomeRecord.platform_fee)
    income_income_cents_expr = _sum_cents_expr(
        LawyerIncomeRecord.lawyer_income_cents, LawyerIncomeRecord.lawyer_income
    )

    platform_fee_month_cents = int(
        (
            await db.execute(
                select(func.sum(income_fee_cents_expr)).where(
                    LawyerIncomeRecord.created_at >= month_start,
                    LawyerIncomeRecord.created_at < month_end,
                )
            )
        ).scalar()
        or 0
    )
    lawyer_income_month_cents = int(
        (
            await db.execute(
                select(func.sum(income_income_cents_expr)).where(
                    LawyerIncomeRecord.created_at >= month_start,
                    LawyerIncomeRecord.created_at < month_end,
                )
            )
        ).scalar()
        or 0
    )

    income_sum = func.sum(income_income_cents_expr).label("income_sum")
    fee_sum = func.sum(income_fee_cents_expr).label("fee_sum")
    rec_cnt = func.count(LawyerIncomeRecord.id).label("rec_cnt")

    top_res = await db.execute(
        select(
            LawyerIncomeRecord.lawyer_id,
            Lawyer.name,
            rec_cnt,
            income_sum,
            fee_sum,
        )
        .join(Lawyer, Lawyer.id == LawyerIncomeRecord.lawyer_id)
        .where(
            LawyerIncomeRecord.created_at >= month_start,
            LawyerIncomeRecord.created_at < month_end,
        )
        .group_by(LawyerIncomeRecord.lawyer_id, Lawyer.name)
        .order_by(income_sum.desc())
        .limit(20)
    )

    top_lawyers: list[SettlementStatsTopLawyerItem] = []
    for lid, name, cnt, inc_cents, fee_cents in top_res.all():
        if lid is None:
            continue
        top_lawyers.append(
            SettlementStatsTopLawyerItem(
                lawyer_id=int(lid),
                lawyer_name=str(name) if name is not None else None,
                income_records=int(cnt or 0),
                lawyer_income=_cents_to_amount(int(inc_cents or 0)),
                platform_fee=_cents_to_amount(int(fee_cents or 0)),
            )
        )

    return AdminSettlementStatsResponse(
        month_start=month_start,
        month_end=month_end,
        wallet_summary=wallet_summary,
        withdrawal_summary=withdrawal_summary,
        platform_fee_month_total=_cents_to_amount(platform_fee_month_cents),
        lawyer_income_month_total=_cents_to_amount(lawyer_income_month_cents),
        top_lawyers=top_lawyers,
    )


@router.post(
    "/admin/withdrawals/{withdrawal_id}/reject",
    response_model=AdminWithdrawalDetailResponse,
    summary="管理员-驳回提现",
)
async def admin_reject_withdrawal(
    withdrawal_id: int,
    data: WithdrawalRejectRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    wr = await settlement_service.admin_set_withdrawal_status(
        db,
        withdrawal_id=int(withdrawal_id),
        action="reject",
        admin_id=int(current_user.id),
        reject_reason=str(data.reject_reason),
        remark=str(data.remark).strip() if data.remark else None,
    )
    return AdminWithdrawalDetailResponse.model_validate(wr)


@router.post(
    "/admin/withdrawals/{withdrawal_id}/complete",
    response_model=AdminWithdrawalDetailResponse,
    summary="管理员-标记打款完成",
)
async def admin_complete_withdrawal(
    withdrawal_id: int,
    data: WithdrawalAdminActionRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    wr = await settlement_service.admin_set_withdrawal_status(
        db,
        withdrawal_id=int(withdrawal_id),
        action="complete",
        admin_id=int(current_user.id),
        remark=str(data.remark).strip() if data.remark else None,
    )
    return AdminWithdrawalDetailResponse.model_validate(wr)


@router.post(
    "/admin/withdrawals/{withdrawal_id}/fail",
    response_model=AdminWithdrawalDetailResponse,
    summary="管理员-标记打款失败",
)
async def admin_fail_withdrawal(
    withdrawal_id: int,
    data: WithdrawalAdminActionRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    wr = await settlement_service.admin_set_withdrawal_status(
        db,
        withdrawal_id=int(withdrawal_id),
        action="fail",
        admin_id=int(current_user.id),
        remark=str(data.remark).strip() if data.remark else None,
    )
    return AdminWithdrawalDetailResponse.model_validate(wr)


@router.post("/admin/settlement/run", summary="管理员-执行到期结算")
async def admin_run_settlement(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = current_user
    return await settlement_service.settle_due_income_records(db)
