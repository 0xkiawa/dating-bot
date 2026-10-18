"""Add saved body type and attraction preferences to profiles."""

from alembic import op

revision = "20261019_body_preferences"
down_revision = "20261017_mode_aware"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from database.schema import ensure_profile_match_columns

    ensure_profile_match_columns(op.get_bind())


def downgrade() -> None:
    # Removing these columns would erase users' saved preferences.
    raise RuntimeError(
        "Profile body preference migration is intentionally irreversible to preserve data"
    )
