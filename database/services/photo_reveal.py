from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.services.base import BaseService
from utils.logging import logger

from ..models.photo_reveal import PhotoRevealModel


class PhotoReveal(BaseService):
    model = PhotoRevealModel

    @staticmethod
    async def has_revealed(session: AsyncSession, media_id: int, viewer_id: int) -> bool:
        """Has this viewer already used their one-time reveal on this photo?"""
        result = await session.execute(
            select(PhotoRevealModel).where(
                PhotoRevealModel.media_id == media_id,
                PhotoRevealModel.viewer_id == viewer_id,
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def mark_revealed(session: AsyncSession, media_id: int, viewer_id: int) -> bool:
        """
        Records that this viewer has used their one-time reveal.
        Returns True if this is a NEW reveal, False if they'd already revealed it
        (guards against double-tap race conditions).
        """
        try:
            session.add(PhotoRevealModel(media_id=media_id, viewer_id=viewer_id))
            await session.commit()
            logger.log("DATABASE", f"Viewer {viewer_id} revealed media {media_id}")
            return True
        except IntegrityError:
            await session.rollback()
            return False