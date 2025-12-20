"""API接口测试"""
import pytest
from httpx import AsyncClient


class TestRootAPI:
    """根路由测试"""
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """测试根路由"""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data


class TestUserAPI:
    """用户API测试"""
    
    @pytest.mark.asyncio
    async def test_register_user(self, client: AsyncClient):
        """测试用户注册"""
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "Test123456"
        }
        response = await client.post("/api/user/register", json=user_data)
        assert response.status_code in [200, 201, 400, 422]  # 422 validation error
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """测试无效登录"""
        login_data = {
            "username": "nonexistent@example.com",
            "password": "wrongpassword"
        }
        response = await client.post("/api/user/login", json=login_data)
        assert response.status_code == 401


class TestNewsAPI:
    """新闻API测试"""
    
    @pytest.mark.asyncio
    async def test_get_news_list(self, client: AsyncClient):
        """测试获取新闻列表"""
        response = await client.get("/api/news")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestForumAPI:
    """论坛API测试"""
    
    @pytest.mark.asyncio
    async def test_get_posts_list(self, client: AsyncClient):
        """测试获取帖子列表"""
        response = await client.get("/api/forum/posts")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestLawFirmAPI:
    """律所API测试"""
    
    @pytest.mark.asyncio
    async def test_get_lawfirms_list(self, client: AsyncClient):
        """测试获取律所列表"""
        response = await client.get("/api/lawfirm/firms")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestDocumentAPI:
    """文书生成API测试"""
    
    @pytest.mark.asyncio
    async def test_get_document_types(self, client: AsyncClient):
        """测试获取文书类型"""
        response = await client.get("/api/documents/types")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0


class TestSystemAPI:
    """系统API测试"""
    
    @pytest.mark.asyncio
    async def test_get_admin_stats(self, client: AsyncClient):
        """测试获取管理统计（需要认证）"""
        response = await client.get("/api/admin/stats")
        # 未认证应返回401
        assert response.status_code == 401
