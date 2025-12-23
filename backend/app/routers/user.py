"""用户API路由"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.user import User
from ..schemas.user import (
    UserCreate, UserLogin, UserUpdate, UserResponse,
    Token, LoginResponse, RegisterResponse, PasswordChange, MessageResponse,
    PasswordResetRequest, PasswordResetConfirm
)
from ..services.user_service import user_service
from ..services.forum_service import forum_service
from ..services.email_service import email_service
from ..utils.security import create_access_token, verify_password, hash_password
from ..utils.deps import get_current_user, require_admin
from ..utils.rate_limiter import rate_limit, RateLimitConfig
from ..config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["用户管理"])


@router.post("/register", response_model=RegisterResponse, summary="用户注册")
async def register(user_data: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    """
    用户注册接口
    
    - **username**: 用户名（3-50字符）
    - **email**: 邮箱
    - **password**: 密码（至少6位）
    - **nickname**: 昵称（可选）
    """
    try:
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
        
        return RegisterResponse(
            user=UserResponse.model_validate(user),
            message="注册成功"
        )
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
    current_user: Annotated[User, Depends(get_current_user)],
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
