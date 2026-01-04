"""法律咨询所相关的Pydantic模式"""
from typing import ClassVar
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


# ============ 律所相关 ============

class LawFirmCreate(BaseModel):
    """创建律所"""
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    address: str | None = None
    city: str | None = None
    province: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    logo: str | None = None
    license_no: str | None = None
    specialties: str | None = None


class LawFirmUpdate(BaseModel):
    """更新律所"""
    name: str | None = Field(None, max_length=200)
    description: str | None = None
    address: str | None = None
    city: str | None = None
    province: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    logo: str | None = None
    license_no: str | None = None
    specialties: str | None = None
    is_verified: bool | None = None
    is_active: bool | None = None


class LawFirmResponse(BaseModel):
    """律所响应"""
    id: int
    name: str
    description: str | None = None
    address: str | None = None
    city: str | None = None
    province: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    logo: str | None = None
    license_no: str | None = None
    specialties: list[str] = []
    rating: float
    review_count: int
    is_verified: bool
    is_active: bool
    created_at: datetime
    lawyer_count: int = 0
    
    model_config: ClassVar[ConfigDict] = {"from_attributes": True}


class LawFirmListResponse(BaseModel):
    """律所列表响应"""
    items: list[LawFirmResponse]
    total: int
    page: int
    page_size: int


# ============ 律师相关 ============

class LawyerCreate(BaseModel):
    """创建律师"""
    firm_id: int | None = None
    name: str = Field(..., min_length=1, max_length=50)
    avatar: str | None = None
    title: str | None = None
    license_no: str | None = None
    phone: str | None = None
    email: str | None = None
    introduction: str | None = None
    specialties: str | None = None
    experience_years: int = 0
    consultation_fee: float = 0.0


class LawyerUpdate(BaseModel):
    """更新律师"""
    firm_id: int | None = None
    name: str | None = Field(None, max_length=50)
    avatar: str | None = None
    title: str | None = None
    license_no: str | None = None
    phone: str | None = None
    email: str | None = None
    introduction: str | None = None
    specialties: str | None = None
    experience_years: int | None = None
    consultation_fee: float | None = None
    is_verified: bool | None = None
    is_active: bool | None = None


class LawyerResponse(BaseModel):
    """律师响应"""
    id: int
    user_id: int | None = None
    firm_id: int | None = None
    name: str
    avatar: str | None = None
    title: str | None = None
    license_no: str | None = None
    phone: str | None = None
    email: str | None = None
    introduction: str | None = None
    specialties: str | None = None
    experience_years: int
    case_count: int
    rating: float
    review_count: int
    consultation_fee: float
    is_verified: bool
    is_active: bool
    created_at: datetime
    firm_name: str | None = None
    
    model_config: ClassVar[ConfigDict] = {"from_attributes": True}


class LawyerListResponse(BaseModel):
    """律师列表响应"""
    items: list[LawyerResponse]
    total: int
    page: int
    page_size: int


# ============ 咨询预约相关 ============

class ConsultationCreate(BaseModel):
    """创建咨询预约"""
    lawyer_id: int
    subject: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    category: str | None = None
    contact_phone: str | None = None
    preferred_time: datetime | None = None


class ConsultationUpdate(BaseModel):
    """更新咨询状态"""
    status: str | None = None
    admin_note: str | None = None


class ConsultationResponse(BaseModel):
    """咨询预约响应"""
    id: int
    user_id: int
    lawyer_id: int
    subject: str
    description: str | None = None
    category: str | None = None
    contact_phone: str | None = None
    preferred_time: datetime | None = None
    status: str
    admin_note: str | None = None
    created_at: datetime
    updated_at: datetime
    lawyer_name: str | None = None
    payment_order_no: str | None = None
    payment_status: str | None = None
    payment_amount: float | None = None
    review_id: int | None = None
    can_review: bool = False
    
    model_config: ClassVar[ConfigDict] = {"from_attributes": True}


class ConsultationListResponse(BaseModel):
    """咨询列表响应"""
    items: list[ConsultationResponse]
    total: int
    page: int
    page_size: int


# ============ 评价相关 ============

class ReviewCreate(BaseModel):
    """创建评价"""
    lawyer_id: int
    consultation_id: int | None = None
    rating: int = Field(..., ge=1, le=5)
    content: str | None = None
    is_anonymous: bool = False


class ReviewResponse(BaseModel):
    """评价响应"""
    id: int
    lawyer_id: int
    user_id: int
    consultation_id: int | None = None
    rating: int
    content: str | None = None
    is_anonymous: bool
    created_at: datetime
    username: str | None = None
    
    model_config: ClassVar[ConfigDict] = {"from_attributes": True}


class ReviewListResponse(BaseModel):
    """评价列表响应"""
    items: list[ReviewResponse]
    total: int
    average_rating: float
