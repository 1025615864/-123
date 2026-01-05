import csv
import io
import json
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lawfirm import Lawyer
from app.models.settlement import LawyerBankAccount, LawyerIncomeRecord, LawyerWallet, WithdrawalRequest
from app.models.user import User
from app.utils.security import create_access_token, hash_password


async def _create_user(
    session: AsyncSession,
    *,
    username: str,
    email: str,
    role: str,
) -> User:
    u = User(
        username=username,
        email=email,
        nickname=username,
        hashed_password=hash_password("Test123456"),
        role=role,
        is_active=True,
    )
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


async def _create_lawyer_profile(session: AsyncSession, *, user_id: int) -> Lawyer:
    lawyer = Lawyer(
        user_id=int(user_id),
        firm_id=None,
        name="张律师",
        avatar=None,
        title="律师",
        license_no="TEST-LICENSE",
        phone=None,
        email=None,
        introduction=None,
        specialties=None,
        experience_years=1,
        case_count=0,
        rating=4.6,
        review_count=10,
        consultation_fee=200.0,
        is_verified=True,
        is_active=True,
    )
    session.add(lawyer)
    await session.commit()
    await session.refresh(lawyer)
    return lawyer


async def _seed_wallet(session: AsyncSession, *, lawyer_id: int, total_income: float) -> LawyerWallet:
    wallet = LawyerWallet(
        lawyer_id=int(lawyer_id),
        total_income=float(total_income),
        withdrawn_amount=0.0,
        pending_amount=0.0,
        frozen_amount=0.0,
        available_amount=float(total_income),
    )
    session.add(wallet)
    await session.commit()
    await session.refresh(wallet)
    return wallet


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_settlement_withdrawal_flow_and_bank_account_encrypted(
    client: AsyncClient,
    test_session: AsyncSession,
):
    lawyer_user = await _create_user(
        test_session,
        username="lawyer_settle",
        email="lawyer_settle@example.com",
        role="lawyer",
    )
    admin_user = await _create_user(
        test_session,
        username="admin_settle",
        email="admin_settle@example.com",
        role="admin",
    )

    lawyer = await _create_lawyer_profile(test_session, user_id=int(lawyer_user.id))
    await _seed_wallet(test_session, lawyer_id=int(lawyer.id), total_income=1000.0)

    # Create bank account
    create_bank_res = await client.post(
        "/api/lawyer/bank-accounts",
        headers=_auth_header(lawyer_user),
        json={
            "account_type": "bank_card",
            "bank_name": "工商银行",
            "account_no": "6222333344445555",
            "account_holder": "张律师",
            "is_default": True,
        },
    )
    assert create_bank_res.status_code == 200
    bank_payload = create_bank_res.json()
    bank_id = int(bank_payload["id"])
    assert str(bank_payload["account_no_masked"]).endswith("5555")

    # Ensure DB stored encrypted value
    bank_row = (
        await test_session.execute(select(LawyerBankAccount).where(LawyerBankAccount.id == bank_id))
    ).scalar_one()
    assert str(bank_row.account_no).startswith("enc:")

    # Update bank account number and ensure response masked uses decrypted value
    update_bank_res = await client.put(
        f"/api/lawyer/bank-accounts/{bank_id}",
        headers=_auth_header(lawyer_user),
        json={"account_no": "1234567890123456"},
    )
    assert update_bank_res.status_code == 200
    assert str(update_bank_res.json()["account_no_masked"]).endswith("3456")

    bank_row2 = (
        await test_session.execute(select(LawyerBankAccount).where(LawyerBankAccount.id == bank_id))
    ).scalar_one()
    assert str(bank_row2.account_no).startswith("enc:")

    # Exceed withdraw max (default 50000)
    too_big = await client.post(
        "/api/lawyer/withdrawals",
        headers=_auth_header(lawyer_user),
        json={"amount": 60000, "withdraw_method": "bank_card", "bank_account_id": bank_id},
    )
    assert too_big.status_code == 400

    # Create withdrawal
    w1 = await client.post(
        "/api/lawyer/withdrawals",
        headers=_auth_header(lawyer_user),
        json={"amount": 200, "withdraw_method": "bank_card", "bank_account_id": bank_id},
    )
    assert w1.status_code == 200
    w1_payload = w1.json()
    w1_id = int(w1_payload["id"])
    assert str(w1_payload["status"]).lower() == "pending"
    assert "3456" in str(w1_payload["account_info_masked"])

    wallet_after_create = (
        await test_session.execute(select(LawyerWallet).where(LawyerWallet.lawyer_id == int(lawyer.id)))
    ).scalar_one()
    assert float(wallet_after_create.frozen_amount) == pytest.approx(200.0)
    assert float(wallet_after_create.available_amount) == pytest.approx(800.0)

    # Admin detail should not expose enc: token
    admin_detail = await client.get(
        f"/api/admin/withdrawals/{w1_id}",
        headers=_auth_header(admin_user),
    )
    assert admin_detail.status_code == 200
    assert "enc:" not in str(admin_detail.json().get("account_info") or "")

    # Approve then complete
    approve = await client.post(
        f"/api/admin/withdrawals/{w1_id}/approve",
        headers=_auth_header(admin_user),
        json={"remark": "ok"},
    )
    assert approve.status_code == 200
    assert str(approve.json()["status"]).lower() == "approved"

    complete = await client.post(
        f"/api/admin/withdrawals/{w1_id}/complete",
        headers=_auth_header(admin_user),
        json={"remark": "paid"},
    )
    assert complete.status_code == 200
    assert str(complete.json()["status"]).lower() == "completed"

    wallet_after_complete = (
        await test_session.execute(select(LawyerWallet).where(LawyerWallet.lawyer_id == int(lawyer.id)))
    ).scalar_one()
    assert float(wallet_after_complete.frozen_amount) == pytest.approx(0.0)
    assert float(wallet_after_complete.withdrawn_amount) == pytest.approx(200.0)
    assert float(wallet_after_complete.available_amount) == pytest.approx(800.0)

    # Reject flow: create a second withdrawal then reject
    w2 = await client.post(
        "/api/lawyer/withdrawals",
        headers=_auth_header(lawyer_user),
        json={"amount": 100, "withdraw_method": "bank_card", "bank_account_id": bank_id},
    )
    assert w2.status_code == 200
    w2_id = int(w2.json()["id"])

    reject = await client.post(
        f"/api/admin/withdrawals/{w2_id}/reject",
        headers=_auth_header(admin_user),
        json={"reject_reason": "资料不全", "remark": "fix"},
    )
    assert reject.status_code == 200
    assert str(reject.json()["status"]).lower() == "rejected"

    wallet_after_reject = (
        await test_session.execute(select(LawyerWallet).where(LawyerWallet.lawyer_id == int(lawyer.id)))
    ).scalar_one()
    assert float(wallet_after_reject.frozen_amount) == pytest.approx(0.0)
    assert float(wallet_after_reject.available_amount) == pytest.approx(800.0)

    # Fail flow: create third withdrawal, approve then fail -> return funds
    w3 = await client.post(
        "/api/lawyer/withdrawals",
        headers=_auth_header(lawyer_user),
        json={"amount": 100, "withdraw_method": "bank_card", "bank_account_id": bank_id},
    )
    assert w3.status_code == 200
    w3_id = int(w3.json()["id"])

    approve3 = await client.post(
        f"/api/admin/withdrawals/{w3_id}/approve",
        headers=_auth_header(admin_user),
        json={"remark": "ok"},
    )
    assert approve3.status_code == 200

    fail3 = await client.post(
        f"/api/admin/withdrawals/{w3_id}/fail",
        headers=_auth_header(admin_user),
        json={"remark": "bank error"},
    )
    assert fail3.status_code == 200
    assert str(fail3.json()["status"]).lower() == "failed"

    wallet_after_fail = (
        await test_session.execute(select(LawyerWallet).where(LawyerWallet.lawyer_id == int(lawyer.id)))
    ).scalar_one()
    assert float(wallet_after_fail.frozen_amount) == pytest.approx(0.0)
    assert float(wallet_after_fail.available_amount) == pytest.approx(800.0)


@pytest.mark.asyncio
async def test_lawyer_export_income_records_csv_only_current_lawyer_and_status_filter(
    client: AsyncClient,
    test_session: AsyncSession,
):
    lawyer_user_1 = await _create_user(
        test_session,
        username="lawyer_export_1",
        email="lawyer_export_1@example.com",
        role="lawyer",
    )
    lawyer_user_2 = await _create_user(
        test_session,
        username="lawyer_export_2",
        email="lawyer_export_2@example.com",
        role="lawyer",
    )

    lawyer_1 = await _create_lawyer_profile(test_session, user_id=int(lawyer_user_1.id))
    lawyer_2 = await _create_lawyer_profile(test_session, user_id=int(lawyer_user_2.id))

    now = datetime.now(timezone.utc)

    r1 = LawyerIncomeRecord(
        lawyer_id=int(lawyer_1.id),
        consultation_id=None,
        order_no="ORD-1",
        user_paid_amount=100.0,
        platform_fee=10.0,
        lawyer_income=90.0,
        withdrawn_amount=0.0,
        status="settled",
        settle_time=now,
        created_at=now,
    )
    r2 = LawyerIncomeRecord(
        lawyer_id=int(lawyer_1.id),
        consultation_id=None,
        order_no="ORD-2",
        user_paid_amount=200.0,
        platform_fee=20.0,
        lawyer_income=180.0,
        withdrawn_amount=0.0,
        status="pending",
        settle_time=None,
        created_at=now,
    )
    r3 = LawyerIncomeRecord(
        lawyer_id=int(lawyer_2.id),
        consultation_id=None,
        order_no="ORD-3",
        user_paid_amount=300.0,
        platform_fee=30.0,
        lawyer_income=270.0,
        withdrawn_amount=0.0,
        status="settled",
        settle_time=now,
        created_at=now,
    )

    test_session.add_all([r1, r2, r3])
    await test_session.commit()
    await test_session.refresh(r1)
    await test_session.refresh(r2)
    await test_session.refresh(r3)

    # Export (no status filter) -> only current lawyer records
    export_res = await client.get(
        "/api/lawyer/income-records/export",
        headers=_auth_header(lawyer_user_1),
    )
    assert export_res.status_code == 200
    assert str(export_res.headers.get("content-type") or "").startswith("text/csv")
    assert "attachment" in str(export_res.headers.get("content-disposition") or "").lower()

    body_text = export_res.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(body_text))
    rows = list(reader)

    ids = {int(r["id"]) for r in rows if str(r.get("id") or "").strip()}
    assert int(r1.id) in ids
    assert int(r2.id) in ids
    assert int(r3.id) not in ids

    # Export (status=settled) -> only settled records for current lawyer
    export_res2 = await client.get(
        "/api/lawyer/income-records/export",
        headers=_auth_header(lawyer_user_1),
        params={"status": "settled"},
    )
    assert export_res2.status_code == 200
    body_text2 = export_res2.content.decode("utf-8-sig")
    reader2 = csv.DictReader(io.StringIO(body_text2))
    rows2 = list(reader2)

    ids2 = {int(r["id"]) for r in rows2 if str(r.get("id") or "").strip()}
    assert int(r1.id) in ids2
    assert int(r2.id) not in ids2
    assert int(r3.id) not in ids2


@pytest.mark.asyncio
async def test_admin_export_withdrawals_csv_filter_status_and_keyword(
    client: AsyncClient,
    test_session: AsyncSession,
):
    admin_user = await _create_user(
        test_session,
        username="admin_export_wd",
        email="admin_export_wd@example.com",
        role="admin",
    )
    lawyer_user_1 = await _create_user(
        test_session,
        username="lawyer_export_wd_1",
        email="lawyer_export_wd_1@example.com",
        role="lawyer",
    )
    lawyer_user_2 = await _create_user(
        test_session,
        username="lawyer_export_wd_2",
        email="lawyer_export_wd_2@example.com",
        role="lawyer",
    )

    lawyer_1 = await _create_lawyer_profile(test_session, user_id=int(lawyer_user_1.id))
    lawyer_2 = await _create_lawyer_profile(test_session, user_id=int(lawyer_user_2.id))

    now = datetime.now(timezone.utc)
    w1 = WithdrawalRequest(
        request_no="WTEST_EXPORT_0001",
        lawyer_id=int(lawyer_1.id),
        amount=100.0,
        fee=0.0,
        actual_amount=100.0,
        withdraw_method="bank_card",
        account_info=json.dumps(
            {
                "account_holder": "张律师",
                "account_no": "6222333344445555",
                "bank_name": "工商银行",
            },
            ensure_ascii=False,
        ),
        status="pending",
        created_at=now,
    )
    w2 = WithdrawalRequest(
        request_no="WTEST_EXPORT_0002",
        lawyer_id=int(lawyer_2.id),
        amount=200.0,
        fee=0.0,
        actual_amount=200.0,
        withdraw_method="bank_card",
        account_info=json.dumps({"account_no": "12345678"}, ensure_ascii=False),
        status="completed",
        created_at=now,
    )
    test_session.add_all([w1, w2])
    await test_session.commit()
    await test_session.refresh(w1)
    await test_session.refresh(w2)

    # Export pending only
    res = await client.get(
        "/api/admin/withdrawals/export",
        headers=_auth_header(admin_user),
        params={"status": "pending"},
    )
    assert res.status_code == 200
    body_text = res.content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(body_text)))
    ids = {int(r["id"]) for r in rows if str(r.get("id") or "").strip()}
    assert int(w1.id) in ids
    assert int(w2.id) not in ids
    # Masked account should include last 4 only
    acc = str(rows[0].get("account_info_masked") or "")
    assert "5555" in acc
    assert "4444" not in acc

    # Export keyword filter
    res2 = await client.get(
        "/api/admin/withdrawals/export",
        headers=_auth_header(admin_user),
        params={"keyword": "0002"},
    )
    assert res2.status_code == 200
    body_text2 = res2.content.decode("utf-8-sig")
    rows2 = list(csv.DictReader(io.StringIO(body_text2)))
    ids2 = {int(r["id"]) for r in rows2 if str(r.get("id") or "").strip()}
    assert int(w2.id) in ids2
    assert int(w1.id) not in ids2


@pytest.mark.asyncio
async def test_admin_export_income_records_csv_date_range_and_filters(
    client: AsyncClient,
    test_session: AsyncSession,
):
    admin_user = await _create_user(
        test_session,
        username="admin_export_income",
        email="admin_export_income@example.com",
        role="admin",
    )
    lawyer_user_1 = await _create_user(
        test_session,
        username="lawyer_export_income_1",
        email="lawyer_export_income_1@example.com",
        role="lawyer",
    )
    lawyer_user_2 = await _create_user(
        test_session,
        username="lawyer_export_income_2",
        email="lawyer_export_income_2@example.com",
        role="lawyer",
    )

    lawyer_1 = await _create_lawyer_profile(test_session, user_id=int(lawyer_user_1.id))
    lawyer_2 = await _create_lawyer_profile(test_session, user_id=int(lawyer_user_2.id))

    now = datetime.now(timezone.utc)
    # create within range and outside range
    in_range_1 = LawyerIncomeRecord(
        lawyer_id=int(lawyer_1.id),
        consultation_id=None,
        order_no="ADMIN-ORD-1",
        user_paid_amount=100.0,
        platform_fee=10.0,
        lawyer_income=90.0,
        withdrawn_amount=0.0,
        status="settled",
        settle_time=now,
        created_at=now,
    )
    in_range_2 = LawyerIncomeRecord(
        lawyer_id=int(lawyer_2.id),
        consultation_id=None,
        order_no="ADMIN-ORD-2",
        user_paid_amount=200.0,
        platform_fee=20.0,
        lawyer_income=180.0,
        withdrawn_amount=0.0,
        status="pending",
        settle_time=None,
        created_at=now,
    )
    out_of_range = LawyerIncomeRecord(
        lawyer_id=int(lawyer_1.id),
        consultation_id=None,
        order_no="ADMIN-ORD-OLD",
        user_paid_amount=300.0,
        platform_fee=30.0,
        lawyer_income=270.0,
        withdrawn_amount=0.0,
        status="settled",
        settle_time=now,
        created_at=datetime(1990, 1, 1, tzinfo=timezone.utc),
    )

    test_session.add_all([in_range_1, in_range_2, out_of_range])
    await test_session.commit()
    await test_session.refresh(in_range_1)
    await test_session.refresh(in_range_2)
    await test_session.refresh(out_of_range)

    # Range filter should exclude out-of-range
    res = await client.get(
        "/api/admin/income-records/export",
        headers=_auth_header(admin_user),
        params={
            "from": datetime(1999, 1, 1, tzinfo=timezone.utc).isoformat(),
            "to": datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat(),
        },
    )
    assert res.status_code == 200
    body_text = res.content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(body_text)))
    ids = {int(r["id"]) for r in rows if str(r.get("id") or "").strip()}
    assert int(in_range_1.id) in ids
    assert int(in_range_2.id) in ids
    assert int(out_of_range.id) not in ids

    # Filter by lawyer_id and status
    res2 = await client.get(
        "/api/admin/income-records/export",
        headers=_auth_header(admin_user),
        params={
            "from": datetime(1999, 1, 1, tzinfo=timezone.utc).isoformat(),
            "to": datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat(),
            "lawyer_id": str(int(lawyer_1.id)),
            "status": "settled",
        },
    )
    assert res2.status_code == 200
    body_text2 = res2.content.decode("utf-8-sig")
    rows2 = list(csv.DictReader(io.StringIO(body_text2)))
    ids2 = {int(r["id"]) for r in rows2 if str(r.get("id") or "").strip()}
    assert int(in_range_1.id) in ids2
    assert int(out_of_range.id) not in ids2
    assert int(in_range_2.id) not in ids2
