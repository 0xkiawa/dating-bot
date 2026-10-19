import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import and_, case, exists, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from database.services.base import BaseService
from utils.logging import logger

from ..models.complaint import CompleintStatus, ProfileCompleintsModel
from ..models.match import (
    DiscoveryDeliveryCursorModel,
    DiscoveryDeliveryEventModel,
    InteractionDecisionModel,
    MatchModel,
    MatchNotificationModel,
    MatchStatus,
    PairMatchModel,
)
from ..models.profile import ProfileModel
from ..models.user import UserBlockModel, UserModel


class Match(BaseService):
    model = MatchModel
    _decision_locks: dict[tuple[int, int, str], asyncio.Lock] = {}

    @staticmethod
    def _insert_do_nothing(session: AsyncSession, model, values: dict, conflict_columns: list[str]):
        """Use the database's native conflict handling for idempotent writes."""
        dialect = session.get_bind().dialect.name
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as dialect_insert

            return dialect_insert(model).values(**values).on_conflict_do_nothing(
                index_elements=conflict_columns
            )
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as dialect_insert

            return dialect_insert(model).values(**values).on_conflict_do_nothing(
                index_elements=conflict_columns
            )
        return insert(model).values(**values)

    @staticmethod
    async def record_decision(
        session: AsyncSession,
        actor_id: int,
        target_id: int,
        mode: str,
        decision: str,
        message: str | None = None,
    ) -> tuple[bool, int | None]:
        """Serialize same-pair writes in-process; database keys remain authoritative."""
        pair_key = (*sorted((actor_id, target_id)), mode)
        lock = Match._decision_locks.setdefault(pair_key, asyncio.Lock())
        async with lock:
            return await Match._record_decision(
                session, actor_id, target_id, mode, decision, message
            )

    @staticmethod
    async def _record_decision(
        session: AsyncSession,
        actor_id: int,
        target_id: int,
        mode: str,
        decision: str,
        message: str | None = None,
    ) -> tuple[bool, int | None]:
        """Persist an idempotent mode-specific decision and create a unique match."""
        if mode not in {"fun", "dates", "friends"}:
            return False, None
        if actor_id == target_id or decision not in {"like", "pass"}:
            return False, None

        if decision == "like":
            existing_pass = await session.scalar(
                select(InteractionDecisionModel.id).where(
                    InteractionDecisionModel.mode == mode,
                    InteractionDecisionModel.decision == "pass",
                    or_(
                        and_(
                            InteractionDecisionModel.actor_id == actor_id,
                            InteractionDecisionModel.target_id == target_id,
                        ),
                        and_(
                            InteractionDecisionModel.actor_id == target_id,
                            InteractionDecisionModel.target_id == actor_id,
                        ),
                    ),
                ).limit(1)
            )
            safety_exclusion = await session.scalar(
                select(UserBlockModel.id).where(
                    or_(
                        and_(
                            UserBlockModel.blocker_id == actor_id,
                            UserBlockModel.blocked_id == target_id,
                        ),
                        and_(
                            UserBlockModel.blocker_id == target_id,
                            UserBlockModel.blocked_id == actor_id,
                        ),
                    )
                ).limit(1)
            )
            reported_pair = await session.scalar(
                select(ProfileCompleintsModel.id).where(
                    ProfileCompleintsModel.status.in_(
                        (CompleintStatus.Pending, CompleintStatus.Accepted)
                    ),
                    or_(
                        and_(
                            ProfileCompleintsModel.sender_id == actor_id,
                            ProfileCompleintsModel.receiver_id == target_id,
                        ),
                        and_(
                            ProfileCompleintsModel.sender_id == target_id,
                            ProfileCompleintsModel.receiver_id == actor_id,
                        ),
                    ),
                ).limit(1)
            )
            if existing_pass or safety_exclusion or reported_pair:
                return False, None

        values = {
            "actor_id": actor_id,
            "target_id": target_id,
            "mode": mode,
            "decision": decision,
            "message": message,
        }
        result = await session.execute(
            Match._insert_do_nothing(
                session,
                InteractionDecisionModel,
                values,
                ["actor_id", "target_id", "mode"],
            )
        )
        inserted = result.rowcount == 1
        await session.commit()

        if decision != "like":
            return inserted, None

        # A reciprocal Like only counts in the exact mode of the original Like.
        reciprocal_like = await session.scalar(
            select(InteractionDecisionModel.id).where(
                InteractionDecisionModel.actor_id == target_id,
                InteractionDecisionModel.target_id == actor_id,
                InteractionDecisionModel.mode == mode,
                InteractionDecisionModel.decision == "like",
            )
        )
        either_passed = await session.scalar(
            select(InteractionDecisionModel.id).where(
                InteractionDecisionModel.mode == mode,
                InteractionDecisionModel.decision == "pass",
                or_(
                    and_(
                        InteractionDecisionModel.actor_id == actor_id,
                        InteractionDecisionModel.target_id == target_id,
                    ),
                    and_(
                        InteractionDecisionModel.actor_id == target_id,
                        InteractionDecisionModel.target_id == actor_id,
                    ),
                ),
            ).limit(1)
        )
        if not reciprocal_like or either_passed:
            return inserted, None

        safety_exclusion = await session.scalar(
            select(UserBlockModel.id).where(
                or_(
                    and_(
                        UserBlockModel.blocker_id == actor_id,
                        UserBlockModel.blocked_id == target_id,
                    ),
                    and_(
                        UserBlockModel.blocker_id == target_id,
                        UserBlockModel.blocked_id == actor_id,
                    ),
                )
            ).limit(1)
        )
        reported_pair = await session.scalar(
            select(ProfileCompleintsModel.id).where(
                ProfileCompleintsModel.status.in_(
                    (CompleintStatus.Pending, CompleintStatus.Accepted)
                ),
                or_(
                    and_(
                        ProfileCompleintsModel.sender_id == actor_id,
                        ProfileCompleintsModel.receiver_id == target_id,
                    ),
                    and_(
                        ProfileCompleintsModel.sender_id == target_id,
                        ProfileCompleintsModel.receiver_id == actor_id,
                    ),
                ),
            ).limit(1)
        )
        if safety_exclusion or reported_pair:
            return inserted, None

        low_id, high_id = sorted((actor_id, target_id))
        create_result = await session.execute(
            Match._insert_do_nothing(
                session,
                PairMatchModel,
                {"user_low_id": low_id, "user_high_id": high_id, "mode": mode},
                ["user_low_id", "user_high_id", "mode"],
            )
        )
        match_created = create_result.rowcount == 1
        pair_match = await session.scalar(
            select(PairMatchModel).where(
                PairMatchModel.user_low_id == low_id,
                PairMatchModel.user_high_id == high_id,
                PairMatchModel.mode == mode,
            )
        )
        if pair_match and match_created:
            for recipient_id in (low_id, high_id):
                await session.execute(
                    Match._insert_do_nothing(
                        session,
                        MatchNotificationModel,
                        {"match_id": pair_match.id, "recipient_id": recipient_id},
                        ["match_id", "recipient_id"],
                    )
                )
        await session.commit()
        return inserted, pair_match.id if pair_match else None

    @staticmethod
    async def inbox_items(session: AsyncSession, user_id: int) -> list[dict]:
        """Return pending Likes and all confirmed matches, across every mode."""
        passed = aliased(InteractionDecisionModel)
        block = aliased(UserBlockModel)
        report = aliased(ProfileCompleintsModel)
        # A pending incoming Like is hidden if the recipient passed its sender.
        incoming = await session.execute(
            select(InteractionDecisionModel).where(
                InteractionDecisionModel.target_id == user_id,
                InteractionDecisionModel.decision == "like",
                ~exists(
                    select(PairMatchModel.id).where(
                        PairMatchModel.mode == InteractionDecisionModel.mode,
                        or_(
                            and_(
                                PairMatchModel.user_low_id == user_id,
                                PairMatchModel.user_high_id == InteractionDecisionModel.actor_id,
                            ),
                            and_(
                                PairMatchModel.user_high_id == user_id,
                                PairMatchModel.user_low_id == InteractionDecisionModel.actor_id,
                            ),
                        ),
                    )
                ),
                ~exists(
                    select(block.id).where(
                        or_(
                            and_(
                                block.blocker_id == user_id,
                                block.blocked_id == InteractionDecisionModel.actor_id,
                            ),
                            and_(
                                block.blocked_id == user_id,
                                block.blocker_id == InteractionDecisionModel.actor_id,
                            ),
                        )
                    )
                ),
                ~exists(
                    select(report.id).where(
                        report.status.in_((CompleintStatus.Pending, CompleintStatus.Accepted)),
                        or_(
                            and_(
                                report.sender_id == user_id,
                                report.receiver_id == InteractionDecisionModel.actor_id,
                            ),
                            and_(
                                report.receiver_id == user_id,
                                report.sender_id == InteractionDecisionModel.actor_id,
                            ),
                        ),
                    )
                ),
                ~exists(
                    select(passed.id).where(
                        or_(
                            and_(
                                passed.actor_id == user_id,
                                passed.target_id == InteractionDecisionModel.actor_id,
                            ),
                            and_(
                                passed.target_id == user_id,
                                passed.actor_id == InteractionDecisionModel.actor_id,
                            ),
                        ),
                        passed.mode == InteractionDecisionModel.mode,
                        passed.decision == "pass",
                    )
                ),
            )
        )
        items = [
            {
                "user_id": decision.actor_id,
                "mode": decision.mode,
                "kind": "like",
                "message": decision.message,
            }
            for decision in incoming.scalars()
        ]

        matched_rows = await session.execute(
            select(PairMatchModel).where(
                or_(PairMatchModel.user_low_id == user_id, PairMatchModel.user_high_id == user_id)
            )
        )
        items.extend(
            {
                "user_id": (
                    match.user_high_id if match.user_low_id == user_id else match.user_low_id
                ),
                "mode": match.mode,
                "kind": "match",
                "message": None,
            }
            for match in matched_rows.scalars()
        )

        legacy = await session.execute(
            select(MatchModel).where(
                MatchModel.receiver_id == user_id,
                MatchModel.status == MatchStatus.Pending,
                MatchModel.is_active.is_(True),
            )
        )
        items.extend(
            {
                "user_id": row.sender_id,
                "mode": row.mode or "legacy",
                "kind": "legacy_like",
                "message": row.message,
            }
            for row in legacy.scalars()
        )
        items.sort(key=lambda item: (item["kind"] == "match", item["user_id"]))
        return items

    @staticmethod
    async def record_legacy_match(
        session: AsyncSession, first_user_id: int, second_user_id: int
    ) -> int | None:
        """Keep a reciprocated pre-migration Like available with unknown mode."""
        low_id, high_id = sorted((first_user_id, second_user_id))
        result = await session.execute(
            Match._insert_do_nothing(
                session,
                PairMatchModel,
                {"user_low_id": low_id, "user_high_id": high_id, "mode": "legacy"},
                ["user_low_id", "user_high_id", "mode"],
            )
        )
        pair_match = await session.scalar(
            select(PairMatchModel).where(
                PairMatchModel.user_low_id == low_id,
                PairMatchModel.user_high_id == high_id,
                PairMatchModel.mode == "legacy",
            )
        )
        if pair_match and result.rowcount == 1:
            for recipient_id in (low_id, high_id):
                await session.execute(
                    Match._insert_do_nothing(
                        session,
                        MatchNotificationModel,
                        {"match_id": pair_match.id, "recipient_id": recipient_id},
                        ["match_id", "recipient_id"],
                    )
                )
        await session.commit()
        return pair_match.id if pair_match else None

    @staticmethod
    async def reserve_delivery(
        session: AsyncSession,
        viewer_id: int,
        target_id: int,
        mode: str,
        *,
        shared: bool = False,
    ) -> str | None:
        """Atomically reserve a pair/mode delivery, rechecking mode and eligibility.

        A share-card delivery uses the target's mode and bypasses prior swipes,
        matches and cooldowns, while preserving profile, account, report and
        global-block safety checks.
        """
        from data.config import search

        if mode not in {"fun", "dates", "friends"} or viewer_id == target_id:
            return None

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=search.REDISCOVERY_COOLDOWN_DAYS)
        stale_reservation = now - timedelta(minutes=search.DELIVERY_RESERVATION_MINUTES)
        token = str(uuid4())

        # Make the cursor row first. Concurrent first deliveries race safely on
        # its unique pair/mode key; the losing insert simply reuses the row.
        try:
            await session.execute(
                Match._insert_do_nothing(
                    session,
                    DiscoveryDeliveryCursorModel,
                    {"viewer_id": viewer_id, "target_id": target_id, "mode": mode},
                    ["viewer_id", "target_id", "mode"],
                )
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()

        viewer = UserModel.__table__.alias("delivery_viewer")
        target = UserModel.__table__.alias("delivery_target")
        active_users = exists(
            select(viewer.c.id)
            .select_from(viewer.join(target, target.c.id == target_id))
            .where(
                viewer.c.id == viewer_id,
                (shared or viewer.c.current_mode == mode),
                target.c.current_mode == mode,
                viewer.c.status != 0,
                target.c.status != 0,
            )
        )
        active_profiles = exists(
            select(ProfileModel.id).where(
                ProfileModel.id == target_id,
                ProfileModel.is_active.is_(True),
                ProfileModel.age >= 18,
            )
        )
        active_viewer_profile = exists(
            select(ProfileModel.id).where(
                ProfileModel.id == viewer_id,
                ProfileModel.is_active.is_(True),
                ProfileModel.age >= 18,
            )
        )
        excluded_decision = exists(
            select(InteractionDecisionModel.id).where(
                InteractionDecisionModel.mode == mode,
                or_(
                    and_(
                        InteractionDecisionModel.actor_id == viewer_id,
                        InteractionDecisionModel.target_id == target_id,
                        InteractionDecisionModel.decision.in_(("like", "pass")),
                    ),
                    and_(
                        InteractionDecisionModel.actor_id == target_id,
                        InteractionDecisionModel.target_id == viewer_id,
                        InteractionDecisionModel.decision.in_(("like", "pass")),
                    ),
                ),
            )
        )
        excluded_match = exists(
            select(PairMatchModel.id).where(
                PairMatchModel.mode.in_((mode, "legacy")),
                PairMatchModel.user_low_id == min(viewer_id, target_id),
                PairMatchModel.user_high_id == max(viewer_id, target_id),
            )
        )
        recent_delivery = exists(
            select(DiscoveryDeliveryEventModel.id).where(
                DiscoveryDeliveryEventModel.viewer_id == viewer_id,
                DiscoveryDeliveryEventModel.target_id == target_id,
                DiscoveryDeliveryEventModel.mode == mode,
                DiscoveryDeliveryEventModel.status == "delivered",
                or_(
                    and_(
                        DiscoveryDeliveryEventModel.source == "search",
                        DiscoveryDeliveryEventModel.delivered_at >= cutoff,
                    ),
                    and_(
                        DiscoveryDeliveryEventModel.source == "shared",
                        DiscoveryDeliveryEventModel.delivered_at
                        >= now - timedelta(days=21),
                    ),
                ),
            )
        )
        recent_shared_delivery = exists(
            select(DiscoveryDeliveryEventModel.id).where(
                DiscoveryDeliveryEventModel.viewer_id == viewer_id,
                DiscoveryDeliveryEventModel.target_id == target_id,
                DiscoveryDeliveryEventModel.mode == mode,
                DiscoveryDeliveryEventModel.status == "delivered",
                DiscoveryDeliveryEventModel.source == "shared",
                DiscoveryDeliveryEventModel.delivered_at >= now - timedelta(days=21),
            )
        )
        legacy_exclusion = exists(
            select(MatchModel.id).where(
                or_(
                    and_(MatchModel.sender_id == viewer_id, MatchModel.receiver_id == target_id),
                    and_(MatchModel.sender_id == target_id, MatchModel.receiver_id == viewer_id),
                ),
                MatchModel.is_active.is_(True),
                or_(MatchModel.mode == "legacy", MatchModel.mode == mode),
            )
        )
        blocked = exists(
            select(UserBlockModel.id).where(
                or_(
                    and_(
                        UserBlockModel.blocker_id == viewer_id,
                        UserBlockModel.blocked_id == target_id,
                    ),
                    and_(
                        UserBlockModel.blocker_id == target_id,
                        UserBlockModel.blocked_id == viewer_id,
                    ),
                )
            )
        )
        reported = exists(
            select(ProfileCompleintsModel.id).where(
                ProfileCompleintsModel.status.in_(
                    (CompleintStatus.Pending, CompleintStatus.Accepted)
                ),
                or_(
                    and_(
                        ProfileCompleintsModel.sender_id == viewer_id,
                        ProfileCompleintsModel.receiver_id == target_id,
                    ),
                    and_(
                        ProfileCompleintsModel.sender_id == target_id,
                        ProfileCompleintsModel.receiver_id == viewer_id,
                    ),
                ),
            )
        )

        delivery_conditions = [
            DiscoveryDeliveryCursorModel.viewer_id == viewer_id,
            DiscoveryDeliveryCursorModel.target_id == target_id,
            DiscoveryDeliveryCursorModel.mode == mode,
            or_(
                shared,
                and_(
                    or_(
                        DiscoveryDeliveryCursorModel.latest_delivered_at.is_(None),
                        DiscoveryDeliveryCursorModel.latest_delivered_at <= cutoff,
                    ),
                    ~recent_shared_delivery,
                ),
            ),
            or_(
                DiscoveryDeliveryCursorModel.reserved_at.is_(None),
                DiscoveryDeliveryCursorModel.reserved_at < stale_reservation,
            ),
            active_users,
            active_profiles,
            active_viewer_profile,
            ~blocked,
            ~reported,
        ]
        if not shared:
            delivery_conditions.extend(
                [~excluded_decision, ~excluded_match, ~recent_delivery, ~legacy_exclusion]
            )

        updated = await session.execute(
            update(DiscoveryDeliveryCursorModel)
            .where(*delivery_conditions)
            .values(reservation_token=token, reserved_at=now)
        )
        if updated.rowcount != 1:
            await session.rollback()
            return None

        session.add(
            DiscoveryDeliveryEventModel(
                viewer_id=viewer_id,
                target_id=target_id,
                mode=mode,
                source="shared" if shared else "search",
                status="reserved",
                reservation_token=token,
                reserved_at=now,
            )
        )
        await session.execute(
            update(DiscoveryDeliveryEventModel)
            .where(
                DiscoveryDeliveryEventModel.viewer_id == viewer_id,
                DiscoveryDeliveryEventModel.target_id == target_id,
                DiscoveryDeliveryEventModel.mode == mode,
                DiscoveryDeliveryEventModel.status == "reserved",
                DiscoveryDeliveryEventModel.reserved_at < stale_reservation,
                DiscoveryDeliveryEventModel.reservation_token != token,
            )
            .values(status="failed")
        )
        await session.commit()
        return token

    @staticmethod
    async def complete_delivery(
        session: AsyncSession, token: str, delivered: bool
    ) -> None:
        """Finalize a reservation after Telegram confirms or rejects the send."""
        now = datetime.now(timezone.utc)
        event = await session.scalar(
            select(DiscoveryDeliveryEventModel).where(
                DiscoveryDeliveryEventModel.reservation_token == token
            )
        )
        if not event or event.status != "reserved":
            return
        event.status = "delivered" if delivered else "failed"
        if delivered:
            event.delivered_at = now
            await session.execute(
                update(DiscoveryDeliveryCursorModel)
                .where(
                    DiscoveryDeliveryCursorModel.viewer_id == event.viewer_id,
                    DiscoveryDeliveryCursorModel.target_id == event.target_id,
                    DiscoveryDeliveryCursorModel.mode == event.mode,
                    DiscoveryDeliveryCursorModel.reservation_token == token,
                )
                .values(latest_delivered_at=now, reservation_token=None, reserved_at=None)
            )
        else:
            await session.execute(
                update(DiscoveryDeliveryCursorModel)
                .where(
                    DiscoveryDeliveryCursorModel.viewer_id == event.viewer_id,
                    DiscoveryDeliveryCursorModel.target_id == event.target_id,
                    DiscoveryDeliveryCursorModel.mode == event.mode,
                    DiscoveryDeliveryCursorModel.reservation_token == token,
                )
                .values(reservation_token=None, reserved_at=None)
            )
        await session.commit()

    @staticmethod
    async def pending_notifications(session: AsyncSession, recipient_id: int):
        return await session.scalars(
            select(MatchNotificationModel)
            .where(
                MatchNotificationModel.recipient_id == recipient_id,
                MatchNotificationModel.delivered_at.is_(None),
            )
            .order_by(MatchNotificationModel.id)
        )

    @staticmethod
    async def create(
        session: AsyncSession,
        sender_id: int,
        receiver_id: int,
        mail_text: str | None,
        status: int = 1,
        is_active: bool = True,
    ) -> bool:
        """Compatibility adapter for old callers; new history is mode-scoped."""
        mode = await session.scalar(select(UserModel.current_mode).where(UserModel.id == sender_id))
        if status == MatchStatus.Rejected:
            decision = "pass"
        elif status in (MatchStatus.Pending, MatchStatus.Accepted):
            decision = "like"
        else:
            return False
        created, _match_id = await Match.record_decision(
            session, sender_id, receiver_id, mode, decision, mail_text
        )
        return created

    @staticmethod
    async def get_user_matchs(session: AsyncSession, id: int) -> list:
        """
        Возвращает список пользователей, которые связаны с пользователем через лайки.
        Логика:
        1. Показывать активные лайки (is_active = True)
        2. Показывать лайки, полученные от других пользователей (receiver_id = id)
        3. Показывать взаимные лайки (где пользователь отправитель, но получил ответ status = 2)
        """

        incoming = await session.scalars(
            select(InteractionDecisionModel.actor_id).where(
                InteractionDecisionModel.target_id == id,
                InteractionDecisionModel.decision == "like",
            )
        )
        ids = set(incoming.all())
        legacy = await session.scalars(
            select(MatchModel.sender_id)
            .where(MatchModel.receiver_id == id)
            .where(MatchModel.status == MatchStatus.Pending)
            .where(MatchModel.is_active.is_(True))
        )
        ids.update(legacy.all())
        return list(ids)

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
        
        incoming = await session.scalars(
            select(InteractionDecisionModel.actor_id).where(
                InteractionDecisionModel.target_id == id,
                InteractionDecisionModel.mode == mode,
                InteractionDecisionModel.decision == "like",
            )
        )
        matched = await session.scalars(
            select(
                case(
                    (PairMatchModel.user_low_id == id, PairMatchModel.user_high_id),
                    else_=PairMatchModel.user_low_id,
                )
            ).where(
                PairMatchModel.mode == mode,
                or_(PairMatchModel.user_low_id == id, PairMatchModel.user_high_id == id),
            )
        )
        legacy = await session.scalars(
            select(MatchModel.sender_id)
            .where(MatchModel.receiver_id == id)
            .where(MatchModel.status == MatchStatus.Pending)
            .where(MatchModel.is_active.is_(True))
            .where(or_(MatchModel.mode == mode, MatchModel.mode == "legacy"))
        )
        return list(dict.fromkeys([*incoming.all(), *matched.all(), *legacy.all()]))

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
