"""add news workbench tables

Revision ID: b9c7a0f3d2a1
Revises: 
Create Date: 2025-12-27

"""

from __future__ import annotations

from typing import Iterable

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9c7a0f3d2a1"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def _get_index_names(insp: sa.Inspector, table_name: str) -> set[str]:
    try:
        indexes = insp.get_indexes(table_name)
    except Exception:
        return set()
    return {str(ix.get("name") or "") for ix in indexes if ix.get("name")}


def _ensure_indexes(table_name: str, index_specs: Iterable[tuple[str, list[str], bool]]) -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = _get_index_names(insp, table_name)

    for name, cols, unique in index_specs:
        if name in existing:
            continue
        op.create_index(name, table_name, cols, unique=bool(unique))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("news_versions"):
        op.create_table(
            "news_versions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("news_id", sa.Integer(), sa.ForeignKey("news.id"), nullable=False),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("reason", sa.String(length=200), nullable=True),
            sa.Column("snapshot_json", sa.Text(), nullable=False),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        )

    _ensure_indexes(
        "news_versions",
        [
            ("ix_news_versions_news_id", ["news_id"], False),
            ("ix_news_versions_created_by", ["created_by"], False),
            ("ix_news_versions_created_at", ["created_at"], False),
            ("ix_news_versions_news_created", ["news_id", "created_at"], False),
        ],
    )

    if not insp.has_table("news_ai_generations"):
        op.create_table(
            "news_ai_generations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("news_id", sa.Integer(), sa.ForeignKey("news.id"), nullable=True),
            sa.Column("task_type", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=True),
            sa.Column("input_json", sa.Text(), nullable=False),
            sa.Column("output_json", sa.Text(), nullable=True),
            sa.Column("raw_output", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        )

    _ensure_indexes(
        "news_ai_generations",
        [
            ("ix_news_ai_generations_user_id", ["user_id"], False),
            ("ix_news_ai_generations_news_id", ["news_id"], False),
            ("ix_news_ai_generations_created_at", ["created_at"], False),
            ("ix_news_ai_generations_user_created", ["user_id", "created_at"], False),
            ("ix_news_ai_generations_news_created", ["news_id", "created_at"], False),
        ],
    )

    if not insp.has_table("news_link_checks"):
        op.create_table(
            "news_link_checks",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("run_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("news_id", sa.Integer(), sa.ForeignKey("news.id"), nullable=True),
            sa.Column("url", sa.String(length=800), nullable=False),
            sa.Column("final_url", sa.String(length=800), nullable=True),
            sa.Column("ok", sa.Boolean(), nullable=True),
            sa.Column("status_code", sa.Integer(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        )

    _ensure_indexes(
        "news_link_checks",
        [
            ("ix_news_link_checks_run_id", ["run_id"], False),
            ("ix_news_link_checks_user_id", ["user_id"], False),
            ("ix_news_link_checks_news_id", ["news_id"], False),
            ("ix_news_link_checks_checked_at", ["checked_at"], False),
            ("ix_news_link_checks_run_url", ["run_id", "url"], False),
            ("ix_news_link_checks_news_checked", ["news_id", "checked_at"], False),
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    def drop_indexes(table: str, names: list[str]) -> None:
        existing = _get_index_names(insp, table)
        for name in names:
            if name not in existing:
                continue
            op.drop_index(name, table_name=table)

    if insp.has_table("news_link_checks"):
        drop_indexes(
            "news_link_checks",
            [
                "ix_news_link_checks_run_id",
                "ix_news_link_checks_user_id",
                "ix_news_link_checks_news_id",
                "ix_news_link_checks_checked_at",
                "ix_news_link_checks_run_url",
                "ix_news_link_checks_news_checked",
            ],
        )
        op.drop_table("news_link_checks")

    if insp.has_table("news_ai_generations"):
        drop_indexes(
            "news_ai_generations",
            [
                "ix_news_ai_generations_user_id",
                "ix_news_ai_generations_news_id",
                "ix_news_ai_generations_created_at",
                "ix_news_ai_generations_user_created",
                "ix_news_ai_generations_news_created",
            ],
        )
        op.drop_table("news_ai_generations")

    if insp.has_table("news_versions"):
        drop_indexes(
            "news_versions",
            [
                "ix_news_versions_news_id",
                "ix_news_versions_created_by",
                "ix_news_versions_created_at",
                "ix_news_versions_news_created",
            ],
        )
        op.drop_table("news_versions")
