"""Cleanup E2E / test data.

This script is intended for local/dev environments when E2E tests or manual tests
leave residual data in the database.

- Safe by default (dry-run)
- Only mutates data when --apply is used

Typical usage:
  py backend/scripts/cleanup_e2e_data.py
  py backend/scripts/cleanup_e2e_data.py --apply

"""

from __future__ import annotations

import argparse
import asyncio
import os
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if os.environ.get("DEBUG") is None:
    os.environ["DEBUG"] = "1"

logger_sqlalchemy_engine = logging.getLogger("sqlalchemy.engine")
logger_sqlalchemy_engine_engine = logging.getLogger("sqlalchemy.engine.Engine")

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, init_db, engine
from app.models.calendar import CalendarReminder
from app.models.consultation import ChatMessage, Consultation
from app.models.document import GeneratedDocument
from app.models.forum import Comment, CommentLike, Post, PostFavorite, PostLike, PostReaction
from app.models.news import (
    News,
    NewsComment,
    NewsFavorite,
    NewsSubscription,
    NewsTopic,
    NewsTopicItem,
    NewsViewHistory,
)
from app.models.news_ai import NewsAIAnnotation
from app.models.news_workbench import NewsAIGeneration, NewsLinkCheck, NewsVersion
from app.models.notification import Notification
from app.models.payment import BalanceTransaction, PaymentOrder, UserBalance
from app.models.system import AdminLog, SearchHistory, SystemConfig, UserActivity
from app.models.user import User
from app.models.lawfirm import Lawyer, LawyerConsultation, LawyerReview, LawyerVerification


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cleanup residual E2E / test data")
    p.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to database (default: dry-run only)",
    )
    p.add_argument(
        "--token",
        action="append",
        default=["e2e_"],
        help="Token to match (case-insensitive). Can be specified multiple times. Default: e2e_",
    )
    p.add_argument(
        "--delete-news",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Delete News + related rows matched by token (default: true)",
    )
    p.add_argument(
        "--delete-topics",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Delete NewsTopic + items matched by token (default: true)",
    )
    p.add_argument(
        "--delete-consultations",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Delete Consultation/ChatMessage matched by token (default: true)",
    )
    p.add_argument(
        "--delete-forum",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Delete forum Post/Comment etc matched by token (default: true)",
    )
    p.add_argument(
        "--delete-users",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Delete E2E users (username/email starts with e2e_) and related rows (default: true)",
    )
    p.add_argument(
        "--delete-analytics",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Delete SearchHistory/UserActivity matched by token or e2e users (default: true)",
    )
    p.add_argument(
        "--verbose-sql",
        action="store_true",
        help="Print SQL statements (default: off)",
    )
    return p.parse_args()


def _norm_tokens(tokens: list[str]) -> list[str]:
    out: list[str] = []
    for t in tokens:
        cleaned = str(t or "").strip().lower()
        if not cleaned:
            continue
        if cleaned in out:
            continue
        out.append(cleaned)
    return out


def _contains(col, token: str):
    # Case-insensitive contains (SQLite friendly)
    return func.lower(func.coalesce(col, "")).like(f"%{token}%")


def _startswith(col, token: str):
    return func.lower(func.coalesce(col, "")).like(f"{token}%")


async def _scalar_int(db: AsyncSession, stmt) -> int:
    res = await db.execute(stmt)
    return int(res.scalar() or 0)


async def _fetch_int_list(db: AsyncSession, stmt) -> list[int]:
    res = await db.execute(stmt)
    return [int(x) for x in res.scalars().all()]


async def _exec_delete(db: AsyncSession, stmt) -> int:
    res = await db.execute(stmt)
    return int(getattr(res, "rowcount", 0) or 0)


async def _run() -> int:
    args = _parse_args()
    apply = bool(args.apply)
    tokens = _norm_tokens(list(args.token or []))

    if not bool(args.verbose_sql):
        logger_sqlalchemy_engine.setLevel(logging.WARNING)
        logger_sqlalchemy_engine_engine.setLevel(logging.WARNING)
    engine.echo = bool(args.verbose_sql)
    try:
        engine.sync_engine.echo = bool(args.verbose_sql)
    except Exception:
        pass

    print("=" * 72)
    print("cleanup_e2e_data")
    print("mode:", "APPLY" if apply else "DRY-RUN")
    print("tokens:", tokens)
    print("delete_news:", bool(args.delete_news))
    print("delete_topics:", bool(args.delete_topics))
    print("delete_consultations:", bool(args.delete_consultations))
    print("delete_forum:", bool(args.delete_forum))
    print("delete_users:", bool(args.delete_users))
    print("delete_analytics:", bool(args.delete_analytics))
    print("=" * 72)

    await init_db()

    async with AsyncSessionLocal() as db:
        changed = 0

        user_ids: list[int] = []
        if bool(args.delete_users):
            user_match = or_(
                _startswith(User.username, "e2e_"),
                _startswith(User.email, "e2e_"),
                _startswith(User.nickname, "e2e_"),
            )
            user_ids = await _fetch_int_list(db, select(User.id).where(user_match))

        news_ids: list[int] = []
        if bool(args.delete_news):
            conds = []
            for t in tokens:
                conds.extend(
                    [
                        _contains(News.title, t),
                        _contains(News.content, t),
                        _contains(News.summary, t),
                        _contains(News.source, t),
                        _contains(News.author, t),
                    ]
                )
            # common E2E marker used by tests
            conds.extend([
                func.lower(func.coalesce(News.source, "")) == "e2e",
                func.lower(func.coalesce(News.author, "")) == "e2e",
            ])
            news_ids = await _fetch_int_list(db, select(News.id).where(or_(*conds)))

        topic_ids: list[int] = []
        if bool(args.delete_topics):
            conds = []
            for t in tokens:
                conds.extend(
                    [
                        _contains(NewsTopic.title, t),
                        _contains(NewsTopic.description, t),
                        _contains(NewsTopic.auto_keyword, t),
                    ]
                )
            topic_ids = await _fetch_int_list(db, select(NewsTopic.id).where(or_(*conds)))

        consultation_ids: list[int] = []
        if bool(args.delete_consultations):
            conds = []
            for t in tokens:
                conds.append(_startswith(Consultation.session_id, t))
            # E2E mock stream uses session_id like e2e_<uuid>
            conds.append(_startswith(Consultation.session_id, "e2e_"))
            if user_ids:
                conds.append(Consultation.user_id.in_(user_ids))
            consultation_ids = await _fetch_int_list(db, select(Consultation.id).where(or_(*conds)))

        post_ids: list[int] = []
        if bool(args.delete_forum):
            conds = []
            for t in tokens:
                conds.extend([
                    _contains(Post.title, t),
                    _contains(Post.content, t),
                ])
            if user_ids:
                conds.append(Post.user_id.in_(user_ids))
            if conds:
                post_ids = await _fetch_int_list(db, select(Post.id).where(or_(*conds)))

        # --- DRY-RUN counts ---
        print("matched users:", len(user_ids))
        print("matched news:", len(news_ids))
        print("matched topics:", len(topic_ids))
        print("matched consultations:", len(consultation_ids))
        print("matched forum posts:", len(post_ids))

        if not apply:
            # Estimate affected rows (best-effort)
            if news_ids:
                approx = 0
                approx += await _scalar_int(db, select(func.count(NewsAIAnnotation.id)).where(NewsAIAnnotation.news_id.in_(news_ids)))
                approx += await _scalar_int(db, select(func.count(NewsComment.id)).where(NewsComment.news_id.in_(news_ids)))
                approx += await _scalar_int(db, select(func.count(NewsFavorite.id)).where(NewsFavorite.news_id.in_(news_ids)))
                approx += await _scalar_int(db, select(func.count(NewsViewHistory.id)).where(NewsViewHistory.news_id.in_(news_ids)))
                approx += await _scalar_int(db, select(func.count(NewsTopicItem.id)).where(NewsTopicItem.news_id.in_(news_ids)))
                approx += await _scalar_int(db, select(func.count(NewsVersion.id)).where(NewsVersion.news_id.in_(news_ids)))
                approx += await _scalar_int(db, select(func.count(NewsAIGeneration.id)).where(NewsAIGeneration.news_id.in_(news_ids)))
                approx += await _scalar_int(db, select(func.count(NewsLinkCheck.id)).where(NewsLinkCheck.news_id.in_(news_ids)))
                print("news-related rows (approx):", approx)

            if topic_ids:
                cnt_items = await _scalar_int(db, select(func.count(NewsTopicItem.id)).where(NewsTopicItem.topic_id.in_(topic_ids)))
                print("topic items:", cnt_items)

            if consultation_ids:
                cnt_msgs = await _scalar_int(db, select(func.count(ChatMessage.id)).where(ChatMessage.consultation_id.in_(consultation_ids)))
                print("consultation messages:", cnt_msgs)

            if post_ids:
                cnt_comments = await _scalar_int(db, select(func.count(Comment.id)).where(Comment.post_id.in_(post_ids)))
                cnt_likes = await _scalar_int(db, select(func.count(PostLike.id)).where(PostLike.post_id.in_(post_ids)))
                cnt_favs = await _scalar_int(db, select(func.count(PostFavorite.id)).where(PostFavorite.post_id.in_(post_ids)))
                cnt_reactions = await _scalar_int(db, select(func.count(PostReaction.id)).where(PostReaction.post_id.in_(post_ids)))
                print("forum-related rows (approx):", cnt_comments + cnt_likes + cnt_favs + cnt_reactions)

            if user_ids and bool(args.delete_users):
                cnt_notif = await _scalar_int(
                    db,
                    select(func.count(Notification.id)).where(
                        or_(Notification.user_id.in_(user_ids), Notification.related_user_id.in_(user_ids))
                    ),
                )
                cnt_forum_comment_likes_by_user = await _scalar_int(
                    db, select(func.count(CommentLike.id)).where(CommentLike.user_id.in_(user_ids))
                )
                cnt_forum_comments_by_user = await _scalar_int(
                    db, select(func.count(Comment.id)).where(Comment.user_id.in_(user_ids))
                )
                cnt_forum_post_likes_by_user = await _scalar_int(
                    db, select(func.count(PostLike.id)).where(PostLike.user_id.in_(user_ids))
                )
                cnt_forum_post_favs_by_user = await _scalar_int(
                    db, select(func.count(PostFavorite.id)).where(PostFavorite.user_id.in_(user_ids))
                )
                cnt_forum_post_reactions_by_user = await _scalar_int(
                    db, select(func.count(PostReaction.id)).where(PostReaction.user_id.in_(user_ids))
                )

                cnt_consultations_by_user = await _scalar_int(
                    db, select(func.count(Consultation.id)).where(Consultation.user_id.in_(user_ids))
                )

                cnt_news_comments_by_user = await _scalar_int(
                    db, select(func.count(NewsComment.id)).where(NewsComment.user_id.in_(user_ids))
                )
                cnt_news_favorites_by_user = await _scalar_int(
                    db, select(func.count(NewsFavorite.id)).where(NewsFavorite.user_id.in_(user_ids))
                )
                cnt_news_views_by_user = await _scalar_int(
                    db, select(func.count(NewsViewHistory.id)).where(NewsViewHistory.user_id.in_(user_ids))
                )
                cnt_news_versions_by_user = await _scalar_int(
                    db, select(func.count(NewsVersion.id)).where(NewsVersion.created_by.in_(user_ids))
                )
                cnt_news_ai_generations_by_user = await _scalar_int(
                    db, select(func.count(NewsAIGeneration.id)).where(NewsAIGeneration.user_id.in_(user_ids))
                )
                cnt_news_link_checks_by_user = await _scalar_int(
                    db, select(func.count(NewsLinkCheck.id)).where(NewsLinkCheck.user_id.in_(user_ids))
                )

                cnt_documents_by_user = await _scalar_int(
                    db, select(func.count(GeneratedDocument.id)).where(GeneratedDocument.user_id.in_(user_ids))
                )
                cnt_reminders_by_user = await _scalar_int(
                    db, select(func.count(CalendarReminder.id)).where(CalendarReminder.user_id.in_(user_ids))
                )

                cnt_orders = await _scalar_int(db, select(func.count(PaymentOrder.id)).where(PaymentOrder.user_id.in_(user_ids)))
                cnt_bal = await _scalar_int(db, select(func.count(UserBalance.id)).where(UserBalance.user_id.in_(user_ids)))
                cnt_tx = await _scalar_int(db, select(func.count(BalanceTransaction.id)).where(BalanceTransaction.user_id.in_(user_ids)))
                cnt_logs = await _scalar_int(db, select(func.count(AdminLog.id)).where(AdminLog.user_id.in_(user_ids)))
                cnt_cfg = await _scalar_int(db, select(func.count(SystemConfig.id)).where(SystemConfig.updated_by.in_(user_ids)))
                print(
                    "user-related rows (approx):",
                    cnt_notif
                    + cnt_forum_comment_likes_by_user
                    + cnt_forum_comments_by_user
                    + cnt_forum_post_likes_by_user
                    + cnt_forum_post_favs_by_user
                    + cnt_forum_post_reactions_by_user
                    + cnt_consultations_by_user
                    + cnt_news_comments_by_user
                    + cnt_news_favorites_by_user
                    + cnt_news_views_by_user
                    + cnt_news_versions_by_user
                    + cnt_news_ai_generations_by_user
                    + cnt_news_link_checks_by_user
                    + cnt_documents_by_user
                    + cnt_reminders_by_user
                    + cnt_orders
                    + cnt_bal
                    + cnt_tx
                    + cnt_logs
                    + cnt_cfg,
                )

            if bool(args.delete_analytics):
                conds = []
                for t in tokens:
                    conds.append(_contains(SearchHistory.keyword, t))
                if user_ids:
                    conds.append(SearchHistory.user_id.in_(user_ids))
                if conds:
                    cnt_hist = await _scalar_int(db, select(func.count(SearchHistory.id)).where(or_(*conds)))
                else:
                    cnt_hist = 0

                aconds = []
                for t in tokens:
                    aconds.append(_contains(UserActivity.session_id, t))
                    aconds.append(_contains(UserActivity.target, t))
                if user_ids:
                    aconds.append(UserActivity.user_id.in_(user_ids))
                cnt_act = await _scalar_int(db, select(func.count(UserActivity.id)).where(or_(*aconds))) if aconds else 0
                print("analytics rows (approx):", cnt_hist + cnt_act)

            await db.rollback()
            print("=" * 72)
            print("dry-run done (no changes applied)")
            return 0

        # --- APPLY deletion order ---
        # Forum first (often references users)
        if post_ids and bool(args.delete_forum):
            comment_ids = await _fetch_int_list(db, select(Comment.id).where(Comment.post_id.in_(post_ids)))
            if comment_ids:
                changed += await _exec_delete(db, delete(CommentLike).where(CommentLike.comment_id.in_(comment_ids)))
            changed += await _exec_delete(db, delete(Comment).where(Comment.post_id.in_(post_ids)))
            changed += await _exec_delete(db, delete(PostLike).where(PostLike.post_id.in_(post_ids)))
            changed += await _exec_delete(db, delete(PostFavorite).where(PostFavorite.post_id.in_(post_ids)))
            changed += await _exec_delete(db, delete(PostReaction).where(PostReaction.post_id.in_(post_ids)))
            changed += await _exec_delete(db, delete(Post).where(Post.id.in_(post_ids)))

        # Consultations
        if consultation_ids and bool(args.delete_consultations):
            changed += await _exec_delete(db, delete(ChatMessage).where(ChatMessage.consultation_id.in_(consultation_ids)))
            changed += await _exec_delete(db, delete(Consultation).where(Consultation.id.in_(consultation_ids)))

        # News topics (items first)
        if topic_ids and bool(args.delete_topics):
            changed += await _exec_delete(db, delete(NewsTopicItem).where(NewsTopicItem.topic_id.in_(topic_ids)))
            changed += await _exec_delete(db, delete(NewsTopic).where(NewsTopic.id.in_(topic_ids)))

        # News and related
        if news_ids and bool(args.delete_news):
            changed += await _exec_delete(db, delete(NewsTopicItem).where(NewsTopicItem.news_id.in_(news_ids)))
            changed += await _exec_delete(
                db,
                delete(NewsAIAnnotation).where(
                    or_(
                        NewsAIAnnotation.news_id.in_(news_ids),
                        NewsAIAnnotation.duplicate_of_news_id.in_(news_ids),
                    )
                ),
            )
            changed += await _exec_delete(db, delete(NewsComment).where(NewsComment.news_id.in_(news_ids)))
            changed += await _exec_delete(db, delete(NewsFavorite).where(NewsFavorite.news_id.in_(news_ids)))
            changed += await _exec_delete(db, delete(NewsViewHistory).where(NewsViewHistory.news_id.in_(news_ids)))
            changed += await _exec_delete(db, delete(NewsVersion).where(NewsVersion.news_id.in_(news_ids)))
            changed += await _exec_delete(db, delete(NewsAIGeneration).where(NewsAIGeneration.news_id.in_(news_ids)))
            changed += await _exec_delete(db, delete(NewsLinkCheck).where(NewsLinkCheck.news_id.in_(news_ids)))
            changed += await _exec_delete(db, delete(News).where(News.id.in_(news_ids)))

        # Analytics
        if bool(args.delete_analytics):
            hist_conds = []
            for t in tokens:
                hist_conds.append(_contains(SearchHistory.keyword, t))
            if user_ids:
                hist_conds.append(SearchHistory.user_id.in_(user_ids))
            if hist_conds:
                changed += await _exec_delete(db, delete(SearchHistory).where(or_(*hist_conds)))

            act_conds = []
            for t in tokens:
                act_conds.append(_contains(UserActivity.session_id, t))
                act_conds.append(_contains(UserActivity.target, t))
            if user_ids:
                act_conds.append(UserActivity.user_id.in_(user_ids))
            if act_conds:
                changed += await _exec_delete(db, delete(UserActivity).where(or_(*act_conds)))

        # Users (and their related rows)
        if user_ids and bool(args.delete_users):
            # Forum interactions by user
            changed += await _exec_delete(db, delete(CommentLike).where(CommentLike.user_id.in_(user_ids)))
            changed += await _exec_delete(db, delete(PostLike).where(PostLike.user_id.in_(user_ids)))
            changed += await _exec_delete(db, delete(PostFavorite).where(PostFavorite.user_id.in_(user_ids)))
            changed += await _exec_delete(db, delete(PostReaction).where(PostReaction.user_id.in_(user_ids)))

            # Delete posts authored by E2E users (and their related rows) so users can be deleted safely.
            user_post_ids = await _fetch_int_list(db, select(Post.id).where(Post.user_id.in_(user_ids)))
            if user_post_ids:
                user_post_comment_ids = await _fetch_int_list(
                    db, select(Comment.id).where(Comment.post_id.in_(user_post_ids))
                )
                if user_post_comment_ids:
                    changed += await _exec_delete(
                        db, delete(CommentLike).where(CommentLike.comment_id.in_(user_post_comment_ids))
                    )
                changed += await _exec_delete(db, delete(Comment).where(Comment.post_id.in_(user_post_ids)))
                changed += await _exec_delete(db, delete(PostLike).where(PostLike.post_id.in_(user_post_ids)))
                changed += await _exec_delete(db, delete(PostFavorite).where(PostFavorite.post_id.in_(user_post_ids)))
                changed += await _exec_delete(db, delete(PostReaction).where(PostReaction.post_id.in_(user_post_ids)))
                changed += await _exec_delete(db, delete(Post).where(Post.id.in_(user_post_ids)))

            # Remaining comments authored by E2E users (could be on other users' posts)
            user_comment_ids = await _fetch_int_list(db, select(Comment.id).where(Comment.user_id.in_(user_ids)))
            if user_comment_ids:
                changed += await _exec_delete(
                    db, delete(CommentLike).where(CommentLike.comment_id.in_(user_comment_ids))
                )
                changed += await _exec_delete(db, delete(Comment).where(Comment.id.in_(user_comment_ids)))

            # Consultations by user
            user_consultation_ids = await _fetch_int_list(
                db, select(Consultation.id).where(Consultation.user_id.in_(user_ids))
            )
            if user_consultation_ids:
                changed += await _exec_delete(
                    db,
                    delete(ChatMessage).where(ChatMessage.consultation_id.in_(user_consultation_ids)),
                )
                changed += await _exec_delete(
                    db, delete(Consultation).where(Consultation.id.in_(user_consultation_ids))
                )

            # News interactions by user
            changed += await _exec_delete(db, delete(NewsComment).where(NewsComment.user_id.in_(user_ids)))
            changed += await _exec_delete(db, delete(NewsFavorite).where(NewsFavorite.user_id.in_(user_ids)))
            changed += await _exec_delete(db, delete(NewsViewHistory).where(NewsViewHistory.user_id.in_(user_ids)))

            # News workbench logs by user
            changed += await _exec_delete(db, delete(NewsVersion).where(NewsVersion.created_by.in_(user_ids)))
            changed += await _exec_delete(db, delete(NewsAIGeneration).where(NewsAIGeneration.user_id.in_(user_ids)))
            changed += await _exec_delete(db, delete(NewsLinkCheck).where(NewsLinkCheck.user_id.in_(user_ids)))

            # User-created content
            changed += await _exec_delete(db, delete(GeneratedDocument).where(GeneratedDocument.user_id.in_(user_ids)))
            changed += await _exec_delete(db, delete(CalendarReminder).where(CalendarReminder.user_id.in_(user_ids)))

            changed += await _exec_delete(
                db,
                delete(Notification).where(
                    or_(Notification.user_id.in_(user_ids), Notification.related_user_id.in_(user_ids))
                ),
            )

            # news subscriptions (owned by user)
            changed += await _exec_delete(db, delete(NewsSubscription).where(NewsSubscription.user_id.in_(user_ids)))

            # law firm domain
            changed += await _exec_delete(db, delete(LawyerConsultation).where(LawyerConsultation.user_id.in_(user_ids)))
            changed += await _exec_delete(db, delete(LawyerReview).where(LawyerReview.user_id.in_(user_ids)))
            changed += await _exec_delete(
                db,
                delete(LawyerVerification).where(
                    or_(
                        LawyerVerification.user_id.in_(user_ids),
                        LawyerVerification.reviewed_by.in_(user_ids),
                    )
                ),
            )
            changed += await _exec_delete(db, delete(Lawyer).where(Lawyer.user_id.in_(user_ids)))

            # system & admin
            changed += await _exec_delete(db, delete(SearchHistory).where(SearchHistory.user_id.in_(user_ids)))
            changed += await _exec_delete(db, delete(UserActivity).where(UserActivity.user_id.in_(user_ids)))
            changed += await _exec_delete(db, delete(AdminLog).where(AdminLog.user_id.in_(user_ids)))
            changed += await _exec_delete(db, delete(SystemConfig).where(SystemConfig.updated_by.in_(user_ids)))

            # payments
            changed += await _exec_delete(db, delete(BalanceTransaction).where(BalanceTransaction.user_id.in_(user_ids)))
            changed += await _exec_delete(db, delete(UserBalance).where(UserBalance.user_id.in_(user_ids)))
            changed += await _exec_delete(db, delete(PaymentOrder).where(PaymentOrder.user_id.in_(user_ids)))

            # finally users
            changed += await _exec_delete(db, delete(User).where(User.id.in_(user_ids)))

        await db.commit()

    print("=" * 72)
    print("done, total changes:", int(changed), "(applied)")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
