"""News AI / dedupe related data cleanup script.

This script is intended for one-off operational cleanup in production.
It is safe by default (dry-run) and will only mutate data when --apply is used.

Typical usages:
- Dry run (recommended first):
  py backend/scripts/cleanup_news_ai_data.py

- Apply changes:
  py backend/scripts/cleanup_news_ai_data.py --apply

- Only cleanup specific items:
  py backend/scripts/cleanup_news_ai_data.py --apply --no-delete-orphan-annotations

Notes:
- This script only performs conservative cleanup:
  - Delete orphan NewsAIAnnotation rows (news_id points to missing news)
  - Set duplicate_of_news_id to NULL when it points to missing news
  - Optionally dedupe NewsAIAnnotation by news_id (keep newest)

- It does NOT merge/hide duplicate news items in product/UI.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database import AsyncSessionLocal, init_db
from app.models.news import News
from app.models.news_ai import NewsAIAnnotation


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cleanup historical News AI data")
    p.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to database (default: dry-run only)",
    )
    p.add_argument(
        "--delete-orphan-annotations",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Delete NewsAIAnnotation rows whose news_id does not exist (default: true)",
    )
    p.add_argument(
        "--null-invalid-duplicate-of",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Set duplicate_of_news_id=NULL when referenced news does not exist (default: true)",
    )
    p.add_argument(
        "--dedupe-annotations-by-news-id",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Dedupe NewsAIAnnotation rows by news_id, keep newest id (default: false)",
    )
    return p.parse_args()


async def _delete_orphan_annotations(db: AsyncSession, *, apply: bool) -> int:
    q = (
        select(func.count(NewsAIAnnotation.id))
        .select_from(NewsAIAnnotation)
        .outerjoin(News, News.id == NewsAIAnnotation.news_id)
        .where(News.id.is_(None))
    )
    cnt_res = await db.execute(q)
    cnt = int(cnt_res.scalar() or 0)
    if cnt <= 0:
        return 0

    if not apply:
        return cnt

    del_stmt = (
        delete(NewsAIAnnotation)
        .where(NewsAIAnnotation.id.in_(
            select(NewsAIAnnotation.id)
            .select_from(NewsAIAnnotation)
            .outerjoin(News, News.id == NewsAIAnnotation.news_id)
            .where(News.id.is_(None))
        ))
    )
    res = await db.execute(del_stmt)
    return int(getattr(res, "rowcount", 0) or 0)


async def _null_invalid_duplicate_of(db: AsyncSession, *, apply: bool) -> int:
    NewsAlias = aliased(News)

    q = (
        select(func.count(NewsAIAnnotation.id))
        .select_from(NewsAIAnnotation)
        .outerjoin(NewsAlias, NewsAlias.id == NewsAIAnnotation.duplicate_of_news_id)
        .where(NewsAIAnnotation.duplicate_of_news_id.is_not(None))
        .where(NewsAlias.id.is_(None))
    )
    cnt_res = await db.execute(q)
    cnt = int(cnt_res.scalar() or 0)
    if cnt <= 0:
        return 0

    if not apply:
        return cnt

    upd = (
        update(NewsAIAnnotation)
        .where(NewsAIAnnotation.id.in_(
            select(NewsAIAnnotation.id)
            .select_from(NewsAIAnnotation)
            .outerjoin(NewsAlias, NewsAlias.id == NewsAIAnnotation.duplicate_of_news_id)
            .where(NewsAIAnnotation.duplicate_of_news_id.is_not(None))
            .where(NewsAlias.id.is_(None))
        ))
        .values(duplicate_of_news_id=None)
    )
    res = await db.execute(upd)
    return int(getattr(res, "rowcount", 0) or 0)


async def _dedupe_annotations_by_news_id(db: AsyncSession, *, apply: bool) -> int:
    # Find news_id that has multiple annotations
    dup_news_ids_res = await db.execute(
        select(NewsAIAnnotation.news_id)
        .group_by(NewsAIAnnotation.news_id)
        .having(func.count(NewsAIAnnotation.id) > 1)
    )
    news_ids = [int(x) for x in dup_news_ids_res.scalars().all()]
    if not news_ids:
        return 0

    # For each news_id keep the newest (max id), delete others.
    total_to_delete = 0
    ids_to_delete: list[int] = []

    for nid in news_ids:
        ids_res = await db.execute(
            select(NewsAIAnnotation.id)
            .where(NewsAIAnnotation.news_id == int(nid))
            .order_by(NewsAIAnnotation.id.asc())
        )
        ids = [int(x) for x in ids_res.scalars().all()]
        if len(ids) <= 1:
            continue
        # keep last
        to_del = ids[:-1]
        total_to_delete += len(to_del)
        ids_to_delete.extend(to_del)

    if total_to_delete <= 0:
        return 0

    if not apply:
        return total_to_delete

    res = await db.execute(delete(NewsAIAnnotation).where(NewsAIAnnotation.id.in_(ids_to_delete)))
    return int(getattr(res, "rowcount", 0) or 0)


async def _run() -> int:
    args = _parse_args()
    apply = bool(args.apply)

    print("=" * 72)
    print("News AI cleanup")
    print("mode:", "APPLY" if apply else "DRY-RUN")
    print("delete_orphan_annotations:", bool(args.delete_orphan_annotations))
    print("null_invalid_duplicate_of:", bool(args.null_invalid_duplicate_of))
    print("dedupe_annotations_by_news_id:", bool(args.dedupe_annotations_by_news_id))
    print("=" * 72)

    await init_db()

    async with AsyncSessionLocal() as db:
        changed = 0

        if bool(args.delete_orphan_annotations):
            cnt = await _delete_orphan_annotations(db, apply=apply)
            print("orphan NewsAIAnnotation:", cnt, "(deleted)" if apply else "(would delete)")
            changed += int(cnt)

        if bool(args.null_invalid_duplicate_of):
            cnt = await _null_invalid_duplicate_of(db, apply=apply)
            print("invalid duplicate_of_news_id:", cnt, "(updated)" if apply else "(would update)")
            changed += int(cnt)

        if bool(args.dedupe_annotations_by_news_id):
            cnt = await _dedupe_annotations_by_news_id(db, apply=apply)
            print("duplicate annotations by news_id:", cnt, "(deleted)" if apply else "(would delete)")
            changed += int(cnt)

        if apply:
            await db.commit()
        else:
            await db.rollback()

    print("=" * 72)
    print("done, total changes:", int(changed), "(applied)" if apply else "(dry-run)")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
