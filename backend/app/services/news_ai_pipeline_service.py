import base64
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime
from typing import Literal, TypedDict, cast

import httpx
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..services.critical_event_reporter import critical_event_reporter
from ..models.news import News
from ..models.news_ai import NewsAIAnnotation
from ..utils.content_filter import content_filter
from ..utils.pii import sanitize_pii


logger = logging.getLogger(__name__)


def _current_env_token() -> str | None:
    raw = str(os.getenv("APP_ENV") or os.getenv("ENV") or os.getenv("ENVIRONMENT") or "").strip()
    if not raw:
        return None
    v = raw.strip().lower()
    if v in {"prod", "production"}:
        return "PROD"
    if v in {"stag", "staging"}:
        return "STAGING"
    if v in {"dev", "development"}:
        return "DEV"
    if v in {"test", "testing"}:
        return "TEST"
    v2 = re.sub(r"[^a-z0-9]+", "_", v).strip("_")
    return v2.upper() if v2 else None


class _NewsSummaryLLMProvider(TypedDict, total=False):
    name: str
    base_url: str
    api_key: str
    model: str
    response_format: str
    auth_type: Literal["bearer", "header"]
    auth_header_name: str
    auth_prefix: str
    chat_completions_path: str
    weight: int
    priority: int


def _truncate(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    if len(v) <= int(max_len):
        return v
    return v[: int(max_len)]


def _normalize_title(title: str) -> str:
    t = str(title or "").strip().lower()
    t = " ".join(t.split())
    return t


def _fingerprint(news: News) -> str:
    base = f"{_normalize_title(news.title)}|{str(getattr(news, 'source_site', '') or '').strip().lower()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _risk_from_filter(passed: bool, reason: str) -> str:
    r = str(reason or "").strip()
    if passed:
        return "safe"
    if r == "内容疑似广告":
        return "warning"
    if r == "内容包含敏感词汇":
        return "danger"
    return "warning"


class NewsAIPipelineService:
    def __init__(self) -> None:
        self._rr_cursor: int = 0

    @staticmethod
    async def load_system_config_overrides(db: AsyncSession) -> dict[str, str]:
        from ..models.system import SystemConfig

        base_keys = {
            "NEWS_AI_SUMMARY_LLM_ENABLED",
            "NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT",
            "NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY",
            "NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON",
            "NEWS_AI_SUMMARY_LLM_PROVIDERS_B64",
            "NEWS_REVIEW_POLICY_ENABLED",
            "NEWS_REVIEW_POLICY_JSON",
        }

        env_token = _current_env_token()
        keys = set(base_keys)
        if env_token:
            for k in base_keys:
                keys.add(f"{k}_{env_token}")

        res = await db.execute(select(SystemConfig.key, SystemConfig.value).where(SystemConfig.key.in_(keys)))
        rows = cast(list[tuple[object, object]], list(res.all()))
        raw: dict[str, str] = {}
        for k_obj, v_obj in rows:
            key = str(k_obj or "").strip()
            if not key:
                continue
            if v_obj is None:
                continue
            val = str(v_obj).strip()
            if not val:
                continue
            raw[key] = val

        out: dict[str, str] = {}
        for k in base_keys:
            if env_token:
                k_env = f"{k}_{env_token}"
                if k_env in raw:
                    out[k] = raw[k_env]
                    continue
            if k in raw:
                out[k] = raw[k]
        return out

    @staticmethod
    def _make_local_highlights_keywords(
        *,
        title: str,
        content: str,
        highlights_max: int,
        keywords_max: int,
        item_max_chars: int,
    ) -> tuple[list[str], list[str]]:
        text = f"{str(title or '').strip()}\n{str(content or '').strip()}".strip()
        if not text:
            return [], []

        parts = [p.strip() for p in re.split(r"[。！？.!?]+", text) if p.strip()]
        highlights: list[str] = []
        for p in parts:
            if len(highlights) >= int(highlights_max):
                break
            s = _truncate(p, int(item_max_chars)) or ""
            if s:
                highlights.append(s)

        candidates = cast(
            list[str],
            re.findall(r"[\u4e00-\u9fff]{2,6}|[A-Za-z0-9]{3,20}", text),
        )
        seen: set[str] = set()
        keywords: list[str] = []
        for c in candidates:
            if len(keywords) >= int(keywords_max):
                break
            s = _truncate(str(c or "").strip(), int(item_max_chars)) or ""
            if (not s) or (s in seen):
                continue
            seen.add(s)
            keywords.append(s)

        return highlights, keywords

    async def run_once(self, db: AsyncSession) -> dict[str, int]:
        batch_size = int(os.getenv("NEWS_AI_BATCH_SIZE", "50").strip() or "50")

        started = time.perf_counter()

        cfg_overrides = await self.load_system_config_overrides(db)

        review_policy_enabled_raw = cfg_overrides.get("NEWS_REVIEW_POLICY_ENABLED")
        if review_policy_enabled_raw is None or (not str(review_policy_enabled_raw).strip()):
            review_policy_enabled_raw = os.getenv("NEWS_REVIEW_POLICY_ENABLED")
        review_policy_enabled = False
        if review_policy_enabled_raw is not None and str(review_policy_enabled_raw).strip():
            review_policy_enabled = str(review_policy_enabled_raw).strip().lower() in {"1", "true", "yes", "y", "on"}

        review_policy_json = cfg_overrides.get("NEWS_REVIEW_POLICY_JSON")
        if review_policy_json is None or (not str(review_policy_json).strip()):
            review_policy_json = os.getenv("NEWS_REVIEW_POLICY_JSON")

        review_policy_map: dict[str, str] = {
            "safe": "approved",
            "warning": "pending",
            "danger": "pending",
            "unknown": "pending",
        }
        if review_policy_json is not None and str(review_policy_json).strip():
            try:
                parsed_policy_obj: object = cast(object, json.loads(str(review_policy_json)))
                if isinstance(parsed_policy_obj, dict):
                    parsed_policy = cast(dict[object, object], parsed_policy_obj)
                    for k_obj, v_obj in parsed_policy.items():
                        k = str(k_obj or "").strip().lower()
                        v = str(v_obj or "").strip().lower()
                        if not k:
                            continue
                        if v not in {"approved", "pending", "rejected"}:
                            continue
                        review_policy_map[k] = v
            except Exception:
                logger.exception("invalid NEWS_REVIEW_POLICY_JSON")

        where_clause = or_(
            NewsAIAnnotation.id.is_(None),
            NewsAIAnnotation.processed_at.is_(None),
            NewsAIAnnotation.highlights.is_(None),
            NewsAIAnnotation.keywords.is_(None),
        )

        q = (
            select(News)
            .outerjoin(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id)
            .where(where_clause)
            .order_by(News.created_at.asc(), News.id.asc())
            .limit(max(1, batch_size))
        )

        pending_total_res = await db.execute(
            select(func.count(News.id))
            .select_from(News)
            .outerjoin(NewsAIAnnotation, NewsAIAnnotation.news_id == News.id)
            .where(where_clause)
        )
        pending_total = int(pending_total_res.scalar() or 0)

        res = await db.execute(q)
        items = list(res.scalars().all())
        if not items:
            return {"processed": 0, "created": 0, "updated": 0, "errors": 0}

        processed = 0
        created = 0
        updated = 0
        errors = 0
        now = datetime.now()

        error_max_chars = int(os.getenv("NEWS_AI_LAST_ERROR_MAX_CHARS", "800").strip() or "800")

        for news in items:
            news_id = int(getattr(news, "id", 0) or 0)
            ann: NewsAIAnnotation | None = None
            try:
                ann = await self._get_or_create_annotation(db, news, news_id=news_id)
                is_new = ann.processed_at is None and (ann.summary is None) and (ann.risk_level in {"unknown", ""})

                summary, summary_is_llm, highlights, keywords = await self._make_summary(news, env_overrides=cfg_overrides)
                risk_level, sensitive_words = self._make_risk(news)
                duplicate_of = await self._find_duplicate_of(db, news)

                if review_policy_enabled:
                    current_review_status = str(getattr(news, "review_status", "") or "").strip().lower() or "approved"
                    if current_review_status == "pending":
                        target_review_status = review_policy_map.get(str(risk_level or "").strip().lower(), "pending")
                        if target_review_status != current_review_status:
                            news.review_status = target_review_status
                            if target_review_status == "rejected":
                                news.review_reason = _truncate(f"auto_review:risk={str(risk_level)}", 200)
                            else:
                                news.review_reason = None
                            news.reviewed_at = now

                ann.summary = summary
                ann.risk_level = risk_level
                ann.sensitive_words = sensitive_words
                ann.highlights = json.dumps(highlights, ensure_ascii=False) if highlights else None
                ann.keywords = json.dumps(keywords, ensure_ascii=False) if keywords else None
                ann.duplicate_of_news_id = duplicate_of
                ann.processed_at = now

                ann.retry_count = 0
                ann.last_error = None
                ann.last_error_at = None

                if summary_is_llm and self._bool_env("NEWS_AI_SUMMARY_WRITEBACK_ENABLED", False):
                    existing = str(getattr(news, "summary", None) or "").strip()
                    if (not existing) and summary:
                        news.summary = summary

                await db.commit()
                processed += 1
                if is_new:
                    created += 1
                else:
                    updated += 1
            except Exception:
                errors += 1
                await db.rollback()
                logger.exception("news_ai_pipeline failed news_id=%s", int(news_id))

                try:
                    if ann is None:
                        ann = await self._get_or_create_annotation(db, news, news_id=news_id)

                    ann.retry_count = int(getattr(ann, "retry_count", 0) or 0) + 1
                    exc = sys.exc_info()[1]
                    ann.last_error = _truncate(str(exc or ""), error_max_chars)
                    ann.last_error_at = datetime.now()
                    await db.commit()
                except Exception:
                    await db.rollback()
                    logger.exception(
                        "news_ai_pipeline persist_error failed news_id=%s",
                        int(news_id),
                    )

        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "news_ai_pipeline done processed=%s created=%s updated=%s errors=%s duration_ms=%s batch_size=%s pending_total=%s",
            processed,
            created,
            updated,
            errors,
            duration_ms,
            int(batch_size),
            int(pending_total),
        )
        if int(errors) > 0:
            critical_event_reporter.fire_and_forget(
                event="news_ai_pipeline_errors",
                severity="warning",
                request_id=None,
                title="News AI pipeline errors",
                message=f"errors={int(errors)} processed={int(processed)} batch_size={int(batch_size)}",
                data={
                    "processed": int(processed),
                    "created": int(created),
                    "updated": int(updated),
                    "errors": int(errors),
                    "duration_ms": int(duration_ms),
                    "batch_size": int(batch_size),
                    "pending_total": int(pending_total),
                },
                dedup_key="news_ai_pipeline_errors",
            )
        return {"processed": processed, "created": created, "updated": updated, "errors": errors}

    async def rerun_news(self, db: AsyncSession, news_id: int) -> None:
        cfg_overrides = await self.load_system_config_overrides(db)

        review_policy_enabled_raw = cfg_overrides.get("NEWS_REVIEW_POLICY_ENABLED")
        if review_policy_enabled_raw is None or (not str(review_policy_enabled_raw).strip()):
            review_policy_enabled_raw = os.getenv("NEWS_REVIEW_POLICY_ENABLED")
        review_policy_enabled = False
        if review_policy_enabled_raw is not None and str(review_policy_enabled_raw).strip():
            review_policy_enabled = str(review_policy_enabled_raw).strip().lower() in {"1", "true", "yes", "y", "on"}

        review_policy_json = cfg_overrides.get("NEWS_REVIEW_POLICY_JSON")
        if review_policy_json is None or (not str(review_policy_json).strip()):
            review_policy_json = os.getenv("NEWS_REVIEW_POLICY_JSON")

        review_policy_map: dict[str, str] = {
            "safe": "approved",
            "warning": "pending",
            "danger": "pending",
            "unknown": "pending",
        }
        if review_policy_json is not None and str(review_policy_json).strip():
            try:
                parsed_policy_obj: object = cast(object, json.loads(str(review_policy_json)))
                if isinstance(parsed_policy_obj, dict):
                    parsed_policy = cast(dict[object, object], parsed_policy_obj)
                    for k_obj, v_obj in parsed_policy.items():
                        k = str(k_obj or "").strip().lower()
                        v = str(v_obj or "").strip().lower()
                        if not k:
                            continue
                        if v not in {"approved", "pending", "rejected"}:
                            continue
                        review_policy_map[k] = v
            except Exception:
                logger.exception("invalid NEWS_REVIEW_POLICY_JSON")

        res = await db.execute(select(News).where(News.id == int(news_id)))
        news = res.scalar_one_or_none()
        if news is None:
            raise ValueError("news not found")

        ann: NewsAIAnnotation | None = None
        now = datetime.now()
        error_max_chars = int(os.getenv("NEWS_AI_LAST_ERROR_MAX_CHARS", "800").strip() or "800")
        try:
            ann = await self._get_or_create_annotation(db, news, news_id=int(news_id))

            summary, summary_is_llm, highlights, keywords = await self._make_summary(
                news,
                env_overrides=cfg_overrides,
                force_generate=True,
            )
            risk_level, sensitive_words = self._make_risk(news)
            duplicate_of = await self._find_duplicate_of(db, news)

            if review_policy_enabled:
                current_review_status = str(getattr(news, "review_status", "") or "").strip().lower() or "approved"
                if current_review_status == "pending":
                    target_review_status = review_policy_map.get(str(risk_level or "").strip().lower(), "pending")
                    if target_review_status != current_review_status:
                        news.review_status = target_review_status
                        if target_review_status == "rejected":
                            news.review_reason = _truncate(f"auto_review:risk={str(risk_level)}", 200)
                        else:
                            news.review_reason = None
                        news.reviewed_at = now

            ann.summary = summary
            ann.risk_level = risk_level
            ann.sensitive_words = sensitive_words
            ann.highlights = json.dumps(highlights, ensure_ascii=False) if highlights else None
            ann.keywords = json.dumps(keywords, ensure_ascii=False) if keywords else None
            ann.duplicate_of_news_id = duplicate_of
            ann.processed_at = now

            ann.retry_count = 0
            ann.last_error = None
            ann.last_error_at = None

            if summary_is_llm and self._bool_env("NEWS_AI_SUMMARY_WRITEBACK_ENABLED", False):
                existing = str(getattr(news, "summary", None) or "").strip()
                if (not existing) and summary:
                    news.summary = summary

            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("news_ai_rerun failed news_id=%s", int(news_id))
            try:
                if ann is None:
                    ann = await self._get_or_create_annotation(db, news, news_id=int(news_id))
                ann.retry_count = int(getattr(ann, "retry_count", 0) or 0) + 1
                exc = sys.exc_info()[1]
                ann.last_error = _truncate(str(exc or ""), error_max_chars)
                ann.last_error_at = datetime.now()
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception("news_ai_rerun persist_error failed news_id=%s", int(news_id))
            raise

    async def _get_or_create_annotation(self, db: AsyncSession, news: News, *, news_id: int | None = None) -> NewsAIAnnotation:
        nid = int(news_id) if news_id is not None else int(news.id)
        res = await db.execute(select(NewsAIAnnotation).where(NewsAIAnnotation.news_id == int(nid)))
        ann = res.scalar_one_or_none()
        if ann is not None:
            return ann

        ann = NewsAIAnnotation(
            news_id=int(nid),
            summary=None,
            risk_level="unknown",
            sensitive_words=None,
            highlights=None,
            keywords=None,
            duplicate_of_news_id=None,
            processed_at=None,
        )
        db.add(ann)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            res2 = await db.execute(select(NewsAIAnnotation).where(NewsAIAnnotation.news_id == int(nid)))
            ann2 = res2.scalar_one_or_none()
            if ann2 is None:
                raise
            return ann2
        await db.refresh(ann)
        return ann

    @staticmethod
    def _bool_env(name: str, default: bool = False) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return bool(default)
        v = str(raw).strip().lower()
        if not v:
            return bool(default)
        return v in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, object] | None:
        t = str(text or "").strip()
        if not t:
            return None

        if t.startswith("```"):
            t = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", t)
            t = re.sub(r"\n```$", "", t).strip()

        try:
            parsed: object = cast(object, json.loads(t))
            if isinstance(parsed, dict):
                parsed_dict = cast(dict[object, object], parsed)
                return {str(k): v for k, v in parsed_dict.items()}
        except Exception:
            pass

        start = t.find("{")
        end = t.rfind("}")
        if start >= 0 and end > start:
            snippet = t[start : end + 1]
            try:
                parsed2: object = cast(object, json.loads(snippet))
                if isinstance(parsed2, dict):
                    parsed2_dict = cast(dict[object, object], parsed2)
                    return {str(k): v for k, v in parsed2_dict.items()}
            except Exception:
                return None

        return None

    @staticmethod
    def _extract_structured_summary(text: str) -> str | None:
        t = str(text or "").strip()
        if not t:
            return None
        obj = NewsAIPipelineService._extract_json_object(t)
        if obj is None:
            return t
        summary = obj.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
        return None

    @staticmethod
    def _extract_structured_output(
        text: str,
        *,
        highlights_max: int,
        keywords_max: int,
        item_max_chars: int,
    ) -> tuple[str | None, list[str], list[str]]:
        t = str(text or "").strip()
        if not t:
            return None, [], []

        obj = NewsAIPipelineService._extract_json_object(t)
        if obj is None:
            return t, [], []

        summary_raw = obj.get("summary")
        summary = summary_raw.strip() if isinstance(summary_raw, str) and summary_raw.strip() else None

        def _as_list(value: object, max_items: int) -> list[str]:
            if not isinstance(value, list):
                return []

            out: list[str] = []
            items = cast(list[object], value)
            for x in items:
                if len(out) >= int(max_items):
                    break
                s = str(x or "").strip()
                s = _truncate(s, int(item_max_chars)) or ""
                if s:
                    out.append(s)
            return out

        highlights = _as_list(obj.get("highlights"), int(highlights_max))
        keywords = _as_list(obj.get("keywords"), int(keywords_max))
        return summary, highlights, keywords

    async def _make_summary(
        self,
        news: News,
        *,
        env_overrides: dict[str, str] | None = None,
        force_generate: bool = False,
    ) -> tuple[str | None, bool, list[str], list[str]]:
        if not bool(force_generate):
            s = _truncate(getattr(news, "summary", None), 500)
            if s:
                return s, False, [], []

        settings = get_settings()

        def _env(name: str, default: str = "") -> str:
            if env_overrides is not None:
                v = env_overrides.get(name)
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
            v = raw.strip().lower()
            return v in {"1", "true", "yes", "y", "on"}

        providers = self._get_summary_llm_providers(settings, env_overrides=env_overrides)

        mock_generated = str(os.getenv("NEWS_AI_SUMMARY_LLM_MOCK_RESPONSE", "") or "").strip()
        mock_b64_raw = str(os.getenv("NEWS_AI_SUMMARY_LLM_MOCK_RESPONSE_B64", "") or "").strip()
        if not mock_generated:
            if mock_b64_raw:
                try:
                    mock_generated = base64.b64decode(mock_b64_raw).decode("utf-8").strip()
                except Exception:
                    mock_generated = ""

        logger.debug(
            "news_ai_summary mock_plain=%s mock_b64_len=%s mock_decoded_len=%s",
            bool(str(os.getenv("NEWS_AI_SUMMARY_LLM_MOCK_RESPONSE", "") or "").strip()),
            len(mock_b64_raw) if mock_b64_raw else 0,
            len(mock_generated) if mock_generated else 0,
        )

        highlights_max = int(os.getenv("NEWS_AI_SUMMARY_LLM_HIGHLIGHTS_MAX", "3").strip() or "3")
        keywords_max = int(os.getenv("NEWS_AI_SUMMARY_LLM_KEYWORDS_MAX", "5").strip() or "5")
        item_max_chars = int(os.getenv("NEWS_AI_SUMMARY_LLM_ITEM_MAX_CHARS", "40").strip() or "40")

        if (not mock_generated) and (not _bool("NEWS_AI_SUMMARY_LLM_ENABLED", False)):
            local_summary = self._make_summary_local(news)
            highlights, keywords = self._make_local_highlights_keywords(
                title=str(getattr(news, "title", "") or ""),
                content=str(getattr(news, "content", "") or ""),
                highlights_max=int(highlights_max),
                keywords_max=int(keywords_max),
                item_max_chars=int(item_max_chars),
            )
            return local_summary, False, highlights, keywords

        if (not mock_generated) and (not providers):
            local_summary = self._make_summary_local(news)
            highlights, keywords = self._make_local_highlights_keywords(
                title=str(getattr(news, "title", "") or ""),
                content=str(getattr(news, "content", "") or ""),
                highlights_max=int(highlights_max),
                keywords_max=int(keywords_max),
                item_max_chars=int(item_max_chars),
            )
            return local_summary, False, highlights, keywords

        title = str(getattr(news, "title", "") or "").strip()
        content = str(getattr(news, "content", "") or "").strip()
        if not content and title:
            highlights, keywords = self._make_local_highlights_keywords(
                title=title,
                content="",
                highlights_max=int(highlights_max),
                keywords_max=int(keywords_max),
                item_max_chars=int(item_max_chars),
            )
            return _truncate(title, 500), False, highlights, keywords

        max_chars = int(os.getenv("NEWS_AI_SUMMARY_LLM_MAX_CHARS", "4000").strip() or "4000")
        summary_max_chars = int(os.getenv("NEWS_AI_SUMMARY_LLM_SUMMARY_MAX_CHARS", "120").strip() or "120")
        content_for_prompt = content.replace("\n", " ")
        if len(content_for_prompt) > int(max_chars):
            content_for_prompt = content_for_prompt[: int(max_chars)]

        timeout_seconds = float(os.getenv("NEWS_AI_SUMMARY_LLM_TIMEOUT_SECONDS", "20").strip() or "20")
        try:
            if mock_generated:
                generated = mock_generated
            else:
                generated: str | None = None
                last_exc: Exception | None = None
                strategy = _env("NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY", "priority").strip()
                ordered = self._order_summary_llm_providers(providers, strategy=strategy)
                for p in ordered:
                    p_api_key = str(p.get("api_key", "") or "").strip()
                    p_base_url = str(p.get("base_url", "") or "").strip()
                    p_model = str(p.get("model", "") or "").strip() or "gpt-4o-mini"

                    if (not p_base_url) or (not p_api_key):
                        continue

                    auth_type = str(p.get("auth_type", "bearer") or "bearer").strip().lower()
                    auth_header_name: str | None = None
                    auth_prefix: str | None = None
                    if auth_type == "header":
                        auth_header_name = str(p.get("auth_header_name", "") or "").strip() or "api-key"
                        auth_prefix = str(p.get("auth_prefix", "") or "")

                    chat_path_raw = str(p.get("chat_completions_path", "") or "").strip()
                    chat_path = chat_path_raw if chat_path_raw else None

                    rf_raw = str(p.get("response_format", "") or "").strip()
                    global_rf = _env("NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT", "").strip()
                    rf = rf_raw if rf_raw else (global_rf if global_rf else None)

                    try:
                        generated = await self._llm_summarize(
                            api_key=p_api_key,
                            base_url=p_base_url,
                            model=p_model,
                            title=title,
                            content=content_for_prompt,
                            timeout_seconds=timeout_seconds,
                            summary_max_chars=int(summary_max_chars),
                            highlights_max=int(highlights_max),
                            keywords_max=int(keywords_max),
                            response_format=rf,
                            auth_header_name=auth_header_name,
                            auth_prefix=auth_prefix,
                            chat_completions_path=chat_path,
                        )
                        if generated:
                            break
                    except Exception as e:
                        last_exc = e
                        if logger.isEnabledFor(logging.INFO):
                            logger.info(
                                "news_ai_summary_llm provider_failed name=%s base_url=%s",
                                str(p.get("name", "") or ""),
                                p_base_url,
                                exc_info=True,
                            )
                        continue

                if (not generated) and (last_exc is not None):
                    raise last_exc
        except Exception:
            logger.exception("news_ai_summary_llm failed news_id=%s", int(getattr(news, "id", 0) or 0))
            local_summary = self._make_summary_local(news)
            highlights, keywords = self._make_local_highlights_keywords(
                title=title,
                content=content,
                highlights_max=int(highlights_max),
                keywords_max=int(keywords_max),
                item_max_chars=int(item_max_chars),
            )
            return local_summary, False, highlights, keywords

        summary, highlights, keywords = self._extract_structured_output(
            str(generated or ""),
            highlights_max=int(highlights_max),
            keywords_max=int(keywords_max),
            item_max_chars=int(item_max_chars),
        )
        summary = _truncate(summary, int(summary_max_chars))
        if (not highlights) or (not keywords):
            local_highlights, local_keywords = self._make_local_highlights_keywords(
                title=title,
                content=content,
                highlights_max=int(highlights_max),
                keywords_max=int(keywords_max),
                item_max_chars=int(item_max_chars),
            )
            if not highlights:
                highlights = local_highlights
            if not keywords:
                keywords = local_keywords
        if summary:
            return _truncate(summary, 500), True, highlights, keywords
        local_summary = self._make_summary_local(news)
        local_highlights, local_keywords = self._make_local_highlights_keywords(
            title=title,
            content=content,
            highlights_max=int(highlights_max),
            keywords_max=int(keywords_max),
            item_max_chars=int(item_max_chars),
        )
        return local_summary, False, local_highlights, local_keywords

    def _get_summary_llm_providers(
        self,
        settings: object,
        *,
        env_overrides: dict[str, str] | None = None,
    ) -> list[_NewsSummaryLLMProvider]:
        override_json = (env_overrides or {}).get("NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON")
        override_b64 = (env_overrides or {}).get("NEWS_AI_SUMMARY_LLM_PROVIDERS_B64")
        providers_from_overrides = bool(
            (override_json is not None and str(override_json).strip())
            or (override_b64 is not None and str(override_b64).strip())
        )

        env_token = _current_env_token()
        raw_json_env = (
            str(os.getenv(f"NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON_{env_token}", "") or "").strip()
            if env_token
            else ""
        )
        raw_b64_env = (
            str(os.getenv(f"NEWS_AI_SUMMARY_LLM_PROVIDERS_B64_{env_token}", "") or "").strip()
            if env_token
            else ""
        )

        raw_json = str(override_json or raw_json_env or os.getenv("NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON", "") or "").strip()
        raw_b64 = str(override_b64 or raw_b64_env or os.getenv("NEWS_AI_SUMMARY_LLM_PROVIDERS_B64", "") or "").strip()

        default_api_key = str(getattr(settings, "openai_api_key", "") or "").strip()
        default_base_url = str(getattr(settings, "openai_base_url", "") or "").strip()
        default_model = str(getattr(settings, "ai_model", "") or "").strip() or "gpt-4o-mini"

        def _provider_token(name: str) -> str:
            s = re.sub(r"[^A-Za-z0-9]+", "_", str(name or "").strip()).strip("_")
            return s.upper() if s else ""

        def _env_str(var_name: str) -> str:
            return str(os.getenv(var_name, "") or "").strip()

        providers: list[_NewsSummaryLLMProvider] = []
        decoded = raw_json
        if (not decoded) and raw_b64:
            try:
                decoded = base64.b64decode(raw_b64).decode("utf-8").strip()
            except Exception:
                decoded = ""

        if decoded:
            try:
                obj: object = cast(object, json.loads(decoded))
                if isinstance(obj, list):
                    items = cast(list[object], obj)
                    for item_obj in items:
                        if not isinstance(item_obj, dict):
                            continue
                        d_obj = cast(dict[object, object], item_obj)
                        d = {str(k): v for k, v in d_obj.items()}
                        name_raw = str(d.get("name", "") or "").strip()
                        base_url = str(d.get("base_url", "") or "").strip()
                        token = _provider_token(name_raw or base_url)

                        if not base_url:
                            if token == "OPENAI":
                                base_url = default_base_url
                            elif token:
                                base_url = _env_str(f"{token}_BASE_URL")

                        api_key_from_env = _env_str(f"{token}_API_KEY") if token else ""
                        api_key = api_key_from_env or default_api_key
                        if not providers_from_overrides:
                            api_key = str(d.get("api_key", "") or "").strip() or api_key

                        if not base_url or not api_key:
                            continue

                        p: _NewsSummaryLLMProvider = {
                            "name": name_raw or base_url,
                            "base_url": base_url,
                            "api_key": api_key,
                        }

                        model_from_env = _env_str(f"{token}_MODEL") if token else ""
                        model = str(d.get("model", "") or "").strip() or model_from_env or default_model
                        if model:
                            p["model"] = model

                        priority_raw = d.get("priority")
                        if isinstance(priority_raw, int):
                            p["priority"] = int(priority_raw)
                        elif isinstance(priority_raw, str):
                            s = priority_raw.strip()
                            if s and re.fullmatch(r"-?\d+", s):
                                p["priority"] = int(s)
                        rf = str(d.get("response_format", "") or "").strip()
                        if rf:
                            p["response_format"] = rf

                        auth_type = str(d.get("auth_type", "") or "").strip().lower()
                        if (not auth_type) and token.startswith("AZURE"):
                            auth_type = "header"
                        if auth_type in {"bearer", "header"}:
                            p["auth_type"] = cast(Literal["bearer", "header"], auth_type)
                        auth_header_name = str(d.get("auth_header_name", "") or "").strip()
                        if (not auth_header_name) and auth_type == "header" and token.startswith("AZURE"):
                            auth_header_name = "api-key"
                        if auth_header_name:
                            p["auth_header_name"] = auth_header_name
                        auth_prefix = str(d.get("auth_prefix", "") or "")
                        if auth_prefix:
                            p["auth_prefix"] = auth_prefix

                        chat_path = str(d.get("chat_completions_path", "") or "").strip()
                        if chat_path:
                            p["chat_completions_path"] = chat_path

                        weight_raw = d.get("weight")
                        if isinstance(weight_raw, int) and weight_raw > 0:
                            p["weight"] = int(weight_raw)

                        providers.append(p)
            except Exception:
                providers = []

        if providers:
            return providers

        api_key = default_api_key
        base_url = str(getattr(settings, "openai_base_url", "") or "").strip()
        model = str(getattr(settings, "ai_model", "") or "").strip() or "gpt-4o-mini"
        if api_key and base_url:
            return [
                {
                    "name": "default",
                    "base_url": base_url,
                    "api_key": api_key,
                    "model": model,
                }
            ]
        return []

    def get_summary_llm_providers(
        self,
        settings: object,
        *,
        env_overrides: dict[str, str] | None = None,
    ) -> list[_NewsSummaryLLMProvider]:
        return self._get_summary_llm_providers(settings, env_overrides=env_overrides)

    def _order_summary_llm_providers(
        self,
        providers: list[_NewsSummaryLLMProvider],
        *,
        strategy: str | None = None,
    ) -> list[_NewsSummaryLLMProvider]:
        strategy_value = str(strategy if strategy is not None else os.getenv("NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY", "priority") or "priority").strip().lower()
        if strategy_value == "priority":
            if not providers:
                return []
            indexed = list(enumerate(providers))

            def _key(x: tuple[int, _NewsSummaryLLMProvider]) -> tuple[int, int]:
                idx, p = x
                pr = p.get("priority")
                if isinstance(pr, int):
                    return (int(pr), int(idx))
                return (1_000_000_000, int(idx))

            ordered = sorted(indexed, key=_key)
            return [p for _, p in ordered]
        if strategy_value == "round_robin":
            if not providers:
                return []
            start = int(self._rr_cursor) % len(providers)
            self._rr_cursor = int(self._rr_cursor) + 1
            return list(providers[start:]) + list(providers[:start])
        if strategy_value == "random":
            if not providers:
                return []
            weights = [int(p.get("weight", 1) or 1) for p in providers]
            total = sum(weights)
            r = random.randint(1, max(1, total))
            acc = 0
            idx = 0
            for i, w in enumerate(weights):
                acc += int(w)
                if r <= acc:
                    idx = i
                    break
            first = providers[idx]
            rest = [p for i, p in enumerate(providers) if i != idx]
            return [first] + rest
        return list(providers)

    async def _llm_summarize(
        self,
        api_key: str,
        base_url: str,
        model: str,
        title: str,
        content: str,
        timeout_seconds: float,
        summary_max_chars: int,
        highlights_max: int,
        keywords_max: int,
        response_format: str | None = None,
        auth_header_name: str | None = None,
        auth_prefix: str | None = None,
        chat_completions_path: str | None = None,
    ) -> str | None:
        path = str(chat_completions_path or "/chat/completions").strip() or "/chat/completions"
        if not path.startswith("/"):
            path = "/" + path
        url = base_url.rstrip("/") + path

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if auth_header_name:
            prefix = str(auth_prefix or "")
            headers[str(auth_header_name)] = f"{prefix}{api_key}"
        else:
            headers["Authorization"] = f"Bearer {api_key}"
        system_prompt = (
            "你是一个新闻摘要助手。请只输出一个 JSON 对象，不要输出其它任何文字。"
            "JSON 格式为："
            '{"summary": "...", "highlights": ["..."], "keywords": ["..."]}。'
            f"其中 summary 为中文摘要，长度不超过 {int(summary_max_chars)} 字；"
            f"highlights 最多 {int(highlights_max)} 条；keywords 最多 {int(keywords_max)} 个。"
        )
        user_prompt = sanitize_pii(f"标题：{title}\n正文：{content}")
        payload: dict[str, object] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 256,
        }

        rf_raw = (
            str(response_format)
            if response_format is not None
            else str(os.getenv("NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT", "") or "")
        ).strip().lower()
        if rf_raw in {"0", "off", "none", "disable", "disabled"}:
            rf = ""
        else:
            rf = rf_raw or "json_object"

        if rf in {"json_object", "json_schema"}:
            if rf == "json_object":
                payload["response_format"] = {"type": "json_object"}
            else:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "news_summary",
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "summary": {"type": "string", "maxLength": int(summary_max_chars)},
                                "highlights": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "maxItems": int(highlights_max),
                                },
                                "keywords": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "maxItems": int(keywords_max),
                                },
                            },
                            "required": ["summary", "highlights", "keywords"],
                        },
                        "strict": True,
                    },
                }

        timeout = httpx.Timeout(timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(url, headers=headers, json=payload)
            if (res.status_code in {400, 422}) and ("response_format" in payload):
                try:
                    body: object = cast(object, res.json())
                except Exception:
                    body = str(getattr(res, "text", "") or "")
                logger.warning(
                    "news_ai_summary_llm response_format unsupported, fallback to prompt-only. status=%s body=%s",
                    int(res.status_code),
                    body,
                )
                payload2: dict[str, object] = dict(payload)
                _ = payload2.pop("response_format", None)
                res = await client.post(url, headers=headers, json=payload2)
            _ = res.raise_for_status()
            data_obj: object = cast(object, res.json())

        if not isinstance(data_obj, dict):
            return None
        data = cast(dict[str, object], data_obj)

        choices_obj = data.get("choices")
        if not isinstance(choices_obj, list) or not choices_obj:
            return None
        choices = cast(list[object], choices_obj)
        first_obj = choices[0]
        if not isinstance(first_obj, dict):
            return None
        first = cast(dict[str, object], first_obj)
        msg_any = first.get("message")
        if not isinstance(msg_any, dict):
            return None
        msg_obj = cast(dict[str, object], msg_any)
        content_any = msg_obj.get("content")
        if not isinstance(content_any, str):
            return None
        return content_any.strip() or None

    def _make_summary_local(self, news: News) -> str | None:
        s = _truncate(getattr(news, "summary", None), 500)
        if s:
            return s
        content = str(getattr(news, "content", "") or "").strip()
        if not content:
            return _truncate(str(getattr(news, "title", "") or "").strip(), 500)
        return _truncate(content.replace("\n", " "), 500)

    def _make_risk(self, news: News) -> tuple[str, str | None]:
        title = str(getattr(news, "title", "") or "").strip()
        content = str(getattr(news, "content", "") or "").strip()
        passed, reason, matched = content_filter.check_content(f"{title}\n{content}")
        risk = _risk_from_filter(passed, reason)
        matched_str = ",".join([str(w).strip() for w in matched if str(w).strip()])
        return risk, matched_str or None

    async def _find_duplicate_of(self, db: AsyncSession, news: News) -> int | None:
        fp = _fingerprint(news)
        title_norm = _normalize_title(news.title)
        if not title_norm:
            return None

        site = str(getattr(news, "source_site", "") or "").strip()
        candidates_q = (
            select(News.id, News.title, News.source_site)
            .where(
                and_(
                    News.id != int(news.id),
                    func.lower(News.title) == title_norm,
                    func.coalesce(News.source_site, "") == site,
                )
            )
            .order_by(News.id.asc())
            .limit(1)
        )
        res = await db.execute(candidates_q)
        row = res.first()
        if row is None:
            return None

        other_id = int(cast(int, row[0]))
        other_news_res = await db.execute(select(News).where(News.id == other_id))
        other = other_news_res.scalar_one_or_none()
        if other is None:
            return None

        if _fingerprint(other) == fp:
            return other_id
        return None


news_ai_pipeline_service = NewsAIPipelineService()
