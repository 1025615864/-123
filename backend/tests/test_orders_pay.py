import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.payment.orders_pay as op


class _Metrics:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def record_payment_pay(self, *, method: str, result: str) -> None:
        self.calls.append((method, result))


class _Expr:
    def __init__(self, text: str) -> None:
        self.text = text

    def __repr__(self) -> str:
        return self.text

    def _bin(self, op_: str, other: object) -> "_Expr":
        return _Expr(f"({self.text}{op_}{other})")

    def __eq__(self, other: object) -> "_Expr":  # type: ignore[override]
        return self._bin("==", other)

    def __ge__(self, other: object) -> "_Expr":
        return self._bin(">=", other)

    def __add__(self, other: object) -> "_Expr":
        return self._bin("+", other)

    def __radd__(self, other: object) -> "_Expr":
        return _Expr(f"({other}+{self.text})")

    def __sub__(self, other: object) -> "_Expr":
        return self._bin("-", other)

    def __rsub__(self, other: object) -> "_Expr":
        return _Expr(f"({other}-{self.text})")

    def __mul__(self, other: object) -> "_Expr":
        return self._bin("*", other)

    def __rmul__(self, other: object) -> "_Expr":
        return _Expr(f"({other}*{self.text})")


class _Func:
    def coalesce(self, *args: object) -> _Expr:
        return _Expr(f"coalesce{args}")

    def round(self, *args: object) -> _Expr:
        return _Expr(f"round{args}")


class _Stmt:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def where(self, *_args: object, **_kwargs: object) -> "_Stmt":
        return self

    def values(self, **_kwargs: object) -> "_Stmt":
        return self


class _Table:
    def __init__(self, name: str) -> None:
        self.order_no = _Expr(f"{name}.order_no")
        self.user_id = _Expr(f"{name}.user_id")
        self.id = _Expr(f"{name}.id")
        self.status = _Expr(f"{name}.status")
        self.amount = _Expr(f"{name}.amount")
        self.amount_cents = _Expr(f"{name}.amount_cents")
        self.actual_amount = _Expr(f"{name}.actual_amount")
        self.actual_amount_cents = _Expr(f"{name}.actual_amount_cents")
        self.balance = _Expr(f"{name}.balance")
        self.balance_cents = _Expr(f"{name}.balance_cents")
        self.total_consumed = _Expr(f"{name}.total_consumed")
        self.total_consumed_cents = _Expr(f"{name}.total_consumed_cents")


class _ScalarResult:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class _ExecResult:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount


class _DB:
    def __init__(self, results: list[object]):
        self._results = list(results)
        self.commit_calls = 0
        self.rollback_calls = 0
        self.added: list[object] = []

    async def execute(self, _stmt: object):
        return self._results.pop(0)

    async def commit(self):
        self.commit_calls += 1

    async def rollback(self):
        self.rollback_calls += 1

    def add(self, obj: object):
        self.added.append(obj)

    async def refresh(self, order):
        if getattr(order, "trade_no", None) is None:
            order.trade_no = "BAL123"
        if getattr(order, "payment_method", None) is None:
            order.payment_method = "balance"


class _Order:
    def __init__(
        self,
        *,
        id: int = 1,
        order_no: str = "ON",
        user_id: int = 1,
        order_type: str = "normal",
        status: str = "pending",
        actual_amount: float = 1.0,
        expires_at: datetime.datetime | None = None,
        title: str = "t",
        trade_no: str | None = None,
        payment_method: str | None = None,
    ) -> None:
        self.id = id
        self.order_no = order_no
        self.user_id = user_id
        self.order_type = order_type
        self.status = status
        self.actual_amount = actual_amount
        self.expires_at = expires_at
        self.title = title
        self.trade_no = trade_no
        self.payment_method = payment_method


@pytest.fixture()
def _patched(monkeypatch: pytest.MonkeyPatch):
    metrics = _Metrics()
    monkeypatch.setattr(op, "prometheus_metrics", metrics)

    class _PaymentStatus:
        PAID = "paid"
        PENDING = "pending"
        CANCELLED = "cancelled"

    monkeypatch.setattr(op.legacy, "PaymentStatus", _PaymentStatus, raising=False)
    monkeypatch.setattr(op.legacy, "HTTPException", HTTPException, raising=False)

    monkeypatch.setattr(op.legacy, "select", lambda *_a, **_k: _Stmt("select"), raising=False)
    monkeypatch.setattr(op.legacy, "update", lambda *_a, **_k: _Stmt("update"), raising=False)
    monkeypatch.setattr(op.legacy, "PaymentOrder", _Table("PaymentOrder"), raising=False)
    monkeypatch.setattr(op.legacy, "UserBalance", _Table("UserBalance"), raising=False)
    monkeypatch.setattr(op.legacy, "func", _Func(), raising=False)
    monkeypatch.setattr(op.legacy, "sa_cast", lambda expr, _typ: _Expr(f"cast({expr})"), raising=False)
    monkeypatch.setattr(op.legacy, "Integer", object(), raising=False)

    monkeypatch.setattr(op.legacy, "_quantize_amount", lambda v: float(v), raising=False)
    monkeypatch.setattr(op.legacy, "_decimal_to_cents", lambda v: int(round(float(v) * 100)), raising=False)
    monkeypatch.setattr(op.legacy, "generate_order_no", lambda: "123", raising=False)

    async def _noop(*_a, **_k):
        return None

    monkeypatch.setattr(op.legacy, "_maybe_apply_vip_membership_in_tx", _noop, raising=False)
    monkeypatch.setattr(op.legacy, "_maybe_apply_ai_pack_in_tx", _noop, raising=False)
    monkeypatch.setattr(op.legacy, "_maybe_confirm_lawyer_consultation_in_tx", _noop, raising=False)
    monkeypatch.setattr(op.legacy, "_maybe_create_consultation_review_task_in_tx", _noop, raising=False)

    monkeypatch.setattr(op.legacy, "BalanceTransaction", lambda **kwargs: kwargs, raising=False)

    return metrics


@pytest.mark.asyncio
async def test_pay_order_invalid_method(_patched) -> None:
    db = _DB([])
    user = SimpleNamespace(id=1)
    data = SimpleNamespace(payment_method="bad")

    with pytest.raises(HTTPException) as e:
        await op.pay_order("ON", data, user, db)

    assert e.value.status_code == 400
    assert _patched.calls == [("bad", "invalid_method")]


@pytest.mark.asyncio
async def test_pay_order_order_not_found(_patched) -> None:
    db = _DB([_ScalarResult(None)])
    user = SimpleNamespace(id=1)
    data = SimpleNamespace(payment_method="alipay")

    with pytest.raises(HTTPException) as e:
        await op.pay_order("ON", data, user, db)

    assert e.value.status_code == 404
    assert _patched.calls[-1] == ("alipay", "order_not_found")


@pytest.mark.asyncio
async def test_pay_order_already_paid(_patched, monkeypatch: pytest.MonkeyPatch) -> None:
    order = _Order(status="paid", trade_no="T", payment_method="alipay")
    db = _DB([_ScalarResult(order)])
    user = SimpleNamespace(id=1)
    data = SimpleNamespace(payment_method="alipay")

    out = await op.pay_order("ON", data, user, db)
    assert out["trade_no"] == "T"
    assert _patched.calls[-1] == ("alipay", "already_paid")


@pytest.mark.asyncio
async def test_pay_order_status_invalid(_patched) -> None:
    order = _Order(status="cancelled")
    db = _DB([_ScalarResult(order)])
    user = SimpleNamespace(id=1)
    data = SimpleNamespace(payment_method="alipay")

    with pytest.raises(HTTPException) as e:
        await op.pay_order("ON", data, user, db)

    assert e.value.status_code == 400
    assert _patched.calls[-1] == ("alipay", "status_invalid")


@pytest.mark.asyncio
async def test_pay_order_expired_marks_cancelled(_patched) -> None:
    past_naive = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)).replace(tzinfo=None)
    order = _Order(status="pending", expires_at=past_naive)
    db = _DB([_ScalarResult(order)])
    user = SimpleNamespace(id=1)
    data = SimpleNamespace(payment_method="alipay")

    with pytest.raises(HTTPException) as e:
        await op.pay_order("ON", data, user, db)

    assert e.value.status_code == 400
    assert order.status == op.legacy.PaymentStatus.CANCELLED
    assert db.commit_calls == 1
    assert _patched.calls[-1] == ("alipay", "expired")


@pytest.mark.asyncio
async def test_pay_order_recharge_cannot_balance(_patched) -> None:
    order = _Order(status="pending", order_type="recharge")
    db = _DB([_ScalarResult(order)])
    user = SimpleNamespace(id=1)
    data = SimpleNamespace(payment_method="balance")

    with pytest.raises(HTTPException) as e:
        await op.pay_order("ON", data, user, db)

    assert e.value.status_code == 400
    assert _patched.calls[-1] == ("balance", "not_allowed")


@pytest.mark.asyncio
async def test_pay_order_wechat_not_supported(_patched) -> None:
    order = _Order(status="pending")
    db = _DB([_ScalarResult(order)])
    user = SimpleNamespace(id=1)
    data = SimpleNamespace(payment_method="wechat")

    with pytest.raises(HTTPException) as e:
        await op.pay_order("ON", data, user, db)

    assert e.value.status_code == 400
    assert _patched.calls[-1] == ("wechat", "not_supported")


@pytest.mark.asyncio
async def test_pay_order_balance_insufficient_before_check(_patched, monkeypatch: pytest.MonkeyPatch) -> None:
    order = _Order(status="pending", actual_amount=10.0)

    async def _get_balance(_db, _uid):
        return SimpleNamespace(balance=1.0)

    monkeypatch.setattr(op.legacy, "_get_or_create_balance_in_tx", _get_balance, raising=False)

    db = _DB([_ScalarResult(order)])
    user = SimpleNamespace(id=1)
    data = SimpleNamespace(payment_method="balance")

    with pytest.raises(HTTPException) as e:
        await op.pay_order("ON", data, user, db)

    assert e.value.status_code == 400
    assert db.rollback_calls == 1


@pytest.mark.asyncio
async def test_pay_order_balance_insufficient_rowcount(_patched, monkeypatch: pytest.MonkeyPatch) -> None:
    order = _Order(status="pending", actual_amount=1.0)

    async def _get_balance(_db, _uid):
        return SimpleNamespace(balance=10.0)

    monkeypatch.setattr(op.legacy, "_get_or_create_balance_in_tx", _get_balance, raising=False)

    db = _DB([_ScalarResult(order), _ExecResult(0)])
    user = SimpleNamespace(id=1)
    data = SimpleNamespace(payment_method="balance")

    with pytest.raises(HTTPException) as e:
        await op.pay_order("ON", data, user, db)

    assert e.value.status_code == 400
    assert db.rollback_calls == 1


@pytest.mark.asyncio
async def test_pay_order_balance_success(_patched, monkeypatch: pytest.MonkeyPatch) -> None:
    order = _Order(status="pending", actual_amount=1.0)

    async def _get_balance(_db, _uid):
        return SimpleNamespace(balance=10.0)

    monkeypatch.setattr(op.legacy, "_get_or_create_balance_in_tx", _get_balance, raising=False)

    db = _DB([_ScalarResult(order), _ExecResult(1), _ExecResult(1)])
    user = SimpleNamespace(id=1)
    data = SimpleNamespace(payment_method="balance")

    out = await op.pay_order("ON", data, user, db)

    assert out["trade_no"] == "BAL123"
    assert db.commit_calls == 1
    assert _patched.calls[-1] == ("balance", "ok")


@pytest.mark.asyncio
async def test_pay_order_ikunpay_config_missing(_patched, monkeypatch: pytest.MonkeyPatch) -> None:
    order = _Order(status="pending")
    db = _DB([_ScalarResult(order)])
    user = SimpleNamespace(id=1)
    data = SimpleNamespace(payment_method="ikunpay")

    settings = SimpleNamespace(
        ikunpay_pid="",
        ikunpay_key="k",
        ikunpay_notify_url="n",
        ikunpay_default_type="",
        ikunpay_return_url="",
        ikunpay_gateway_url="",
        frontend_base_url="",
    )
    monkeypatch.setattr(op.legacy, "settings", settings, raising=False)

    with pytest.raises(HTTPException) as e:
        await op.pay_order("ON", data, user, db)

    assert e.value.status_code == 400
    assert _patched.calls[-1] == ("ikunpay", "config_missing")


@pytest.mark.asyncio
async def test_pay_order_ikunpay_ok_builds_url(_patched, monkeypatch: pytest.MonkeyPatch) -> None:
    order = _Order(status="pending", payment_method="")
    db = _DB([_ScalarResult(order)])
    user = SimpleNamespace(id=1)
    data = SimpleNamespace(payment_method="ikunpay")

    settings = SimpleNamespace(
        ikunpay_pid="pid",
        ikunpay_key="key",
        ikunpay_notify_url="notify",
        ikunpay_default_type="",
        ikunpay_return_url="",
        ikunpay_gateway_url="",
        frontend_base_url="https://frontend",
    )
    monkeypatch.setattr(op.legacy, "settings", settings, raising=False)

    monkeypatch.setattr(op.legacy, "_append_query_param", lambda url, k, v: f"{url}?{k}={v}", raising=False)
    monkeypatch.setattr(op.legacy, "_ikunpay_build_submit_pay_url", lambda **_k: "PAYURL", raising=False)

    out = await op.pay_order("ON", data, user, db)

    assert out["pay_url"] == "PAYURL"
    assert out["payment_method"] == "ikunpay"
    assert db.commit_calls == 1
    assert _patched.calls[-1] == ("ikunpay", "ok")


@pytest.mark.asyncio
async def test_pay_order_alipay_config_missing(_patched, monkeypatch: pytest.MonkeyPatch) -> None:
    order = _Order(status="pending")
    db = _DB([_ScalarResult(order)])
    user = SimpleNamespace(id=1)
    data = SimpleNamespace(payment_method="alipay")

    settings = SimpleNamespace(
        alipay_app_id="",
        alipay_private_key="",
        alipay_notify_url="",
        alipay_gateway_url="",
        alipay_return_url="",
        frontend_base_url="",
    )
    monkeypatch.setattr(op.legacy, "settings", settings, raising=False)

    with pytest.raises(HTTPException) as e:
        await op.pay_order("ON", data, user, db)

    assert e.value.status_code == 400
    assert _patched.calls[-1] == ("alipay", "config_missing")


@pytest.mark.asyncio
async def test_pay_order_alipay_ok_builds_url(_patched, monkeypatch: pytest.MonkeyPatch) -> None:
    order = _Order(status="pending", payment_method="")
    db = _DB([_ScalarResult(order)])
    user = SimpleNamespace(id=1)
    data = SimpleNamespace(payment_method="alipay")

    settings = SimpleNamespace(
        alipay_app_id="app",
        alipay_private_key="pk",
        alipay_notify_url="notify",
        alipay_gateway_url="gw",
        alipay_return_url="",
        frontend_base_url="https://frontend",
    )
    monkeypatch.setattr(op.legacy, "settings", settings, raising=False)

    monkeypatch.setattr(op.legacy, "_append_query_param", lambda url, k, v: f"{url}?{k}={v}", raising=False)
    monkeypatch.setattr(op.legacy, "_alipay_build_page_pay_url", lambda **_k: "ALIURL", raising=False)

    out = await op.pay_order("ON", data, user, db)

    assert out["pay_url"] == "ALIURL"
    assert out["payment_method"] == "alipay"
    assert db.commit_calls == 1
    assert _patched.calls[-1] == ("alipay", "ok")
