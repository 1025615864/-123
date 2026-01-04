"""法律咨询所服务层"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import selectinload

from ..models.lawfirm import LawFirm, Lawyer, LawyerConsultation, LawyerReview
from ..schemas.lawfirm import (
    LawFirmCreate, LawFirmUpdate, LawyerCreate, LawyerUpdate,
    ConsultationCreate, ConsultationUpdate, ReviewCreate
)


class LawFirmService:
    """律所服务"""
    
    @staticmethod
    async def create(db: AsyncSession, data: LawFirmCreate) -> LawFirm:
        """创建律所"""
        firm = LawFirm(**data.model_dump())
        db.add(firm)
        await db.commit()
        await db.refresh(firm)
        return firm
    
    @staticmethod
    async def get_by_id(db: AsyncSession, firm_id: int) -> LawFirm | None:
        """获取律所"""
        result = await db.execute(
            select(LawFirm).where(LawFirm.id == firm_id, LawFirm.is_active == True)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_list(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        city: str | None = None,
        keyword: str | None = None
    ) -> tuple[list[LawFirm], int]:
        """获取律所列表"""
        query = select(LawFirm).where(LawFirm.is_active == True)
        count_query = select(func.count(LawFirm.id)).where(LawFirm.is_active == True)
        
        if city:
            query = query.where(LawFirm.city == city)
            count_query = count_query.where(LawFirm.city == city)
        
        if keyword:
            search_filter = or_(
                LawFirm.name.contains(keyword),
                LawFirm.specialties.contains(keyword)
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        query = query.order_by(desc(LawFirm.is_verified), desc(LawFirm.rating))
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        firms = result.scalars().all()
        
        count_result = await db.execute(count_query)
        total = int(count_result.scalar() or 0)
        
        return list(firms), total
    
    @staticmethod
    async def update(db: AsyncSession, firm: LawFirm, data: LawFirmUpdate) -> LawFirm:
        """更新律所"""
        update_data: dict[str, object] = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(firm, field, value)
        await db.commit()
        await db.refresh(firm)
        return firm
    
    @staticmethod
    async def get_lawyer_count(db: AsyncSession, firm_id: int) -> int:
        """获取律所律师数量"""
        result = await db.execute(
            select(func.count(Lawyer.id)).where(
                Lawyer.firm_id == firm_id, Lawyer.is_active == True
            )
        )
        return result.scalar() or 0


class LawyerService:
    """律师服务"""
    
    @staticmethod
    async def create(db: AsyncSession, data: LawyerCreate, user_id: int | None = None) -> Lawyer:
        """创建律师"""
        lawyer = Lawyer(**data.model_dump(), user_id=user_id)
        db.add(lawyer)
        await db.commit()
        await db.refresh(lawyer)
        return lawyer
    
    @staticmethod
    async def get_by_id(db: AsyncSession, lawyer_id: int) -> Lawyer | None:
        """获取律师"""
        result = await db.execute(
            select(Lawyer)
            .options(selectinload(Lawyer.firm))
            .where(Lawyer.id == lawyer_id, Lawyer.is_active == True)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_list(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        firm_id: int | None = None,
        specialty: str | None = None,
        keyword: str | None = None
    ) -> tuple[list[Lawyer], int]:
        """获取律师列表"""
        query = select(Lawyer).options(selectinload(Lawyer.firm)).where(Lawyer.is_active == True)
        count_query = select(func.count(Lawyer.id)).where(Lawyer.is_active == True)
        
        if firm_id:
            query = query.where(Lawyer.firm_id == firm_id)
            count_query = count_query.where(Lawyer.firm_id == firm_id)
        
        if specialty:
            query = query.where(Lawyer.specialties.contains(specialty))
            count_query = count_query.where(Lawyer.specialties.contains(specialty))
        
        if keyword:
            search_filter = or_(
                Lawyer.name.contains(keyword),
                Lawyer.introduction.contains(keyword)
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        query = query.order_by(desc(Lawyer.is_verified), desc(Lawyer.rating))
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        lawyers = result.scalars().all()
        
        count_result = await db.execute(count_query)
        total = int(count_result.scalar() or 0)
        
        return list(lawyers), total
    
    @staticmethod
    async def update(db: AsyncSession, lawyer: Lawyer, data: LawyerUpdate) -> Lawyer:
        """更新律师"""
        update_data: dict[str, object] = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(lawyer, field, value)
        await db.commit()
        await db.refresh(lawyer)
        return lawyer
    
    @staticmethod
    async def update_rating(db: AsyncSession, lawyer_id: int) -> None:
        """更新律师评分"""
        result = await db.execute(
            select(
                func.avg(LawyerReview.rating),
                func.count(LawyerReview.id)
            ).where(LawyerReview.lawyer_id == lawyer_id)
        )
        row = result.one()
        avg_rating = row[0] or 0.0
        review_count = row[1] or 0
        
        lawyer_result = await db.execute(select(Lawyer).where(Lawyer.id == lawyer_id))
        lawyer = lawyer_result.scalar_one_or_none()
        if lawyer:
            lawyer.rating = round(float(avg_rating), 1)
            lawyer.review_count = review_count
            await db.commit()


class LawyerConsultationService:
    """咨询预约服务"""
    
    @staticmethod
    async def create(db: AsyncSession, user_id: int, data: ConsultationCreate) -> LawyerConsultation:
        """创建咨询预约"""
        consultation = LawyerConsultation(
            user_id=user_id,
            **data.model_dump()
        )
        db.add(consultation)
        await db.commit()
        await db.refresh(consultation)
        return consultation
    
    @staticmethod
    async def get_by_id(db: AsyncSession, consultation_id: int) -> LawyerConsultation | None:
        """获取咨询"""
        result = await db.execute(
            select(LawyerConsultation)
            .options(selectinload(LawyerConsultation.lawyer))
            .where(LawyerConsultation.id == consultation_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_consultations(
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[LawyerConsultation], int]:
        """获取用户的咨询列表"""
        query = (
            select(LawyerConsultation)
            .options(selectinload(LawyerConsultation.lawyer))
            .where(LawyerConsultation.user_id == user_id)
            .order_by(desc(LawyerConsultation.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        
        result = await db.execute(query)
        consultations = result.scalars().all()
        
        count_result = await db.execute(
            select(func.count(LawyerConsultation.id)).where(LawyerConsultation.user_id == user_id)
        )
        total = int(count_result.scalar() or 0)
        
        return list(consultations), total
    
    @staticmethod
    async def update_status(
        db: AsyncSession,
        consultation: LawyerConsultation,
        data: ConsultationUpdate
    ) -> LawyerConsultation:
        """更新咨询状态"""
        update_data: dict[str, object] = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(consultation, field, value)
        await db.commit()
        await db.refresh(consultation)
        return consultation


class ReviewService:
    """评价服务"""
    
    @staticmethod
    async def create(db: AsyncSession, user_id: int, data: ReviewCreate) -> LawyerReview:
        """创建评价"""
        review = LawyerReview(user_id=user_id, **data.model_dump())
        db.add(review)
        await db.commit()
        await db.refresh(review)
        
        # 更新律师评分
        await LawyerService.update_rating(db, data.lawyer_id)
        
        return review
    
    @staticmethod
    async def get_lawyer_reviews(
        db: AsyncSession,
        lawyer_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[LawyerReview], int, float]:
        """获取律师评价"""
        query = (
            select(LawyerReview)
            .options(selectinload(LawyerReview.user))
            .where(LawyerReview.lawyer_id == lawyer_id)
            .order_by(desc(LawyerReview.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        
        result = await db.execute(query)
        reviews = result.scalars().all()
        
        count_result = await db.execute(
            select(func.count(LawyerReview.id)).where(LawyerReview.lawyer_id == lawyer_id)
        )
        total = int(count_result.scalar() or 0)
        
        avg_result = await db.execute(
            select(func.avg(LawyerReview.rating)).where(LawyerReview.lawyer_id == lawyer_id)
        )
        avg_rating = avg_result.scalar() or 0.0
        
        return list(reviews), total, float(avg_rating)


lawfirm_service = LawFirmService()
lawyer_service = LawyerService()
consultation_service = LawyerConsultationService()
review_service = ReviewService()
