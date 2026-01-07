"""依赖注入"""
import logging
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..models.user import User
from .security import decode_token
from .permissions import Role, has_role, has_any_role

security = HTTPBearer(auto_error=False)

logger = logging.getLogger(__name__)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
) -> User:
    """获取当前登录用户"""
    if not credentials:
        logger.info("auth: missing credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        logger.info("auth: token decode failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    sub = payload.get("sub")
    if sub is None:
        logger.info("auth: token missing sub")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
        )

    try:
        user_id = int(str(sub))
    except (TypeError, ValueError):
        logger.info("auth: token sub not int")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        logger.info("auth: user not found (id=%s)", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    
    return user


async def get_current_user_optional(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
) -> User | None:
    """获取当前用户（可选，未登录返回None）"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(db=db, credentials=credentials)
    except HTTPException:
        return None


async def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """要求管理员权限"""
    if not has_any_role(current_user, [Role.ADMIN, Role.SUPER_ADMIN]):
        logger.warning(
            f"权限检查失败: 用户 {current_user.username} (role={current_user.role}) "
            f"尝试访问管理员资源"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


async def require_moderator(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """要求版主或管理员权限"""
    if not has_any_role(current_user, [Role.MODERATOR, Role.ADMIN, Role.SUPER_ADMIN]):
        logger.warning(
            f"权限检查失败: 用户 {current_user.username} (role={current_user.role}) "
            f"尝试访问版主资源"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要版主或管理员权限"
        )
    return current_user


async def require_lawyer(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """要求律师权限"""
    if not has_role(current_user, Role.LAWYER):
        logger.warning(
            f"权限检查失败: 用户 {current_user.username} (role={current_user.role}) "
            f"尝试访问律师资源"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要律师权限"
        )
    return current_user


async def require_phone_verified(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """要求手机号已验证（敏感操作兜底）"""
    if not bool(getattr(current_user, "phone_verified", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先完成手机号验证",
        )
    return current_user


async def require_email_verified(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """要求邮箱已验证（敏感操作兜底）"""
    if not bool(getattr(current_user, "email_verified", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先完成邮箱验证",
        )
    return current_user


async def require_lawyer_phone_verified(current_user: Annotated[User, Depends(require_lawyer)]) -> User:
    """要求律师权限且手机号已验证（敏感操作兜底）"""
    if not bool(getattr(current_user, "phone_verified", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先完成手机号验证",
        )
    return current_user


async def require_lawyer_verified(current_user: Annotated[User, Depends(require_lawyer)]) -> User:
    """要求律师权限且手机号/邮箱均已验证（敏感操作兜底）"""
    if not bool(getattr(current_user, "phone_verified", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先完成手机号验证",
        )
    if not bool(getattr(current_user, "email_verified", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先完成邮箱验证",
        )
    return current_user
