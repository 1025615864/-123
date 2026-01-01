"""add consultation share_token_version

Revision ID: e2a7d8c9f0a1
Revises: c4f1a2b3d4e5
Create Date: 2026-01-01

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e2a7d8c9f0a1"
down_revision: str | None = "c4f1a2b3d4e5"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("consultations"):
        return

    try:
        cols = {str(c.get("name") or "") for c in insp.get_columns("consultations")}
    except Exception:
        cols = set()

    if "share_token_version" not in cols:
        op.add_column(
            "consultations",
            sa.Column("share_token_version", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("consultations"):
        return

    try:
        cols = {str(c.get("name") or "") for c in insp.get_columns("consultations")}
    except Exception:
        cols = set()

    if "share_token_version" in cols:
        try:
            op.drop_column("consultations", "share_token_version")
        except Exception:
            # sqlite may not support drop_column in-place
            pass
