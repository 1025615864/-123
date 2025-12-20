"""输入验证工具"""
import re
from typing import Callable


def validate_phone(phone: str) -> bool:
    """验证中国手机号"""
    pattern = r'^1[3-9]\d{9}$'
    return bool(re.match(pattern, phone))


def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    验证密码强度
    
    Returns:
        (is_valid, message)
    """
    if len(password) < 8:
        return False, "密码长度至少8位"
    
    if len(password) > 50:
        return False, "密码长度不能超过50位"
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    if not (has_upper and has_lower and has_digit):
        return False, "密码需包含大小写字母和数字"
    
    return True, "密码强度合格"


def validate_username(username: str) -> tuple[bool, str]:
    """
    验证用户名
    
    Returns:
        (is_valid, message)
    """
    if len(username) < 2:
        return False, "用户名至少2个字符"
    
    if len(username) > 20:
        return False, "用户名不能超过20个字符"
    
    # 允许中文、英文、数字、下划线
    pattern = r'^[\u4e00-\u9fa5a-zA-Z0-9_]+$'
    if not re.match(pattern, username):
        return False, "用户名只能包含中文、英文、数字和下划线"
    
    return True, "用户名合法"


def sanitize_html(text: str) -> str:
    """清理HTML标签，防止XSS"""
    # 移除所有HTML标签
    clean = re.sub(r'<[^>]+>', '', text)
    # 转义特殊字符
    clean = clean.replace('&', '&amp;')
    clean = clean.replace('<', '&lt;')
    clean = clean.replace('>', '&gt;')
    clean = clean.replace('"', '&quot;')
    clean = clean.replace("'", '&#x27;')
    return clean


def validate_url(url: str) -> bool:
    """验证URL格式"""
    pattern = r'^https?://[^\s<>"{}|\\^`\[\]]+$'
    return bool(re.match(pattern, url))


def validate_id_card(id_card: str) -> bool:
    """验证中国身份证号（简单校验）"""
    pattern = r'^[1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]$'
    return bool(re.match(pattern, id_card))


class InputValidator:
    """输入验证器类"""
    
    def __init__(self):
        self.errors: list[str] = []
    
    def reset(self) -> "InputValidator":
        """重置错误列表"""
        self.errors = []
        return self
    
    def validate(self, value: str, validator: Callable[[str], bool], error_msg: str) -> "InputValidator":
        """通用验证"""
        if not validator(value):
            self.errors.append(error_msg)
        return self
    
    def required(self, value: str | None, field_name: str) -> "InputValidator":
        """必填验证"""
        if not value or not value.strip():
            self.errors.append(f"{field_name}不能为空")
        return self
    
    def min_length(self, value: str, min_len: int, field_name: str) -> "InputValidator":
        """最小长度验证"""
        if len(value) < min_len:
            self.errors.append(f"{field_name}长度至少{min_len}个字符")
        return self
    
    def max_length(self, value: str, max_len: int, field_name: str) -> "InputValidator":
        """最大长度验证"""
        if len(value) > max_len:
            self.errors.append(f"{field_name}长度不能超过{max_len}个字符")
        return self
    
    def is_valid(self) -> bool:
        """是否验证通过"""
        return len(self.errors) == 0
    
    def get_errors(self) -> list[str]:
        """获取错误列表"""
        return self.errors
    
    def get_first_error(self) -> str | None:
        """获取第一个错误"""
        return self.errors[0] if self.errors else None
