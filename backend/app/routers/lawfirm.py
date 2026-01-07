"""法律咨询所API路由"""
from datetime import datetime, timedelta, timezone
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_, desc, update, cast as sa_cast, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models.lawfirm import (
    LawyerVerification,
    Lawyer,
    LawFirm,
    LawyerConsultation,
    LawyerConsultationMessage,
    LawyerReview,
)
from ..models.payment import PaymentOrder, PaymentStatus, UserBalance, BalanceTransaction
from ..models.user import User
from ..services.settlement_service import settlement_service
from ..schemas.lawfirm import (
    LawFirmCreate, LawFirmUpdate, LawFirmResponse, LawFirmListResponse,
    LawyerCreate, LawyerResponse, LawyerListResponse,
    ConsultationCreate, ConsultationResponse, ConsultationListResponse,
    ReviewCreate, ReviewResponse, ReviewListResponse
)
from ..services.lawfirm_service import (
    lawfirm_service, lawyer_service, consultation_service, review_service
)
from ..utils.deps import get_current_user, require_admin

router = APIRouter(prefix="/lawfirm", tags=["律所服务"])


def _split_specialties(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [p.strip() for p in value.replace("，", ",").split(",")]
    return [p for p in parts if p]


async def _get_owned_consultation(db: AsyncSession, consultation_id: int, user_id: int):
    res = await db.execute(
        select(LawyerConsultation)
        .options(selectinload(LawyerConsultation.lawyer))
        .where(
            LawyerConsultation.id == int(consultation_id),
            LawyerConsultation.user_id == int(user_id),
        )
    )
    return res.scalar_one_or_none()


async def _get_participating_consultation(
    db: AsyncSession,
    consultation_id: int,
    *,
    current_user: User,
) -> tuple[LawyerConsultation | None, str | None]:
    # 管理员允许只读查看（便于运营/排障），但不允许发送消息
    role = str(getattr(current_user, "role", "") or "").lower()
    if role in {"admin", "super_admin"}:
        res = await db.execute(
            select(LawyerConsultation)
            .options(selectinload(LawyerConsultation.lawyer))
            .where(LawyerConsultation.id == int(consultation_id))
        )
        return res.scalar_one_or_none(), "admin"

    if role == "lawyer":
        lawyer = await _get_current_lawyer(db, int(current_user.id))
        if not lawyer:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")
        res = await db.execute(
            select(LawyerConsultation)
            .options(selectinload(LawyerConsultation.lawyer))
            .where(
                LawyerConsultation.id == int(consultation_id),
                LawyerConsultation.lawyer_id == int(lawyer.id),
            )
        )
        return res.scalar_one_or_none(), "lawyer"

    consultation = await _get_owned_consultation(db, consultation_id, int(current_user.id))
    return consultation, "user"


async def _get_latest_consultation_order_any(
    db: AsyncSession,
    consultation_id: int,
) -> PaymentOrder | None:
    res = await db.execute(
        select(PaymentOrder)
        .where(
            PaymentOrder.related_type == "lawyer_consultation",
            PaymentOrder.related_id == int(consultation_id),
        )
        .order_by(PaymentOrder.created_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def _get_current_lawyer(db: AsyncSession, user_id: int) -> Lawyer | None:
    res = await db.execute(
        select(Lawyer).where(
            Lawyer.user_id == int(user_id),
            Lawyer.is_active == True,
        )
    )
    return res.scalar_one_or_none()


async def _get_latest_verification(db: AsyncSession, user_id: int) -> LawyerVerification | None:
    res = await db.execute(
        select(LawyerVerification)
        .where(LawyerVerification.user_id == int(user_id))
        .order_by(LawyerVerification.created_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def _require_verified_lawyer(db: AsyncSession, current_user: User) -> Lawyer:
    role = str(getattr(current_user, "role", "") or "").lower()
    if role in {"admin", "super_admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="管理员不支持使用律师工作台")

    if role != "lawyer":
        v = await _get_latest_verification(db, int(current_user.id))
        if v and str(getattr(v, "status", "") or "").lower() == "pending":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="律师认证审核中")
        if v and str(getattr(v, "status", "") or "").lower() == "rejected":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="律师认证已驳回")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要律师权限")

    lawyer = await _get_current_lawyer(db, int(current_user.id))
    if not lawyer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未绑定律师资料")

    if not bool(getattr(lawyer, "is_verified", False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="律师认证未通过")

    return lawyer


def _generate_order_no() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


def _quantize_amount(amount: float) -> Decimal:
    return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _decimal_to_cents(amount: Decimal) -> int:
    return int(amount * 100)


async def _get_latest_consultation_order(
    db: AsyncSession,
    consultation_id: int,
    *,
    user_id: int,
) -> PaymentOrder | None:
    res = await db.execute(
        select(PaymentOrder)
        .where(
            PaymentOrder.user_id == int(user_id),
            PaymentOrder.related_type == "lawyer_consultation",
            PaymentOrder.related_id == int(consultation_id),
        )
        .order_by(PaymentOrder.created_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


# ============ 律所相关 ============

@router.get("/firms", response_model=LawFirmListResponse, summary="获取律所列表")
async def get_law_firms(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    city: str | None = None,
    keyword: str | None = None,
):
    """获取律所列表"""
    firms, total = await lawfirm_service.get_list(db, page, page_size, city, keyword)
    
    items: list[LawFirmResponse] = []
    for firm in firms:
        lawyer_count = await lawfirm_service.get_lawyer_count(db, firm.id)
        items.append(LawFirmResponse(
            id=firm.id,
            name=firm.name,
            description=firm.description,
            address=firm.address,
            city=firm.city,
            province=firm.province,
            phone=firm.phone,
            email=firm.email,
            website=firm.website,
            logo=firm.logo,
            license_no=firm.license_no,
            specialties=_split_specialties(firm.specialties),
            rating=firm.rating,
            review_count=firm.review_count,
            is_verified=firm.is_verified,
            is_active=firm.is_active,
            created_at=firm.created_at,
            lawyer_count=lawyer_count
        ))
    
    return LawFirmListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/firms/{firm_id}", response_model=LawFirmResponse, summary="获取律所详情")
async def get_law_firm(firm_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    """获取律所详情"""
    firm = await lawfirm_service.get_by_id(db, firm_id)
    if not firm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="律所不存在")
    
    lawyer_count = await lawfirm_service.get_lawyer_count(db, firm.id)
    return LawFirmResponse(
        id=firm.id,
        name=firm.name,
        description=firm.description,
        address=firm.address,
        city=firm.city,
        province=firm.province,
        phone=firm.phone,
        email=firm.email,
        website=firm.website,
        logo=firm.logo,
        license_no=firm.license_no,
        specialties=_split_specialties(firm.specialties),
        rating=firm.rating,
        review_count=firm.review_count,
        is_verified=firm.is_verified,
        is_active=firm.is_active,
        created_at=firm.created_at,
        lawyer_count=lawyer_count
    )


@router.post("/firms", response_model=LawFirmResponse, summary="创建律所")
async def create_law_firm(
    data: LawFirmCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """创建律所（需要管理员权限）"""
    _ = current_user
    firm = await lawfirm_service.create(db, data)
    return LawFirmResponse(
        id=firm.id,
        name=firm.name,
        description=firm.description,
        address=firm.address,
        city=firm.city,
        province=firm.province,
        phone=firm.phone,
        email=firm.email,
        website=firm.website,
        logo=firm.logo,
        license_no=firm.license_no,
        specialties=_split_specialties(firm.specialties),
        rating=firm.rating,
        review_count=firm.review_count,
        is_verified=firm.is_verified,
        is_active=firm.is_active,
        created_at=firm.created_at,
        lawyer_count=0
    )


@router.get("/admin/firms", response_model=LawFirmListResponse, summary="管理员获取律所列表")
async def admin_list_law_firms(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    city: str | None = None,
    keyword: str | None = None,
    include_inactive: Annotated[bool, Query(description="是否包含已禁用的律所")] = True,
):
    """管理员获取律所列表（可包含已禁用律所）"""
    _ = current_user

    query = select(LawFirm)
    count_query = select(func.count(LawFirm.id))

    if not include_inactive:
        query = query.where(LawFirm.is_active == True)
        count_query = count_query.where(LawFirm.is_active == True)

    if city:
        query = query.where(LawFirm.city == city)
        count_query = count_query.where(LawFirm.city == city)

    if keyword:
        search_filter = or_(
            LawFirm.name.contains(keyword),
            LawFirm.specialties.contains(keyword),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    query = query.order_by(desc(LawFirm.is_verified), desc(LawFirm.is_active), desc(LawFirm.rating))
    query = query.offset((page - 1) * page_size).limit(page_size)

    firms = (await db.execute(query)).scalars().all()
    total = int((await db.execute(count_query)).scalar() or 0)

    items: list[LawFirmResponse] = []
    for firm in firms:
        lawyer_count = await lawfirm_service.get_lawyer_count(db, firm.id)
        items.append(
            LawFirmResponse(
                id=firm.id,
                name=firm.name,
                description=firm.description,
                address=firm.address,
                city=firm.city,
                province=firm.province,
                phone=firm.phone,
                email=firm.email,
                website=firm.website,
                logo=firm.logo,
                license_no=firm.license_no,
                specialties=_split_specialties(firm.specialties),
                rating=firm.rating,
                review_count=firm.review_count,
                is_verified=firm.is_verified,
                is_active=firm.is_active,
                created_at=firm.created_at,
                lawyer_count=lawyer_count,
            )
        )

    return LawFirmListResponse(items=items, total=total, page=page, page_size=page_size)


@router.put("/admin/firms/{firm_id}", response_model=LawFirmResponse, summary="管理员更新律所")
async def admin_update_law_firm(
    firm_id: int,
    data: LawFirmUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """管理员更新律所信息（含认证/启用禁用）"""
    _ = current_user
    firm = (await db.execute(select(LawFirm).where(LawFirm.id == firm_id))).scalar_one_or_none()
    if not firm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="律所不存在")

    firm = await lawfirm_service.update(db, firm, data)
    lawyer_count = await lawfirm_service.get_lawyer_count(db, firm.id)
    return LawFirmResponse(
        id=firm.id,
        name=firm.name,
        description=firm.description,
        address=firm.address,
        city=firm.city,
        province=firm.province,
        phone=firm.phone,
        email=firm.email,
        website=firm.website,
        logo=firm.logo,
        license_no=firm.license_no,
        specialties=_split_specialties(firm.specialties),
        rating=firm.rating,
        review_count=firm.review_count,
        is_verified=firm.is_verified,
        is_active=firm.is_active,
        created_at=firm.created_at,
        lawyer_count=lawyer_count,
    )


@router.delete("/admin/firms/{firm_id}", summary="管理员删除律所")
async def admin_delete_law_firm(
    firm_id: int,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """管理员软删除律所（设置 is_active=false）"""
    _ = current_user
    firm = (await db.execute(select(LawFirm).where(LawFirm.id == firm_id))).scalar_one_or_none()
    if not firm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="律所不存在")

    firm.is_active = False
    db.add(firm)
    await db.commit()
    return {"message": "删除成功"}


# ============ 律师相关 ============

@router.get("/lawyers", response_model=LawyerListResponse, summary="获取律师列表")
async def get_lawyers(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    firm_id: int | None = None,
    specialty: str | None = None,
    keyword: str | None = None,
):
    """获取律师列表"""
    lawyers, total = await lawyer_service.get_list(db, page, page_size, firm_id, specialty, keyword)
    
    items: list[LawyerResponse] = []
    for lawyer in lawyers:
        items.append(LawyerResponse(
            id=lawyer.id,
            user_id=lawyer.user_id,
            firm_id=lawyer.firm_id,
            name=lawyer.name,
            avatar=lawyer.avatar,
            title=lawyer.title,
            license_no=lawyer.license_no,
            phone=lawyer.phone,
            email=lawyer.email,
            introduction=lawyer.introduction,
            specialties=lawyer.specialties,
            experience_years=lawyer.experience_years,
            case_count=lawyer.case_count,
            rating=lawyer.rating,
            review_count=lawyer.review_count,
            consultation_fee=lawyer.consultation_fee,
            is_verified=lawyer.is_verified,
            is_active=lawyer.is_active,
            created_at=lawyer.created_at,
            firm_name=lawyer.firm.name if lawyer.firm else None
        ))
    
    return LawyerListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/lawyers/{lawyer_id}", response_model=LawyerResponse, summary="获取律师详情")
async def get_lawyer(lawyer_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    """获取律师详情"""
    lawyer = await lawyer_service.get_by_id(db, lawyer_id)
    if not lawyer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="律师不存在")
    
    return LawyerResponse(
        id=lawyer.id,
        user_id=lawyer.user_id,
        firm_id=lawyer.firm_id,
        name=lawyer.name,
        avatar=lawyer.avatar,
        title=lawyer.title,
        license_no=lawyer.license_no,
        phone=lawyer.phone,
        email=lawyer.email,
        introduction=lawyer.introduction,
        specialties=lawyer.specialties,
        experience_years=lawyer.experience_years,
        case_count=lawyer.case_count,
        rating=lawyer.rating,
        review_count=lawyer.review_count,
        consultation_fee=lawyer.consultation_fee,
        is_verified=lawyer.is_verified,
        is_active=lawyer.is_active,
        created_at=lawyer.created_at,
        firm_name=lawyer.firm.name if lawyer.firm else None
    )


@router.post("/lawyers", response_model=LawyerResponse, summary="创建律师")
async def create_lawyer(
    data: LawyerCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """创建律师（需要管理员权限）"""
    _ = current_user
    lawyer = await lawyer_service.create(db, data)
    return LawyerResponse(
        id=lawyer.id,
        user_id=lawyer.user_id,
        firm_id=lawyer.firm_id,
        name=lawyer.name,
        avatar=lawyer.avatar,
        title=lawyer.title,
        license_no=lawyer.license_no,
        phone=lawyer.phone,
        email=lawyer.email,
        introduction=lawyer.introduction,
        specialties=lawyer.specialties,
        experience_years=lawyer.experience_years,
        case_count=lawyer.case_count,
        rating=lawyer.rating,
        review_count=lawyer.review_count,
        consultation_fee=lawyer.consultation_fee,
        is_verified=lawyer.is_verified,
        is_active=lawyer.is_active,
        created_at=lawyer.created_at,
        firm_name=None
    )


# ============ 咨询预约相关 ============

@router.post("/consultations", response_model=ConsultationResponse, summary="预约咨询")
async def create_consultation(
    data: ConsultationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """预约律师咨询"""
    # 检查律师是否存在
    lawyer = await lawyer_service.get_by_id(db, data.lawyer_id)
    if not lawyer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="律师不存在")
    
    consultation = await consultation_service.create(db, current_user.id, data)

    order: PaymentOrder | None = None
    fee = float(getattr(lawyer, "consultation_fee", 0.0) or 0.0)
    if fee > 0:
        amount = _quantize_amount(fee)
        amount_cents = _decimal_to_cents(amount)
        order = PaymentOrder(
            order_no=_generate_order_no(),
            user_id=int(current_user.id),
            order_type="consultation",
            amount=float(amount),
            actual_amount=float(amount),
            amount_cents=amount_cents,
            actual_amount_cents=amount_cents,
            status=PaymentStatus.PENDING,
            title=f"律师咨询：{lawyer.name}",
            description=data.subject,
            related_id=int(consultation.id),
            related_type="lawyer_consultation",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)

    return ConsultationResponse(
        id=consultation.id,
        user_id=consultation.user_id,
        lawyer_id=consultation.lawyer_id,
        subject=consultation.subject,
        description=consultation.description,
        category=consultation.category,
        contact_phone=consultation.contact_phone,
        preferred_time=consultation.preferred_time,
        status=consultation.status,
        admin_note=consultation.admin_note,
        created_at=consultation.created_at,
        updated_at=consultation.updated_at,
        lawyer_name=lawyer.name,
        payment_order_no=order.order_no if order else None,
        payment_status=order.status if order else None,
        payment_amount=order.actual_amount if order else None,
    )


@router.get("/lawyer/consultations", response_model=ConsultationListResponse, summary="律师-获取我的咨询预约")
async def lawyer_get_my_consultations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    lawyer = await _require_verified_lawyer(db, current_user)

    query = (
        select(LawyerConsultation)
        .options(selectinload(LawyerConsultation.lawyer))
        .where(LawyerConsultation.lawyer_id == int(lawyer.id))
        .order_by(desc(LawyerConsultation.created_at))
    )
    count_query = select(func.count(LawyerConsultation.id)).where(
        LawyerConsultation.lawyer_id == int(lawyer.id)
    )

    total_result = await db.execute(count_query)
    total = int(total_result.scalar() or 0)

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    consultations = list(result.scalars().all())

    consultation_ids = [int(c.id) for c in consultations]
    orders_by_consultation: dict[int, PaymentOrder] = {}
    if consultation_ids:
        orders_res = await db.execute(
            select(PaymentOrder)
            .where(
                PaymentOrder.related_type == "lawyer_consultation",
                PaymentOrder.related_id.in_(consultation_ids),
            )
            .order_by(PaymentOrder.created_at.desc())
        )
        for o in orders_res.scalars().all():
            rid = getattr(o, "related_id", None)
            if isinstance(rid, int) and rid not in orders_by_consultation:
                orders_by_consultation[rid] = o

    items: list[ConsultationResponse] = []
    for c in consultations:
        o = orders_by_consultation.get(int(c.id))
        items.append(
            ConsultationResponse(
                id=c.id,
                user_id=c.user_id,
                lawyer_id=c.lawyer_id,
                subject=c.subject,
                description=c.description,
                category=c.category,
                contact_phone=c.contact_phone,
                preferred_time=c.preferred_time,
                status=c.status,
                admin_note=c.admin_note,
                created_at=c.created_at,
                updated_at=c.updated_at,
                lawyer_name=lawyer.name,
                payment_order_no=o.order_no if o else None,
                payment_status=o.status if o else None,
                payment_amount=o.actual_amount if o else None,
            )
        )

    return ConsultationListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/lawyer/consultations/{consultation_id}/accept", response_model=ConsultationResponse, summary="律师-接单")
async def lawyer_accept_consultation(
    consultation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lawyer = await _require_verified_lawyer(db, current_user)

    res = await db.execute(
        select(LawyerConsultation)
        .options(selectinload(LawyerConsultation.lawyer))
        .where(
            LawyerConsultation.id == int(consultation_id),
            LawyerConsultation.lawyer_id == int(lawyer.id),
        )
    )
    consultation = res.scalar_one_or_none()
    if not consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="咨询不存在")

    order = await _get_latest_consultation_order_any(db, int(consultation.id))
    if order and str(order.status).lower() == "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户尚未完成支付")

    if consultation.status == "confirmed":
        return ConsultationResponse(
            id=consultation.id,
            user_id=consultation.user_id,
            lawyer_id=consultation.lawyer_id,
            subject=consultation.subject,
            description=consultation.description,
            category=consultation.category,
            contact_phone=consultation.contact_phone,
            preferred_time=consultation.preferred_time,
            status=consultation.status,
            admin_note=consultation.admin_note,
            created_at=consultation.created_at,
            updated_at=consultation.updated_at,
            lawyer_name=lawyer.name,
            payment_order_no=order.order_no if order else None,
            payment_status=order.status if order else None,
            payment_amount=order.actual_amount if order else None,
        )

    if consultation.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅待处理咨询可接单")

    consultation.status = "confirmed"
    db.add(consultation)
    await db.commit()
    await db.refresh(consultation)

    return ConsultationResponse(
        id=consultation.id,
        user_id=consultation.user_id,
        lawyer_id=consultation.lawyer_id,
        subject=consultation.subject,
        description=consultation.description,
        category=consultation.category,
        contact_phone=consultation.contact_phone,
        preferred_time=consultation.preferred_time,
        status=consultation.status,
        admin_note=consultation.admin_note,
        created_at=consultation.created_at,
        updated_at=consultation.updated_at,
        lawyer_name=lawyer.name,
        payment_order_no=order.order_no if order else None,
        payment_status=order.status if order else None,
        payment_amount=order.actual_amount if order else None,
    )


@router.post("/lawyer/consultations/{consultation_id}/reject", response_model=ConsultationResponse, summary="律师-拒单")
async def lawyer_reject_consultation(
    consultation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lawyer = await _require_verified_lawyer(db, current_user)

    res = await db.execute(
        select(LawyerConsultation)
        .options(selectinload(LawyerConsultation.lawyer))
        .where(
            LawyerConsultation.id == int(consultation_id),
            LawyerConsultation.lawyer_id == int(lawyer.id),
        )
    )
    consultation = res.scalar_one_or_none()
    if not consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="咨询不存在")

    if consultation.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅待处理咨询可拒单")

    order = await _get_latest_consultation_order_any(db, int(consultation.id))
    if order and str(order.status).lower() == "paid":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="订单已支付，请走退款流程")

    consultation.status = "cancelled"
    db.add(consultation)
    await db.commit()
    await db.refresh(consultation)

    return ConsultationResponse(
        id=consultation.id,
        user_id=consultation.user_id,
        lawyer_id=consultation.lawyer_id,
        subject=consultation.subject,
        description=consultation.description,
        category=consultation.category,
        contact_phone=consultation.contact_phone,
        preferred_time=consultation.preferred_time,
        status=consultation.status,
        admin_note=consultation.admin_note,
        created_at=consultation.created_at,
        updated_at=consultation.updated_at,
        lawyer_name=lawyer.name,
        payment_order_no=order.order_no if order else None,
        payment_status=order.status if order else None,
        payment_amount=order.actual_amount if order else None,
    )


@router.post("/lawyer/consultations/{consultation_id}/complete", response_model=ConsultationResponse, summary="律师-标记完成")
async def lawyer_complete_consultation(
    consultation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lawyer = await _require_verified_lawyer(db, current_user)

    res = await db.execute(
        select(LawyerConsultation)
        .options(selectinload(LawyerConsultation.lawyer))
        .where(
            LawyerConsultation.id == int(consultation_id),
            LawyerConsultation.lawyer_id == int(lawyer.id),
        )
    )
    consultation = res.scalar_one_or_none()
    if not consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="咨询不存在")

    if consultation.status != "confirmed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅已确认咨询可标记完成")

    consultation.status = "completed"
    db.add(consultation)
    await db.commit()
    await db.refresh(consultation)

    order = await _get_latest_consultation_order_any(db, int(consultation.id))

    _ = await settlement_service.ensure_income_record_for_completed_consultation(
        db,
        consultation,
        order,
    )

    return ConsultationResponse(
        id=consultation.id,
        user_id=consultation.user_id,
        lawyer_id=consultation.lawyer_id,
        subject=consultation.subject,
        description=consultation.description,
        category=consultation.category,
        contact_phone=consultation.contact_phone,
        preferred_time=consultation.preferred_time,
        status=consultation.status,
        admin_note=consultation.admin_note,
        created_at=consultation.created_at,
        updated_at=consultation.updated_at,
        lawyer_name=lawyer.name,
        payment_order_no=order.order_no if order else None,
        payment_status=order.status if order else None,
        payment_amount=order.actual_amount if order else None,
    )


@router.get("/consultations", response_model=ConsultationListResponse, summary="获取我的咨询")
async def get_my_consultations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """获取当前用户的咨询列表"""
    consultations, total = await consultation_service.get_user_consultations(
        db, current_user.id, page, page_size
    )
    
    consultation_ids = [int(c.id) for c in consultations]
    orders_by_consultation: dict[int, PaymentOrder] = {}
    if consultation_ids:
        orders_res = await db.execute(
            select(PaymentOrder)
            .where(
                PaymentOrder.user_id == int(current_user.id),
                PaymentOrder.related_type == "lawyer_consultation",
                PaymentOrder.related_id.in_(consultation_ids),
            )
            .order_by(PaymentOrder.created_at.desc())
        )
        for o in orders_res.scalars().all():
            rid = getattr(o, "related_id", None)
            if isinstance(rid, int) and rid not in orders_by_consultation:
                orders_by_consultation[rid] = o

    reviews_by_consultation: dict[int, LawyerReview] = {}
    if consultation_ids:
        reviews_res = await db.execute(
            select(LawyerReview)
            .where(
                LawyerReview.user_id == int(current_user.id),
                LawyerReview.consultation_id.in_(consultation_ids),
            )
            .order_by(LawyerReview.created_at.desc())
        )
        for r in reviews_res.scalars().all():
            cid = getattr(r, "consultation_id", None)
            if isinstance(cid, int) and cid not in reviews_by_consultation:
                reviews_by_consultation[cid] = r

    items: list[ConsultationResponse] = []
    for c in consultations:
        o = orders_by_consultation.get(int(c.id))
        r = reviews_by_consultation.get(int(c.id))
        review_id = int(r.id) if r else None
        can_review = (str(c.status).lower() == "completed") and (review_id is None)
        items.append(ConsultationResponse(
            id=c.id,
            user_id=c.user_id,
            lawyer_id=c.lawyer_id,
            subject=c.subject,
            description=c.description,
            category=c.category,
            contact_phone=c.contact_phone,
            preferred_time=c.preferred_time,
            status=c.status,
            admin_note=c.admin_note,
            created_at=c.created_at,
            updated_at=c.updated_at,
            lawyer_name=c.lawyer.name if c.lawyer else None,
            payment_order_no=o.order_no if o else None,
            payment_status=o.status if o else None,
            payment_amount=o.actual_amount if o else None,
            review_id=review_id,
            can_review=can_review,
        ))
    
    return ConsultationListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/consultations/{consultation_id}/cancel", response_model=ConsultationResponse, summary="取消我的咨询")
async def cancel_my_consultation(
    consultation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """取消当前用户的咨询预约"""
    consultation = await _get_owned_consultation(db, consultation_id, current_user.id)
    if not consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="咨询不存在")

    if consultation.status == "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="咨询已完成，无法取消")

    order = await _get_latest_consultation_order(db, int(consultation.id), user_id=int(current_user.id))

    try:
        if order and order.status == PaymentStatus.PAID:
            if str(order.payment_method or "").lower() != "balance":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="订单已支付，暂不支持自动退款，请联系管理员")

            refund_amount = _quantize_amount(float(order.actual_amount))
            refund_amount_cents = _decimal_to_cents(refund_amount)

            order_update = await db.execute(
                update(PaymentOrder)
                .where(PaymentOrder.id == order.id, PaymentOrder.status == PaymentStatus.PAID)
                .values(status=PaymentStatus.REFUNDED)
            )
            if getattr(order_update, "rowcount", 0) == 1:
                order.status = PaymentStatus.REFUNDED

                bal_res = await db.execute(select(UserBalance).where(UserBalance.user_id == order.user_id))
                balance_account = bal_res.scalar_one_or_none()
                if balance_account is None:
                    balance_account = UserBalance(
                        user_id=int(order.user_id),
                        balance=0.0,
                        frozen=0.0,
                        total_recharged=0.0,
                        total_consumed=0.0,
                    )
                    db.add(balance_account)
                    await db.flush()

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

        if consultation.status != "cancelled":
            consultation.status = "cancelled"
            db.add(consultation)

        await db.commit()
        await db.refresh(consultation)
        if order is not None:
            try:
                await db.refresh(order)
            except Exception:
                pass
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    return ConsultationResponse(
        id=consultation.id,
        user_id=consultation.user_id,
        lawyer_id=consultation.lawyer_id,
        subject=consultation.subject,
        description=consultation.description,
        category=consultation.category,
        contact_phone=consultation.contact_phone,
        preferred_time=consultation.preferred_time,
        status=consultation.status,
        admin_note=consultation.admin_note,
        created_at=consultation.created_at,
        updated_at=consultation.updated_at,
        lawyer_name=consultation.lawyer.name if consultation.lawyer else None,
        payment_order_no=order.order_no if order else None,
        payment_status=order.status if order else None,
        payment_amount=order.actual_amount if order else None,
    )


# ============ 咨询留言/消息线程 ============


class ConsultationMessageCreate(BaseModel):
    content: str


class ConsultationMessageResponse(BaseModel):
    id: int
    consultation_id: int
    sender_user_id: int
    sender_role: str
    sender_name: str | None = None
    content: str
    created_at: datetime


class ConsultationMessageListResponse(BaseModel):
    items: list[ConsultationMessageResponse]
    total: int
    page: int
    page_size: int


@router.get(
    "/consultations/{consultation_id}/messages",
    response_model=ConsultationMessageListResponse,
    summary="获取咨询留言",
)
async def get_consultation_messages(
    consultation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
):
    consultation, _ = await _get_participating_consultation(
        db, int(consultation_id), current_user=current_user
    )
    if not consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="咨询不存在")

    count_res = await db.execute(
        select(func.count(LawyerConsultationMessage.id)).where(
            LawyerConsultationMessage.consultation_id == int(consultation.id)
        )
    )
    total = int(count_res.scalar() or 0)

    res = await db.execute(
        select(LawyerConsultationMessage)
        .options(selectinload(LawyerConsultationMessage.sender))
        .where(LawyerConsultationMessage.consultation_id == int(consultation.id))
        .order_by(LawyerConsultationMessage.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    messages = list(res.scalars().all())

    items: list[ConsultationMessageResponse] = []
    for m in messages:
        sender_name = m.sender.nickname or m.sender.username
        items.append(
            ConsultationMessageResponse(
                id=int(m.id),
                consultation_id=int(m.consultation_id),
                sender_user_id=int(m.sender_user_id),
                sender_role=str(m.sender_role),
                sender_name=sender_name,
                content=str(m.content),
                created_at=m.created_at,
            )
        )

    return ConsultationMessageListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/consultations/{consultation_id}/messages",
    response_model=ConsultationMessageResponse,
    summary="发送咨询留言",
)
async def create_consultation_message(
    consultation_id: int,
    data: ConsultationMessageCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    consultation, sender_role = await _get_participating_consultation(
        db, int(consultation_id), current_user=current_user
    )
    if not consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="咨询不存在")

    if sender_role not in {"user", "lawyer"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅咨询双方可发送消息")

    content = str(getattr(data, "content", "") or "").strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="消息内容不能为空")

    msg = LawyerConsultationMessage(
        consultation_id=int(consultation.id),
        sender_user_id=int(current_user.id),
        sender_role=str(sender_role),
        content=content,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    return ConsultationMessageResponse(
        id=int(msg.id),
        consultation_id=int(msg.consultation_id),
        sender_user_id=int(msg.sender_user_id),
        sender_role=str(msg.sender_role),
        sender_name=current_user.nickname or current_user.username,
        content=str(msg.content),
        created_at=msg.created_at,
    )


# ============ 评价相关 ============

@router.post("/reviews", response_model=ReviewResponse, summary="提交评价")
async def create_review(
    data: ReviewCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """提交律师评价"""
    # 检查律师是否存在
    lawyer = await lawyer_service.get_by_id(db, data.lawyer_id)
    if not lawyer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="律师不存在")

    if data.consultation_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="必须指定咨询ID")

    consultation = await _get_owned_consultation(db, int(data.consultation_id), int(current_user.id))
    if not consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="咨询不存在")

    if int(consultation.lawyer_id) != int(data.lawyer_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="咨询与律师不匹配")

    if str(consultation.status).lower() != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅已完成咨询可评价")

    existing = await db.execute(
        select(LawyerReview).where(
            LawyerReview.user_id == int(current_user.id),
            LawyerReview.consultation_id == int(data.consultation_id),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该咨询已评价")
    
    review = await review_service.create(db, current_user.id, data)
    return ReviewResponse(
        id=review.id,
        lawyer_id=review.lawyer_id,
        user_id=review.user_id,
        consultation_id=review.consultation_id,
        rating=review.rating,
        content=review.content,
        is_anonymous=review.is_anonymous,
        created_at=review.created_at,
        username=None if review.is_anonymous else current_user.username
    )


@router.get("/lawyers/{lawyer_id}/reviews", response_model=ReviewListResponse, summary="获取律师评价")
async def get_lawyer_reviews(
    lawyer_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """获取律师评价列表"""
    reviews, total, avg_rating = await review_service.get_lawyer_reviews(db, lawyer_id, page, page_size)
    
    items: list[ReviewResponse] = []
    for r in reviews:
        items.append(ReviewResponse(
            id=r.id,
            lawyer_id=r.lawyer_id,
            user_id=r.user_id,
            consultation_id=r.consultation_id,
            rating=r.rating,
            content=r.content,
            is_anonymous=r.is_anonymous,
            created_at=r.created_at,
            username=None if r.is_anonymous else (r.user.username if r.user else None)
        ))
    
    return ReviewListResponse(items=items, total=total, average_rating=round(avg_rating, 1))


# ============ 律师认证 ============

class VerificationCreate(BaseModel):
    """律师认证申请"""
    real_name: str
    id_card_no: str
    license_no: str
    firm_name: str
    id_card_front: str | None = None
    id_card_back: str | None = None
    license_photo: str | None = None
    specialties: str | None = None
    introduction: str | None = None
    experience_years: int = 0


class VerificationResponse(BaseModel):
    id: int
    user_id: int
    real_name: str
    license_no: str
    firm_name: str
    status: str
    reject_reason: str | None
    created_at: datetime
    reviewed_at: datetime | None


class VerificationReview(BaseModel):
    """审核认证申请"""
    approved: bool
    reject_reason: str | None = None


@router.post("/verification/apply", summary="申请律师认证")
async def apply_verification(
    data: VerificationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    用户申请律师认证
    
    提交实名信息和执业资质进行审核
    """
    # 检查是否已有待审核的申请
    existing = await db.execute(
        select(LawyerVerification).where(
            LawyerVerification.user_id == current_user.id,
            LawyerVerification.status == "pending"
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="您已有待审核的认证申请")
    
    # 检查是否已是认证律师
    lawyer_check = await db.execute(
        select(Lawyer).where(
            Lawyer.user_id == current_user.id,
            Lawyer.is_verified == True
        )
    )
    if lawyer_check.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="您已是认证律师")
    
    verification = LawyerVerification(
        user_id=current_user.id,
        real_name=data.real_name,
        id_card_no=data.id_card_no,
        license_no=data.license_no,
        firm_name=data.firm_name,
        id_card_front=data.id_card_front,
        id_card_back=data.id_card_back,
        license_photo=data.license_photo,
        specialties=data.specialties,
        introduction=data.introduction,
        experience_years=data.experience_years,
        status="pending"
    )
    db.add(verification)
    await db.commit()
    await db.refresh(verification)
    
    return {
        "message": "认证申请已提交，请等待审核",
        "verification_id": verification.id
    }


@router.get("/verification/status", summary="查询认证状态")
async def get_verification_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """查询当前用户的律师认证状态"""
    result = await db.execute(
        select(LawyerVerification)
        .where(LawyerVerification.user_id == current_user.id)
        .order_by(LawyerVerification.created_at.desc())
        .limit(1)
    )
    verification = result.scalar_one_or_none()
    
    if not verification:
        return {"status": "none", "message": "尚未申请认证"}
    
    return {
        "status": verification.status,
        "verification_id": verification.id,
        "created_at": verification.created_at,
        "reviewed_at": verification.reviewed_at,
        "reject_reason": verification.reject_reason if verification.status == "rejected" else None
    }


@router.get("/admin/verifications", summary="获取认证申请列表（管理员）")
async def get_verification_list(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(description="状态筛选: pending/approved/rejected")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """管理员获取律师认证申请列表"""
    _ = current_user
    query = select(LawyerVerification)
    
    if status_filter:
        query = query.where(LawyerVerification.status == status_filter)
    
    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total: int = int(total_result.scalar() or 0)
    
    # 分页
    query = query.order_by(LawyerVerification.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    verifications = result.scalars().all()
    
    items: list[dict[str, object]] = []
    for v in verifications:
        # 获取用户信息
        user_result = await db.execute(select(User).where(User.id == v.user_id))
        user = user_result.scalar_one_or_none()
        
        items.append({
            "id": v.id,
            "user_id": v.user_id,
            "username": user.username if user else None,
            "real_name": v.real_name,
            "id_card_no": v.id_card_no[:6] + "****" + v.id_card_no[-4:],  # 脱敏
            "license_no": v.license_no,
            "firm_name": v.firm_name,
            "specialties": v.specialties,
            "experience_years": v.experience_years,
            "status": v.status,
            "created_at": v.created_at,
            "reviewed_at": v.reviewed_at,
        })
    
    return {"items": items, "total": total}


@router.post("/admin/verifications/{verification_id}/review", summary="审核认证申请（管理员）")
async def review_verification(
    verification_id: int,
    data: VerificationReview,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """管理员审核律师认证申请"""
    result = await db.execute(
        select(LawyerVerification).where(LawyerVerification.id == verification_id)
    )
    verification = result.scalar_one_or_none()
    
    if not verification:
        raise HTTPException(status_code=404, detail="认证申请不存在")
    
    if verification.status != "pending":
        raise HTTPException(status_code=400, detail="该申请已被处理")
    
    from datetime import datetime as dt
    
    if data.approved:
        verification.status = "approved"
        verification.reviewed_by = current_user.id
        verification.reviewed_at = dt.now()

        user_result = await db.execute(select(User).where(User.id == verification.user_id))
        user = user_result.scalar_one_or_none()
        if user and str(getattr(user, "role", "")) not in {"admin", "super_admin"}:
            user.role = "lawyer"
            db.add(user)
        
        # 创建或更新律师档案
        existing_lawyer = await db.execute(
            select(Lawyer).where(Lawyer.user_id == verification.user_id)
        )
        lawyer = existing_lawyer.scalar_one_or_none()
        
        if lawyer:
            lawyer.name = verification.real_name
            lawyer.license_no = verification.license_no
            lawyer.specialties = verification.specialties
            lawyer.introduction = verification.introduction
            lawyer.experience_years = verification.experience_years
            lawyer.is_verified = True
        else:
            lawyer = Lawyer(
                user_id=verification.user_id,
                name=verification.real_name,
                license_no=verification.license_no,
                specialties=verification.specialties,
                introduction=verification.introduction,
                experience_years=verification.experience_years,
                is_verified=True,
                is_active=True
            )
            db.add(lawyer)
        
        await db.commit()
        return {"message": "认证通过", "lawyer_id": lawyer.id}
    else:
        verification.status = "rejected"
        verification.reject_reason = data.reject_reason
        verification.reviewed_by = current_user.id
        verification.reviewed_at = dt.now()
        await db.commit()
        return {"message": "认证已驳回"}
