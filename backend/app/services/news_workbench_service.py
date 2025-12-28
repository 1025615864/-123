from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any, cast

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from ..config import get_settings
from ..models.news import News
from ..models.news_workbench import NewsAIGeneration, NewsLinkCheck


class NewsWorkbenchService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def _require_ai(self) -> ChatOpenAI:
        if not str(self._settings.openai_api_key or "").strip():
            raise RuntimeError("ai_not_configured")
        return ChatOpenAI(
            model=str(self._settings.ai_model or "").strip() or "gpt-4o-mini",
            api_key=cast(Any, self._settings.openai_api_key),
            base_url=str(self._settings.openai_base_url or "").strip() or None,
            temperature=0.7,
            max_completion_tokens=2000,
        )

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any] | None:
        t = str(text or "").strip()
        if not t:
            return None
        start = t.find("{")
        end = t.rfind("}")
        if start < 0 or end < 0 or end <= start:
            return None
        chunk = t[start : end + 1]
        try:
            obj: object = json.loads(chunk)
        except Exception:
            return None
        if not isinstance(obj, dict):
            return None
        return cast(dict[str, Any], obj)

    @staticmethod
    def _normalize_task_type(task_type: str) -> str:
        return str(task_type or "").strip().lower()

    @staticmethod
    def extract_links_from_markdown(markdown: str) -> list[str]:
        text = str(markdown or "")

        url_pattern = re.compile(r"https?://[^\s)\]}>\"']+", flags=re.IGNORECASE)
        urls = set(m.group(0).strip() for m in url_pattern.finditer(text) if m.group(0).strip())

        return sorted(urls)

    async def create_generation(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        news_id: int | None,
        task_type: str,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any] | None,
        raw_output: str | None,
        status: str,
        error: str | None,
    ) -> NewsAIGeneration:
        rec = NewsAIGeneration(
            user_id=int(user_id),
            news_id=int(news_id) if news_id is not None else None,
            task_type=str(task_type),
            status=str(status),
            input_json=json.dumps(input_payload, ensure_ascii=False),
            output_json=json.dumps(output_payload, ensure_ascii=False) if output_payload is not None else None,
            raw_output=raw_output,
            error=error,
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return rec

    async def generate(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        news_id: int | None,
        task_type: str,
        title: str | None,
        summary: str | None,
        content: str | None,
        style: str | None,
        word_count_min: int | None,
        word_count_max: int | None,
        append: bool,
    ) -> NewsAIGeneration:
        task = self._normalize_task_type(task_type)

        input_payload: dict[str, Any] = {
            "task_type": task,
            "title": title,
            "summary": summary,
            "content": content,
            "style": style,
            "word_count_min": word_count_min,
            "word_count_max": word_count_max,
            "append": bool(append),
        }

        try:
            llm = self._require_ai()
        except RuntimeError as e:
            return await self.create_generation(
                db,
                user_id=int(user_id),
                news_id=news_id,
                task_type=task,
                input_payload=input_payload,
                output_payload=None,
                raw_output=None,
                status="error",
                error=str(e),
            )

        sys = (
            "你是新闻编辑工作台助手。只输出一个 JSON 对象，不要输出任何其它文字。"
            "JSON 允许字段：title, summary, content, points, risk_warnings。"
        )

        style_text = str(style or "").strip()
        wc_min = int(word_count_min) if word_count_min is not None else None
        wc_max = int(word_count_max) if word_count_max is not None else None

        user_lines: list[str] = [f"任务类型：{task}"]
        if style_text:
            user_lines.append(f"写作风格：{style_text}")
        if wc_min is not None or wc_max is not None:
            user_lines.append(f"字数范围：{wc_min or ''}~{wc_max or ''}")
        if title:
            user_lines.append(f"现有标题：{title}")
        if summary:
            user_lines.append(f"现有摘要：{summary}")
        if content:
            user_lines.append(f"现有正文：\n{content}")

        if task in {"outline", "plan"}:
            user_lines.append("请输出 points 为大纲要点列表，content 可为空或为 markdown 大纲。")
        elif task in {"full", "article", "rewrite"}:
            user_lines.append("请输出 content 为 markdown 正文；可同时输出 title/summary。")
        elif task in {"polish", "proofread"}:
            user_lines.append("请输出 content 为润色后的 markdown 正文；可输出 summary。")
        elif task in {"title_candidates"}:
            user_lines.append("请输出 title 为一个推荐标题；points 可为标题候选列表。")
        elif task in {"summary_candidates"}:
            user_lines.append("请输出 summary 为一个推荐摘要；points 可为摘要候选列表。")
        elif task in {"risk_warnings"}:
            user_lines.append("请输出 risk_warnings 为风险提示段落列表；content 可为空。")
        else:
            user_lines.append("请按任务类型输出最合适的字段。")

        user_prompt = "\n".join(user_lines)

        raw_output: str | None = None
        output_payload: dict[str, Any] | None = None
        try:
            res = await llm.ainvoke(
                [
                    SystemMessage(content=sys),
                    HumanMessage(content=user_prompt),
                ]
            )
            raw_output = str(getattr(res, "content", "") or "").strip() or None
            if raw_output:
                output_payload = self._extract_json_object(raw_output)
        except Exception as e:
            return await self.create_generation(
                db,
                user_id=int(user_id),
                news_id=news_id,
                task_type=task,
                input_payload=input_payload,
                output_payload=None,
                raw_output=raw_output,
                status="error",
                error=str(e),
            )

        if output_payload is None:
            return await self.create_generation(
                db,
                user_id=int(user_id),
                news_id=news_id,
                task_type=task,
                input_payload=input_payload,
                output_payload=None,
                raw_output=raw_output,
                status="error",
                error="invalid_json",
            )

        if append and content and isinstance(output_payload.get("content"), str):
            output_payload["content"] = str(content) + "\n\n" + str(output_payload.get("content") or "")

        return await self.create_generation(
            db,
            user_id=int(user_id),
            news_id=news_id,
            task_type=task,
            input_payload=input_payload,
            output_payload=output_payload,
            raw_output=raw_output,
            status="success",
            error=None,
        )

    async def list_generations(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        news_id: int | None,
        limit: int = 50,
    ) -> list[NewsAIGeneration]:
        q = select(NewsAIGeneration).where(NewsAIGeneration.user_id == int(user_id))
        if news_id is not None:
            q = q.where(NewsAIGeneration.news_id == int(news_id))
        q = q.order_by(desc(NewsAIGeneration.created_at), desc(NewsAIGeneration.id)).limit(int(max(1, min(200, limit))))
        res = await db.execute(q)
        return list(res.scalars().all())

    async def check_links(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        news_id: int | None,
        markdown: str,
        timeout_seconds: float = 6.0,
        max_urls: int = 50,
    ) -> tuple[str, list[NewsLinkCheck]]:
        run_id = uuid.uuid4().hex
        urls = self.extract_links_from_markdown(markdown)
        max_urls_int = int(max(1, min(200, max_urls)))
        urls = urls[:max_urls_int]

        concurrency = int(max(1, min(20, 10)))
        semaphore = asyncio.Semaphore(concurrency)

        async def _check_one(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
            async with semaphore:
                ok = False
                status_code: int | None = None
                final_url: str | None = None
                err: str | None = None
                try:
                    r = await client.get(url)
                    status_code = int(r.status_code)
                    final_url = str(r.url) if getattr(r, "url", None) is not None else None
                    ok = bool(status_code < 400)
                except Exception as e:
                    err = str(e)
                return {
                    "url": str(url),
                    "ok": bool(ok),
                    "status_code": status_code,
                    "final_url": final_url,
                    "error": err,
                }

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds), follow_redirects=True) as client:
            results = await asyncio.gather(*[_check_one(client, str(u)) for u in urls])

        for r in results:
            db.add(
                NewsLinkCheck(
                    run_id=str(run_id),
                    user_id=int(user_id),
                    news_id=int(news_id) if news_id is not None else None,
                    url=str(r.get("url") or ""),
                    final_url=cast(str | None, r.get("final_url")),
                    ok=bool(r.get("ok")),
                    status_code=cast(int | None, r.get("status_code")),
                    error=cast(str | None, r.get("error")),
                )
            )

        await db.commit()

        items = await self.get_link_checks_by_run_id(db, run_id=str(run_id), user_id=int(user_id))
        return str(run_id), items

    async def get_link_checks_by_run_id(
        self,
        db: AsyncSession,
        *,
        run_id: str,
        user_id: int | None = None,
    ) -> list[NewsLinkCheck]:
        rid = str(run_id or "").strip()
        if not rid:
            return []
        q = select(NewsLinkCheck).where(NewsLinkCheck.run_id == rid)
        if user_id is not None:
            q = q.where(NewsLinkCheck.user_id == int(user_id))
        q = q.order_by(NewsLinkCheck.id.asc())
        res = await db.execute(q)
        return list(res.scalars().all())

    async def get_news_content_for_task(self, db: AsyncSession, news_id: int) -> tuple[str | None, str | None, str | None]:
        res = await db.execute(select(News).where(News.id == int(news_id)))
        news = res.scalar_one_or_none()
        if news is None:
            return None, None, None
        return (
            str(getattr(news, "title", "") or "") or None,
            cast(str | None, getattr(news, "summary", None)),
            str(getattr(news, "content", "") or "") or None,
        )


news_workbench_service = NewsWorkbenchService()
