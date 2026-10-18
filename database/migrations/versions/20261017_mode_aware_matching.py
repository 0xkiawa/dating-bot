"""Add mode-scoped decisions, matches, and discovery delivery history.

Revision ID: 20261017_mode_aware
Revises:
Create Date: 2026-10-17

Existing interaction rows are retained and marked ``legacy`` because the old
schema did not record a swipe's mode and current mode cannot prove history.
"""

from alembic import op
from sqlalchemy import Column, String, inspect, text

revision = "20261017_mode_aware"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Support both a fresh database and an existing installation with legacy
    # tables. create_all is non-destructive for tables that already exist.
    import database.models  # noqa: F401
    from database.models.base import BaseModel
    from database.schema import backfill_legacy_pair_matches

    BaseModel.metadata.create_all(bind=bind, checkfirst=True)
    columns = {column["name"] for column in inspect(bind).get_columns("matchs")}
    if "mode" not in columns:
        op.add_column("matchs", Column("mode", String(20), nullable=True))
    op.execute(
        text("UPDATE matchs SET mode = 'legacy' WHERE mode IS NULL")
    )

    backfill_legacy_pair_matches(bind)


def downgrade() -> None:
    # These tables store user interactions. Dropping them would erase history.
    raise RuntimeError(
        "Mode-aware matching migration is intentionally irreversible to preserve data"
    )
