from __future__ import annotations

from typing import Iterable

from alembic import op
import sqlalchemy as sa


revision: str = "c3a4d1e7f9ab"
down_revision: str | None = "b9c7a0f3d2a1"
branch_labels: str | None = None
depends_on: str | None = None


def _get_column_names(insp: sa.Inspector, table_name: str) -> set[str]:
    try:
        cols = insp.get_columns(table_name)
    except Exception:
        return set()
    return {str(c.get("name") or "") for c in cols if c.get("name")}


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

    if insp.has_table("payment_callback_events"):
        cols = _get_column_names(insp, "payment_callback_events")
        if "raw_payload_hash" not in cols:
            op.add_column(
                "payment_callback_events",
                sa.Column("raw_payload_hash", sa.String(length=64), nullable=True),
            )
        if "source_ip" not in cols:
            op.add_column(
                "payment_callback_events",
                sa.Column("source_ip", sa.String(length=45), nullable=True),
            )
        if "user_agent" not in cols:
            op.add_column(
                "payment_callback_events",
                sa.Column("user_agent", sa.String(length=512), nullable=True),
            )

    if insp.has_table("legal_knowledge"):
        cols = _get_column_names(insp, "legal_knowledge")
        if "source_url" not in cols:
            op.add_column(
                "legal_knowledge",
                sa.Column("source_url", sa.String(length=500), nullable=True),
            )
        if "source_version" not in cols:
            op.add_column(
                "legal_knowledge",
                sa.Column("source_version", sa.String(length=50), nullable=True),
            )
        if "source_hash" not in cols:
            op.add_column(
                "legal_knowledge",
                sa.Column("source_hash", sa.String(length=64), nullable=True),
            )
        if "ingest_batch_id" not in cols:
            op.add_column(
                "legal_knowledge",
                sa.Column("ingest_batch_id", sa.String(length=36), nullable=True),
            )

        _ensure_indexes(
            "legal_knowledge",
            [
                ("ix_legal_knowledge_source_hash", ["source_hash"], False),
                ("ix_legal_knowledge_ingest_batch_id", ["ingest_batch_id"], False),
            ],
        )


def downgrade() -> None:
    # Downgrade is best-effort; columns may not be removable on some backends.
    pass
