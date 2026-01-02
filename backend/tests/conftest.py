"""Pytest配置文件"""
import importlib
import inspect
from typing import Any, cast
import pytest
import pytest_asyncio
from collections.abc import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.database import Base, get_db

# 使用内存数据库进行测试
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# pytest-asyncio 配置
pytest_plugins = ('pytest_asyncio',)


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """创建测试数据库引擎"""
    for module_name in (
        "app.models.user",
        "app.models.consultation",
        "app.models.forum",
        "app.models.news",
        "app.models.news_ai",
        "app.models.lawfirm",
        "app.models.knowledge",
        "app.models.notification",
        "app.models.payment",
        "app.models.system",
        "app.models.calendar",
    ):
        _ = importlib.import_module(module_name)

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """创建测试会话"""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()
        yield session


@pytest_asyncio.fixture
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """创建测试客户端"""
    async def override_get_db():
        yield test_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    extra_transport_kwargs: dict[str, Any] = {}
    if "lifespan" in inspect.signature(ASGITransport.__init__).parameters:
        extra_transport_kwargs["lifespan"] = "off"
    transport = ASGITransport(app=app, **cast(Any, extra_transport_kwargs))
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()
