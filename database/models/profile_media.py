from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import BaseModel, StatusMixin

class MediaTypes(StatusMixin):
    Photo = "photo"
    Video = "video"

class ProfileMediaModel(BaseModel):
    __tablename__ = "profile_media"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)
    order: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    media: Mapped[str] = mapped_column(String(300), nullable=False)

    # NEW: Privacy/blur-reveal feature
    # None = blur disabled for this photo (owner opted out, shows normally)
    # 0/3/10/30 = seconds the clear photo stays visible after a viewer taps reveal
    reveal_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # NEW: Caches the blurred version's Telegram file_id after first generation,
    # so we don't re-download/re-blur/re-upload for every new viewer
    blurred_file_id: Mapped[str | None] = mapped_column(String(300), nullable=True)

    profile: Mapped["ProfileModel"] = relationship(  # type: ignore
        back_populates="profile_media"
    )

    __table_args__ = (
        CheckConstraint("media_type IN ('photo', 'video')", name="media_type_check"),
    )