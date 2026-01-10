"""用户API路由"""
from datetime import datetime, timezone
import secrets
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.user import User
from ..models.user_consent import ConsentDocType, UserConsent
from ..schemas.user import (
    UserCreate, UserLogin, UserUpdate, UserResponse,
    Token, LoginResponse, RegisterResponse, PasswordChange, MessageResponse,
    PasswordResetRequest, PasswordResetConfirm,
    PasswordResetDebugRequest, PasswordResetDebugResponse,
    EmailVerificationRequestResponse,
    SmsSendRequest,
    SmsVerifyRequest,
    SmsSendResponse,
)
from ..schemas.quota import UserQuotaDailyResponse
from ..services.user_service import user_service
from ..services.forum_service import forum_service
from ..services.email_service import email_service
from ..services.cache_service import cache_service
from ..utils.security import create_access_token, verify_password, hash_password
from ..utils.deps import get_current_user, require_admin, require_user_verified
from ..utils.rate_limiter import rate_limit, RateLimitConfig
from ..config import get_settings
from ..services.quota_service import quota_service

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["用户管理"])

_SMS_CODE_TTL_SECONDS = 300
_SMS_SEND_LOCK_SECONDS = 60


@router.post("/register", response_model=RegisterResponse, summary="用户注册")
async def register(
    request: Request,
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    用户注册接口
    
    - **username**: 用户名（3-50字符）
    - **email**: 邮箱
    - **password**: 密码（至少6位）
    - **nickname**: 昵称（可选）
    """
    try:
        if (not user_data.agree_terms) or (not user_data.agree_privacy) or (not user_data.agree_ai_disclaimer):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请阅读并同意用户协议、隐私政策及AI咨询免责声明",
            )

        if await user_service.is_username_taken(db, user_data.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已被使用"
            )
        
        if await user_service.is_email_taken(db, user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )
        
        user = await user_service.create(db, user_data)

        ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        consent_version = "v1"
        db.add_all(
            [
                UserConsent(
                    user_id=int(user.id),
                    doc_type=ConsentDocType.TERMS,
                    doc_version=consent_version,
                    ip=ip,
                    user_agent=user_agent,
                ),
                UserConsent(
                    user_id=int(user.id),
                    doc_type=ConsentDocType.PRIVACY,
                    doc_version=consent_version,
                    ip=ip,
                    user_agent=user_agent,
                ),
                UserConsent(
                    user_id=int(user.id),
                    doc_type=ConsentDocType.AI_DISCLAIMER,
                    doc_version=consent_version,
                    ip=ip,
                    user_agent=user_agent,
                ),
            ]
        )
        await db.commit()
        await db.refresh(user)

        msg = "注册成功"
        try:
            if not bool(getattr(user, "email_verified", False)):
                token = await email_service.generate_email_verification_token(int(user.id), str(user.email))
                base = settings.frontend_base_url.rstrip("/")
                verify_url = f"{base}/verify-email?token={token}"
                ok = await email_service.send_email_verification_email(str(user.email), verify_url)
                if ok:
                    msg = "注册成功，验证邮件已发送，请查收邮箱"
                else:
                    msg = "注册成功，但验证邮件发送失败，请稍后在个人中心重发"
        except Exception:
            logger.exception("register: failed to send verification email")
            msg = "注册成功，但验证邮件发送失败，请稍后在个人中心重发"

        return RegisterResponse(user=UserResponse.model_validate(user), message=msg)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("注册错误")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败"
        )


@router.post("/login", response_model=LoginResponse, summary="用户登录")
async def login(login_data: UserLogin, db: Annotated[AsyncSession, Depends(get_db)]):
    """
    用户登录接口
    
    - **username**: 用户名或邮箱
    - **password**: 密码
    """
    user = await user_service.authenticate(db, login_data.username, login_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用"
        )
    
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return LoginResponse(
        user=UserResponse.model_validate(user),
        token=Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60
        ),
        message="登录成功"
    )


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    """获取当前登录用户的信息"""
    return UserResponse.model_validate(current_user)


@router.get("/me/quotas", response_model=UserQuotaDailyResponse, summary="获取当前用户配额")
async def get_my_quotas(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    data = await quota_service.get_today_quota(db, current_user)
    return UserQuotaDailyResponse.model_validate(data)


@router.put("/me", response_model=UserResponse, summary="更新当前用户信息")
async def update_me(
    user_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    更新当前用户信息
    
    - **nickname**: 昵称
    - **avatar**: 头像URL
    - **phone**: 手机号
    """
    payload = user_data.model_dump(exclude_unset=True)
    if "phone" in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号请通过短信验证码完成绑定",
        )
    updated_user = await user_service.update(db, current_user, user_data)
    return UserResponse.model_validate(updated_user)


@router.get("/{user_id}", response_model=UserResponse, summary="获取用户信息")
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    """根据ID获取用户公开信息"""
    user = await user_service.get_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return UserResponse.model_validate(user)


@router.put("/me/password", response_model=MessageResponse, summary="修改密码")
async def change_password(
    password_data: PasswordChange,
    current_user: Annotated[User, Depends(require_user_verified)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    修改当前用户密码
    
    - **old_password**: 当前密码
    - **new_password**: 新密码（至少6位）
    """
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码错误"
        )
    
    if password_data.old_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与当前密码相同"
        )
    
    current_user.hashed_password = hash_password(password_data.new_password)
    db.add(current_user)
    await db.commit()
    
    return MessageResponse(message="密码修改成功", success=True)


@router.get("/me/stats", summary="获取用户统计数据")
async def get_user_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取当前用户的统计数据（帖子数、收藏数、评论数）"""
    stats = await forum_service.get_user_stats(db, current_user.id)
    return stats


@router.post(
    "/email-verification/request",
    response_model=EmailVerificationRequestResponse,
    summary="请求邮箱验证邮件",
)
@rate_limit(*RateLimitConfig.AUTH_PASSWORD_RESET, by_ip=True)
async def request_email_verification(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
):
    _ = request
    if bool(getattr(current_user, "email_verified", False)):
        return EmailVerificationRequestResponse(message="邮箱已验证", success=True)

    token = await email_service.generate_email_verification_token(int(current_user.id), str(current_user.email))
    base = settings.frontend_base_url.rstrip("/")
    verify_url = f"{base}/verify-email?token={token}"

    ok = await email_service.send_email_verification_email(str(current_user.email), verify_url)

    if not ok:
        if bool(settings.debug):
            return EmailVerificationRequestResponse(
                message="邮件服务未配置，已返回验证链接（开发环境）",
                success=True,
                token=token,
                verify_url=verify_url,
            )
        raise HTTPException(status_code=500, detail="验证邮件发送失败")

    if bool(settings.debug):
        return EmailVerificationRequestResponse(
            message="验证邮件已发送",
            success=True,
            token=token,
            verify_url=verify_url,
        )
    return EmailVerificationRequestResponse(message="验证邮件已发送", success=True)


@router.get(
    "/email-verification/verify",
    response_model=MessageResponse,
    summary="邮箱验证（通过token）",
)
@rate_limit(*RateLimitConfig.AUTH_PASSWORD_RESET, by_ip=True)
async def verify_email(
    token: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = request
    token_data = await email_service.verify_email_verification_token(token)
    if not token_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效或已过期的验证令牌")

    user = await user_service.get_by_id(db, int(token_data["user_id"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if str(user.email) != str(token_data["email"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱不匹配")

    if not bool(getattr(user, "email_verified", False)):
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)
        db.add(user)
        await db.commit()

    await email_service.invalidate_email_verification_token(token)
    return MessageResponse(message="邮箱验证成功", success=True)


@router.post("/sms/send", response_model=SmsSendResponse, summary="发送短信验证码")
@rate_limit(*RateLimitConfig.AUTH_PASSWORD_RESET, by_ip=True)
async def send_sms_code(
    data: SmsSendRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
):
    _ = request
    _ = current_user

    phone = str(data.phone).strip()
    scene = str(data.scene or "bind_phone").strip() or "bind_phone"

    lock_key = f"sms_send_lock:{scene}:{phone}"
    lock_value = f"{int(getattr(current_user, 'id', 0) or 0)}"
    acquired = await cache_service.acquire_lock(lock_key, lock_value, expire=_SMS_SEND_LOCK_SECONDS)
    if not acquired:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="发送过于频繁，请稍后再试")

    code = f"{secrets.randbelow(1000000):06d}"
    cache_key = f"sms_code:{scene}:{phone}"
    _ = await cache_service.set_json(
        cache_key,
        {
            "code": code,
            "phone": phone,
            "scene": scene,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        expire=_SMS_CODE_TTL_SECONDS,
    )

    logger.info("[DEV] sms code for %s(%s): %s", phone, scene, code)

    if bool(settings.debug):
        return SmsSendResponse(message="验证码已发送", success=True, code=code)
    return SmsSendResponse(message="验证码已发送", success=True)


@router.post("/sms/verify", response_model=MessageResponse, summary="校验短信验证码并绑定手机号")
@rate_limit(*RateLimitConfig.AUTH_PASSWORD_RESET, by_ip=True)
async def verify_sms_code(
    data: SmsVerifyRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = request

    phone = str(data.phone).strip()
    scene = str(data.scene or "bind_phone").strip() or "bind_phone"
    code = str(data.code).strip()

    cache_key = f"sms_code:{scene}:{phone}"
    raw = await cache_service.get_json(cache_key)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码无效或已过期")

    expected = str(raw.get("code") or "").strip()
    if not expected or expected != code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误")

    current_user.phone = phone
    current_user.phone_verified = True
    current_user.phone_verified_at = datetime.now(timezone.utc)
    db.add(current_user)
    await db.commit()

    _ = await cache_service.delete(cache_key)
    return MessageResponse(message="手机验证成功", success=True)


@router.get("/{user_id}/stats", summary="获取用户统计数据（管理员）")
async def admin_get_user_stats(
    user_id: int,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """管理员获取指定用户统计数据"""
    _ = current_user
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    stats = await forum_service.get_user_stats(db, user_id)
    return stats


# ============ 管理员接口 ============

@router.get("/admin/list", response_model=dict, summary="获取用户列表（管理员）")
async def admin_list_users(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    keyword: Annotated[str | None, Query()] = None,
):
    """获取所有用户列表（需要管理员权限）"""
    _ = current_user
    users, total = await user_service.get_list(db, page, page_size, keyword)
    return {
        "items": [UserResponse.model_validate(u) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.put("/admin/{user_id}/toggle-active", response_model=UserResponse, summary="切换用户状态（管理员）")
async def admin_toggle_user_active(
    user_id: int,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """切换用户激活状态（需要管理员权限）"""
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能修改自己的状态")
    
    user.is_active = not user.is_active
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.put("/admin/{user_id}/role", response_model=UserResponse, summary="修改用户角色（管理员）")
async def admin_update_user_role(
    user_id: int,
    role: str,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """修改用户角色（需要管理员权限）"""
    if role not in ["user", "lawyer", "admin"]:
        raise HTTPException(status_code=400, detail="无效的角色")
    
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能修改自己的角色")
    
    user.role = role
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


# ============ 密码重置 ============


@router.post(
    "/admin/debug/password-reset-token",
    response_model=PasswordResetDebugResponse,
    summary="生成密码重置 token（仅调试/E2E）",
)
async def admin_debug_password_reset_token(
    data: PasswordResetDebugRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = current_user

    if not bool(settings.debug):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    user = await user_service.get_by_email(db, str(data.email))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    reset_token = await email_service.generate_reset_token(int(user.id), str(data.email))
    base = settings.frontend_base_url.rstrip("/")
    reset_url = f"{base}/reset-password?token={reset_token}"

    return PasswordResetDebugResponse(
        message="OK",
        success=True,
        token=reset_token,
        reset_url=reset_url,
    )

@router.post("/password-reset/request", response_model=MessageResponse, summary="请求密码重置")
@rate_limit(*RateLimitConfig.AUTH_PASSWORD_RESET, by_ip=True)
async def request_password_reset(
    data: PasswordResetRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    请求密码重置
    
    发送重置邮件到用户邮箱
    """
    user = await user_service.get_by_email(db, data.email)
    
    if not user:
        # 出于安全考虑，不透露邮箱是否存在
        return MessageResponse(message="如果邮箱存在，我们将发送重置链接")
    
    # 生成重置令牌
    _ = request
    reset_token = await email_service.generate_reset_token(user.id, data.email)
    
    # 构建重置链接
    base = settings.frontend_base_url.rstrip("/")
    reset_url = f"{base}/reset-password?token={reset_token}"
    
    # 发送重置邮件
    _ = await email_service.send_password_reset_email(data.email, reset_token, reset_url)
    
    logger.info("Password reset requested for: %s", data.email)
    return MessageResponse(message="如果邮箱存在，我们将发送重置链接")


@router.post("/password-reset/confirm", response_model=MessageResponse, summary="确认密码重置")
@rate_limit(*RateLimitConfig.AUTH_PASSWORD_RESET, by_ip=True)
async def confirm_password_reset(
    data: PasswordResetConfirm,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    确认密码重置
    
    使用令牌和新密码完成重置
    """
    # 验证令牌
    _ = request
    token_data = await email_service.verify_reset_token(data.token)
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效或已过期的重置令牌"
        )
    
    # 获取用户
    user = await user_service.get_by_id(db, token_data["user_id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 更新密码
    user.hashed_password = hash_password(data.new_password)
    db.add(user)
    await db.commit()
    
    # 使令牌失效
    await email_service.invalidate_token(data.token)
    
    logger.info("Password reset completed for user: %s", user.id)
    return MessageResponse(message="密码重置成功")
