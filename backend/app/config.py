"""应用配置"""
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field, field_validator, model_validator
from functools import lru_cache
from typing import ClassVar, cast


def _running_tests() -> bool:
    return "pytest" in sys.modules


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

    cors_allow_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"]
    cors_allow_credentials: bool = False
    
    frontend_base_url: str = "http://localhost:5173"
    redis_url: str = ""
    trusted_proxies: list[str] = []
    
    # AI配置
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "deepseek-chat"
    
    # 向量数据库配置
    chroma_persist_dir: str = "./chroma_db"
    
    model_config: ClassVar[SettingsConfigDict] = cast(
        SettingsConfigDict,
        cast(
            object,
            {
                "env_file": None if _running_tests() else ".env",
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
