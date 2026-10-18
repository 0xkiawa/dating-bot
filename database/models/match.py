from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel, StatusMixin


# not currently in use
class MatchStatus(StatusMixin):
    Rejected = 0
    Pending = 1
    Accepted = 2


class MatchModel(BaseModel):
    __tablename__ = "matchs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  # CHANGED
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    receiver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    message: Mapped[str] = mapped_column(String(250), nullable=True)
    status: Mapped[int] = mapped_column(Integer, server_default="1")
    is_active: Mapped[bool] = mapped_column(server_default="True", nullable=False)
    # Existing mode-less rows are marked "legacy" because their swipe mode is unknown.
    mode: Mapped[str | None] = mapped_column(String(20), nullable=True)


class InteractionDecisionModel(BaseModel):
    """One durable Like or Pass in a single discovery mode."""

    __tablename__ = "interaction_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    message: Mapped[str | None] = mapped_column(String(250), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("actor_id", "target_id", "mode", name="uq_decision_actor_target_mode"),
        Index("ix_decision_target_mode", "target_id", "mode", "decision"),
        CheckConstraint("mode IN ('fun', 'dates', 'friends')", name="decision_mode_check"),
        CheckConstraint("decision IN ('like', 'pass')", name="decision_value_check"),
    )


class PairMatchModel(BaseModel):
    """A confirmed match for an unordered pair and the mode it formed in."""

    __tablename__ = "pair_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_low_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    user_high_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_low_id", "user_high_id", "mode", name="uq_pair_match_mode"),
        Index("ix_pair_matches_low", "user_low_id", "mode"),
        Index("ix_pair_matches_high", "user_high_id", "mode"),
        CheckConstraint(
            "mode IN ('fun', 'dates', 'friends', 'legacy')", name="pair_match_mode_check"
        ),
    )


class DiscoveryDeliveryCursorModel(BaseModel):
    """Per-pair reservation lock and latest successful delivery timestamp."""

    __tablename__ = "discovery_delivery_cursors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    viewer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    latest_delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reservation_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("viewer_id", "target_id", "mode", name="uq_delivery_cursor_pair_mode"),
    )


class DiscoveryDeliveryEventModel(BaseModel):
    """Audit history for reserved, delivered, and failed Telegram profile sends."""

    __tablename__ = "discovery_delivery_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    viewer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="reserved")
    reservation_token: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_delivery_event_pair", "viewer_id", "target_id", "mode"),
        Index("ix_delivery_cooldown", "viewer_id", "mode", "status", "delivered_at"),
        CheckConstraint("mode IN ('fun', 'dates', 'friends')", name="delivery_mode_check"),
        CheckConstraint(
            "status IN ('reserved', 'delivered', 'failed')", name="delivery_status_check"
        ),
    )


class MatchNotificationModel(BaseModel):
    """Retryable per-recipient match notification outbox."""

    __tablename__ = "match_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("pair_matches.id", ondelete="CASCADE"), nullable=False
    )
    recipient_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("match_id", "recipient_id", name="uq_match_notification_recipient"),
        Index("ix_match_notification_pending", "recipient_id", "delivered_at"),
    )
