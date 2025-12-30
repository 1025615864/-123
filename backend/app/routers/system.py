"""系统配置和日志API路由"""
from typing import Annotated, ClassVar, cast
import base64
import json
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_
from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from datetime import datetime, timedelta

from ..database import get_db
from ..models.system import SystemConfig, AdminLog, LogAction, LogModule
from ..models.user import User
from ..utils.deps import require_admin, get_current_user_optional
from ..utils.rate_limiter import get_client_ip, rate_limit, RateLimitConfig

router = APIRouter(prefix="/system", tags=["系统管理"])


# ============ 系统配置 ============

class ConfigItem(BaseModel):
    key: str
    value: str | None
    description: str | None = None
    category: str = "general"


class ConfigResponse(BaseModel):
    key: str
    value: str | None
    description: str | None
    category: str
    updated_at: datetime | None

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class ConfigBatchUpdate(BaseModel):
    configs: list[ConfigItem] = Field(validation_alias=AliasChoices("configs", "items"))


def _mask_config_value(key_name: str, value: str | None) -> str | None:
    if value is None:
        return None
    k = key_name.lower()
    if any(token in k for token in ("secret", "password", "token", "api_key", "apikey", "providers", "private_key", "secret_key")):
        return "***"
    if re.search(r"(^|_)key($|_)", k):
        return "***"
    return value


def _news_ai_providers_config_contains_api_key(decoded_json: str) -> bool:
    s = str(decoded_json or "").strip()
    if not s:
        return False
    try:
        obj_raw: object = cast(object, json.loads(s))
        if isinstance(obj_raw, list):
            for item_obj in cast(list[object], obj_raw):
                if not isinstance(item_obj, dict):
                    continue
                item_dict = cast(dict[object, object], item_obj)
                for k_obj in item_dict.keys():
                    kk = str(k_obj or "").strip().lower()
                    if kk in {"api_key", "apikey"}:
                        return True
            return False
        if isinstance(obj_raw, dict):
            obj_dict = cast(dict[object, object], obj_raw)
            for k_obj in obj_dict.keys():
                kk = str(k_obj or "").strip().lower()
                if kk in {"api_key", "apikey"}:
                    return True
            return False
    except Exception:
        return bool(re.search(r'"api_key"|\bapi_key\b|"apikey"|\bapikey\b', s, flags=re.IGNORECASE))
    return False


def _validate_system_config_no_secrets(key: str, value: str | None) -> None:
    k = str(key or "").strip()
    if value is None or not str(value).strip():
        return

    k_upper = k.upper()
    k_lower = k.lower()
    providers_prefixes = ("NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON", "NEWS_AI_SUMMARY_LLM_PROVIDERS_B64")
    is_providers_key = k_upper in providers_prefixes or any(k_upper.startswith(f"{p}_") for p in providers_prefixes)
    if (
        any(token in k_lower for token in ("secret", "password", "api_key", "apikey", "private_key"))
        and not is_providers_key
    ):
        raise HTTPException(
            status_code=400,
            detail="Secret values must not be stored in SystemConfig. Use environment variables / Secret Manager.",
        )

    if not is_providers_key:
        return

    decoded = str(value)
    if k_upper.startswith("NEWS_AI_SUMMARY_LLM_PROVIDERS_B64"):
        try:
            decoded = base64.b64decode(str(value).strip()).decode("utf-8")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail="NEWS_AI_SUMMARY_LLM_PROVIDERS_B64 must be valid base64-encoded JSON",
            ) from e

    if _news_ai_providers_config_contains_api_key(decoded):
        raise HTTPException(
            status_code=400,
            detail=(
                "NEWS_AI providers config must not include api_key in SystemConfig. "
                "Use OPENAI_API_KEY (Secret/env) and omit api_key from providers JSON (Scheme A)."
            ),
        )


@router.get("/configs", response_model=list[ConfigResponse])
async def get_all_configs(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = None,
):
    """获取所有系统配置"""
    query = select(SystemConfig)
    if category:
        query = query.where(SystemConfig.category == category)
    query = query.order_by(SystemConfig.category, SystemConfig.key)
    
    result = await db.execute(query)
    configs = result.scalars().all()
    
    return [ConfigResponse(
        key=c.key,
        value=_mask_config_value(str(c.key), c.value),
        description=c.description,
        category=c.category,
        updated_at=c.updated_at
    ) for c in configs]


@router.get("/configs/{key}")
async def get_config(
    key: str,
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取单个配置项"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        return {"key": key, "value": None}
    
    return {"key": config.key, "value": _mask_config_value(str(config.key), config.value)}


class NewsAiProviderPublic(BaseModel):
    name: str | None = None
    base_url: str
    model: str | None = None
    response_format: str | None = None
    auth_type: str | None = None
    auth_header_name: str | None = None
    auth_prefix: str | None = None
    chat_completions_path: str | None = None
    weight: int | None = None
    api_key_configured: bool = False


class NewsAiRecentError(BaseModel):
    news_id: int
    retry_count: int
    last_error: str | None
    last_error_at: datetime | None


class NewsAiErrorTrendItem(BaseModel):
    date: str
    errors: int


class NewsAiTopError(BaseModel):
    message: str
    count: int


class NewsAiStatusResponse(BaseModel):
    news_ai_enabled: bool
    news_ai_interval_seconds: float
    summary_llm_enabled: bool
    response_format: str | None
    provider_strategy: str
    providers: list[NewsAiProviderPublic]
    pending_total: int
    errors_total: int
    errors_last_24h: int
    errors_last_7d: int
    errors_trend_7d: list[NewsAiErrorTrendItem]
    top_errors: list[NewsAiTopError]
    recent_errors: list[NewsAiRecentError]
    config_overrides: dict[str, str]


@router.get("/news-ai/status", response_model=NewsAiStatusResponse)
async def get_news_ai_status(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from ..config import get_settings
    from ..models.news import News
    from ..models.news_ai import NewsAIAnnotation
    from ..services.news_ai_pipeline_service import news_ai_pipeline_service

    cfg_overrides = await news_ai_pipeline_service.load_system_config_overrides(db)

    def _env(name: str, default: str = "") -> str:
        v = cfg_overrides.get(name)
        if v is not None and str(v).strip():
            return str(v).strip()
        raw = os.getenv(name)
        if raw is None:
            return default
        return str(raw)

    def _bool(name: str, default: bool = False) -> bool:
        raw = _env(name, "")
        if not raw.strip():
            return bool(default)
        return raw.strip().lower() in {"1", "true", "yes", "y", "on"}

    settings = get_settings()
    providers_raw = news_ai_pipeline_service.get_summary_llm_providers(settings, env_overrides=cfg_overrides)
    providers: list[NewsAiProviderPublic] = []
    for p in providers_raw:
        api_key = str(p.get("api_key", "") or "").strip()
        providers.append(
            NewsAiProviderPublic(
                name=str(p.get("name", "") or "").strip() or None,
                base_url=str(p.get("base_url", "") or "").strip(),
                model=str(p.get("model", "") or "").strip() or None,
                response_format=str(p.get("response_format", "") or "").strip() or None,
                auth_type=str(p.get("auth_type", "") or "").strip() or None,
                auth_header_name=str(p.get("auth_header_name", "") or "").strip() or None,
                auth_prefix=str(p.get("auth_prefix", "") or "") if p.get("auth_prefix") is not None else None,
                chat_completions_path=str(p.get("chat_completions_path", "") or "").strip() or None,
                weight=int(p.get("weight", 0) or 0) if p.get("weight") is not None else None,
                api_key_configured=bool(api_key),
            )
        )

    where_clause = or_(
        NewsAIAnnotation.id.is_(None),
        NewsAIAnnotation.processed_at.is_(None),
        NewsAIAnnotation.highlights.is_(None),
        NewsAIAnnotation.keywords.is_(None),
    )

    pending_total_res = await db.execute(
        select(func.count(News.id))
        .select_from(News)
        .outerjoin(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id)
        .where(where_clause)
    )
    pending_total = int(pending_total_res.scalar() or 0)

    errors_total_res = await db.execute(select(func.count(NewsAIAnnotation.id)).where(NewsAIAnnotation.last_error.is_not(None)))
    errors_total = int(errors_total_res.scalar() or 0)

    now_dt = datetime.now()
    since_24h = now_dt - timedelta(hours=24)
    since_7d = now_dt - timedelta(days=7)

    errors_last_24h_res = await db.execute(
        select(func.count(NewsAIAnnotation.id)).where(
            and_(
                NewsAIAnnotation.last_error.is_not(None),
                NewsAIAnnotation.last_error_at.is_not(None),
                NewsAIAnnotation.last_error_at >= since_24h,
            )
        )
    )
    errors_last_24h = int(errors_last_24h_res.scalar() or 0)

    errors_last_7d_res = await db.execute(
        select(func.count(NewsAIAnnotation.id)).where(
            and_(
                NewsAIAnnotation.last_error.is_not(None),
                NewsAIAnnotation.last_error_at.is_not(None),
                NewsAIAnnotation.last_error_at >= since_7d,
            )
        )
    )
    errors_last_7d = int(errors_last_7d_res.scalar() or 0)

    today = now_dt.date()
    errors_trend_7d: list[NewsAiErrorTrendItem] = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=int(i))
        day_cnt_res = await db.execute(
            select(func.count(NewsAIAnnotation.id)).where(
                and_(
                    NewsAIAnnotation.last_error.is_not(None),
                    NewsAIAnnotation.last_error_at.is_not(None),
                    func.date(NewsAIAnnotation.last_error_at) == day,
                )
            )
        )
        errors_trend_7d.append(NewsAiErrorTrendItem(date=day.isoformat(), errors=int(day_cnt_res.scalar() or 0)))

    cnt = func.count(NewsAIAnnotation.id).label("cnt")
    top_res = await db.execute(
        select(NewsAIAnnotation.last_error, cnt)
        .where(NewsAIAnnotation.last_error.is_not(None))
        .group_by(NewsAIAnnotation.last_error)
        .order_by(desc(cnt))
        .limit(10)
    )
    top_any = cast(list[tuple[object, object]], list(top_res.all()))
    top_errors: list[NewsAiTopError] = []
    for msg_obj, cnt_obj in top_any:
        msg = str(msg_obj or "").strip()
        if not msg:
            continue
        c_int = 0
        if isinstance(cnt_obj, int):
            c_int = int(cnt_obj)
        elif isinstance(cnt_obj, float):
            c_int = int(cnt_obj)
        elif isinstance(cnt_obj, str):
            s = cnt_obj.strip()
            if s.isdigit():
                c_int = int(s)
        top_errors.append(NewsAiTopError(message=msg, count=int(c_int)))

    recent_res = await db.execute(
        select(
            NewsAIAnnotation.news_id,
            NewsAIAnnotation.retry_count,
            NewsAIAnnotation.last_error,
            NewsAIAnnotation.last_error_at,
        )
        .where(NewsAIAnnotation.last_error.is_not(None))
        .order_by(desc(NewsAIAnnotation.last_error_at), desc(NewsAIAnnotation.id))
        .limit(20)
    )

    recent_any = cast(list[tuple[object, object, object, object]], list(recent_res.all()))
    recent_rows: list[tuple[int, int, str | None, datetime | None]] = []
    for nid, rc, le, lea in recent_any:
        nid_int = 0
        if isinstance(nid, int):
            nid_int = int(nid)
        elif isinstance(nid, float):
            nid_int = int(nid)
        elif isinstance(nid, str):
            s = nid.strip()
            if s and re.fullmatch(r"-?\d+", s):
                nid_int = int(s)

        rc_int = 0
        if isinstance(rc, int):
            rc_int = int(rc)
        elif isinstance(rc, float):
            rc_int = int(rc)
        elif isinstance(rc, str):
            s = rc.strip()
            if s and re.fullmatch(r"-?\d+", s):
                rc_int = int(s)

        recent_rows.append(
            (
                int(nid_int),
                int(rc_int),
                (str(le) if le is not None else None),
                cast(datetime | None, lea),
            )
        )
    recent_errors = [
        NewsAiRecentError(
            news_id=int(nid),
            retry_count=int(rc or 0),
            last_error=le,
            last_error_at=lea,
        )
        for nid, rc, le, lea in recent_rows
    ]

    news_ai_enabled = str(os.getenv("NEWS_AI_ENABLED", "") or "").strip().lower() in {"1", "true", "yes", "on"}
    news_ai_interval_seconds = float(os.getenv("NEWS_AI_INTERVAL_SECONDS", "120").strip() or "120")

    provider_strategy = _env("NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY", "priority").strip() or "priority"
    response_format = _env("NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT", "").strip() or None

    return NewsAiStatusResponse(
        news_ai_enabled=bool(news_ai_enabled),
        news_ai_interval_seconds=float(news_ai_interval_seconds),
        summary_llm_enabled=bool(_bool("NEWS_AI_SUMMARY_LLM_ENABLED", False)),
        response_format=response_format,
        provider_strategy=str(provider_strategy),
        providers=providers,
        pending_total=int(pending_total),
        errors_total=int(errors_total),
        errors_last_24h=int(errors_last_24h),
        errors_last_7d=int(errors_last_7d),
        errors_trend_7d=errors_trend_7d,
        top_errors=top_errors,
        recent_errors=recent_errors,
        config_overrides={k: (_mask_config_value(k, v) or "") for k, v in cfg_overrides.items()},
    )


class AiOpsRecentError(BaseModel):
    at: str
    request_id: str
    endpoint: str
    error_code: str
    status_code: int | None
    message: str | None


class AiOpsTopErrorCode(BaseModel):
    error_code: str
    count: int


class AiOpsTopEndpoint(BaseModel):
    endpoint: str
    count: int


class AiOpsStatusResponse(BaseModel):
    ai_router_enabled: bool
    openai_api_key_configured: bool
    openai_base_url: str
    ai_model: str
    chroma_persist_dir: str
    started_at: float
    started_at_iso: str
    chat_requests_total: int
    chat_stream_requests_total: int
    errors_total: int
    recent_errors: list[AiOpsRecentError]
    top_error_codes: list[AiOpsTopErrorCode]
    top_endpoints: list[AiOpsTopEndpoint]


@router.get("/ai/status", response_model=AiOpsStatusResponse)
async def get_ai_ops_status(
    _current_user: Annotated[User, Depends(require_admin)],
):
    from ..config import get_settings
    from ..services.ai_metrics import ai_metrics

    settings = get_settings()

    ai_router_enabled = False
    try:
        from ..routers import ai as _ai_router

        _ = _ai_router
        ai_router_enabled = True
    except Exception:
        ai_router_enabled = False

    snap = ai_metrics.snapshot()

    recent_errors_obj = snap.get("recent_errors")
    recent_errors: list[AiOpsRecentError] = []
    if isinstance(recent_errors_obj, list):
        for row_obj in cast(list[object], recent_errors_obj):
            if not isinstance(row_obj, dict):
                continue
            row = cast(dict[str, object], row_obj)
            at = str(row.get("at") or "")
            request_id = str(row.get("request_id") or "")
            endpoint = str(row.get("endpoint") or "")
            error_code = str(row.get("error_code") or "")
            status_code_obj = row.get("status_code")

            status_code: int | None = None
            if isinstance(status_code_obj, int):
                status_code = int(status_code_obj)
            elif isinstance(status_code_obj, float):
                status_code = int(status_code_obj)
            elif isinstance(status_code_obj, str):
                s2 = status_code_obj.strip()
                if s2.isdigit():
                    status_code = int(s2)

            msg_obj = row.get("message")
            msg = str(msg_obj) if msg_obj is not None else None
            recent_errors.append(
                AiOpsRecentError(
                    at=at,
                    request_id=request_id,
                    endpoint=endpoint,
                    error_code=error_code,
                    status_code=status_code,
                    message=msg,
                )
            )

    top_error_codes_obj = snap.get("top_error_codes")
    top_error_codes: list[AiOpsTopErrorCode] = []
    if isinstance(top_error_codes_obj, list):
        for row_obj in cast(list[object], top_error_codes_obj):
            if not isinstance(row_obj, dict):
                continue
            row = cast(dict[str, object], row_obj)
            error_code = str(row.get("error_code") or "").strip()
            if not error_code:
                continue
            count_obj = row.get("count")
            count = 0
            if isinstance(count_obj, int):
                count = int(count_obj)
            elif isinstance(count_obj, float):
                count = int(count_obj)
            elif isinstance(count_obj, str):
                s3 = count_obj.strip()
                if s3.isdigit():
                    count = int(s3)
            top_error_codes.append(AiOpsTopErrorCode(error_code=error_code, count=int(count)))

    top_endpoints_obj = snap.get("top_endpoints")
    top_endpoints: list[AiOpsTopEndpoint] = []
    if isinstance(top_endpoints_obj, list):
        for row_obj in cast(list[object], top_endpoints_obj):
            if not isinstance(row_obj, dict):
                continue
            row = cast(dict[str, object], row_obj)
            endpoint = str(row.get("endpoint") or "").strip()
            if not endpoint:
                continue
            count_obj = row.get("count")
            count = 0
            if isinstance(count_obj, int):
                count = int(count_obj)
            elif isinstance(count_obj, float):
                count = int(count_obj)
            elif isinstance(count_obj, str):
                s4 = count_obj.strip()
                if s4.isdigit():
                    count = int(s4)
            top_endpoints.append(AiOpsTopEndpoint(endpoint=endpoint, count=int(count)))

    started_at_obj = snap.get("started_at")
    started_at = 0.0
    if isinstance(started_at_obj, (int, float)):
        started_at = float(started_at_obj)
    elif isinstance(started_at_obj, str):
        try:
            started_at = float(started_at_obj)
        except Exception:
            started_at = 0.0

    started_at_iso = str(snap.get("started_at_iso") or "")

    chat_requests_total_obj = snap.get("chat_requests_total")
    chat_requests_total = int(chat_requests_total_obj) if isinstance(chat_requests_total_obj, int) else 0

    chat_stream_requests_total_obj = snap.get("chat_stream_requests_total")
    chat_stream_requests_total = (
        int(chat_stream_requests_total_obj) if isinstance(chat_stream_requests_total_obj, int) else 0
    )

    errors_total_obj = snap.get("errors_total")
    errors_total = int(errors_total_obj) if isinstance(errors_total_obj, int) else 0

    return AiOpsStatusResponse(
        ai_router_enabled=bool(ai_router_enabled),
        openai_api_key_configured=bool(str(settings.openai_api_key or "").strip()),
        openai_base_url=str(settings.openai_base_url),
        ai_model=str(settings.ai_model),
        chroma_persist_dir=str(settings.chroma_persist_dir),
        started_at=started_at,
        started_at_iso=started_at_iso,
        chat_requests_total=chat_requests_total,
        chat_stream_requests_total=chat_stream_requests_total,
        errors_total=errors_total,
        recent_errors=recent_errors,
        top_error_codes=top_error_codes,
        top_endpoints=top_endpoints,
    )


@router.put("/configs/{key}")
async def update_config(
    key: str,
    data: ConfigItem,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    """更新配置项"""
    new_value = data.value
    if new_value is not None and (not str(new_value).strip()):
        new_value = None
    _validate_system_config_no_secrets(key, new_value)
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    config = result.scalar_one_or_none()
    
    if config:
        old_value = config.value
        config.value = new_value
        config.description = data.description or config.description
        config.updated_by = current_user.id
    else:
        config = SystemConfig(
            key=key,
            value=new_value,
            description=data.description,
            category=data.category,
            updated_by=current_user.id
        )
        db.add(config)
        old_value = None
    
    def _mask_value(key_name: str, value: str | None) -> str | None:
        if value is None:
            return None
        return _mask_config_value(key_name, value)

    masked_old = _mask_value(key, old_value)
    masked_new = _mask_value(key, new_value)

    # 记录日志
    await _log_action(
        db, current_user.id, LogAction.CONFIG, LogModule.SYSTEM,
        description=f"更新配置 {key}: {masked_old} -> {masked_new}",
        request=request
    )
    
    await db.commit()
    return {"message": "配置已更新", "key": key, "value": _mask_config_value(key, new_value)}


@router.post("/configs/batch")
async def batch_update_configs(
    data: ConfigBatchUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    """批量更新配置"""
    updated: list[str] = []
    for item in data.configs:
        new_value = item.value
        if new_value is not None and (not str(new_value).strip()):
            new_value = None
        _validate_system_config_no_secrets(item.key, new_value)
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == item.key)
        )
        config = result.scalar_one_or_none()
        
        if config:
            config.value = new_value
            config.updated_by = current_user.id
        else:
            config = SystemConfig(
                key=item.key,
                value=new_value,
                description=item.description,
                category=item.category,
                updated_by=current_user.id
            )
            db.add(config)
        updated.append(item.key)
    
    # 记录日志
    await _log_action(
        db, current_user.id, LogAction.CONFIG, LogModule.SYSTEM,
        description=f"批量更新配置: {', '.join(updated)}",
        request=request
    )
    
    await db.commit()
    return {"message": "配置已批量更新", "updated": updated}


# ============ 操作日志 ============

class LogResponse(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    action: str
    module: str
    target_id: int | None
    target_type: str | None
    description: str | None
    ip_address: str | None
    extra_data: dict[str, object] | None = None
    created_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class LogListResponse(BaseModel):
    items: list[LogResponse]
    total: int
    page: int
    page_size: int


@router.get("/logs", response_model=LogListResponse)
async def get_admin_logs(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    module: str | None = None,
    action: str | None = None,
    user_id: int | None = None,
):
    """获取操作日志列表"""
    query = select(AdminLog, User.nickname, User.username).outerjoin(User, User.id == AdminLog.user_id)
    
    if module:
        query = query.where(AdminLog.module == module)
    if action:
        query = query.where(AdminLog.action == action)
    if user_id:
        query = query.where(AdminLog.user_id == user_id)
    
    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 分页查询
    query = query.order_by(AdminLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = cast(list[tuple[AdminLog, str | None, str]], result.all())
    
    items: list[LogResponse] = []
    for log, nickname, username in rows:
        user_name: str | None = nickname or username
        parsed_extra: dict[str, object] | None = None
        if log.extra_data:
            try:
                value = cast(object, json.loads(log.extra_data))
                if isinstance(value, dict):
                    parsed_extra = cast(dict[str, object], value)
                else:
                    parsed_extra = {"value": value}
            except Exception:
                parsed_extra = {"raw": str(log.extra_data)}
        items.append(
            LogResponse(
                id=int(log.id),
                user_id=int(log.user_id),
                user_name=user_name,
                action=str(log.action),
                module=str(log.module),
                target_id=(int(log.target_id) if log.target_id is not None else None),
                target_type=log.target_type,
                description=log.description,
                ip_address=log.ip_address,
                extra_data=parsed_extra,
                created_at=log.created_at,
            )
        )
    
    return LogListResponse(items=items, total=total, page=page, page_size=page_size)


# ============ 辅助函数 ============

async def _log_action(
    db: AsyncSession,
    user_id: int,
    action: str,
    module: str,
    target_id: int | None = None,
    target_type: str | None = None,
    description: str | None = None,
    extra_data: dict[str, object] | None = None,
    request: Request | None = None,
):
    """记录操作日志"""
    ip_address = None
    user_agent = None
    
    if request:
        ip_address = get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")[:500]
    
    log = AdminLog(
        user_id=user_id,
        action=action,
        module=module,
        target_id=target_id,
        target_type=target_type,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        extra_data=json.dumps(extra_data, ensure_ascii=False) if extra_data else None
    )
    db.add(log)


# 导出日志函数供其他模块使用
async def log_admin_action(
    db: AsyncSession,
    user_id: int,
    action: str,
    module: str,
    target_id: int | None = None,
    description: str | None = None,
    request: Request | None = None,
):
    """供其他模块调用的日志记录函数"""
    await _log_action(db, user_id, action, module, target_id, None, description, None, request)


# ============ 数据统计 ============

from ..models.news import News
from ..models.forum import Post, Comment
from ..models.lawfirm import LawFirm, Lawyer
from ..models.consultation import Consultation, ChatMessage


class StatsOverview(BaseModel):
    """统计概览"""
    total_users: int = 0
    active_users_today: int = 0
    total_consultations: int = 0
    consultations_today: int = 0
    total_posts: int = 0
    posts_today: int = 0
    total_news: int = 0
    total_lawfirms: int = 0
    total_lawyers: int = 0


class DailyStats(BaseModel):
    """每日统计"""
    date: str
    users: int = 0
    consultations: int = 0
    posts: int = 0
    messages: int = 0


@router.get("/stats/overview", response_model=StatsOverview)
async def get_stats_overview(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取统计概览"""
    from datetime import date
    today = date.today()
    
    # 用户统计
    total_users = await db.scalar(select(func.count()).select_from(User))
    active_today = await db.scalar(
        select(func.count()).select_from(User).where(
            func.date(User.updated_at) == today
        )
    )
    
    # 咨询统计
    total_consultations = await db.scalar(select(func.count()).select_from(Consultation))
    consultations_today = await db.scalar(
        select(func.count()).select_from(Consultation).where(
            func.date(Consultation.created_at) == today
        )
    )
    
    # 帖子统计
    total_posts = await db.scalar(select(func.count()).select_from(Post))
    posts_today = await db.scalar(
        select(func.count()).select_from(Post).where(
            func.date(Post.created_at) == today
        )
    )
    
    # 其他统计
    total_news = await db.scalar(select(func.count()).select_from(News))
    total_lawfirms = await db.scalar(select(func.count()).select_from(LawFirm))
    total_lawyers = await db.scalar(select(func.count()).select_from(Lawyer))
    
    return StatsOverview(
        total_users=total_users or 0,
        active_users_today=active_today or 0,
        total_consultations=total_consultations or 0,
        consultations_today=consultations_today or 0,
        total_posts=total_posts or 0,
        posts_today=posts_today or 0,
        total_news=total_news or 0,
        total_lawfirms=total_lawfirms or 0,
        total_lawyers=total_lawyers or 0
    )


@router.get("/stats/daily", response_model=list[DailyStats])
async def get_daily_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=30)] = 7,
):
    """获取每日统计（最近N天）"""
    from datetime import date, timedelta
    
    results: list[DailyStats] = []
    today = date.today()
    
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        
        users = await db.scalar(
            select(func.count()).select_from(User).where(
                func.date(User.created_at) == day
            )
        )
        
        consultations = await db.scalar(
            select(func.count()).select_from(Consultation).where(
                func.date(Consultation.created_at) == day
            )
        )
        
        posts = await db.scalar(
            select(func.count()).select_from(Post).where(
                func.date(Post.created_at) == day
            )
        )
        
        messages = await db.scalar(
            select(func.count()).select_from(ChatMessage).where(
                func.date(ChatMessage.created_at) == day
            )
        )
        
        results.append(DailyStats(
            date=day.isoformat(),
            users=users or 0,
            consultations=consultations or 0,
            posts=posts or 0,
            messages=messages or 0
        ))
    
    return results


@router.get("/stats/ai-feedback")
async def get_ai_feedback_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取AI反馈统计"""
    total_rated = await db.scalar(
        select(func.count()).select_from(ChatMessage).where(
            ChatMessage.rating.isnot(None)
        )
    )
    
    good_count = await db.scalar(
        select(func.count()).select_from(ChatMessage).where(
            ChatMessage.rating == 3
        )
    )
    
    neutral_count = await db.scalar(
        select(func.count()).select_from(ChatMessage).where(
            ChatMessage.rating == 2
        )
    )
    
    bad_count = await db.scalar(
        select(func.count()).select_from(ChatMessage).where(
            ChatMessage.rating == 1
        )
    )
    
    return {
        "total_rated": total_rated or 0,
        "good": good_count or 0,
        "neutral": neutral_count or 0,
        "bad": bad_count or 0,
        "satisfaction_rate": round((good_count or 0) / (total_rated or 1) * 100, 1)
    }


# ============ 数据统计大屏 ============

from ..models.knowledge import LegalKnowledge


@router.get("/dashboard/overview", summary="仪表板概览数据")
async def get_dashboard_overview(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取仪表板概览统计数据"""
    from datetime import timedelta
    today = datetime.now().date()
    _yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    _month_ago = today - timedelta(days=30)
    
    # 用户统计
    total_users = await db.scalar(select(func.count()).select_from(User)) or 0
    new_users_today = await db.scalar(
        select(func.count()).select_from(User).where(func.date(User.created_at) == today)
    ) or 0
    new_users_week = await db.scalar(
        select(func.count()).select_from(User).where(func.date(User.created_at) >= week_ago)
    ) or 0
    active_users_week = await db.scalar(
        select(func.count(func.distinct(Consultation.user_id))).where(
            func.date(Consultation.created_at) >= week_ago
        )
    ) or 0
    
    # 内容统计
    total_posts = await db.scalar(select(func.count()).select_from(Post).where(Post.is_deleted == False)) or 0
    total_comments = await db.scalar(select(func.count()).select_from(Comment).where(Comment.is_deleted == False)) or 0
    total_news = await db.scalar(select(func.count()).select_from(News).where(News.is_published == True)) or 0
    
    # 咨询统计
    total_consultations = await db.scalar(select(func.count()).select_from(Consultation)) or 0
    consultations_today = await db.scalar(
        select(func.count()).select_from(Consultation).where(func.date(Consultation.created_at) == today)
    ) or 0
    total_messages = await db.scalar(select(func.count()).select_from(ChatMessage)) or 0
    
    # 律所统计
    total_lawfirms = await db.scalar(select(func.count()).select_from(LawFirm).where(LawFirm.is_active == True)) or 0
    total_lawyers = await db.scalar(select(func.count()).select_from(Lawyer).where(Lawyer.is_active == True)) or 0
    verified_lawyers = await db.scalar(select(func.count()).select_from(Lawyer).where(Lawyer.is_verified == True)) or 0
    
    # 知识库统计
    total_knowledge = await db.scalar(select(func.count()).select_from(LegalKnowledge).where(LegalKnowledge.is_active == True)) or 0
    vectorized_count = await db.scalar(select(func.count()).select_from(LegalKnowledge).where(LegalKnowledge.is_vectorized == True)) or 0
    
    return {
        "users": {
            "total": total_users,
            "new_today": new_users_today,
            "new_week": new_users_week,
            "active_week": active_users_week,
        },
        "content": {
            "posts": total_posts,
            "comments": total_comments,
            "news": total_news,
        },
        "consultations": {
            "total": total_consultations,
            "today": consultations_today,
            "messages": total_messages,
        },
        "lawfirms": {
            "firms": total_lawfirms,
            "lawyers": total_lawyers,
            "verified": verified_lawyers,
        },
        "knowledge": {
            "total": total_knowledge,
            "vectorized": vectorized_count,
            "vectorize_rate": round(vectorized_count / max(total_knowledge, 1) * 100, 1),
        }
    }


@router.get("/dashboard/trends", summary="趋势数据")
async def get_dashboard_trends(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=7, le=90, description="统计天数")] = 30,
):
    """获取近N天的趋势数据"""
    from datetime import timedelta
    today = datetime.now().date()
    
    trends: list[dict[str, object]] = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        
        users = await db.scalar(
            select(func.count()).select_from(User).where(func.date(User.created_at) == day)
        ) or 0
        
        consultations = await db.scalar(
            select(func.count()).select_from(Consultation).where(func.date(Consultation.created_at) == day)
        ) or 0
        
        posts = await db.scalar(
            select(func.count()).select_from(Post).where(func.date(Post.created_at) == day)
        ) or 0
        
        trends.append({
            "date": day.isoformat(),
            "users": users,
            "consultations": consultations,
            "posts": posts,
        })
    
    return {"trends": trends, "days": days}


@router.get("/dashboard/category-stats", summary="分类统计")
async def get_category_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取各类别统计数据"""
    # 帖子分类统计
    post_categories = await db.execute(
        select(Post.category, func.count(Post.id).label('count'))
        .where(Post.is_deleted == False, Post.category.isnot(None))
        .group_by(Post.category)
        .order_by(func.count(Post.id).desc())
        .limit(10)
    )
    post_cat_data: list[dict[str, object]] = [
        {"name": str(r[0] or ""), "value": int(r[1] or 0)} for r in post_categories.all()
    ]
    
    # 新闻分类统计
    news_categories = await db.execute(
        select(News.category, func.count(News.id).label('count'))
        .where(News.is_published == True, News.category.isnot(None))
        .group_by(News.category)
        .order_by(func.count(News.id).desc())
        .limit(10)
    )
    news_cat_data: list[dict[str, object]] = [
        {"name": str(r[0] or ""), "value": int(r[1] or 0)} for r in news_categories.all()
    ]
    
    # 知识库分类统计
    knowledge_categories = await db.execute(
        select(LegalKnowledge.category, func.count(LegalKnowledge.id).label('count'))
        .where(LegalKnowledge.is_active == True)
        .group_by(LegalKnowledge.category)
        .order_by(func.count(LegalKnowledge.id).desc())
        .limit(10)
    )
    knowledge_cat_data: list[dict[str, object]] = [
        {"name": str(r[0] or ""), "value": int(r[1] or 0)} for r in knowledge_categories.all()
    ]
    
    # 律所城市分布
    firm_cities = await db.execute(
        select(LawFirm.city, func.count(LawFirm.id).label('count'))
        .where(LawFirm.is_active == True, LawFirm.city.isnot(None))
        .group_by(LawFirm.city)
        .order_by(func.count(LawFirm.id).desc())
        .limit(10)
    )
    city_data: list[dict[str, object]] = [
        {"name": str(r[0] or ""), "value": int(r[1] or 0)} for r in firm_cities.all()
    ]
    
    return {
        "post_categories": post_cat_data,
        "news_categories": news_cat_data,
        "knowledge_categories": knowledge_cat_data,
        "firm_cities": city_data,
    }


@router.get("/dashboard/news-stats", summary="新闻统计")
async def get_dashboard_news_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=90)] = 7,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
):
    from datetime import timedelta

    today = datetime.now().date()

    total = await db.scalar(select(func.count()).select_from(News)) or 0
    published = await db.scalar(
        select(func.count()).select_from(News).where(News.is_published == True)
    ) or 0
    drafts = await db.scalar(
        select(func.count()).select_from(News).where(News.is_published == False)
    ) or 0

    trends: list[dict[str, object]] = []
    for i in range(int(days) - 1, -1, -1):
        day = today - timedelta(days=i)
        published_day = await db.scalar(
            select(func.count()).select_from(News).where(
                and_(
                    News.is_published == True,
                    func.date(func.coalesce(News.published_at, News.created_at)) == day,
                )
            )
        ) or 0
        trends.append({"date": day.isoformat(), "published": int(published_day)})

    cat_rows = await db.execute(
        select(News.category, func.count(News.id).label("count"))
        .where(News.is_published == True, News.category.isnot(None))
        .group_by(News.category)
        .order_by(func.count(News.id).desc())
        .limit(10)
    )
    categories: list[dict[str, object]] = [
        {"name": str(r[0] or ""), "value": int(r[1] or 0)} for r in cat_rows.all()
    ]

    hot_rows = await db.execute(
        select(News.id, News.title, News.category, News.view_count)
        .where(News.is_published == True)
        .order_by(desc(func.coalesce(News.view_count, 0)), desc(News.published_at), desc(News.created_at))
        .limit(limit)
    )
    hot_items = cast(list[tuple[int, str | None, str | None, int | None]], hot_rows.all())
    hot: list[dict[str, object]] = [
        {
            "id": int(r_id),
            "title": str(r_title or ""),
            "category": str(r_cat or ""),
            "views": int(r_views or 0),
        }
        for r_id, r_title, r_cat, r_views in hot_items
    ]

    return {
        "total": int(total),
        "published": int(published),
        "drafts": int(drafts),
        "days": int(days),
        "trends": trends,
        "categories": categories,
        "hot": hot,
    }


@router.get("/dashboard/realtime", summary="实时数据")
async def get_realtime_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取实时统计数据（最近1小时）"""
    from datetime import timedelta
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)
    
    # 最近1小时活跃数据
    new_users = await db.scalar(
        select(func.count()).select_from(User).where(User.created_at >= hour_ago)
    ) or 0
    
    new_consultations = await db.scalar(
        select(func.count()).select_from(Consultation).where(Consultation.created_at >= hour_ago)
    ) or 0
    
    new_messages = await db.scalar(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.created_at >= hour_ago)
    ) or 0
    
    new_posts = await db.scalar(
        select(func.count()).select_from(Post).where(Post.created_at >= hour_ago)
    ) or 0
    
    new_comments = await db.scalar(
        select(func.count()).select_from(Comment).where(Comment.created_at >= hour_ago)
    ) or 0
    
    # 最近活动
    recent_consultations = await db.execute(
        select(Consultation.id, Consultation.title, User.username, Consultation.created_at)
        .join(User, Consultation.user_id == User.id)
        .order_by(Consultation.created_at.desc())
        .limit(5)
    )
    recent_rows = cast(list[tuple[int, str | None, str | None, datetime]], recent_consultations.all())
    recent_list: list[dict[str, object]] = [
        {
            "id": int(r_id),
            "title": str(r_title or "AI法律咨询"),
            "user": str(r_user or ""),
            "time": r_created_at.isoformat(),
        }
        for r_id, r_title, r_user, r_created_at in recent_rows
    ]
    
    return {
        "hour_stats": {
            "users": new_users,
            "consultations": new_consultations,
            "messages": new_messages,
            "posts": new_posts,
            "comments": new_comments,
        },
        "recent_consultations": recent_list,
        "timestamp": now.isoformat(),
    }


@router.get("/dashboard/hot-content", summary="热门内容")
async def get_hot_content(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
):
    """获取热门内容（帖子 counting by view_count，新闻 counting by view_count）"""
    _ = _current_user

    post_rows = await db.execute(
        select(Post.id, Post.title, Post.view_count)
        .where(Post.is_deleted == False)
        .order_by(desc(func.coalesce(Post.view_count, 0)), desc(Post.created_at))
        .limit(limit)
    )
    post_items = cast(list[tuple[int, str | None, int | None]], post_rows.all())
    posts: list[dict[str, object]] = [
        {"type": "post", "id": int(r_id), "title": str(r_title or ""), "views": int(r_views or 0)}
        for r_id, r_title, r_views in post_items
    ]

    news_rows = await db.execute(
        select(News.id, News.title, News.view_count)
        .where(News.is_published == True)
        .order_by(desc(func.coalesce(News.view_count, 0)), desc(News.published_at), desc(News.created_at))
        .limit(limit)
    )
    news_items = cast(list[tuple[int, str | None, int | None]], news_rows.all())
    news: list[dict[str, object]] = [
        {"type": "news", "id": int(r_id), "title": str(r_title or ""), "views": int(r_views or 0)}
        for r_id, r_title, r_views in news_items
    ]

    items = sorted(posts + news, key=lambda x: cast(int, x.get("views", 0)), reverse=True)
    return {"items": items[:limit]}


# ============ 用户行为分析 ============

from ..models.system import UserActivity


class ActivityCreate(BaseModel):
    action: str  # page_view, click, search, etc.
    page: str | None = None
    target: str | None = None
    target_id: int | None = None
    referrer: str | None = None
    duration: int | None = None
    extra_data: str | None = None


@router.post("/analytics/track", summary="记录用户行为")
@rate_limit(*RateLimitConfig.ANALYTICS_TRACK, by_ip=True, by_user=False)
async def track_activity(
    data: ActivityCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
):
    """记录用户行为数据（前端调用）"""
    user_agent = request.headers.get("user-agent", "")
    
    # 解析设备类型
    device_type = "desktop"
    ua_lower = user_agent.lower()
    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        device_type = "mobile"
    elif "tablet" in ua_lower or "ipad" in ua_lower:
        device_type = "tablet"
    
    activity = UserActivity(
        user_id=current_user.id if current_user else None,
        session_id=(request.cookies.get("session_id") or "")[:200] or None,
        action=data.action,
        page=(data.page[:500] if data.page else None),
        target=(data.target[:500] if data.target else None),
        target_id=data.target_id,
        referrer=(data.referrer[:500] if data.referrer else None),
        user_agent=user_agent[:500] if user_agent else None,
        ip_address=get_client_ip(request),
        device_type=device_type,
        extra_data=(data.extra_data[:2000] if data.extra_data else None),
        duration=data.duration,
    )
    db.add(activity)
    await db.commit()
    
    return {"status": "ok"}


@router.get("/analytics/page-stats", summary="页面访问统计")
async def get_page_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=30)] = 7,
):
    """获取页面访问统计"""
    from datetime import timedelta
    start_date = datetime.now() - timedelta(days=days)
    
    # 按页面统计访问量
    page_stats = await db.execute(
        select(
            UserActivity.page,
            func.count(UserActivity.id).label('views'),
            func.count(func.distinct(UserActivity.user_id)).label('unique_users'),
            func.avg(UserActivity.duration).label('avg_duration')
        )
        .where(
            UserActivity.action == "page_view",
            UserActivity.created_at >= start_date,
            UserActivity.page.isnot(None)
        )
        .group_by(UserActivity.page)
        .order_by(func.count(UserActivity.id).desc())
        .limit(20)
    )
    
    pages: list[dict[str, object]] = []
    for row in page_stats.all():
        pages.append({
            "page": str(row[0] or ""),
            "views": int(row[1] or 0),
            "unique_users": int(row[2] or 0),
            "avg_duration": round(float(row[3] or 0), 1),
        })
    
    return {"pages": pages, "days": days}


@router.get("/analytics/user-behavior", summary="用户行为分析")
async def get_user_behavior(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=30)] = 7,
):
    """获取用户行为分析数据"""
    from datetime import timedelta
    start_date = datetime.now() - timedelta(days=days)
    
    # 按行为类型统计
    action_stats = await db.execute(
        select(
            UserActivity.action,
            func.count(UserActivity.id).label('count')
        )
        .where(UserActivity.created_at >= start_date)
        .group_by(UserActivity.action)
        .order_by(func.count(UserActivity.id).desc())
    )
    actions: list[dict[str, object]] = [
        {"action": str(r[0] or ""), "count": int(r[1] or 0)} for r in action_stats.all()
    ]
    
    # 按设备类型统计
    device_stats = await db.execute(
        select(
            UserActivity.device_type,
            func.count(UserActivity.id).label('count')
        )
        .where(
            UserActivity.created_at >= start_date,
            UserActivity.device_type.isnot(None)
        )
        .group_by(UserActivity.device_type)
    )
    devices: list[dict[str, object]] = [
        {"device": str(r[0] or ""), "count": int(r[1] or 0)} for r in device_stats.all()
    ]
    
    # 按小时统计活跃度
    hourly_stats = await db.execute(
        select(
            func.extract('hour', UserActivity.created_at).label('hour'),
            func.count(UserActivity.id).label('count')
        )
        .where(UserActivity.created_at >= start_date)
        .group_by(func.extract('hour', UserActivity.created_at))
        .order_by(func.extract('hour', UserActivity.created_at))
    )
    hourly: list[dict[str, object]] = [
        {"hour": int(cast(int | float, r[0] or 0)), "count": int(r[1] or 0)} for r in hourly_stats.all()
    ]
    
    return {
        "actions": actions,
        "devices": devices,
        "hourly_activity": hourly,
        "days": days,
    }


@router.get("/analytics/user-journey", summary="用户路径分析")
async def get_user_journey(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=10, le=500)] = 100,
):
    """获取用户访问路径（最近N条记录）"""
    result = await db.execute(
        select(
            UserActivity.page,
            UserActivity.referrer,
            func.count(UserActivity.id).label('count')
        )
        .where(
            UserActivity.action == "page_view",
            UserActivity.page.isnot(None)
        )
        .group_by(UserActivity.page, UserActivity.referrer)
        .order_by(func.count(UserActivity.id).desc())
        .limit(limit)
    )
    
    journeys: list[dict[str, object]] = []
    for row in result.all():
        journeys.append({
            "from": str(row[1] or "直接访问"),
            "to": str(row[0] or ""),
            "count": int(row[2] or 0),
        })
    
    return {"journeys": journeys}


@router.get("/analytics/retention", summary="用户留存分析")
async def get_retention_stats(
    _current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取用户留存率数据"""
    from datetime import timedelta
    today = datetime.now().date()
    
    retention_data: list[dict[str, object]] = []
    for i in range(7):  # 近7天
        day = today - timedelta(days=i)
        next_day = day + timedelta(days=1)
        
        # 当天新注册用户
        new_users = await db.scalar(
            select(func.count(func.distinct(User.id)))
            .where(func.date(User.created_at) == day)
        ) or 0
        
        # 次日活跃用户(在次日有行为记录的新用户)
        if i > 0:  # 最后一天没有次日数据
            retained = await db.scalar(
                select(func.count(func.distinct(UserActivity.user_id)))
                .where(
                    UserActivity.user_id.in_(
                        select(User.id).where(func.date(User.created_at) == day)
                    ),
                    func.date(UserActivity.created_at) == next_day
                )
            ) or 0
        else:
            retained = 0
        
        retention_data.append({
            "date": day.isoformat(),
            "new_users": new_users,
            "retained": retained,
            "retention_rate": round(retained / max(new_users, 1) * 100, 1),
        })
    
    return {"retention": retention_data}


