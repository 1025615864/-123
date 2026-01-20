from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from sqlalchemy import select

from app.models.consultation import Consultation
from app.models.consultation_review import ConsultationReviewTask
from app.models.lawfirm import Lawyer
from app.models.notification import Notification
from app.models.payment import OrderType, PaymentOrder
from app.models.system import SystemConfig
from app.models.user import User
from app.services import review_task_sla_service as svc


def test_parse_int() -> None:
    assert svc._parse_int(None, 7) == 7
    assert svc._parse_int(True, 7) == 7
    assert svc._parse_int(3, 7) == 3
    assert svc._parse_int(3.2, 7) == 3
    assert svc._parse_int(" 4 ", 7) == 4
    assert svc._parse_int("", 7) == 7
    assert svc._parse_int("bad", 7) == 7


def test_compute_review_due_at_submitted_none() -> None:
    t = ConsultationReviewTask(
        consultation_id=1,
        user_id=1,
        order_id=1,
        order_no="o",
        status="submitted",
        lawyer_id=1,
        created_at=datetime.now(timezone.utc),
    )
    assert svc.compute_review_due_at(t, {}) is None


def test_compute_review_due_at_claimed_prefers_claimed_at() -> None:
    now = datetime.now(timezone.utc)
    t = ConsultationReviewTask(
        consultation_id=1,
        user_id=1,
        order_id=1,
        order_no="o",
        status="claimed",
        lawyer_id=1,
        created_at=now - timedelta(days=1),
        claimed_at=now - timedelta(minutes=10),
    )
    due = svc.compute_review_due_at(t, {"pending_sla_minutes": 1000, "claimed_sla_minutes": 5})
    assert isinstance(due, datetime)
    assert abs((due - (t.claimed_at or now)).total_seconds() - 5 * 60) < 1.0


def test_compute_review_due_at_returns_none_when_base_missing() -> None:
    t = ConsultationReviewTask(
        consultation_id=1,
        user_id=1,
        order_id=1,
        order_no="o",
        status="pending",
        lawyer_id=1,
        created_at=None,
        claimed_at=None,
    )
    assert svc.compute_review_due_at(t, {}) is None


def test_compute_review_due_at_normalizes_naive_base_and_min_minutes() -> None:
    base = datetime.utcnow()
    t = ConsultationReviewTask(
        consultation_id=1,
        user_id=1,
        order_id=1,
        order_no="o",
        status="pending",
        lawyer_id=1,
        created_at=base,
    )
    due = svc.compute_review_due_at(t, {"pending_sla_minutes": 0})
    assert isinstance(due, datetime)
    assert due.tzinfo == timezone.utc
    base_utc = base.replace(tzinfo=timezone.utc)
    assert abs((due - base_utc).total_seconds() - 60.0) < 1.0


@pytest.mark.asyncio
async def test_load_review_sla_config_env_fallback(monkeypatch) -> None:
    monkeypatch.setenv(svc.CONSULT_REVIEW_SLA_CONFIG_KEY, json.dumps({"pending_sla_minutes": 1}))

    class DummyRes:
        def scalar_one_or_none(self):
            raise RuntimeError("db")

    class DummyDb:
        async def execute(self, _q):
            return DummyRes()

    cfg = await svc.load_review_sla_config(DummyDb())  # type: ignore[arg-type]
    assert cfg.get("pending_sla_minutes") == 1


@pytest.mark.asyncio
async def test_load_review_sla_config_invalid_json_returns_default(monkeypatch) -> None:
    monkeypatch.delenv(svc.CONSULT_REVIEW_SLA_CONFIG_KEY, raising=False)

    class DummyCfg:
        value = "{"

    class DummyRes:
        def scalar_one_or_none(self):
            return DummyCfg()

    class DummyDb:
        async def execute(self, _q):
            return DummyRes()

    cfg = await svc.load_review_sla_config(DummyDb())  # type: ignore[arg-type]
    assert cfg.get("pending_sla_minutes") == 24 * 60
    assert cfg.get("claimed_sla_minutes") == 12 * 60


@pytest.mark.asyncio
async def test_scan_skipped_when_notifications_disabled(test_session) -> None:
    test_session.add(SystemConfig(key=svc.ENABLE_NOTIFICATIONS_CONFIG_KEY, value="0"))
    await test_session.commit()

    out = await svc.scan_and_notify_review_task_sla(test_session)
    assert out.get("skipped") == 1
    assert out.get("inserted") == 0


@pytest.mark.asyncio
async def test_scan_inserts_notifications_sqlite(test_session, monkeypatch) -> None:
    import app.services.websocket_service as websocket_service

    async def fake_notify_user(*args, **kwargs):
        return True

    monkeypatch.setattr(websocket_service, "notify_user", fake_notify_user, raising=True)

    cfg = {
        "pending_sla_minutes": 1,
        "claimed_sla_minutes": 1,
        "remind_before_minutes": 60,
    }
    test_session.add(SystemConfig(key=svc.CONSULT_REVIEW_SLA_CONFIG_KEY, value=json.dumps(cfg)))
    test_session.add(SystemConfig(key=svc.ENABLE_NOTIFICATIONS_CONFIG_KEY, value="1"))

    u = User(username="u_sla", email="u_sla@example.com", nickname="u_sla", hashed_password="x", role="user")
    lawyer_user = User(
        username="lawyer_sla",
        email="lawyer_sla@example.com",
        nickname="lawyer_sla",
        hashed_password="x",
        role="lawyer",
    )
    test_session.add_all([u, lawyer_user])
    await test_session.flush()

    lawyer = Lawyer(user_id=int(lawyer_user.id), name="L")
    test_session.add(lawyer)
    await test_session.flush()

    order1 = PaymentOrder(
        order_no="sla_order_1",
        user_id=int(u.id),
        order_type=OrderType.LIGHT_CONSULT_REVIEW.value,
        amount=1.0,
        actual_amount=1.0,
        status="paid",
        title="t",
    )
    order2 = PaymentOrder(
        order_no="sla_order_2",
        user_id=int(u.id),
        order_type=OrderType.LIGHT_CONSULT_REVIEW.value,
        amount=1.0,
        actual_amount=1.0,
        status="paid",
        title="t",
    )
    test_session.add_all([order1, order2])

    consult = Consultation(user_id=int(u.id), session_id="s_sla", title="t")
    test_session.add(consult)
    await test_session.flush()

    now = datetime.now(timezone.utc)

    overdue_task = ConsultationReviewTask(
        consultation_id=int(consult.id),
        user_id=int(u.id),
        order_id=int(order1.id),
        order_no=str(order1.order_no),
        status="pending",
        lawyer_id=int(lawyer.id),
        created_at=now - timedelta(minutes=10),
    )
    due_soon_task = ConsultationReviewTask(
        consultation_id=int(consult.id),
        user_id=int(u.id),
        order_id=int(order2.id),
        order_no=str(order2.order_no),
        status="pending",
        lawyer_id=int(lawyer.id),
        created_at=now,
    )
    test_session.add_all([overdue_task, due_soon_task])
    await test_session.commit()

    out = await svc.scan_and_notify_review_task_sla(test_session)
    assert out.get("scanned") == 2
    assert out.get("candidates") == 2
    assert int(out.get("inserted") or 0) >= 1
    assert int(out.get("due_soon") or 0) >= 1
    assert int(out.get("overdue") or 0) >= 1

    res = await test_session.execute(select(Notification).order_by(Notification.id.asc()))
    notes = res.scalars().all()
    assert len(notes) >= 1
    assert all(n.type == "system" for n in notes)
    assert all((n.link or "") == "/lawyer?tab=reviews" for n in notes)


@pytest.mark.asyncio
async def test_scan_swallow_enable_notifications_query_error_and_no_values(monkeypatch) -> None:
    now = datetime.now(timezone.utc)

    t1 = ConsultationReviewTask(
        consultation_id=1,
        user_id=1,
        order_id=1,
        order_no="o",
        status="pending",
        lawyer_id=1,
        created_at=now,
    )
    t2 = ConsultationReviewTask(
        consultation_id=1,
        user_id=1,
        order_id=2,
        order_no="o2",
        status="submitted",
        lawyer_id=1,
        created_at=now,
    )

    class DummyRes:
        def __init__(self, *, scalar=None, rows=None):
            self._scalar = scalar
            self._rows = rows

        def scalar_one_or_none(self):
            return self._scalar

        def all(self):
            return self._rows or []

    class DummyBind:
        class dialect:
            name = "sqlite"

    class DummyDb:
        def __init__(self):
            self.calls = 0

        async def execute(self, _q):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("boom")
            if self.calls == 2:
                return DummyRes(scalar=None)
            return DummyRes(rows=[(t1, None), (t2, 1), (t1, 1)])

        async def commit(self):
            return None

        def get_bind(self):
            return DummyBind()

    original = svc.compute_review_due_at

    def fake_due_at(task, cfg):
        if str(getattr(task, "status", "")) == "submitted":
            return None
        return datetime.utcnow() + timedelta(minutes=120)

    monkeypatch.setattr(svc, "compute_review_due_at", fake_due_at, raising=True)
    out = await svc.scan_and_notify_review_task_sla(DummyDb())  # type: ignore[arg-type]
    monkeypatch.setattr(svc, "compute_review_due_at", original, raising=True)

    assert out.get("scanned") == 3
    assert out.get("candidates") == 0
    assert out.get("inserted") == 0


@pytest.mark.asyncio
async def test_scan_postgresql_returning_branch_and_notify(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    t = ConsultationReviewTask(
        consultation_id=1,
        user_id=1,
        order_id=1,
        order_no="o",
        status="pending",
        lawyer_id=1,
        created_at=now - timedelta(minutes=10),
    )

    class DummyCfg:
        value = json.dumps({"pending_sla_minutes": 1, "claimed_sla_minutes": 1, "remind_before_minutes": 60})

    class DummyRes:
        def __init__(self, *, scalar=None, rows=None, inserted_rows=None):
            self._scalar = scalar
            self._rows = rows
            self._inserted_rows = inserted_rows

        def scalar_one_or_none(self):
            return self._scalar

        def all(self):
            return self._rows or self._inserted_rows or []

    class DummyBind:
        class dialect:
            name = "postgresql"

    calls = {"notify": 0}

    async def fake_notify_user(*args, **kwargs):
        calls["notify"] += 1
        return True

    import app.services.websocket_service as websocket_service

    monkeypatch.setattr(websocket_service, "notify_user", fake_notify_user, raising=True)

    class DummyDb:
        def __init__(self):
            self.calls = 0

        async def execute(self, _q):
            self.calls += 1
            if self.calls == 1:
                return DummyRes(scalar="1")
            if self.calls == 2:
                return DummyRes(scalar=DummyCfg())
            if self.calls == 3:
                return DummyRes(rows=[(t, 2)])
            return DummyRes(inserted_rows=[(0, "t", "c", "/l", "k"), (2, "t", "c", "/l", "k")])

        async def commit(self):
            return None

        def get_bind(self):
            return DummyBind()

    out = await svc.scan_and_notify_review_task_sla(DummyDb())  # type: ignore[arg-type]
    assert int(out.get("inserted") or 0) == 2
    assert calls["notify"] == 1


@pytest.mark.asyncio
async def test_scan_values_notify_skips_invalid_uid(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    t = ConsultationReviewTask(
        consultation_id=1,
        user_id=1,
        order_id=1,
        order_no="o",
        status="pending",
        lawyer_id=1,
        created_at=now - timedelta(minutes=10),
    )

    class DummyCfg:
        value = json.dumps({"pending_sla_minutes": 1, "claimed_sla_minutes": 1, "remind_before_minutes": 60})

    class DummyRes:
        def __init__(self, *, scalar=None, rows=None, rowcount=0):
            self._scalar = scalar
            self._rows = rows
            self.rowcount = rowcount

        def scalar_one_or_none(self):
            return self._scalar

        def all(self):
            return self._rows or []

    class DummyBind:
        class dialect:
            name = "sqlite"

    async def fake_notify_user(*args, **kwargs):
        return True

    import app.services.websocket_service as websocket_service

    monkeypatch.setattr(websocket_service, "notify_user", fake_notify_user, raising=True)

    class DummyDb:
        def __init__(self):
            self.calls = 0

        async def execute(self, _q):
            self.calls += 1
            if self.calls == 1:
                return DummyRes(scalar="1")
            if self.calls == 2:
                return DummyRes(scalar=DummyCfg())
            if self.calls == 3:
                return DummyRes(rows=[(t, 0)])
            return DummyRes(rowcount=1)

        async def commit(self):
            return None

        def get_bind(self):
            return DummyBind()

    out = await svc.scan_and_notify_review_task_sla(DummyDb())  # type: ignore[arg-type]
    assert int(out.get("inserted") or 0) == 1


@pytest.mark.asyncio
async def test_scan_notify_exception_is_swallowed(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    t = ConsultationReviewTask(
        consultation_id=1,
        user_id=1,
        order_id=1,
        order_no="o",
        status="pending",
        lawyer_id=1,
        created_at=now - timedelta(minutes=10),
    )

    class DummyCfg:
        value = json.dumps({"pending_sla_minutes": 1, "claimed_sla_minutes": 1, "remind_before_minutes": 60})

    class DummyRes:
        def __init__(self, *, scalar=None, rows=None, inserted_rows=None):
            self._scalar = scalar
            self._rows = rows
            self._inserted_rows = inserted_rows

        def scalar_one_or_none(self):
            return self._scalar

        def all(self):
            return self._rows or self._inserted_rows or []

    class DummyBind:
        class dialect:
            name = "postgresql"

    async def boom_notify(*args, **kwargs):
        raise RuntimeError("notify")

    import app.services.websocket_service as websocket_service

    monkeypatch.setattr(websocket_service, "notify_user", boom_notify, raising=True)

    class DummyDb:
        def __init__(self):
            self.calls = 0

        async def execute(self, _q):
            self.calls += 1
            if self.calls == 1:
                return DummyRes(scalar="1")
            if self.calls == 2:
                return DummyRes(scalar=DummyCfg())
            if self.calls == 3:
                return DummyRes(rows=[(t, 2)])
            return DummyRes(inserted_rows=[(2, "t", "c", "/l", "k")])

        async def commit(self):
            return None

        def get_bind(self):
            return DummyBind()

    out = await svc.scan_and_notify_review_task_sla(DummyDb())  # type: ignore[arg-type]
    assert int(out.get("inserted") or 0) == 1
