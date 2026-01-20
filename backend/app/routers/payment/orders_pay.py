from __future__ import annotations

from typing import Any

from .. import payment_legacy as legacy
from ...services.prometheus_metrics import prometheus_metrics


def _record(method: str, result: str) -> None:
    try:
        prometheus_metrics.record_payment_pay(method=str(method), result=str(result))
    except Exception:
        return


def _as_str(value: object) -> str:
    return str(value or "").strip()


async def pay_order(order_no: str, data: Any, current_user: Any, db: Any):
    method = _as_str(getattr(data, "payment_method", ""))

    try:
        out = await legacy.pay_order(order_no, data, current_user, db)
    except legacy.HTTPException as e:
        detail = _as_str(getattr(e, "detail", ""))
        if detail == "无效的支付方式":
            _record(method, "invalid_method")
        elif detail == "订单不存在":
            _record(method, "order_not_found")
        elif detail == "订单已过期":
            _record(method, "expired")
        elif detail == "充值订单不支持余额支付":
            _record(method, "not_allowed")
        elif detail == "微信支付暂未开放":
            _record(method, "not_supported")
        elif detail.startswith("订单状态异常"):
            _record(method, "status_invalid")
        elif method in {"alipay", "ikunpay"} and (
            "未设置" in detail or "配置未设置" in detail
        ):
            _record(method, "config_missing")
        raise

    if (
        method != "balance"
        and isinstance(out, dict)
        and _as_str(out.get("trade_no"))
    ):
        _record(method, "already_paid")
    else:
        _record(method, "ok")
    return out
