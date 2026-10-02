from datetime import datetime, timedelta

from sqlalchemy import case, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.services.base import BaseService
from utils.logging import logger

from ..models.match import MatchModel, MatchStatus
from ..models.user import UserModel


class Match(BaseService):
    model = MatchModel

    @staticmethod
    async def create(
        session: AsyncSession,
        sender_id: int,
        receiver_id: int,
        mail_text: str | None,
        status: int = 1,
        is_active: bool = True,
    ) -> bool:
        """
        Добавляет лайк/дизлайк в БД.
        Если запись уже есть и это НЕ устаревший (30+ дней) дизлайк - ничего не делает.
        Если это устаревший дизлайк от того же sender - перезаписывает его новым статусом.
        Возвращает True, если запись была создана/обновлена, иначе False.
        """
        existing_match = await session.execute(
            select(MatchModel).where(
                or_(
                    # Прямое направление: sender -> receiver
                    (MatchModel.sender_id == sender_id) & (MatchModel.receiver_id == receiver_id),
                    # Обратное направление: receiver -> sender
                    (MatchModel.sender_id == receiver_id) & (MatchModel.receiver_id == sender_id),
                )
                & (MatchModel.is_active == True)
            )
        )
        existing = existing_match.scalar_one_or_none()

        if existing:
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            is_stale_rejection = (
                existing.sender_id == sender_id
                and existing.receiver_id == receiver_id
                and existing.status == MatchStatus.Rejected
                and existing.updated_at is not None
                and existing.updated_at < thirty_days_ago
            )

            if is_stale_rejection:
                existing.status = status
                existing.message = mail_text
                await session.commit()
                logger.log(
                    "DATABASE",
                    f"{sender_id} & {receiver_id}: stale rejection overwritten (status={status})",
                )
                return True

            # Если запись уже существует и не истекла - ничего не делаем
            logger.log("DATABASE", f"{sender_id} & {receiver_id}: лайк повторился")
            return False

        # Если записи нет, добавляем новую
        stmt = insert(MatchModel).values(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message=mail_text,
            status=status,
            is_active=is_active,
        )
        await session.execute(stmt)
        await session.commit()

        logger.log("DATABASE", f"{sender_id}: лайкнул пользователя {receiver_id}")
        return True

    @staticmethod
    async def get_user_matchs(session: AsyncSession, id: int) -> list:
        """
        Возвращает список пользователей, которые связаны с пользователем через лайки.
        Логика:
        1. Показывать активные лайки (is_active = True)
        2. Показывать лайки, полученные от других пользователей (receiver_id = id)
        3. Показывать взаимные лайки (где пользователь отправитель, но получил ответ status = 2)
        """

        # Выбираем соответствующий ID в зависимости от роли пользователя
        result = await session.execute(
            select(
                case(
                    (
                        MatchModel.receiver_id == id,
                        MatchModel.sender_id,
                    ),  # Если пользователь получатель - возвращаем отправителя
                    (
                        MatchModel.sender_id == id,
                        MatchModel.receiver_id,
                    ),  # Если пользователь отправитель - возвращаем получателя
                ).label("user_id")
            )
            .where(MatchModel.is_active == True)
            .where(
                or_(
                    # Лайки, полученные от других пользователей
                    (MatchModel.receiver_id == id) & (MatchModel.sender_id != id),
                    # Взаимные лайки: пользователь отправил лайк и получил ответ (status = 2)
                    (MatchModel.sender_id == id) & (MatchModel.status == MatchStatus.Accepted),
                )
            )
        )

        return [row[0] for row in result.fetchall()]

    @staticmethod
    async def get_user_matchs_by_mode(session: AsyncSession, id: int, mode: str) -> list:
        """
        Возвращает список пользователей, которые связаны с пользователем через лайки,
        ОТФИЛЬТРОВАННЫЙ ПО РЕЖИМУ отправителя лайка.
        
        Логика:
        1. Показывать активные лайки (is_active = True)
        2. Показывать лайки, полученные от других пользователей (receiver_id = id)
        3. Показывать взаимные лайки (где пользователь отправитель, но получил ответ status = 2)
        4. ФИЛЬТР: Показывать только те лайки, где отправитель был в указанном режиме
        """
        
        # Join с UserModel для проверки режима отправителя
        result = await session.execute(
            select(
                case(
                    (
                        MatchModel.receiver_id == id,
                        MatchModel.sender_id,
                    ),  # Если пользователь получатель - возвращаем отправителя
                    (
                        MatchModel.sender_id == id,
                        MatchModel.receiver_id,
                    ),  # Если пользователь отправитель - возвращаем получателя
                ).label("user_id")
            )
            .join(
                UserModel,
                # Join с отправителем для проверки его режима
                case(
                    (MatchModel.receiver_id == id, MatchModel.sender_id),
                    (MatchModel.sender_id == id, MatchModel.receiver_id),
                ) == UserModel.id
            )
            .where(MatchModel.is_active == True)
            .where(UserModel.current_mode == mode)  # ФИЛЬТР ПО РЕЖИМУ
            .where(
                or_(
                    # Лайки, полученные от других пользователей
                    (MatchModel.receiver_id == id) & (MatchModel.sender_id != id),
                    # Взаимные лайки: пользователь отправил лайк и получил ответ (status = 2)
                    (MatchModel.sender_id == id) & (MatchModel.status == MatchStatus.Accepted),
                )
            )
        )

        return [row[0] for row in result.fetchall()]

    @staticmethod
    async def get(session: AsyncSession, user_id: int, other_user_id: int) -> MatchModel | None:
        """
        Возвращает Match между двумя пользователями в любом направлении.
        Ищет как где user_id отправитель, так и где получатель.
        """
        result = await session.execute(
            select(MatchModel)
            .where(
                or_(
                    # user_id получил лайк от other_user_id
                    (MatchModel.receiver_id == user_id) & (MatchModel.sender_id == other_user_id),
                    # user_id отправил лайк other_user_id
                    (MatchModel.sender_id == user_id) & (MatchModel.receiver_id == other_user_id),
                )
            )
            .order_by(MatchModel.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def delete(session: AsyncSession, receiver_id: int, sender_id: int) -> None:
        """Удаляет лайк из БД"""
        await session.execute(
            MatchModel.__table__.delete().where(
                (MatchModel.sender_id == sender_id) & (MatchModel.receiver_id == receiver_id)
            )
        )
        await session.commit()
        logger.log("DATABASE", f"{sender_id} & {receiver_id}: лайк удален")

    @staticmethod
    async def delete_all_by_sender(session: AsyncSession, sender_id: int) -> None:
        """
        Удаляет все записи, где пользователь лайкнул кого-то (по sender_id).
        """
        await session.execute(
            MatchModel.__table__.delete().where(MatchModel.sender_id == sender_id)
        )
        await session.commit()
        logger.log("DATABASE", f"Все лайки пользователя {sender_id} были удалены")

    @staticmethod
    async def deactivate_all_by_sender(session: AsyncSession, sender_id: int) -> None:
        """
        Деактивирует все записи, где пользователь лайкнул кого-то (устанавливает is_active = False).
        """
        from sqlalchemy import update

        await session.execute(
            update(MatchModel).where(MatchModel.sender_id == sender_id).values(is_active=False)
        )
        await session.commit()
        logger.log("DATABASE", f"Все лайки пользователя {sender_id} были деактивированы")