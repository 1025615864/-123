import logging
import os
import asyncio
import hashlib
from datetime import datetime
from typing import TypeAlias
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import xml.etree.ElementTree as ET

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.news import News, NewsSource, NewsIngestRun


logger = logging.getLogger(__name__)


RSSItem: TypeAlias = dict[str, str | None]


def _truncate(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    if len(v) <= int(max_len):
        return v
    return v[: int(max_len)]


def _normalize_url(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""

    try:
        p = urlparse(s)
    except Exception:
        return s

    query_items = list(parse_qsl(p.query, keep_blank_values=True))
    drop_keys = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "spm",
        "from",
        "source",
        "ref",
        "fbclid",
        "gclid",
    }
    query_items = [(k, v) for (k, v) in query_items if str(k).strip().lower() not in drop_keys]
    new_query = urlencode(query_items, doseq=True)
    new_p = p._replace(query=new_query, fragment="")
    return urlunparse(new_p)


def _make_dedupe_hash(*, title: str, content: str, source_url: str) -> str:
    _ = source_url
    t = " ".join(str(title or "").strip().lower().split())
    c = " ".join(str(content or "").strip().split())
    base = f"{t}\n{c}".strip()
    if len(base) > 8000:
        base = base[:8000]
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()


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


def _extract_items(xml_text: str) -> tuple[str | None, list[RSSItem]]:
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
        rss_items: list[RSSItem] = []
        for child in list(channel):
            if _local_name(child.tag) != "item":
                continue
            title = _find_first_text(child, {"title"})
            link = _find_first_text(child, {"link"})
            summary = _find_first_text(child, {"description", "summary"})
            content = _find_first_text(child, {"encoded", "content"})
            author = _find_first_text(child, {"author", "creator"})
            published = _find_first_text(child, {"pubDate", "published"})
            rss_items.append(
                {
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "content": content,
                    "author": author,
                    "published": published,
                }
            )
        return feed_title, rss_items

    if root_name == "feed":
        feed_title = _find_first_text(root, {"title"})
        atom_items: list[RSSItem] = []
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

            atom_items.append(
                {
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "content": content,
                    "author": author_name,
                    "published": published,
                }
            )
        return feed_title, atom_items

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

    @staticmethod
    async def _load_enabled_sources(db: AsyncSession) -> list[NewsSource]:
        res = await db.execute(
            select(NewsSource)
            .where(NewsSource.is_enabled == True)
            .where(NewsSource.source_type == "rss")
            .order_by(NewsSource.id.asc())
        )
        return list(res.scalars().all())

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

    async def run_once(self, db: AsyncSession, *, source_id: int | None = None) -> dict[str, int]:
        sources: list[NewsSource] = []
        if source_id is not None:
            res = await db.execute(select(NewsSource).where(NewsSource.id == int(source_id)))
            s = res.scalar_one_or_none()
            if s is not None:
                sources = [s]
        else:
            sources = await self._load_enabled_sources(db)

        env_specs = self._parse_feed_specs() if not sources else []

        if (not sources) and (not env_specs):
            return {"feeds": 0, "fetched": 0, "inserted": 0, "skipped": 0, "errors": 0}

        fetched_total = 0
        inserted_total = 0
        skipped_total = 0
        errors_total = 0

        default_timeout = float(os.getenv("RSS_FETCH_TIMEOUT_SECONDS", "20").strip() or "20")
        default_max_items_per_feed = int(os.getenv("RSS_MAX_ITEMS_PER_FEED", "20").strip() or "20")

        fetch_retries: int = int(os.getenv("RSS_FETCH_RETRIES", "0").strip() or "0")
        fetch_backoff_seconds: float = float(os.getenv("RSS_FETCH_RETRY_BACKOFF_SECONDS", "0.5").strip() or "0.5")

        dedupe_strategy = str(os.getenv("NEWS_DEDUPE_STRATEGY", "url_only") or "url_only").strip().lower()
        use_hash_dedupe = dedupe_strategy in {"url_hash", "hash", "url+hash"}

        hash_duplicate_action = str(os.getenv("NEWS_DEDUPE_HASH_DUPLICATE_ACTION", "skip") or "skip").strip().lower()
        if hash_duplicate_action not in {"skip", "pending"}:
            hash_duplicate_action = "skip"

        feed_jobs: list[tuple[int | None, str | None, str, str | None, str | None, float, int]] = []
        for s in sources:
            feed_url = str(getattr(s, "feed_url", "") or "").strip()
            if not feed_url:
                continue
            timeout = float(getattr(s, "fetch_timeout_seconds", None) or default_timeout)
            max_items = int(getattr(s, "max_items_per_feed", None) or default_max_items_per_feed)
            feed_jobs.append(
                (
                    int(s.id),
                    str(getattr(s, "name", "") or "").strip() or None,
                    feed_url,
                    str(getattr(s, "site", None) or "").strip() or None,
                    str(getattr(s, "category", None) or "").strip() or None,
                    timeout,
                    max_items,
                )
            )

        for feed_url, site_override, category_override in env_specs:
            feed_jobs.append(
                (
                    None,
                    None,
                    str(feed_url).strip(),
                    site_override,
                    category_override,
                    default_timeout,
                    default_max_items_per_feed,
                )
            )

        seen_urls: set[str] = set()
        timeout_all = max([j[5] for j in feed_jobs] + [default_timeout])

        async with httpx.AsyncClient(timeout=timeout_all, follow_redirects=True) as client:
            for job_source_id, job_source_name, feed_url, site_override, category_override, _timeout, max_items in feed_jobs:
                started_at = datetime.now()
                run = NewsIngestRun(
                    source_id=int(job_source_id) if job_source_id is not None else None,
                    source_name=job_source_name,
                    feed_url=_truncate(feed_url, 500),
                    status="running",
                    fetched=0,
                    inserted=0,
                    skipped=0,
                    errors=0,
                    last_error=None,
                    started_at=started_at,
                    finished_at=None,
                )
                db.add(run)
                await db.flush()

                fetched = 0
                inserted = 0
                skipped = 0
                errors = 0

                try:
                    resp: httpx.Response | None = None
                    last_exc: Exception | None = None
                    for attempt in range(max(0, int(fetch_retries)) + 1):
                        try:
                            resp2 = await client.get(feed_url)
                            resp = resp2
                            if int(resp2.status_code) == 200:
                                break

                            retryable_statuses: set[int] = {408, 429, 500, 502, 503, 504}
                            if (
                                attempt < int(fetch_retries)
                                and int(resp2.status_code) in retryable_statuses
                                and float(fetch_backoff_seconds) > 0
                            ):
                                attempt_i: int = int(attempt)
                                backoff: float = float(fetch_backoff_seconds)
                                delay: float = backoff * pow(2.0, attempt_i)
                                await asyncio.sleep(delay)
                                continue
                            break
                        except Exception as ex:
                            last_exc = ex
                            resp = None
                            if attempt < int(fetch_retries) and float(fetch_backoff_seconds) > 0:
                                attempt_i2: int = int(attempt)
                                backoff2: float = float(fetch_backoff_seconds)
                                delay2: float = backoff2 * pow(2.0, attempt_i2)
                                await asyncio.sleep(delay2)
                                continue
                            raise

                    if resp is None:
                        raise last_exc if last_exc is not None else RuntimeError("RSS fetch failed")
                    if int(resp.status_code) != 200:
                        errors += 1
                        run.status = "failed"
                        run.errors = int(errors)
                        run.last_error = _truncate(f"HTTP {int(resp.status_code)}", 800)
                        continue

                    feed_title, items = _extract_items(resp.text)
                    fetched += 1
                    site = self._normalize_site(feed_url, site_override)
                    category = self._normalize_category(category_override)

                    candidates: list[RSSItem] = []
                    urls_to_check: set[str] = set()
                    for item in items[: max(0, int(max_items))]:
                        link_raw = str(item.get("link", "") or "").strip()
                        link_norm = _normalize_url(link_raw)
                        if not link_norm:
                            skipped += 1
                            continue
                        if link_norm in seen_urls:
                            skipped += 1
                            continue
                        seen_urls.add(link_norm)
                        urls_to_check.add(link_norm)
                        if link_raw and (link_raw != link_norm):
                            urls_to_check.add(link_raw)
                        cand: RSSItem = {k: v for k, v in item.items()}
                        cand["category"] = category
                        cand["_feed_title"] = feed_title
                        cand["_site"] = site or ""
                        cand["_link_raw"] = link_raw
                        cand["_link_norm"] = link_norm
                        candidates.append(cand)

                    existing_urls: set[str] = set()
                    if urls_to_check:
                        res = await db.execute(select(News.source_url).where(News.source_url.in_(list(urls_to_check))))
                        existing_urls = {str(u).strip() for u in res.scalars().all() if u}

                    existing_hashes: set[str] = set()
                    if use_hash_dedupe and candidates:
                        hashes: list[str] = []
                        for it in candidates:
                            link_norm = str(it.get("_link_norm", "") or "").strip()
                            title_for_hash = str(it.get("title", "") or "").strip() or link_norm
                            summary_for_hash = str(it.get("summary", "") or "").strip()
                            content_for_hash = str(it.get("content", "") or "").strip() or summary_for_hash
                            if not content_for_hash:
                                content_for_hash = title_for_hash
                            hashes.append(
                                _make_dedupe_hash(title=title_for_hash, content=content_for_hash, source_url=link_norm)
                            )
                        res2 = await db.execute(select(News.dedupe_hash).where(News.dedupe_hash.in_(hashes)))
                        existing_hashes = {str(h).strip() for h in res2.scalars().all() if h}

                    seen_hashes: set[str] = set()

                    to_create: list[News] = []
                    for item in candidates:
                        link = str(item.get("_link_norm", "") or "").strip() or str(item.get("link", "") or "").strip()
                        link = _normalize_url(link)
                        link_raw = str(item.get("_link_raw", "") or "").strip()
                        if (link in existing_urls) or (link_raw and (link_raw in existing_urls)):
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
                        category_value = str(item.get("category", "general") or "general").strip().lower() or "general"
                        source_site = _truncate(str(item.get("_site", "") or "").strip(), 100)
                        source = _truncate(str(item.get("_feed_title", "") or "").strip(), 100) or source_site

                        review_reason: str | None = None

                        dedupe_hash: str | None = None
                        if use_hash_dedupe:
                            dh = _make_dedupe_hash(title=title, content=content, source_url=link)
                            if dh in seen_hashes:
                                skipped += 1
                                continue

                            is_hash_dup = dh in existing_hashes
                            if is_hash_dup and hash_duplicate_action == "skip":
                                skipped += 1
                                continue

                            seen_hashes.add(dh)
                            dedupe_hash = dh
                            if is_hash_dup and hash_duplicate_action == "pending":
                                review_reason = _truncate(f"dedupe_hash_duplicate:{str(dh)[:10]}", 200)

                        news = News(
                            title=title,
                            summary=summary,
                            content=content,
                            cover_image=None,
                            category=category_value,
                            source=source,
                            source_url=_truncate(link, 500),
                            dedupe_hash=_truncate(dedupe_hash, 40) if dedupe_hash else None,
                            source_site=source_site,
                            author=author,
                            is_top=False,
                            is_published=False,
                            review_status="pending",
                            review_reason=review_reason,
                            reviewed_at=None,
                            published_at=None,
                            scheduled_publish_at=None,
                            scheduled_unpublish_at=None,
                        )
                        to_create.append(news)

                    if to_create:
                        db.add_all(to_create)
                        await db.flush()
                        inserted += len(to_create)

                    run.status = "success"
                except Exception as e:
                    errors += 1
                    run.status = "failed"
                    run.last_error = _truncate(str(e or ""), 800)
                    logger.exception("RSS抓取失败 url=%s", feed_url)
                finally:
                    run.fetched = int(fetched)
                    run.inserted = int(inserted)
                    run.skipped = int(skipped)
                    run.errors = int(errors)
                    run.finished_at = datetime.now()

                    if job_source_id is not None:
                        src_res = await db.execute(select(NewsSource).where(NewsSource.id == int(job_source_id)))
                        src = src_res.scalar_one_or_none()
                        if src is not None:
                            src.last_run_at = run.finished_at
                            if run.status == "success":
                                src.last_success_at = run.finished_at
                                src.last_error = None
                                src.last_error_at = None
                            else:
                                src.last_error = run.last_error
                                src.last_error_at = run.finished_at

                    try:
                        await db.commit()
                    except Exception:
                        await db.rollback()
                        raise

                fetched_total += int(fetched)
                inserted_total += int(inserted)
                skipped_total += int(skipped)
                errors_total += int(errors)

        logger.info(
            "rss_ingest done feeds=%s fetched=%s inserted=%s skipped=%s errors=%s",
            len(feed_jobs),
            fetched_total,
            inserted_total,
            skipped_total,
            errors_total,
        )

        return {
            "feeds": len(feed_jobs),
            "fetched": fetched_total,
            "inserted": inserted_total,
            "skipped": skipped_total,
            "errors": errors_total,
        }


rss_ingest_service = RSSIngestService()
