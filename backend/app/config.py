"""应用配置"""
import os
import sys
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field, field_validator, model_validator
from functools import lru_cache
from typing import ClassVar, cast


def _running_tests() -> bool:
    return "pytest" in sys.modules


def _resolve_env_files() -> list[str] | None:
    if _running_tests():
        return None

    explicit = os.getenv("ENV_FILE", "").strip()
    if explicit:
        return [explicit]

    here = Path(__file__).resolve()
    backend_dir = here.parents[1]
    repo_root = here.parents[2]

    candidates = [backend_dir / ".env", repo_root / ".env"]
    return [str(p) for p in candidates if p.exists()]


class Settings(BaseSettings):
    """应用设置"""
    # 应用配置
    app_name: str = "百姓法律助手"
    debug: bool = Field(default_factory=_running_tests)
    
    # 数据库配置
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    
    # JWT配置
    secret_key: str = Field(
        default="your-super-secret-key-change-in-production",
        validation_alias=AliasChoices("SECRET_KEY", "JWT_SECRET_KEY"),
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    payment_webhook_secret: str = Field(
        default="",
        validation_alias=AliasChoices("PAYMENT_WEBHOOK_SECRET", "PAYMENT_CALLBACK_SECRET"),
    )

    alipay_app_id: str = Field(
        default="",
        validation_alias=AliasChoices("ALIPAY_APP_ID", "PAY_ALIPAY_APP_ID"),
    )
    alipay_private_key: str = Field(
        default="",
        validation_alias=AliasChoices("ALIPAY_PRIVATE_KEY", "PAY_ALIPAY_PRIVATE_KEY"),
    )
    alipay_public_key: str = Field(
        default="",
        validation_alias=AliasChoices("ALIPAY_PUBLIC_KEY", "PAY_ALIPAY_PUBLIC_KEY"),
    )
    alipay_gateway_url: str = Field(
        default="https://openapi.alipay.com/gateway.do",
        validation_alias=AliasChoices("ALIPAY_GATEWAY_URL", "PAY_ALIPAY_GATEWAY_URL"),
    )
    alipay_notify_url: str = Field(
        default="",
        validation_alias=AliasChoices("ALIPAY_NOTIFY_URL", "PAY_ALIPAY_NOTIFY_URL"),
    )
    alipay_return_url: str = Field(
        default="",
        validation_alias=AliasChoices("ALIPAY_RETURN_URL", "PAY_ALIPAY_RETURN_URL"),
    )

    ikunpay_pid: str = Field(
        default="",
        validation_alias=AliasChoices("IKUNPAY_PID", "PAY_IKUNPAY_PID"),
    )
    ikunpay_key: str = Field(
        default="",
        validation_alias=AliasChoices("IKUNPAY_KEY", "PAY_IKUNPAY_KEY"),
    )
    ikunpay_gateway_url: str = Field(
        default="https://ikunpay.com/submit.php",
        validation_alias=AliasChoices("IKUNPAY_GATEWAY_URL", "IKUNPAY_SUBMIT_URL", "PAY_IKUNPAY_GATEWAY_URL"),
    )
    ikunpay_notify_url: str = Field(
        default="",
        validation_alias=AliasChoices("IKUNPAY_NOTIFY_URL", "PAY_IKUNPAY_NOTIFY_URL"),
    )
    ikunpay_return_url: str = Field(
        default="",
        validation_alias=AliasChoices("IKUNPAY_RETURN_URL", "PAY_IKUNPAY_RETURN_URL"),
    )
    ikunpay_default_type: str = Field(
        default="",
        validation_alias=AliasChoices("IKUNPAY_DEFAULT_TYPE", "PAY_IKUNPAY_DEFAULT_TYPE"),
    )

    wechatpay_mch_id: str = Field(
        default="",
        validation_alias=AliasChoices("WECHATPAY_MCH_ID", "WECHAT_MCH_ID"),
    )
    wechatpay_mch_serial_no: str = Field(
        default="",
        validation_alias=AliasChoices("WECHATPAY_MCH_SERIAL_NO", "WECHAT_MCH_SERIAL_NO"),
    )
    wechatpay_private_key: str = Field(
        default="",
        validation_alias=AliasChoices("WECHATPAY_PRIVATE_KEY", "WECHAT_PRIVATE_KEY"),
    )
    wechatpay_api_v3_key: str = Field(
        default="",
        validation_alias=AliasChoices("WECHATPAY_API_V3_KEY", "WECHAT_API_V3_KEY"),
    )
    wechatpay_certificates_url: str = Field(
        default="https://api.mch.weixin.qq.com/v3/certificates",
        validation_alias=AliasChoices("WECHATPAY_CERTIFICATES_URL", "WECHAT_CERTIFICATES_URL"),
    )

    cors_allow_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"]
    cors_allow_credentials: bool = False
    
    frontend_base_url: str = "http://localhost:5173"
    redis_url: str = ""
    trusted_proxies: list[str] = []
    
    # AI配置
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "deepseek-chat"
    ai_fallback_models: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("AI_FALLBACK_MODELS", "OPENAI_FALLBACK_MODELS"),
    )
    
    # 向量数据库配置
    chroma_persist_dir: str = "./chroma_db"
    
    model_config: ClassVar[SettingsConfigDict] = cast(
        SettingsConfigDict,
        cast(
            object,
            {
                "env_file": _resolve_env_files(),
                "extra": "ignore",
                "from_attributes": True,
            },
        ),
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _parse_cors_allow_origins(cls, value: object):
        if isinstance(value, str):
            parts = [p.strip() for p in value.replace("，", ",").split(",")]
            return [p for p in parts if p]
        return value

    @field_validator("ai_fallback_models", mode="before")
    @classmethod
    def _parse_ai_fallback_models(cls, value: object):
        if value is None:
            return []
        if isinstance(value, str):
            parts = [p.strip() for p in value.replace("，", ",").split(",")]
            cleaned = [p for p in parts if p]
        elif isinstance(value, list):
            cleaned = [str(v).strip() for v in value if str(v).strip()]
        else:
            cleaned = [str(value).strip()] if str(value).strip() else []

        seen: set[str] = set()
        out: list[str] = []
        for item in cleaned:
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
        return out

    @field_validator("debug", mode="before")
    @classmethod
    def _parse_debug(cls, value: object):
        if value is None:
            return bool(_running_tests())
        if isinstance(value, bool):
            return bool(value)
        if isinstance(value, int):
            return bool(int(value))
        if isinstance(value, str):
            s = value.strip().lower()
            if not s:
                return bool(_running_tests())
            if s in {"1", "true", "yes", "y", "on"}:
                return True
            if s in {"0", "false", "no", "n", "off"}:
                return False
            return True
        return bool(_running_tests())

    @model_validator(mode="after")
    def _validate_security(self):
        if _running_tests():
            return self
        insecure_defaults = {
            "your-super-secret-key-change-in-production",
            "your-secret-key-change-in-production",
            "your-secret-key-here",
        }
        if not self.debug:
            if self.secret_key in insecure_defaults or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be set to a secure value when DEBUG is False")

            if not self.payment_webhook_secret or len(self.payment_webhook_secret) < 16:
                raise ValueError("PAYMENT_WEBHOOK_SECRET must be set when DEBUG is False")
        return self


@lru_cache()
def get_settings() -> Settings:
    """获取缓存的设置实例"""
    return Settings()
