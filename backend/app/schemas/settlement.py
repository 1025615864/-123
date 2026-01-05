from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LawyerWalletResponse(BaseModel):
    lawyer_id: int
    total_income: float
    withdrawn_amount: float
    pending_amount: float
    frozen_amount: float
    available_amount: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SettlementStatsWalletSummary(BaseModel):
    total_income: float
    withdrawn_amount: float
    pending_amount: float
    frozen_amount: float
    available_amount: float


class SettlementStatsWithdrawalSummary(BaseModel):
    pending_count: int
    pending_amount: float
    approved_count: int
    approved_amount: float
    completed_month_count: int
    completed_month_amount: float


class SettlementStatsTopLawyerItem(BaseModel):
    lawyer_id: int
    lawyer_name: str | None = None
    income_records: int
    lawyer_income: float
    platform_fee: float


class AdminSettlementStatsResponse(BaseModel):
    month_start: datetime
    month_end: datetime

    wallet_summary: SettlementStatsWalletSummary
    withdrawal_summary: SettlementStatsWithdrawalSummary

    platform_fee_month_total: float
    lawyer_income_month_total: float
    top_lawyers: list[SettlementStatsTopLawyerItem]


class LawyerIncomeRecordItem(BaseModel):
    id: int
    lawyer_id: int
    consultation_id: int | None
    consultation_subject: str | None = None
    order_no: str | None

    user_paid_amount: float
    platform_fee: float
    lawyer_income: float

    withdrawn_amount: float

    status: str
    settle_time: datetime | None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LawyerIncomeRecordListResponse(BaseModel):
    items: list[LawyerIncomeRecordItem]
    total: int
    page: int
    page_size: int


class LawyerBankAccountCreate(BaseModel):
    account_type: str = Field("bank_card", description="bank_card/alipay")
    bank_name: str | None = Field(default=None, max_length=100)
    account_no: str = Field(..., min_length=4, max_length=100)
    account_holder: str = Field(..., min_length=1, max_length=50)
    is_default: bool = False


class LawyerBankAccountUpdate(BaseModel):
    bank_name: str | None = Field(default=None, max_length=100)
    account_no: str | None = Field(default=None, min_length=4, max_length=100)
    account_holder: str | None = Field(default=None, min_length=1, max_length=50)
    is_default: bool | None = None
    is_active: bool | None = None


class LawyerBankAccountItem(BaseModel):
    id: int
    lawyer_id: int
    account_type: str
    bank_name: str | None
    account_no_masked: str
    account_holder: str
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LawyerBankAccountListResponse(BaseModel):
    items: list[LawyerBankAccountItem]
    total: int


class WithdrawalCreateRequest(BaseModel):
    amount: float = Field(..., gt=0)
    withdraw_method: str = Field("bank_card", description="bank_card/alipay")
    bank_account_id: int = Field(..., ge=1)


class WithdrawalItem(BaseModel):
    id: int
    request_no: str
    lawyer_id: int

    lawyer_name: str | None = None
    lawyer_rating: float | None = None
    lawyer_completed_count: int | None = None
    platform_fee_rate: float | None = None

    amount: float
    fee: float
    actual_amount: float

    withdraw_method: str
    account_info_masked: str

    status: str
    reject_reason: str | None

    admin_id: int | None
    reviewed_at: datetime | None
    completed_at: datetime | None

    remark: str | None

    created_at: datetime
    updated_at: datetime


class WithdrawalListResponse(BaseModel):
    items: list[WithdrawalItem]
    total: int
    page: int
    page_size: int


class WithdrawalAdminActionRequest(BaseModel):
    remark: str | None = Field(default=None, max_length=2000)


class WithdrawalRejectRequest(BaseModel):
    reject_reason: str = Field(..., min_length=1, max_length=2000)
    remark: str | None = Field(default=None, max_length=2000)


class AdminWithdrawalDetailResponse(BaseModel):
    id: int
    request_no: str
    lawyer_id: int

    lawyer_name: str | None = None
    lawyer_rating: float | None = None
    lawyer_completed_count: int | None = None
    platform_fee_rate: float | None = None

    amount: float
    fee: float
    actual_amount: float

    withdraw_method: str
    account_info: str

    status: str
    reject_reason: str | None

    admin_id: int | None
    reviewed_at: datetime | None
    completed_at: datetime | None

    remark: str | None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
