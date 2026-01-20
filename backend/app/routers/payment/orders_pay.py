from __future__ import annotations

import datetime
from typing import Any

from .. import payment_legacy as legacy
from ...services.prometheus_metrics import prometheus_metrics


def _record(method: str, result: str) -> None:
    try:
        prometheus_metrics.record_payment_pay(method=str(method), result=str(result))
    except Exception:
        return


async def pay_order(order_no: str, data: Any, current_user: Any, db: Any):
    method = str(getattr(data, "payment_method", "") or "").strip()

    if method not in {"alipay", "wechat", "balance", "ikunpay"}:
        _record(method, "invalid_method")
        raise legacy.HTTPException(status_code=400, detail="无效的支付方式")

    result = await db.execute(
        legacy.select(legacy.PaymentOrder).where(
            legacy.PaymentOrder.order_no == order_no,
            legacy.PaymentOrder.user_id == current_user.id,
        )
    )
    order = result.scalar_one_or_none()

    if not order:
        _record(method, "order_not_found")
        raise legacy.HTTPException(status_code=404, detail="订单不存在")

    if getattr(order, "order_type", None) == "recharge" and method == "balance":
        _record(method, "not_allowed")
        raise legacy.HTTPException(status_code=400, detail="充值订单不支持余额支付")

    if getattr(order, "status", None) == legacy.PaymentStatus.PAID:
        _record(method, "already_paid")
        return {"message": "支付成功", "trade_no": getattr(order, "trade_no", None)}

    if getattr(order, "status", None) != legacy.PaymentStatus.PENDING:
        _record(method, "status_invalid")
        raise legacy.HTTPException(status_code=400, detail=f"订单状态异常: {getattr(order, 'status', None)}")

    expires_at = getattr(order, "expires_at", None)
    if expires_at is not None and getattr(expires_at, "tzinfo", None) is None:
        expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)

    if expires_at and expires_at < datetime.datetime.now(datetime.timezone.utc):
        order.status = legacy.PaymentStatus.CANCELLED
        await db.commit()
        _record(method, "expired")
        raise legacy.HTTPException(status_code=400, detail="订单已过期")

    if method == "wechat":
        _record(method, "not_supported")
        raise legacy.HTTPException(status_code=400, detail="微信支付暂未开放")

    if method == "balance":
        _record(method, "attempt")
        actual_amount = legacy._quantize_amount(float(getattr(order, "actual_amount", 0) or 0))
        actual_amount_cents = legacy._decimal_to_cents(actual_amount)

        trade_no = f"BAL{legacy.generate_order_no()}"
        paid_at = datetime.datetime.now(datetime.timezone.utc)

        try:
            balance_account = await legacy._get_or_create_balance_in_tx(db, current_user.id)
            balance_before = legacy._quantize_amount(float(getattr(balance_account, "balance", 0) or 0))
            if balance_before < actual_amount:
                _record(method, "insufficient")
                raise legacy.HTTPException(status_code=400, detail="余额不足")

            bal_update = await db.execute(
                legacy.update(legacy.UserBalance)
                .where(
                    legacy.UserBalance.user_id == current_user.id,
                    legacy.func.coalesce(legacy.UserBalance.balance_cents, 0) >= actual_amount_cents,
                )
                .values(
                    balance=legacy.func.coalesce(legacy.UserBalance.balance, 0) - float(actual_amount),
                    total_consumed=legacy.func.coalesce(legacy.UserBalance.total_consumed, 0) + float(actual_amount),
                    balance_cents=legacy.func.coalesce(legacy.UserBalance.balance_cents, 0) - actual_amount_cents,
                    total_consumed_cents=legacy.func.coalesce(legacy.UserBalance.total_consumed_cents, 0) + actual_amount_cents,
                )
            )
            if getattr(bal_update, "rowcount", 0) != 1:
                _record(method, "insufficient")
                raise legacy.HTTPException(status_code=400, detail="余额不足")

            order_update = await db.execute(
                legacy.update(legacy.PaymentOrder)
                .where(legacy.PaymentOrder.id == order.id, legacy.PaymentOrder.status == legacy.PaymentStatus.PENDING)
                .values(
                    status=legacy.PaymentStatus.PAID,
                    payment_method="balance",
                    paid_at=paid_at,
                    trade_no=trade_no,
                    actual_amount_cents=actual_amount_cents,
                )
            )
            if getattr(order_update, "rowcount", 0) != 1:
                _record(method, "status_invalid")
                raise legacy.HTTPException(status_code=400, detail="订单状态异常")

            await db.commit()
        except legacy.HTTPException:
            await db.rollback()
            raise
        except Exception:
            await db.rollback()
            raise

        await db.refresh(order)
        _record(method, "ok")
        return {"message": "支付成功", "trade_no": getattr(order, "trade_no", None)}

    if method == "ikunpay":
        settings = getattr(legacy, "settings", None)
        if not str(getattr(settings, "ikunpay_pid", "") or "").strip() or not str(getattr(settings, "ikunpay_key", "") or "").strip() or not str(getattr(settings, "ikunpay_notify_url", "") or "").strip():
            _record(method, "config_missing")
            raise legacy.HTTPException(status_code=400, detail="支付配置未设置")

        if getattr(order, "payment_method", None) != "ikunpay":
            order.payment_method = "ikunpay"
            await db.commit()

        pay_url = legacy._ikunpay_build_submit_pay_url(
            gateway_url=(str(getattr(settings, "ikunpay_gateway_url", "") or "").strip() or "https://ikunpay.com/submit.php"),
            pid=str(getattr(settings, "ikunpay_pid", "") or ""),
            pay_type=(str(getattr(settings, "ikunpay_default_type", "") or "").strip() or None),
            out_trade_no=str(getattr(order, "order_no", "") or ""),
            notify_url=str(getattr(settings, "ikunpay_notify_url", "") or ""),
            return_url=None,
            name=str(getattr(order, "title", "") or ""),
            money=legacy._quantize_amount(float(getattr(order, "actual_amount", 0) or 0)),
            key=str(getattr(settings, "ikunpay_key", "") or ""),
        )
        _record(method, "ok")
        return {
            "message": "OK",
            "payment_method": "ikunpay",
            "amount": getattr(order, "actual_amount", None),
            "order_no": getattr(order, "order_no", None),
            "pay_url": pay_url,
        }

    if method == "alipay":
        settings = getattr(legacy, "settings", None)
        if not str(getattr(settings, "alipay_app_id", "") or "").strip() or not str(getattr(settings, "alipay_private_key", "") or "").strip() or not str(getattr(settings, "alipay_notify_url", "") or "").strip():
            _record(method, "config_missing")
            raise legacy.HTTPException(status_code=400, detail="支付配置未设置")

        if getattr(order, "payment_method", None) != "alipay":
            order.payment_method = "alipay"
            await db.commit()

        pay_url = legacy._alipay_build_page_pay_url(
            gateway_url=str(getattr(settings, "alipay_gateway_url", "") or ""),
            app_id=str(getattr(settings, "alipay_app_id", "") or ""),
            private_key=str(getattr(settings, "alipay_private_key", "") or ""),
            notify_url=str(getattr(settings, "alipay_notify_url", "") or ""),
            return_url=None,
            out_trade_no=str(getattr(order, "order_no", "") or ""),
            total_amount=legacy._quantize_amount(float(getattr(order, "actual_amount", 0) or 0)),
            subject=str(getattr(order, "title", "") or ""),
        )
        _record(method, "ok")
        return {
            "message": "OK",
            "payment_method": "alipay",
            "amount": getattr(order, "actual_amount", None),
            "order_no": getattr(order, "order_no", None),
            "pay_url": pay_url,
        }

    _record(method, "unknown")
    raise legacy.HTTPException(status_code=400, detail="无效的支付方式")
