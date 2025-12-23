"""法律咨询所API路由"""
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.lawfirm import LawyerVerification, Lawyer, LawFirm
from ..models.user import User
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
        lawyer_name=lawyer.name
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
    
    items: list[ConsultationResponse] = []
    for c in consultations:
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
            lawyer_name=c.lawyer.name if c.lawyer else None
        ))
    
    return ConsultationListResponse(items=items, total=total, page=page, page_size=page_size)


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
    total = total_result.scalar() or 0
    
    # 分页
    query = query.order_by(LawyerVerification.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    verifications = result.scalars().all()
    
    items = []
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
