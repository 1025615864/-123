"""服务层单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestEmailService:
    """邮件服务测试"""
    
    def test_generate_reset_token(self):
        """测试生成重置令牌"""
        from app.services.email_service import EmailService
        
        service = EmailService()
        token = service.generate_reset_token(user_id=1, email="test@example.com")
        
        assert token is not None
        assert len(token) > 0
    
    def test_verify_reset_token_valid(self):
        """测试验证有效令牌"""
        from app.services.email_service import EmailService
        
        service = EmailService()
        email = "test@example.com"
        token = service.generate_reset_token(user_id=1, email=email)
        
        result = service.verify_reset_token(token)
        assert result is not None
        assert result.get("email") == email
    
    def test_verify_reset_token_invalid(self):
        """测试验证无效令牌"""
        from app.services.email_service import EmailService
        
        service = EmailService()
        result = service.verify_reset_token("invalid_token")
        assert result is None


class TestCacheService:
    """缓存服务测试"""
    
    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """测试设置和获取缓存"""
        from app.services.cache_service import cache_service
        
        await cache_service.set("test_key", "test_value", expire=60)
        result = await cache_service.get("test_key")
        
        assert result == "test_value"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """测试获取不存在的键"""
        from app.services.cache_service import cache_service
        
        result = await cache_service.get("nonexistent_key_12345")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_key(self):
        """测试删除键"""
        from app.services.cache_service import cache_service
        
        await cache_service.set("delete_test", "value", expire=60)
        await cache_service.delete("delete_test")
        result = await cache_service.get("delete_test")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_set_and_get_json(self):
        """测试设置和获取JSON"""
        from app.services.cache_service import cache_service
        
        data = {"name": "test", "value": 123}
        await cache_service.set_json("json_test", data, expire=60)
        result = await cache_service.get_json("json_test")
        
        assert result == data


class TestValidators:
    """验证器测试"""
    
    def test_validate_phone_valid(self):
        """测试有效手机号"""
        from app.utils.validators import validate_phone
        
        assert validate_phone("13800138000") is True
        assert validate_phone("15912345678") is True
    
    def test_validate_phone_invalid(self):
        """测试无效手机号"""
        from app.utils.validators import validate_phone
        
        assert validate_phone("1234567890") is False
        assert validate_phone("12345678901") is False
        assert validate_phone("phone") is False
    
    def test_validate_email_valid(self):
        """测试有效邮箱"""
        from app.utils.validators import validate_email
        
        assert validate_email("test@example.com") is True
        assert validate_email("user.name@domain.org") is True
    
    def test_validate_email_invalid(self):
        """测试无效邮箱"""
        from app.utils.validators import validate_email
        
        assert validate_email("invalid") is False
        assert validate_email("@example.com") is False
        assert validate_email("test@") is False
    
    def test_validate_password_strength(self):
        """测试密码强度验证"""
        from app.utils.validators import validate_password_strength
        
        # 有效密码
        is_valid, msg = validate_password_strength("Test1234")
        assert is_valid is True
        
        # 太短
        is_valid, msg = validate_password_strength("Test1")
        assert is_valid is False
        
        # 缺少数字
        is_valid, msg = validate_password_strength("TestTest")
        assert is_valid is False
    
    def test_validate_username(self):
        """测试用户名验证"""
        from app.utils.validators import validate_username
        
        # 有效用户名
        is_valid, msg = validate_username("用户名123")
        assert is_valid is True
        
        is_valid, msg = validate_username("username_test")
        assert is_valid is True
        
        # 太短
        is_valid, msg = validate_username("a")
        assert is_valid is False
    
    def test_sanitize_html(self):
        """测试HTML清理"""
        from app.utils.validators import sanitize_html
        
        result = sanitize_html("<script>alert('xss')</script>Hello")
        assert "<script>" not in result
        assert "Hello" in result
    
    def test_input_validator_chain(self):
        """测试链式验证器"""
        from app.utils.validators import InputValidator
        
        validator = InputValidator()
        validator.required("test", "字段").min_length("test", 2, "字段")
        
        assert validator.is_valid() is True
        assert len(validator.get_errors()) == 0
        
        validator.reset().required("", "空字段")
        assert validator.is_valid() is False
        assert len(validator.get_errors()) == 1


class TestSecurity:
    """安全工具测试"""
    
    def test_hash_password(self):
        """测试密码哈希"""
        from app.utils.security import hash_password, verify_password
        
        password = "TestPassword123"
        hashed = hash_password(password)
        
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrong", hashed) is False
    
    def test_create_and_decode_token(self):
        """测试JWT创建和解码"""
        from app.utils.security import create_access_token, decode_token
        
        data = {"sub": "123"}
        token = create_access_token(data)
        
        decoded = decode_token(token)
        assert decoded is not None
        assert decoded.get("sub") == "123"
    
    def test_decode_invalid_token(self):
        """测试解码无效令牌"""
        from app.utils.security import decode_token
        
        result = decode_token("invalid.token.here")
        assert result is None
