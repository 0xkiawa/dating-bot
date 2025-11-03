from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.services.base import BaseService
from utils.logging import logger

from ..models.user import UserModel, UserStatus
from .match import Match
from .profile import Profile


class User(BaseService):
    model = UserModel

    @staticmethod
    async def get_with_profile(session: AsyncSession, id: int):
        """Returns user with their profile"""
        result = await session.execute(
            select(UserModel).options(joinedload(UserModel.profile)).where(UserModel.id == id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create(
        session: AsyncSession, id: int, username: str = None, language: str = None
    ) -> UserModel:
        if user := await User.get_with_profile(session, id):
            return user, False
        await User.create(session, id=id, username=username, language=language)
        user = await User.get_with_profile(session, id)
        return user, True

    @staticmethod
    async def create(
        session: AsyncSession, id: int, username: str = None, language: str = None
    ) -> UserModel:
        """Creates a new user"""
        logger.log("DATABASE", f"New user: {id} (@{username}) {language}")
        session.add(UserModel(id=id, username=username, language=language))
        await session.commit()

    @staticmethod
    async def set_mode(session: AsyncSession, id: int, mode: str) -> bool:
        """Sets user's current mode (fun/dates/friends)"""
        assert mode in ['fun', 'dates', 'friends'], f"Invalid mode: {mode}"
        
        user = await User.get_by_id(session, id)  # FIXED
        if not user:
            logger.log("DATABASE", f"User {id} not found for mode change")
            return False
        
        user.current_mode = mode
        await session.commit()
        logger.log("DATABASE", f"User {id} switched to {mode} mode")
        return True

    @staticmethod
    async def get_mode(session: AsyncSession, id: int) -> str:
        """Gets user's current mode"""
        user = await User.get_by_id(session, id)  # FIXED
        return user.current_mode if user else None

    @staticmethod
    async def clear_mode(session: AsyncSession, id: int) -> bool:
        """Clears user's current mode"""
        user = await User.get_by_id(session, id)  # FIXED
        if not user:
            return False
        
        user.current_mode = None
        await session.commit()
        logger.log("DATABASE", f"User {id} cleared mode")
        return True

    @staticmethod
    async def increment_referral_count(
        session: AsyncSession, user: UserModel, num: int = 1
    ) -> None:
        """Adds a referred user to inviter's count"""
        user.referral += num
        await session.commit()
        logger.log("DATABASE", f"{user.id} (@{user.username}): referred a new user")

    async def ban(session: AsyncSession, id: int) -> None:
        """
        Bans a user:
        - Sets profile status to inactive
        - Sets user status to banned
        - Deletes all likes sent by user
        """
        user = await User.get_with_profile(session, id)
        if not user:
            logger.log("DATABASE", f"User with ID {id} not found.")
            return

        if user.profile:
            await Profile.update(
                session,
                id=id,
                is_active=False,
            )

        await User.update(
            session=session,
            id=id,
            status=UserStatus.Banned,
        )

        await Match.delete_all_by_sender(session, sender_id=id)
        logger.log("DATABASE", f"User {id} was banned.")

    @staticmethod
    async def unban(session: AsyncSession, id: int) -> None:
        """
        Unbans a user:
        - Sets profile status to active
        - Sets user status to unbanned
        """
        user = await User.get_with_profile(session, id)
        if not user:
            logger.log("DATABASE", f"User with ID {id} not found.")
            return

        if user.profile:
            await Profile.update(
                session,
                id=id,
                is_active=True,
            )

        await User.update(
            session=session,
            id=id,
            status=UserStatus.User,
        )

        logger.log("DATABASE", f"User {id} was unbanned.")