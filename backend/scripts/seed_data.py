"""数据库种子数据脚本"""
import asyncio
import sys
sys.path.insert(0, '..')

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import AsyncSessionLocal, init_db
from app.models.user import User
from app.models.forum import Post
from app.models.news import News
from app.models.lawfirm import LawFirm
from app.utils.security import hash_password


async def create_users(db: AsyncSession):
    """创建测试用户"""
    users = [
        User(
            username="admin",
            email="admin@example.com",
            nickname="管理员",
            hashed_password=hash_password("admin123"),
            role="admin",
            is_active=True
        ),
        User(
            username="lawyer1",
            email="lawyer1@example.com",
            nickname="李律师",
            hashed_password=hash_password("lawyer123"),
            role="lawyer",
            is_active=True
        ),
        User(
            username="user1",
            email="user1@example.com",
            nickname="张三",
            hashed_password=hash_password("user123"),
            role="user",
            is_active=True
        ),
    ]

    created = 0
    result_users: list[User] = []
    for user in users:
        existing = (
            await db.execute(select(User).where(User.username == user.username))
        ).scalar_one_or_none()
        if existing is None:
            db.add(user)
            result_users.append(user)
            created += 1
        else:
            existing.email = user.email
            existing.nickname = user.nickname
            existing.hashed_password = user.hashed_password
            existing.role = user.role
            existing.is_active = user.is_active
            result_users.append(existing)

    await db.commit()
    for u in result_users:
        await db.refresh(u)

    print(f"✓ 创建/更新了 {len(result_users)} 个用户（新增 {created}）")
    return result_users


async def create_news(db: AsyncSession):
    """创建测试新闻"""
    news_items = [
        News(
            title="民法典实施三周年：成效显著",
            summary="自2021年1月1日民法典正式实施以来，我国民事法律制度更加完善...",
            content="民法典作为新中国成立以来第一部以法典命名的法律...",
            category="法律动态",
            is_published=True,
            is_top=True,
            view_count=3420
        ),
        News(
            title="劳动合同法修订草案公开征求意见",
            summary="为进一步保障劳动者权益，劳动合同法修订草案现向社会公开征求意见...",
            content="根据经济社会发展需要，劳动合同法修订草案对现行法律进行了多处修改...",
            category="政策解读",
            is_published=True,
            view_count=2890
        ),
        News(
            title="最高法发布消费者权益保护典型案例",
            summary="最高人民法院发布10个消费者权益保护典型案例，涉及网购、预付卡等领域...",
            content="为充分发挥典型案例的示范引领作用，最高人民法院选取了10个典型案例...",
            category="案例分析",
            is_published=True,
            view_count=2156
        ),
    ]
    for item in news_items:
        db.add(item)
    await db.commit()
    print(f"✓ 创建了 {len(news_items)} 条新闻")


async def create_law_firms(db: AsyncSession):
    """创建测试律所"""
    firms = [
        LawFirm(
            name="北京正义律师事务所",
            description="专注于民商事诉讼、刑事辩护、知识产权保护等领域",
            address="北京市朝阳区建国路88号",
            city="北京",
            province="北京",
            phone="010-12345678",
            email="contact@zhengyilaw.com",
            rating=4.8,
            review_count=156,
            is_verified=True,
            is_active=True,
            specialties="民商事诉讼,刑事辩护,知识产权"
        ),
        LawFirm(
            name="上海明理律师事务所",
            description="为企业和个人提供全方位法律服务",
            address="上海市浦东新区陆家嘴环路1000号",
            city="上海",
            province="上海",
            phone="021-87654321",
            email="info@minglilaw.com",
            rating=4.6,
            review_count=98,
            is_verified=True,
            is_active=True,
            specialties="公司法务,合同纠纷,劳动争议"
        ),
    ]

    created = 0
    for firm in firms:
        existing = (
            await db.execute(select(LawFirm).where(LawFirm.name == firm.name))
        ).scalar_one_or_none()
        if existing is None:
            db.add(firm)
            created += 1
        else:
            existing.description = firm.description
            existing.address = firm.address
            existing.city = firm.city
            existing.province = firm.province
            existing.phone = firm.phone
            existing.email = firm.email
            existing.rating = firm.rating
            existing.review_count = firm.review_count
            existing.is_verified = firm.is_verified
            existing.is_active = firm.is_active
            existing.specialties = firm.specialties

    await db.commit()
    print(f"✓ 创建/更新了 {len(firms)} 个律所（新增 {created}）")


async def create_posts(db: AsyncSession, users: list):
    """创建测试帖子"""
    posts = [
        Post(
            title="劳动合同试用期被无故辞退怎么办？",
            content="我在一家公司工作了2个月，还在试用期内，昨天突然被通知辞退，没有任何理由...",
            category="劳动纠纷",
            user_id=users[2].id if len(users) > 2 else 1
        ),
        Post(
            title="离婚时房产如何分割？求助",
            content="我和丈夫结婚5年，现在准备离婚，婚后共同购买了一套房产，请问如何分割？",
            category="婚姻家庭",
            user_id=users[2].id if len(users) > 2 else 1
        ),
    ]
    for post in posts:
        db.add(post)
    await db.commit()
    print(f"✓ 创建了 {len(posts)} 个帖子")


async def main():
    print("开始初始化种子数据...")
    await init_db()
    
    async with AsyncSessionLocal() as db:
        users = await create_users(db)
        await create_news(db)
        await create_law_firms(db)
        await create_posts(db, users)
    
    print("\n✓ 种子数据初始化完成!")
    print("\n测试账号:")
    print("  管理员: admin / admin123")
    print("  律师: lawyer1 / lawyer123")
    print("  用户: user1 / user123")


if __name__ == "__main__":
    asyncio.run(main())
