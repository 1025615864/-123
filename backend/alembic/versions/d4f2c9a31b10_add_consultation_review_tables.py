from __future__ import annotations

from typing import Iterable

from alembic import op
import sqlalchemy as sa


revision: str = "d4f2c9a31b10"
down_revision: str | None = "c3a4d1e7f9ab"
branch_labels: str | None = None
depends_on: str | None = None


def _get_table_names(insp: sa.Inspector) -> set[str]:
    try:
        names = insp.get_table_names()
    except Exception:
        return set()
    return {str(n) for n in names if n}


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
    tables = _get_table_names(insp)

    if "consultation_review_tasks" not in tables:
        op.create_table(
            "consultation_review_tasks",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("consultation_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("order_no", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("lawyer_id", sa.Integer(), nullable=True),
            sa.Column("result_markdown", sa.Text(), nullable=True),
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["consultation_id"], ["consultations.id"], ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
            sa.ForeignKeyConstraint(["order_id"], ["payment_orders.id"], ),
            sa.ForeignKeyConstraint(["lawyer_id"], ["lawyers.id"], ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("order_id", name="uq_consultation_review_tasks_order_id"),
        )

    if "consultation_review_versions" not in tables:
        op.create_table(
            "consultation_review_versions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("editor_user_id", sa.Integer(), nullable=False),
            sa.Column("editor_role", sa.String(length=20), nullable=False),
            sa.Column("content_markdown", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["task_id"], ["consultation_review_tasks.id"], ),
            sa.ForeignKeyConstraint(["editor_user_id"], ["users.id"], ),
            sa.PrimaryKeyConstraint("id"),
        )

    _ensure_indexes(
        "consultation_review_tasks",
        [
            ("ix_consultation_review_tasks_consultation_id", ["consultation_id"], False),
            ("ix_consultation_review_tasks_user_id", ["user_id"], False),
            ("ix_consultation_review_tasks_order_id", ["order_id"], False),
            ("ix_consultation_review_tasks_order_no", ["order_no"], False),
            ("ix_consultation_review_tasks_status", ["status"], False),
            ("ix_consultation_review_tasks_lawyer_id", ["lawyer_id"], False),
        ],
    )

    _ensure_indexes(
        "consultation_review_versions",
        [
            ("ix_consultation_review_versions_task_id", ["task_id"], False),
            ("ix_consultation_review_versions_editor_user_id", ["editor_user_id"], False),
        ],
    )


def downgrade() -> None:
    # Downgrade is best-effort.
    pass
