# ruff: noqa: E402
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("BOT_TOKEN", "123456:test-token")

from aiogram.types import Chat, Message, User as TelegramUser
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from data.config import search
import database.models  # noqa: F401
from database.models.base import BaseModel
from database.models.share import PendingSharedViewModel, ShareLinkModel
from database.models.match import DiscoveryDeliveryCursorModel, DiscoveryDeliveryEventModel
from database.models.profile import ProfileModel
from database.models.referal import ReferalModel
from database.models.user import UserBlockModel, UserModel, UserStatus
from database.services.share import (
    ADJECTIVES,
    NOUNS,
    _choose_unused_slug,
    get_pending_shared_view,
    get_share_start_payload,
    generate_share_slug,
    insert_shared_profile,
    is_valid_share_slug,
    issue_or_reroll_share_link,
    resolve_share_slug,
    save_pending_shared_view,
    shared_target_is_eligible,
)
from database.services.match import Match
from database.models.match import InteractionDecisionModel
from app.middlewares.common import CommonMiddleware
from utils.base62 import encode_base62


class ShareLinkTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp_root = Path(__file__).resolve().parents[1] / ".test-tmp"
        temp_root.mkdir(exist_ok=True)
        database_fd, database_name = tempfile.mkstemp(
            prefix="share_links_", suffix=".sqlite3", dir=temp_root
        )
        os.close(database_fd)
        self.database_path = Path(database_name)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.database_path}")
        async with self.engine.begin() as connection:
            await connection.run_sync(BaseModel.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as session:
            for user_id, mode in ((101, "dates"), (202, "fun"), (303, "friends")):
                session.add(UserModel(id=user_id, current_mode=mode, status=UserStatus.User))
                session.add(
                    ProfileModel(
                        id=user_id,
                        name=f"User {user_id}",
                        role="top",
                        find_role="all",
                        city="Nairobi",
                        latitude=-1.29,
                        longitude=36.82,
                        age=30,
                        is_active=True,
                    )
                )
            session.add(ShareLinkModel(user_id=202, slug="velvet-lion", is_enabled=True))
            await session.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.database_path.unlink(missing_ok=True)

    def test_word_pair_slug_rules_and_referral_isolation(self):
        self.assertTrue(is_valid_share_slug("velvet-lion"))
        self.assertTrue(is_valid_share_slug(generate_share_slug()))
        self.assertTrue(is_valid_share_slug("velvet-lion-7"))
        self.assertFalse(is_valid_share_slug("admin-help"))
        self.assertFalse(is_valid_share_slug("velvet_lion"))
        self.assertFalse(is_valid_share_slug("velvet-lion-123"))
        self.assertTrue(ADJECTIVES)
        self.assertTrue(NOUNS)
        self.assertIsNone(get_share_start_payload("/start usr_Qr9"))
        self.assertIsNone(get_share_start_payload("/start@conqueerbot usr_Qr9"))
        self.assertEqual("velvet-lion", get_share_start_payload("/start velvet-lion"))
        self.assertEqual(
            "velvet-lion-7",
            get_share_start_payload("/start@conqueerbot velvet-lion-7"),
        )

    def test_shared_profile_is_third_or_last_and_is_not_duplicated(self):
        self.assertEqual([10, 11, 202, 12], insert_shared_profile([10, 202, 11, 12], 202))
        self.assertEqual([10, 202], insert_shared_profile([10], 202))
        self.assertEqual([202], insert_shared_profile([], 202))

    async def test_share_click_never_creates_a_referral_and_usr_links_still_do(self):
        async def next_handler(_event, _data):
            return "handled"

        async with self.sessions() as session:
            share_message = Message(
                message_id=1,
                date=datetime.now(UTC),
                chat=Chat(id=404, type="private"),
                from_user=TelegramUser(
                    id=404, is_bot=False, first_name="Visitor", language_code="en"
                ),
                text="/start velvet-lion",
            )
            await CommonMiddleware()(
                next_handler,
                share_message,
                {
                    "session": session,
                    "command": SimpleNamespace(args="velvet-lion"),
                    "consent_gate_checked": True,
                },
            )
            self.assertEqual(
                0,
                await session.scalar(
                    select(func.count(ReferalModel.id)).where(ReferalModel.user_id == 404)
                ),
            )

            invite_payload = f"usr_{encode_base62(202)}"
            invite_message = Message(
                message_id=2,
                date=datetime.now(UTC),
                chat=Chat(id=405, type="private"),
                from_user=TelegramUser(
                    id=405, is_bot=False, first_name="Invitee", language_code="en"
                ),
                text=f"/start {invite_payload}",
            )
            await CommonMiddleware()(
                next_handler,
                invite_message,
                {
                    "session": session,
                    "command": SimpleNamespace(args=invite_payload),
                    "consent_gate_checked": True,
                },
            )
            referral = await session.scalar(
                select(ReferalModel).where(ReferalModel.user_id == 405)
            )
            self.assertIsNotNone(referral)
            self.assertEqual(202, referral.inviter_id)

    async def test_slug_collision_gets_a_short_random_suffix(self):
        async with self.sessions() as session:
            with (
                patch("database.services.share.generate_share_slug", return_value="velvet-lion"),
                patch("database.services.share.secrets.randbelow", return_value=6),
            ):
                self.assertEqual("velvet-lion-7", await _choose_unused_slug(session))

    async def test_reroll_invalidates_old_slug_and_pending_click(self):
        async with self.sessions() as session:
            await save_pending_shared_view(session, 101, 202)
            link = await issue_or_reroll_share_link(session, 202, reroll=True)
            self.assertNotEqual("velvet-lion", link.slug)
            self.assertTrue(link.is_enabled)
            self.assertIsNone(await resolve_share_slug(session, "velvet-lion"))
            self.assertIsNone(await get_pending_shared_view(session, 101))

    async def test_resolution_checks_link_profile_and_ban_status(self):
        async with self.sessions() as session:
            self.assertEqual(202, (await resolve_share_slug(session, "velvet-lion")).id)
            self.assertIsNone(await resolve_share_slug(session, "unknown-wolf"))

            link = await session.get(ShareLinkModel, 202)
            link.is_enabled = False
            await session.commit()
            self.assertIsNone(await resolve_share_slug(session, "velvet-lion"))

            link.is_enabled = True
            target = await session.get(ProfileModel, 202)
            target.is_active = False
            await session.commit()
            self.assertIsNone(await resolve_share_slug(session, "velvet-lion"))

            target.is_active = True
            owner = await session.get(UserModel, 202)
            owner.status = UserStatus.Banned
            await session.commit()
            self.assertIsNone(await resolve_share_slug(session, "velvet-lion"))

    async def test_pending_click_is_replaced_and_expired_after_fourteen_days(self):
        async with self.sessions() as session:
            await save_pending_shared_view(session, 101, 202)
            await save_pending_shared_view(session, 101, 303)
            pending = await get_pending_shared_view(session, 101)
            self.assertEqual(303, pending.target_id)
            self.assertEqual(
                1,
                await session.scalar(
                    select(func.count(PendingSharedViewModel.id)).where(
                        PendingSharedViewModel.viewer_id == 101,
                        PendingSharedViewModel.status == "pending",
                    )
                ),
            )

            pending.created_at = datetime.now(UTC) - timedelta(days=15)
            await session.commit()
            self.assertIsNone(await get_pending_shared_view(session, 101))

    async def test_eligibility_rejects_self_disabled_profiles_and_global_blocks(self):
        async with self.sessions() as session:
            self.assertIsNone(await shared_target_is_eligible(session, 202, 202))
            self.assertEqual(202, (await shared_target_is_eligible(session, 101, 202)).id)

            session.add(UserBlockModel(blocker_id=101, blocked_id=202))
            await session.commit()
            self.assertIsNone(await shared_target_is_eligible(session, 101, 202))

            await session.delete(await session.get(UserBlockModel, 1))
            link = await session.get(ShareLinkModel, 202)
            link.is_enabled = False
            await session.commit()
            self.assertIsNone(await shared_target_is_eligible(session, 101, 202))

    async def test_shared_delivery_uses_the_rediscovery_cooldown(self):
        async with self.sessions() as session:
            await Match.record_decision(session, 101, 202, "fun", "pass")
            token = await Match.reserve_delivery(
                session, 101, 202, "fun", shared=True
            )
            self.assertIsNotNone(token)
            await Match.complete_delivery(session, token, delivered=True)

            event = await session.scalar(select(DiscoveryDeliveryEventModel))
            self.assertEqual("shared", event.source)
            self.assertEqual(4, search.REDISCOVERY_COOLDOWN_DAYS)
            self.assertEqual(4, search.SHARED_DELIVERY_COOLDOWN_DAYS)
            decision = await session.scalar(select(InteractionDecisionModel))
            await session.delete(decision)
            viewer = await session.get(UserModel, 101)
            viewer.current_mode = "fun"
            await session.commit()

            self.assertIsNone(await Match.reserve_delivery(session, 101, 202, "fun"))

            event = await session.scalar(select(DiscoveryDeliveryEventModel))
            cursor = await session.scalar(select(DiscoveryDeliveryCursorModel))
            old_delivery = datetime.now(UTC) - timedelta(
                days=search.SHARED_DELIVERY_COOLDOWN_DAYS + 1
            )
            event.delivered_at = old_delivery
            cursor.latest_delivered_at = old_delivery
            await session.commit()

            self.assertIsNotNone(await Match.reserve_delivery(session, 101, 202, "fun"))


if __name__ == "__main__":
    unittest.main()
