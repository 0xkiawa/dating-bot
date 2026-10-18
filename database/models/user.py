from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, StatusMixin


class UserStatus(StatusMixin):
    Banned = 0
    User = 1
    Sponsor = 2
    Moderator = 3
    Admin = 4
    Owner = 5


class UserModel(BaseModel):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(70), nullable=True)
    language: Mapped[str] = mapped_column(String(10), server_default="en")
    status: Mapped[int] = mapped_column(Integer, server_default="1")
    current_mode: Mapped[str] = mapped_column(String(20), nullable=True)
    consent_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    profile: Mapped["ProfileModel"] = relationship(  # type: ignore
        "ProfileModel", uselist=False, back_populates="user"
    )


class UserBlockModel(BaseModel):
    """Global safety block that excludes discovery in every mode."""

    __tablename__ = "user_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    blocker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    blocked_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_block_direction"),
    )
