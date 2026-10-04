from sqlalchemy import BigInteger, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class PhotoRevealModel(BaseModel):
    """
    Tracks which viewer has already used their one-time reveal on which photo.
    Once a row exists for (media_id, viewer_id), that viewer NEVER gets
    the reveal button again for that photo - permanently, match or no match.
    """
    __tablename__ = "photo_reveals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    media_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profile_media.id", ondelete="CASCADE"), nullable=False
    )
    viewer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("media_id", "viewer_id", name="uq_photo_reveal_once"),
    )