"""用户相关的Pydantic模式"""
from datetime import datetime
from typing import ClassVar
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """用户基础模式"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    nickname: str | None = Field(None, max_length=50, description="昵称")


class UserCreate(UserBase):
    """用户注册模式"""
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    agree_terms: bool = Field(..., description="同意用户协议")
    agree_privacy: bool = Field(..., description="同意隐私政策")
    agree_ai_disclaimer: bool = Field(..., description="同意AI咨询免责声明")


class UserLogin(BaseModel):
    """用户登录模式"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class UserUpdate(BaseModel):
    """用户更新模式"""
    nickname: str | None = Field(None, max_length=50)
    avatar: str | None = None
    phone: str | None = Field(None, max_length=20)


class UserResponse(UserBase):
    """用户响应模式"""
    id: int
    avatar: str | None = None
    phone: str | None = None
    email_verified: bool = False
    email_verified_at: datetime | None = None
    phone_verified: bool = False
    phone_verified_at: datetime | None = None
    role: str = "user"
    is_active: bool = True
    vip_expires_at: datetime | None = None
    created_at: datetime
    
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """Token响应模式"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Token数据模式"""
    user_id: int | None = None
    username: str | None = None


class LoginResponse(BaseModel):
    """登录响应模式"""
    user: UserResponse
    token: Token
    message: str = "登录成功"


class RegisterResponse(BaseModel):
    """注册响应模式"""
    user: UserResponse
    message: str = "注册成功"


class PasswordChange(BaseModel):
    """密码修改模式"""
    old_password: str = Field(..., min_length=1, description="当前密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str
    success: bool = True


class EmailVerificationRequestResponse(MessageResponse):
    token: str | None = None
    verify_url: str | None = None


class SmsSendRequest(BaseModel):
    phone: str = Field(..., min_length=5, max_length=20, description="手机号")
    scene: str = Field("bind_phone", description="验证码使用场景")


class SmsVerifyRequest(BaseModel):
    phone: str = Field(..., min_length=5, max_length=20, description="手机号")
    scene: str = Field("bind_phone", description="验证码使用场景")
    code: str = Field(..., min_length=4, max_length=10, description="验证码")


class SmsSendResponse(MessageResponse):
    code: str | None = None


class PasswordResetRequest(BaseModel):
    """密码重置请求"""
    email: EmailStr = Field(..., description="注册邮箱")


class PasswordResetConfirm(BaseModel):
    """密码重置确认"""
    token: str = Field(..., description="重置令牌")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


class PasswordResetDebugRequest(BaseModel):
    email: EmailStr = Field(..., description="注册邮箱")


class PasswordResetDebugResponse(MessageResponse):
    token: str
    reset_url: str
