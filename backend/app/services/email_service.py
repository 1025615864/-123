"""邮件服务"""
import logging

from typing_extensions import TypedDict

import secrets
from datetime import datetime, timedelta

from .cache_service import cache_service

logger = logging.getLogger(__name__)

# 存储密码重置令牌（生产环境应使用Redis）
class ResetTokenData(TypedDict):
    user_id: int
    email: str
    expires_at: str
    used: bool


class EmailVerificationTokenData(TypedDict):
    user_id: int
    email: str
    expires_at: str
    used: bool

_reset_tokens: dict[str, ResetTokenData] = {}

_email_verification_tokens: dict[str, EmailVerificationTokenData] = {}

_RESET_TOKEN_PREFIX = "password_reset_token:"
_RESET_TOKEN_TTL_SECONDS = 3600

_EMAIL_VERIFY_TOKEN_PREFIX = "email_verify_token:"
_EMAIL_VERIFY_TOKEN_TTL_SECONDS = 60 * 60 * 24


class EmailService:
    """邮件服务类"""
    
    def __init__(self):
        self.smtp_host: str | None = None
        self.smtp_port: int = 587
        self.smtp_user: str | None = None
        self.smtp_password: str | None = None
        self.from_email: str = "noreply@baixing-law.com"
        self.from_name: str = "百姓法律助手"
    
    def configure(
        self, 
        smtp_host: str, 
        smtp_port: int, 
        smtp_user: str, 
        smtp_password: str,
        from_email: str | None = None
    ) -> None:
        """配置SMTP服务器"""
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        if from_email:
            self.from_email = from_email
    
    @property
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)
    
    async def generate_reset_token(self, user_id: int, email: str) -> str:
        """生成密码重置令牌"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=1)

        token_data: ResetTokenData = {
            "user_id": user_id,
            "email": email,
            "expires_at": expires_at.isoformat(),
            "used": False,
        }

        cache_key = f"{_RESET_TOKEN_PREFIX}{token}"
        try:
            _ = await cache_service.set_json(cache_key, dict(token_data), expire=_RESET_TOKEN_TTL_SECONDS)
        except Exception:
            _reset_tokens[token] = token_data
            self._cleanup_expired_tokens()

        return token

    async def verify_reset_token(self, token: str) -> ResetTokenData | None:
        """验证重置令牌"""
        cache_key = f"{_RESET_TOKEN_PREFIX}{token}"
        try:
            token_data = await cache_service.get_json(cache_key)
            if isinstance(token_data, dict):
                used = token_data.get("used")
                if used:
                    return None
                user_id = token_data.get("user_id")
                email = token_data.get("email")
                expires_at = token_data.get("expires_at")
                if isinstance(user_id, int) and isinstance(email, str) and isinstance(expires_at, str):
                    return {
                        "user_id": user_id,
                        "email": email,
                        "expires_at": expires_at,
                        "used": bool(used),
                    }
        except Exception:
            pass

        if token not in _reset_tokens:
            return None

        token_data = _reset_tokens[token]

        if token_data["used"]:
            return None

        try:
            expires_at = datetime.fromisoformat(token_data["expires_at"])
        except ValueError:
            del _reset_tokens[token]
            return None

        if datetime.now() > expires_at:
            del _reset_tokens[token]
            return None

        return token_data

    async def invalidate_token(self, token: str) -> None:
        """使令牌失效"""
        cache_key = f"{_RESET_TOKEN_PREFIX}{token}"
        try:
            token_data = await cache_service.get_json(cache_key)
            if isinstance(token_data, dict):
                token_data["used"] = True
                _ = await cache_service.set_json(cache_key, token_data, expire=_RESET_TOKEN_TTL_SECONDS)
                return
        except Exception:
            pass

        if token in _reset_tokens:
            _reset_tokens[token]["used"] = True


    async def generate_email_verification_token(self, user_id: int, email: str) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(seconds=_EMAIL_VERIFY_TOKEN_TTL_SECONDS)

        token_data: EmailVerificationTokenData = {
            "user_id": int(user_id),
            "email": str(email),
            "expires_at": expires_at.isoformat(),
            "used": False,
        }

        cache_key = f"{_EMAIL_VERIFY_TOKEN_PREFIX}{token}"
        try:
            _ = await cache_service.set_json(cache_key, dict(token_data), expire=_EMAIL_VERIFY_TOKEN_TTL_SECONDS)
        except Exception:
            _email_verification_tokens[token] = token_data
            self._cleanup_expired_tokens()

        return token


    async def verify_email_verification_token(self, token: str) -> EmailVerificationTokenData | None:
        cache_key = f"{_EMAIL_VERIFY_TOKEN_PREFIX}{token}"
        try:
            token_data = await cache_service.get_json(cache_key)
            if isinstance(token_data, dict):
                used = token_data.get("used")
                if used:
                    return None
                user_id = token_data.get("user_id")
                email = token_data.get("email")
                expires_at = token_data.get("expires_at")
                if isinstance(user_id, int) and isinstance(email, str) and isinstance(expires_at, str):
                    return {
                        "user_id": user_id,
                        "email": email,
                        "expires_at": expires_at,
                        "used": bool(used),
                    }
        except Exception:
            pass

        if token not in _email_verification_tokens:
            return None

        token_data = _email_verification_tokens[token]
        if token_data["used"]:
            return None

        try:
            expires_at_dt = datetime.fromisoformat(token_data["expires_at"])
        except ValueError:
            del _email_verification_tokens[token]
            return None

        if datetime.now() > expires_at_dt:
            del _email_verification_tokens[token]
            return None

        return token_data


    async def invalidate_email_verification_token(self, token: str) -> None:
        cache_key = f"{_EMAIL_VERIFY_TOKEN_PREFIX}{token}"
        try:
            token_data = await cache_service.get_json(cache_key)
            if isinstance(token_data, dict):
                token_data["used"] = True
                _ = await cache_service.set_json(cache_key, token_data, expire=_EMAIL_VERIFY_TOKEN_TTL_SECONDS)
                return
        except Exception:
            pass

        if token in _email_verification_tokens:
            _email_verification_tokens[token]["used"] = True
    
    def _cleanup_expired_tokens(self) -> None:
        """清理过期令牌"""
        now = datetime.now()
        expired: list[str] = []
        for token, data in list(_reset_tokens.items()):
            try:
                expires_at = datetime.fromisoformat(data["expires_at"])
            except ValueError:
                expired.append(token)
                continue
            if now > expires_at:
                expired.append(token)
        for token in expired:
            del _reset_tokens[token]
    
    async def send_password_reset_email(self, email: str, reset_token: str, reset_url: str) -> bool:
        """发送密码重置邮件"""
        if not self.is_configured:
            logger.warning("Email service not configured, skipping email send")
            # 开发模式：打印令牌
            logger.info(f"[DEV] Password reset token for {email}: {reset_token}")
            logger.info(f"[DEV] Reset URL: {reset_url}")
            return True
        
        try:
            import importlib
            aiosmtplib = importlib.import_module("aiosmtplib")
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            message = MIMEMultipart("alternative")
            message["Subject"] = "密码重置 - 百姓法律助手"
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = email
            
            # 纯文本版本
            text_content = f"""
您好，

您正在重置百姓法律助手账号的密码。

请点击以下链接重置密码（1小时内有效）：
{reset_url}

如果您没有请求重置密码，请忽略此邮件。

百姓法律助手团队
"""
            
            # HTML版本
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #f59e0b, #ea580c); padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .header h1 {{ color: white; margin: 0; }}
        .content {{ background: #1a1625; color: #e5e5e5; padding: 30px; border-radius: 0 0 10px 10px; }}
        .button {{ display: inline-block; background: linear-gradient(135deg, #f59e0b, #ea580c); color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; margin: 20px 0; }}
        .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚖️ 百姓法律助手</h1>
        </div>
        <div class="content">
            <p>您好，</p>
            <p>您正在重置百姓法律助手账号的密码。</p>
            <p style="text-align: center;">
                <a href="{reset_url}" class="button">重置密码</a>
            </p>
            <p>此链接将在 <strong>1小时</strong> 后失效。</p>
            <p>如果您没有请求重置密码，请忽略此邮件。</p>
            <p class="footer">© 百姓法律助手团队</p>
        </div>
    </div>
</body>
</html>
"""
            
            message.attach(MIMEText(text_content, "plain", "utf-8"))
            message.attach(MIMEText(html_content, "html", "utf-8"))
            
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True
            )
            
            logger.info(f"Password reset email sent to {email}")
            return True
            
        except ImportError:
            logger.error("aiosmtplib not installed. Run: pip install aiosmtplib")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    async def send_notification_email(self, email: str, subject: str, content: str) -> bool:
        """发送通知邮件"""
        if not self.is_configured:
            logger.warning("Email service not configured")
            return False
        
        try:
            import importlib
            aiosmtplib = importlib.import_module("aiosmtplib")
            from email.mime.text import MIMEText
            
            message = MIMEText(content, "plain", "utf-8")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = email
            
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True
            )
            
            return True
        except ImportError:
            logger.error("aiosmtplib not installed. Run: pip install aiosmtplib")
            return False
        except Exception as e:
            logger.error(f"Failed to send notification email: {e}")
            return False


    async def send_email_verification_email(self, email: str, verify_url: str) -> bool:
        if not self.is_configured:
            logger.warning("Email service not configured, skipping email send")
            logger.info(f"[DEV] Email verification url for {email}: {verify_url}")
            return True

        try:
            import importlib
            aiosmtplib = importlib.import_module("aiosmtplib")
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            message = MIMEMultipart("alternative")
            message["Subject"] = "邮箱验证 - 百姓法律助手"
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = email

            text_content = f"""
您好，

请点击以下链接完成邮箱验证（24小时内有效）：
{verify_url}

如果您没有发起该操作，请忽略此邮件。

百姓法律助手团队
"""

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #f59e0b, #ea580c); padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .header h1 {{ color: white; margin: 0; }}
        .content {{ background: #1a1625; color: #e5e5e5; padding: 30px; border-radius: 0 0 10px 10px; }}
        .button {{ display: inline-block; background: linear-gradient(135deg, #f59e0b, #ea580c); color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; margin: 20px 0; }}
        .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚖️ 百姓法律助手</h1>
        </div>
        <div class="content">
            <p>您好，</p>
            <p>请点击以下按钮完成邮箱验证（<strong>24小时</strong>内有效）：</p>
            <p style="text-align: center;">
                <a href="{verify_url}" class="button">验证邮箱</a>
            </p>
            <p>如果您没有发起该操作，请忽略此邮件。</p>
            <p class="footer">© 百姓法律助手团队</p>
        </div>
    </div>
</body>
</html>
"""

            message.attach(MIMEText(text_content, "plain", "utf-8"))
            message.attach(MIMEText(html_content, "html", "utf-8"))

            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True,
            )
            return True
        except ImportError:
            logger.error("aiosmtplib not installed. Run: pip install aiosmtplib")
            return False
        except Exception as e:
            logger.error(f"Failed to send email verification email: {e}")
            return False


# 单例实例
email_service = EmailService()
