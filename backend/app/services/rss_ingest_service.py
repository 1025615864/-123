import logging
import os
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.news import News


logger = logging.getLogger(__name__)


def _truncate(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    if len(v) <= int(max_len):
        return v
    return v[: int(max_len)]


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_first_text(elem: ET.Element, names: set[str]) -> str | None:
    for child in list(elem):
        name = _local_name(child.tag)
        if name in names:
            txt = (child.text or "").strip()
            if txt:
                return txt
    return None


def _extract_atom_link(entry: ET.Element) -> str | None:
    links: list[str] = []
    preferred: str | None = None
    for child in list(entry):
        if _local_name(child.tag) != "link":
            continue
        href = str(child.attrib.get("href", "") or "").strip()
        if not href:
            continue
        rel = str(child.attrib.get("rel", "") or "").strip().lower()
        if rel in {"alternate", ""} and preferred is None:
            preferred = href
        links.append(href)

    if preferred:
        return preferred
    if links:
        return links[0]
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    v = str(value).strip()
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return dt
    except Exception:
        return None


def _extract_items(xml_text: str) -> tuple[str | None, list[dict[str, Any]]]:
    root = ET.fromstring(xml_text)
    root_name = _local_name(root.tag)

    if root_name == "rss":
        channel = None
        for child in list(root):
            if _local_name(child.tag) == "channel":
                channel = child
                break
        if channel is None:
            return None, []

        feed_title = _find_first_text(channel, {"title"})
        items: list[dict[str, Any]] = []
        for child in list(channel):
            if _local_name(child.tag) != "item":
                continue
            title = _find_first_text(child, {"title"})
            link = _find_first_text(child, {"link"})
            summary = _find_first_text(child, {"description", "summary"})
            content = _find_first_text(child, {"encoded", "content"})
            author = _find_first_text(child, {"author", "creator"})
            published = _find_first_text(child, {"pubDate", "published"})
            items.append(
                {
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "content": content,
                    "author": author,
                    "published": published,
                }
            )
        return feed_title, items

    if root_name == "feed":
        feed_title = _find_first_text(root, {"title"})
        items: list[dict[str, Any]] = []
        for child in list(root):
            if _local_name(child.tag) != "entry":
                continue
            title = _find_first_text(child, {"title"})
            link = _extract_atom_link(child)
            summary = _find_first_text(child, {"summary"})
            content = _find_first_text(child, {"content"})
            published = _find_first_text(child, {"published", "updated"})

            author_name: str | None = None
            for c2 in list(child):
                if _local_name(c2.tag) != "author":
                    continue
                author_name = _find_first_text(c2, {"name"})
                if author_name:
                    break

            items.append(
                {
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "content": content,
                    "author": author_name,
                    "published": published,
                }
            )
        return feed_title, items

    return None, []


class RSSIngestService:
    def _parse_feed_specs(self) -> list[tuple[str, str | None, str | None]]:
        raw = os.getenv("RSS_FEEDS", "").strip()
        if not raw:
            return []

        specs: list[tuple[str, str | None, str | None]] = []
        for token in raw.split(","):
            t = token.strip()
            if not t:
                continue
            parts = [p.strip() for p in t.split("|")]
            url = parts[0] if parts else ""
            if not url:
                continue
            site = parts[1] if len(parts) >= 2 and parts[1] else None
            category = parts[2] if len(parts) >= 3 and parts[2] else None
            specs.append((url, site, category))
        return specs

    def _normalize_site(self, url: str, override: str | None) -> str | None:
        if override:
            return _truncate(override, 100)
        try:
            host = urlparse(url).netloc
        except Exception:
            host = ""
        host = str(host or "").strip()
        if host.startswith("www."):
            host = host[4:]
        return _truncate(host, 100)

    def _normalize_category(self, override: str | None) -> str:
        allowed = {"general", "policy", "case", "interpret"}
        if override:
            v = str(override).strip().lower()
            if v in allowed:
                return v
        env_default = os.getenv("RSS_DEFAULT_CATEGORY", "general").strip().lower() or "general"
        return env_default if env_default in allowed else "general"

    async def run_once(self, db: AsyncSession) -> dict[str, int]:
        feed_specs = self._parse_feed_specs()
        if not feed_specs:
            return {"feeds": 0, "fetched": 0, "inserted": 0, "skipped": 0, "errors": 0}

        fetched = 0
        inserted = 0
        skipped = 0
        errors = 0

        timeout = float(os.getenv("RSS_FETCH_TIMEOUT_SECONDS", "20").strip() or "20")
        max_items_per_feed = int(os.getenv("RSS_MAX_ITEMS_PER_FEED", "20").strip() or "20")

        candidates: list[tuple[str | None, str, dict[str, Any]]] = []

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for feed_url, site_override, category_override in feed_specs:
                try:
                    resp = await client.get(feed_url)
                    if int(resp.status_code) != 200:
                        errors += 1
                        continue
                    feed_title, items = _extract_items(resp.text)
                    fetched += 1
                    site = self._normalize_site(feed_url, site_override)
                    category = self._normalize_category(category_override)

                    for item in items[: max(0, max_items_per_feed)]:
                        candidates.append((feed_title, site or "", {**item, "category": category}))
                except Exception:
                    errors += 1
                    logger.exception("RSS抓取失败 url=%s", feed_url)

        seen_urls: set[str] = set()
        new_items: list[tuple[str | None, str, dict[str, Any]]] = []
        urls: list[str] = []
        for feed_title, site, item in candidates:
            link = str(item.get("link", "") or "").strip()
            if not link:
                skipped += 1
                continue
            if link in seen_urls:
                skipped += 1
                continue
            seen_urls.add(link)
            urls.append(link)
            new_items.append((feed_title, site, item))

        existing_urls: set[str] = set()
        if urls:
            res = await db.execute(select(News.source_url).where(News.source_url.in_(urls)))
            existing_urls = {str(v).strip() for (v,) in res.all() if v}

        to_create: list[News] = []
        for feed_title, site, item in new_items:
            link = str(item.get("link", "") or "").strip()
            if link in existing_urls:
                skipped += 1
                continue

            title = _truncate(str(item.get("title", "") or "").strip() or link, 200) or link
            summary = _truncate(item.get("summary"), 500)
            content = str(item.get("content", "") or "").strip()
            if not content:
                content = str(summary or "").strip()
            if not content:
                content = title

            author = _truncate(item.get("author"), 50)
            category = str(item.get("category", "general") or "general").strip().lower() or "general"
            source_site = _truncate(site, 100)
            source = _truncate(feed_title, 100) or source_site

            news = News(
                title=title,
                summary=summary,
                content=content,
                cover_image=None,
                category=category,
                source=source,
                source_url=_truncate(link, 500),
                source_site=source_site,
                author=author,
                is_top=False,
                is_published=False,
                review_status="pending",
                review_reason=None,
                reviewed_at=None,
                published_at=None,
                scheduled_publish_at=None,
                scheduled_unpublish_at=None,
            )
            to_create.append(news)

        if to_create:
            db.add_all(to_create)
            await db.commit()
            inserted += len(to_create)

        logger.info(
            "rss_ingest done feeds=%s fetched=%s inserted=%s skipped=%s errors=%s",
            len(feed_specs),
            fetched,
            inserted,
            skipped,
            errors,
        )

        return {
            "feeds": len(feed_specs),
            "fetched": fetched,
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
        }


rss_ingest_service = RSSIngestService()
