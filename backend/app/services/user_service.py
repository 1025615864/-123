"""用户服务层"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from sqlalchemy.exc import IntegrityError

from ..models.user import User
from ..schemas.user import UserCreate, UserUpdate
from ..utils.security import hash_password, verify_password


class UserService:
    """用户服务"""
    
    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
        """根据ID获取用户"""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> User | None:
        """根据用户名获取用户"""
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> User | None:
        """根据邮箱获取用户"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_username_or_email(db: AsyncSession, identifier: str) -> User | None:
        """根据用户名或邮箱获取用户"""
        result = await db.execute(
            select(User).where(
                or_(User.username == identifier, User.email == identifier)
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create(db: AsyncSession, user_data: UserCreate) -> User:
        """创建用户"""
        hashed_password = hash_password(user_data.password)
        
        user = User(
            username=user_data.username,
            email=user_data.email,
            nickname=user_data.nickname or user_data.username,
            hashed_password=hashed_password
        )
        
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
            return user
        except IntegrityError:
            await db.rollback()
            raise ValueError("用户名或邮箱已被使用")
        except Exception:
            await db.rollback()
            raise
    
    @staticmethod
    async def update(db: AsyncSession, user: User, user_data: UserUpdate) -> User:
        """更新用户信息"""
        update_data: dict[str, object] = user_data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        await db.commit()
        await db.refresh(user)
        return user
    
    @staticmethod
    async def authenticate(db: AsyncSession, username: str, password: str) -> User | None:
        """验证用户登录"""
        user = await UserService.get_by_username_or_email(db, username)
        
        if not user:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        return user
    
    @staticmethod
    async def is_username_taken(db: AsyncSession, username: str) -> bool:
        """检查用户名是否已被使用"""
        user = await UserService.get_by_username(db, username)
        return user is not None
    
    @staticmethod
    async def is_email_taken(db: AsyncSession, email: str) -> bool:
        """检查邮箱是否已被使用"""
        user = await UserService.get_by_email(db, email)
        return user is not None
    
    @staticmethod
    async def get_list(
        db: AsyncSession, 
        page: int = 1, 
        page_size: int = 20, 
        keyword: str | None = None
    ) -> tuple[list[User], int]:
        """获取用户列表"""
        query = select(User)
        
        if keyword:
            query = query.where(
                or_(
                    User.username.contains(keyword),
                    User.email.contains(keyword),
                    User.nickname.contains(keyword)
                )
            )
        
        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(User.id.desc())
        
        result = await db.execute(query)
        users = list(result.scalars().all())
        
        return users, int(total)


user_service = UserService()
