from typing import List

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class ProfileModel(BaseModel):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    find_role: Mapped[str] = mapped_column(String(20), nullable=False)
    city: Mapped[str] = mapped_column(String(200), nullable=False)
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(900), nullable=True)
    instagram: Mapped[str] = mapped_column(String(200), nullable=True)
    is_shared_location: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    hosting: Mapped[str] = mapped_column(String(20), nullable=True)

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="profile")  # type: ignore
    profile_media: Mapped[List["ProfileMediaModel"]] = relationship(  # type: ignore
        back_populates="profile", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("role IN ('top', 'bottom', 'verse')", name="role_check"),
        CheckConstraint("find_role IN ('top', 'bottom', 'verse', 'all')", name="find_role_check"),
        CheckConstraint("hosting IN ('yes', 'no', 'airbnb')", name="hosting_check"),
    )