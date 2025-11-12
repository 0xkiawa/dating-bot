from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.services.base import BaseService
from database.services.profile_media import ProfileMedia
from utils.logging import logger

from ..models.profile import ProfileModel


class Profile(BaseService):
    model = ProfileModel

    @staticmethod
    async def get(session: AsyncSession, id: int):
        """Returns user profile"""
        return await session.get(ProfileModel, id)

    @staticmethod
    async def delete(session: AsyncSession, id: int):
        """Deletes user profile"""
        stmt = delete(ProfileModel).where(ProfileModel.id == id)
        await session.execute(stmt)
        await session.commit()
        logger.log("DATABASE", f"{id}: deleted profile")

    @classmethod
    async def create_or_update(cls, session: AsyncSession, **kwargs) -> "Profile":
        # Ensure is_active is stored as string 'True'/'False'
        if "is_active" in kwargs:
            kwargs["is_active"] = str(kwargs["is_active"])

        profile_id = kwargs.pop("id")  # Extract profile id
        photo_url = kwargs.pop(
            "photo", None
        )  # Extract photo if exists (backwards compatibility)
        photos = kwargs.pop("photos", None)  # Extract photo list

        obj = await cls.get_by_id(session, profile_id)
        is_new = False

        if obj:
            # Update existing profile
            for key, value in kwargs.items():
                setattr(obj, key, value)
            await session.commit()
        else:
            # Create new profile
            obj = await cls.create(session, id=profile_id, **kwargs)
            is_new = True
            logger.log("DATABASE", f"{profile_id}: created profile")

        # Process photos
        if photos:
            # Delete all old profile photos
            await ProfileMedia.delete_profile_photos(session, profile_id)

            # Add new photos
            for i, photo_file_id in enumerate(photos, 1):
                await ProfileMedia.add_media(
                    session=session,
                    profile_id=profile_id,
                    media_url=photo_file_id,
                    media_type="photo",
                    order=i,
                )
        elif photo_url:
            # Backwards compatibility - if single photo passed
            await ProfileMedia.delete_profile_photos(session, profile_id)

            await ProfileMedia.add_media(
                session=session,
                profile_id=profile_id,
                media_url=photo_url,
                media_type="photo",
                order=1,
            )
        else:
            logger.log("DATABASE", "Error creating profile")
        return obj, is_new