"""支付API路由"""
import hashlib
import hmac
from typing import Annotated, cast
from datetime import datetime, timedelta, timezone
import uuid
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, cast as sa_cast, Integer
from pydantic import BaseModel

from ..config import get_settings
from ..database import get_db
from ..models.payment import PaymentOrder, UserBalance, BalanceTransaction, PaymentStatus
from ..models.user import User
from ..utils.deps import get_current_user, require_admin

router = APIRouter(prefix="/payment", tags=["支付管理"])

settings = get_settings()


# ============ 请求/响应模型 ============

class CreateOrderRequest(BaseModel):
    order_type: str  # consultation/service/vip/recharge
    amount: float
    title: str
    description: str | None = None
    related_id: int | None = None
    related_type: str | None = None


class PayOrderRequest(BaseModel):
    payment_method: str  # alipay/wechat/balance


class MarkPaidRequest(BaseModel):
    payment_method: str  # alipay/wechat


class PaymentWebhookRequest(BaseModel):
    order_no: str
    trade_no: str
    payment_method: str
    amount: float
    signature: str


class OrderResponse(BaseModel):
    id: int
    order_no: str
    order_type: str
    amount: float
    actual_amount: float
    status: str
    payment_method: str | None
    title: str
    created_at: datetime
    paid_at: datetime | None


class BalanceResponse(BaseModel):
    balance: float
    frozen: float
    total_recharged: float
    total_consumed: float


# ============ 工具函数 ============

def generate_order_no() -> str:
    """生成订单号"""
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


def _quantize_amount(amount: float) -> Decimal:
    return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _decimal_to_cents(amount: Decimal) -> int:
    return int(amount * 100)


async def _get_or_create_balance_in_tx(db: AsyncSession, user_id: int) -> UserBalance:
    result = await db.execute(
        select(UserBalance).where(UserBalance.user_id == user_id)
    )
    balance = result.scalar_one_or_none()
    if balance:
        return balance

    balance = UserBalance(
        user_id=user_id,
        balance=0.0,
        frozen=0.0,
        total_recharged=0.0,
        total_consumed=0.0,
        balance_cents=0,
        frozen_cents=0,
        total_recharged_cents=0,
        total_consumed_cents=0,
    )
    db.add(balance)
    await db.flush()
    return balance


async def get_or_create_balance(db: AsyncSession, user_id: int) -> UserBalance:
    """获取或创建用户余额账户"""
    result = await db.execute(
        select(UserBalance).where(UserBalance.user_id == user_id)
    )
    balance = result.scalar_one_or_none()
    
    if not balance:
        balance = UserBalance(
            user_id=user_id,
            balance=0.0,
            frozen=0.0,
            total_recharged=0.0,
            total_consumed=0.0,
            balance_cents=0,
            frozen_cents=0,
            total_recharged_cents=0,
            total_consumed_cents=0,
        )
        db.add(balance)
        await db.commit()
        await db.refresh(balance)
    
    return balance


# ============ 用户接口 ============

@router.post("/orders", summary="创建订单")
async def create_order(
    data: CreateOrderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """创建支付订单"""
    if data.order_type not in {"consultation", "service", "vip", "recharge"}:
        raise HTTPException(status_code=400, detail="无效的订单类型")

    amount = _quantize_amount(data.amount)
    amount_cents = _decimal_to_cents(amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="金额必须大于0")
    
    order = PaymentOrder(
        order_no=generate_order_no(),
        user_id=current_user.id,
        order_type=data.order_type,
        amount=float(amount),
        actual_amount=float(amount),  # 可添加优惠逻辑
        amount_cents=amount_cents,
        actual_amount_cents=amount_cents,
        status=PaymentStatus.PENDING,
        title=data.title,
        description=data.description,
        related_id=data.related_id,
        related_type=data.related_type,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),  # 2小时过期
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "amount": order.actual_amount,
        "expires_at": order.expires_at,
    }


@router.post("/orders/{order_no}/pay", summary="支付订单")
async def pay_order(
    order_no: str,
    data: PayOrderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """支付订单"""
    if data.payment_method not in {"alipay", "wechat", "balance"}:
        raise HTTPException(status_code=400, detail="无效的支付方式")

    result = await db.execute(
        select(PaymentOrder).where(
            PaymentOrder.order_no == order_no,
            PaymentOrder.user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.order_type == "recharge" and data.payment_method == "balance":
        raise HTTPException(status_code=400, detail="充值订单不支持余额支付")
    
    if order.status == PaymentStatus.PAID:
        return {"message": "支付成功", "trade_no": order.trade_no}
    if order.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"订单状态异常: {order.status}")

    expires_at = order.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at and expires_at < datetime.now(timezone.utc):
        order.status = PaymentStatus.CANCELLED
        await db.commit()
        raise HTTPException(status_code=400, detail="订单已过期")

    actual_amount = _quantize_amount(float(order.actual_amount))
    actual_amount_cents = _decimal_to_cents(actual_amount)

    # 余额支付
    if data.payment_method == "balance":
        trade_no = f"BAL{generate_order_no()}"
        paid_at = datetime.now(timezone.utc)
 
        try:
            balance_account = await _get_or_create_balance_in_tx(db, current_user.id)
            balance_before = _quantize_amount(float(balance_account.balance))
            balance_before_cents = _decimal_to_cents(balance_before)

            if balance_before < actual_amount:
                raise HTTPException(status_code=400, detail="余额不足")

            effective_balance_cents = func.coalesce(
                UserBalance.balance_cents,
                sa_cast(func.round(func.coalesce(UserBalance.balance, 0) * 100), Integer),
            )
            effective_total_consumed_cents = func.coalesce(
                UserBalance.total_consumed_cents,
                sa_cast(func.round(func.coalesce(UserBalance.total_consumed, 0) * 100), Integer),
            )

            bal_update = await db.execute(
                update(UserBalance)
                .where(
                    UserBalance.user_id == current_user.id,
                    effective_balance_cents >= actual_amount_cents,
                )
                .values(
                    balance=func.coalesce(UserBalance.balance, 0) - float(actual_amount),
                    total_consumed=func.coalesce(UserBalance.total_consumed, 0) + float(actual_amount),
                    balance_cents=effective_balance_cents - actual_amount_cents,
                    total_consumed_cents=effective_total_consumed_cents + actual_amount_cents,
                )
            )
            if getattr(bal_update, "rowcount", 0) != 1:
                raise HTTPException(status_code=400, detail="余额不足")

            order_update = await db.execute(
                update(PaymentOrder)
                .where(PaymentOrder.id == order.id, PaymentOrder.status == PaymentStatus.PENDING)
                .values(
                    status=PaymentStatus.PAID,
                    payment_method=data.payment_method,
                    paid_at=paid_at,
                    trade_no=trade_no,
                    amount_cents=func.coalesce(
                        PaymentOrder.amount_cents,
                        sa_cast(func.round(PaymentOrder.amount * 100), Integer),
                    ),
                    actual_amount_cents=actual_amount_cents,
                )
            )
            if getattr(order_update, "rowcount", 0) != 1:
                raise HTTPException(status_code=400, detail="订单状态异常")

            balance_after = balance_before - actual_amount
            balance_after_cents = balance_before_cents - actual_amount_cents
            transaction = BalanceTransaction(
                user_id=current_user.id,
                order_id=order.id,
                type="consume",
                amount=-float(actual_amount),
                balance_before=float(balance_before),
                balance_after=float(balance_after),
                amount_cents=-actual_amount_cents,
                balance_before_cents=balance_before_cents,
                balance_after_cents=balance_after_cents,
                description=f"支付订单: {order.title}",
            )
            db.add(transaction)

            await db.commit()
        except HTTPException:
            await db.rollback()
            raise
        except Exception:
            await db.rollback()
            raise

        await db.refresh(order)
        return {"message": "支付成功", "trade_no": order.trade_no}
    
    # 其他支付方式（返回支付链接/二维码）
    # 实际项目中需要对接支付宝/微信支付SDK
    return {
        "message": "请使用第三方支付",
        "payment_method": data.payment_method,
        "amount": order.actual_amount,
        "order_no": order.order_no,
        # "pay_url": "https://...",  # 实际支付链接
    }


@router.post("/webhook", summary="支付回调（验签）")
async def payment_webhook(
    data: PaymentWebhookRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if data.payment_method not in {"alipay", "wechat"}:
        raise HTTPException(status_code=400, detail="无效的支付方式")

    amount = _quantize_amount(data.amount)
    amount_cents = _decimal_to_cents(amount)
    sign_payload = f"{data.order_no}|{data.trade_no}|{data.payment_method}|{amount}"
    expected_signature = hmac.new(
        settings.payment_webhook_secret.encode("utf-8"),
        sign_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, data.signature):
        raise HTTPException(status_code=400, detail="签名校验失败")

    result = await db.execute(select(PaymentOrder).where(PaymentOrder.order_no == data.order_no))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.status == PaymentStatus.PAID:
        return {"message": "OK"}

    if order.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=400, detail="订单状态异常")

    if _quantize_amount(float(order.actual_amount)) != amount:
        raise HTTPException(status_code=400, detail="金额不一致")

    paid_at = datetime.now(timezone.utc)

    try:
        order_update = await db.execute(
            update(PaymentOrder)
            .where(PaymentOrder.id == order.id, PaymentOrder.status == PaymentStatus.PENDING)
            .values(
                status=PaymentStatus.PAID,
                payment_method=data.payment_method,
                paid_at=paid_at,
                trade_no=data.trade_no,
                amount_cents=func.coalesce(
                    PaymentOrder.amount_cents,
                    sa_cast(func.round(PaymentOrder.amount * 100), Integer),
                ),
                actual_amount_cents=amount_cents,
            )
        )
        if getattr(order_update, "rowcount", 0) != 1:
            raise HTTPException(status_code=400, detail="订单状态异常")

        if order.order_type == "recharge":
            balance_account = await _get_or_create_balance_in_tx(db, order.user_id)
            balance_before = _quantize_amount(float(balance_account.balance))
            balance_before_cents = _decimal_to_cents(balance_before)

            effective_balance_cents = func.coalesce(
                UserBalance.balance_cents,
                sa_cast(func.round(func.coalesce(UserBalance.balance, 0) * 100), Integer),
            )
            effective_total_recharged_cents = func.coalesce(
                UserBalance.total_recharged_cents,
                sa_cast(func.round(func.coalesce(UserBalance.total_recharged, 0) * 100), Integer),
            )

            _ = await db.execute(
                update(UserBalance)
                .where(UserBalance.user_id == order.user_id)
                .values(
                    balance=func.coalesce(UserBalance.balance, 0) + float(amount),
                    total_recharged=func.coalesce(UserBalance.total_recharged, 0) + float(amount),
                    balance_cents=effective_balance_cents + amount_cents,
                    total_recharged_cents=effective_total_recharged_cents + amount_cents,
                )
            )

            balance_after = balance_before + amount
            balance_after_cents = balance_before_cents + amount_cents
            transaction = BalanceTransaction(
                user_id=order.user_id,
                order_id=order.id,
                type="recharge",
                amount=float(amount),
                balance_before=float(balance_before),
                balance_after=float(balance_after),
                amount_cents=amount_cents,
                balance_before_cents=balance_before_cents,
                balance_after_cents=balance_after_cents,
                description=f"充值: {order.title}",
            )
            db.add(transaction)

        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    return {"message": "OK"}


@router.get("/orders", summary="获取订单列表")
async def get_orders(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: str | None = None,
):
    """获取当前用户的订单列表"""
    query = select(PaymentOrder).where(PaymentOrder.user_id == current_user.id)
    
    if status_filter:
        query = query.where(PaymentOrder.status == status_filter)
    
    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total: int = int(await db.scalar(count_query) or 0)
    
    # 分页
    query = query.order_by(PaymentOrder.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    orders = result.scalars().all()
    
    items = [
        OrderResponse(
            id=o.id,
            order_no=o.order_no,
            order_type=o.order_type,
            amount=o.amount,
            actual_amount=o.actual_amount,
            status=o.status,
            payment_method=o.payment_method,
            title=o.title,
            created_at=o.created_at,
            paid_at=o.paid_at,
        )
        for o in orders
    ]
    
    return {"items": items, "total": total}


@router.get("/orders/{order_no}", summary="获取订单详情")
async def get_order_detail(
    order_no: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取订单详情"""
    result = await db.execute(
        select(PaymentOrder).where(
            PaymentOrder.order_no == order_no,
            PaymentOrder.user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    return OrderResponse(
        id=order.id,
        order_no=order.order_no,
        order_type=order.order_type,
        amount=order.amount,
        actual_amount=order.actual_amount,
        status=order.status,
        payment_method=order.payment_method,
        title=order.title,
        created_at=order.created_at,
        paid_at=order.paid_at,
    )


@router.post("/orders/{order_no}/cancel", summary="取消订单")
async def cancel_order(
    order_no: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """取消订单"""
    result = await db.execute(
        select(PaymentOrder).where(
            PaymentOrder.order_no == order_no,
            PaymentOrder.user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    if order.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=400, detail="只能取消待支付订单")
    
    order.status = PaymentStatus.CANCELLED
    await db.commit()
    
    return {"message": "订单已取消"}


# ============ 余额相关 ============

@router.get("/balance", summary="获取余额")
async def get_balance(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取当前用户余额"""
    balance = await get_or_create_balance(db, current_user.id)
    
    return BalanceResponse(
        balance=balance.balance,
        frozen=balance.frozen,
        total_recharged=balance.total_recharged,
        total_consumed=balance.total_consumed,
    )


@router.get("/balance/transactions", summary="获取余额交易记录")
async def get_balance_transactions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """获取余额交易记录"""
    query = select(BalanceTransaction).where(
        BalanceTransaction.user_id == current_user.id
    )
    
    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total: int = int(await db.scalar(count_query) or 0)
    
    # 分页
    query = query.order_by(BalanceTransaction.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    transactions = result.scalars().all()
    
    items = [
        {
            "id": t.id,
            "type": t.type,
            "amount": t.amount,
            "balance_after": t.balance_after,
            "description": t.description,
            "created_at": t.created_at,
        }
        for t in transactions
    ]
    
    return {"items": items, "total": total}


# ============ 管理员接口 ============

@router.get("/admin/orders", summary="管理员-订单列表")
async def admin_get_orders(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: str | None = None,
    user_id: int | None = None,
):
    """管理员获取所有订单"""
    _ = current_user
    query = select(PaymentOrder, User.username).join(User, User.id == PaymentOrder.user_id)
    
    if status_filter:
        query = query.where(PaymentOrder.status == status_filter)
    if user_id:
        query = query.where(PaymentOrder.user_id == user_id)
    
    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total: int = int(await db.scalar(count_query) or 0)
    
    # 分页
    query = query.order_by(PaymentOrder.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = cast(list[tuple[PaymentOrder, str]], result.all())
     
    items: list[dict[str, object]] = []
    for o, username in rows:
        items.append({
            "id": o.id,
            "order_no": o.order_no,
            "user_id": o.user_id,
            "username": username,
            "order_type": o.order_type,
            "amount": o.amount,
            "actual_amount": o.actual_amount,
            "status": o.status,
            "payment_method": o.payment_method,
            "title": o.title,
            "created_at": o.created_at,
            "paid_at": o.paid_at,
        })
    
    return {"items": items, "total": total}


@router.post("/admin/refund/{order_no}", summary="管理员-退款")
async def admin_refund(
    order_no: str,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    """管理员退款"""
    _ = current_user
    result = await db.execute(
        select(PaymentOrder).where(PaymentOrder.order_no == order_no)
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    if order.status == PaymentStatus.REFUNDED:
        return {"message": "退款成功"}

    if order.status != PaymentStatus.PAID:
        raise HTTPException(status_code=400, detail="只能退款已支付订单")

    refund_amount = _quantize_amount(float(order.actual_amount))
    refund_amount_cents = _decimal_to_cents(refund_amount)

    try:
        # 原子更新订单状态，确保幂等
        order_update = await db.execute(
            update(PaymentOrder)
            .where(PaymentOrder.id == order.id, PaymentOrder.status == PaymentStatus.PAID)
            .values(status=PaymentStatus.REFUNDED)
        )
        if getattr(order_update, "rowcount", 0) != 1:
            raise HTTPException(status_code=400, detail="订单状态异常")

        # 如果是余额支付，退回余额
        if order.payment_method == "balance":
            balance_account = await _get_or_create_balance_in_tx(db, order.user_id)
            balance_before = _quantize_amount(float(balance_account.balance))

            balance_before_cents = _decimal_to_cents(balance_before)
            effective_balance_cents = func.coalesce(
                UserBalance.balance_cents,
                sa_cast(func.round(func.coalesce(UserBalance.balance, 0) * 100), Integer),
            )

            _ = await db.execute(
                update(UserBalance)
                .where(UserBalance.user_id == order.user_id)
                .values(
                    balance=func.coalesce(UserBalance.balance, 0) + float(refund_amount),
                    balance_cents=effective_balance_cents + refund_amount_cents,
                )
            )

            balance_after = balance_before + refund_amount
            balance_after_cents = balance_before_cents + refund_amount_cents
            transaction = BalanceTransaction(
                user_id=order.user_id,
                order_id=order.id,
                type="refund",
                amount=float(refund_amount),
                balance_before=float(balance_before),
                balance_after=float(balance_after),
                amount_cents=refund_amount_cents,
                balance_before_cents=balance_before_cents,
                balance_after_cents=balance_after_cents,
                description=f"退款: {order.title}",
            )
            db.add(transaction)

        from ..routers.system import log_admin_action

        await log_admin_action(
            db,
            int(current_user.id),
            "refund",
            "payment",
            target_id=int(order.id),
            description=f"refund order_no={str(order_no)}",
            request=request,
        )

        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    return {"message": "退款成功"}


@router.post("/admin/orders/{order_no}/mark-paid", summary="管理员-标记订单已支付")
async def admin_mark_paid(
    order_no: str,
    data: MarkPaidRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    """管理员标记订单已支付（开发环境/人工对账用）"""
    _ = current_user

    if data.payment_method not in {"alipay", "wechat"}:
        raise HTTPException(status_code=400, detail="无效的支付方式")

    result = await db.execute(select(PaymentOrder).where(PaymentOrder.order_no == order_no))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.status == PaymentStatus.PAID:
        return {"message": "订单已是支付成功状态"}

    if order.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=400, detail="订单状态异常")

    if order.order_type != "recharge":
        raise HTTPException(status_code=400, detail="仅充值订单支持该操作")

    paid_at = datetime.now(timezone.utc)
    trade_no = f"ADM{generate_order_no()}"
    recharge_amount = _quantize_amount(float(order.actual_amount))
    recharge_amount_cents = _decimal_to_cents(recharge_amount)

    try:
        order_update = await db.execute(
            update(PaymentOrder)
            .where(PaymentOrder.id == order.id, PaymentOrder.status == PaymentStatus.PENDING)
            .values(
                status=PaymentStatus.PAID,
                payment_method=data.payment_method,
                paid_at=paid_at,
                trade_no=trade_no,
                amount_cents=func.coalesce(
                    PaymentOrder.amount_cents,
                    sa_cast(func.round(PaymentOrder.amount * 100), Integer),
                ),
                actual_amount_cents=recharge_amount_cents,
            )
        )
        if getattr(order_update, "rowcount", 0) != 1:
            raise HTTPException(status_code=400, detail="订单状态异常")

        balance_account = await _get_or_create_balance_in_tx(db, order.user_id)
        balance_before = _quantize_amount(float(balance_account.balance))

        balance_before_cents = _decimal_to_cents(balance_before)
        effective_balance_cents = func.coalesce(
            UserBalance.balance_cents,
            sa_cast(func.round(func.coalesce(UserBalance.balance, 0) * 100), Integer),
        )
        effective_total_recharged_cents = func.coalesce(
            UserBalance.total_recharged_cents,
            sa_cast(func.round(func.coalesce(UserBalance.total_recharged, 0) * 100), Integer),
        )

        _ = await db.execute(
            update(UserBalance)
            .where(UserBalance.user_id == order.user_id)
            .values(
                balance=func.coalesce(UserBalance.balance, 0) + float(recharge_amount),
                total_recharged=func.coalesce(UserBalance.total_recharged, 0) + float(recharge_amount),
                balance_cents=effective_balance_cents + recharge_amount_cents,
                total_recharged_cents=effective_total_recharged_cents + recharge_amount_cents,
            )
        )

        balance_after = balance_before + recharge_amount
        balance_after_cents = balance_before_cents + recharge_amount_cents
        transaction = BalanceTransaction(
            user_id=order.user_id,
            order_id=order.id,
            type="recharge",
            amount=float(recharge_amount),
            balance_before=float(balance_before),
            balance_after=float(balance_after),
            amount_cents=recharge_amount_cents,
            balance_before_cents=balance_before_cents,
            balance_after_cents=balance_after_cents,
            description=f"充值: {order.title}",
        )
        db.add(transaction)

        from ..routers.system import log_admin_action

        await log_admin_action(
            db,
            int(current_user.id),
            "mark_paid",
            "payment",
            target_id=int(order.id),
            description=f"mark_paid order_no={str(order_no)} method={str(getattr(data, 'payment_method', '') or '')}",
            request=request,
        )

        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    return {"message": "标记成功"}


@router.get("/admin/stats", summary="管理员-支付统计")
async def admin_payment_stats(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """支付统计数据"""
    _ = current_user
    # 总订单数
    total_orders = await db.scalar(select(func.count()).select_from(PaymentOrder)) or 0
    
    # 已支付订单
    paid_orders = await db.scalar(
        select(func.count()).select_from(PaymentOrder).where(
            PaymentOrder.status == PaymentStatus.PAID
        )
    ) or 0
    
    # 总收入
    total_revenue_cents = await db.scalar(
        select(
            func.sum(
                func.coalesce(
                    PaymentOrder.actual_amount_cents,
                    sa_cast(func.round(PaymentOrder.actual_amount * 100), Integer),
                )
            )
        ).where(PaymentOrder.status == PaymentStatus.PAID)
    ) or 0
    total_revenue = float((Decimal(int(total_revenue_cents)) / 100).quantize(Decimal("0.01")))
    
    # 今日收入
    today = datetime.now(timezone.utc).date()
    today_revenue_cents = await db.scalar(
        select(
            func.sum(
                func.coalesce(
                    PaymentOrder.actual_amount_cents,
                    sa_cast(func.round(PaymentOrder.actual_amount * 100), Integer),
                )
            )
        ).where(
            PaymentOrder.status == PaymentStatus.PAID,
            func.date(PaymentOrder.paid_at) == today,
        )
    ) or 0
    today_revenue = float((Decimal(int(today_revenue_cents)) / 100).quantize(Decimal("0.01")))
    
    return {
        "total_orders": total_orders,
        "paid_orders": paid_orders,
        "total_revenue": total_revenue,
        "today_revenue": today_revenue,
        "conversion_rate": round(paid_orders / max(total_orders, 1) * 100, 1),
    }
