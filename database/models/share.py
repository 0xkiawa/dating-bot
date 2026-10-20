from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class ShareLinkModel(BaseModel):
    """An opt-in, revocable Telegram deep link for one profile."""

    __tablename__ = "share_links"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    reroll_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    reroll_window_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    share_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (UniqueConstraint("slug", name="uq_share_links_slug"),)


class PendingSharedViewModel(BaseModel):
    """A share click awaiting a successful profile-card delivery."""

    __tablename__ = "pending_shared_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    viewer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="pending"
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'consumed', 'expired')",
            name="pending_shared_view_status_check",
        ),
        Index(
            "uq_pending_shared_viewer",
            "viewer_id",
            unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_pending_shared_view_expiry", "created_at"),
    )
