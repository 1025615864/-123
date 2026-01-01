"""add consultation favorites

Revision ID: c4f1a2b3d4e5
Revises: b9c7a0f3d2a1
Create Date: 2026-01-01

"""

from __future__ import annotations

from typing import Iterable

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4f1a2b3d4e5"
down_revision: str | None = "b9c7a0f3d2a1"
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

    if not insp.has_table("consultation_favorites"):
        op.create_table(
            "consultation_favorites",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("consultation_id", sa.Integer(), sa.ForeignKey("consultations.id"), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.UniqueConstraint(
                "user_id",
                "consultation_id",
                name="uq_consultation_favorites_user_consultation",
            ),
        )

    _ensure_indexes(
        "consultation_favorites",
        [
            ("ix_consultation_favorites_user_id", ["user_id"], False),
            ("ix_consultation_favorites_consultation_id", ["consultation_id"], False),
            ("ix_consultation_favorites_created_at", ["created_at"], False),
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("consultation_favorites"):
        try:
            op.drop_index("ix_consultation_favorites_created_at", table_name="consultation_favorites")
        except Exception:
            pass
        try:
            op.drop_index("ix_consultation_favorites_consultation_id", table_name="consultation_favorites")
        except Exception:
            pass
        try:
            op.drop_index("ix_consultation_favorites_user_id", table_name="consultation_favorites")
        except Exception:
            pass

        op.drop_table("consultation_favorites")
