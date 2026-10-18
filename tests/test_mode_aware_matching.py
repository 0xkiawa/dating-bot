# ruff: noqa: E402
import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("BOT_TOKEN", "123456:test-token")

from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import database.models  # noqa: F401
from database.models.base import BaseModel
from database.models.match import (
    DiscoveryDeliveryCursorModel,
    DiscoveryDeliveryEventModel,
    InteractionDecisionModel,
    MatchNotificationModel,
    PairMatchModel,
)
from database.models.profile import ProfileModel
from database.models.user import UserModel
from database.schema import backfill_legacy_pair_matches, ensure_mode_aware_matching_columns
from database.services.match import Match
from database.services.search import search_profiles
from database.services.user import User


class ModeAwareMatchingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp_root = Path(__file__).resolve().parents[1] / ".test-tmp"
        temp_root.mkdir(exist_ok=True)
        database_fd, database_name = tempfile.mkstemp(
            prefix="mode_matching_", suffix=".sqlite3", dir=temp_root
        )
        os.close(database_fd)
        self.database_path = Path(database_name)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.database_path}")
        async with self.engine.begin() as connection:
            await connection.run_sync(BaseModel.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as session:
            for user_id in (101, 202):
                session.add(UserModel(id=user_id, current_mode="fun", status=1))
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
            await session.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.database_path.unlink(missing_ok=True)

    async def test_mode_specific_mutual_likes_and_duplicate_callback(self):
        async with self.sessions() as session:
            created, match_id = await Match.record_decision(
                session, 101, 202, "fun", "like"
            )
            self.assertTrue(created)
            self.assertIsNone(match_id)

            _, cross_mode_match = await Match.record_decision(
                session, 202, 101, "dates", "like"
            )
            self.assertIsNone(cross_mode_match)

            _, match_id = await Match.record_decision(session, 202, 101, "fun", "like")
            self.assertIsNotNone(match_id)
            _, repeated_match_id = await Match.record_decision(
                session, 202, 101, "fun", "like"
            )
            self.assertEqual(match_id, repeated_match_id)

            matches = list((await session.scalars(select(PairMatchModel))).all())
            decisions = list((await session.scalars(select(InteractionDecisionModel))).all())
            notifications = list((await session.scalars(select(MatchNotificationModel))).all())
            self.assertEqual([(101, 202, "fun")], [
                (match.user_low_id, match.user_high_id, match.mode) for match in matches
            ])
            self.assertEqual(3, len(decisions))
            self.assertEqual(2, len(notifications))

    async def test_pass_is_permanent_in_its_mode_but_other_modes_are_independent(self):
        async with self.sessions() as session:
            await Match.record_decision(session, 101, 202, "dates", "pass")
            for user_id in (101, 202):
                account = await session.get(UserModel, user_id)
                account.current_mode = "dates"
            await session.commit()
            viewer = await session.get(ProfileModel, 101)
            candidate_ids = await search_profiles(
                session, viewer, user_mode="dates", force_shuffle=False
            )
            self.assertNotIn(202, candidate_ids)

            for user_id in (101, 202):
                account = await session.get(UserModel, user_id)
                account.current_mode = "friends"
            await session.commit()
            candidate_ids = await search_profiles(
                session, viewer, user_mode="friends", force_shuffle=False
            )
            self.assertIn(202, candidate_ids)

    async def test_delivery_cooldown_tracks_success_and_failed_send_is_retryable(self):
        async with self.sessions() as session:
            token = await Match.reserve_delivery(session, 101, 202, "fun")
            self.assertIsNotNone(token)
            await Match.complete_delivery(session, token, delivered=False)
            retry = await Match.reserve_delivery(session, 101, 202, "fun")
            self.assertIsNotNone(retry)
            await Match.complete_delivery(session, retry, delivered=True)

            blocked_by_cooldown = await Match.reserve_delivery(session, 101, 202, "fun")
            self.assertIsNone(blocked_by_cooldown)

            old = datetime.now(timezone.utc) - timedelta(days=21)
            cursor = await session.scalar(select(DiscoveryDeliveryCursorModel))
            cursor.latest_delivered_at = old
            events = list((await session.scalars(select(DiscoveryDeliveryEventModel))).all())
            for event in events:
                if event.status == "delivered":
                    event.delivered_at = old
            await session.commit()
            rediscovered = await Match.reserve_delivery(session, 101, 202, "fun")
            self.assertIsNotNone(rediscovered)

    async def test_delivery_history_is_directional_and_mode_scoped(self):
        async with self.sessions() as session:
            token = await Match.reserve_delivery(session, 101, 202, "fun")
            await Match.complete_delivery(session, token, delivered=True)
            self.assertIsNone(await Match.reserve_delivery(session, 101, 202, "fun"))

            # The reverse viewer-target pair has its own cooldown clock.
            reverse = await Match.reserve_delivery(session, 202, 101, "fun")
            self.assertIsNotNone(reverse)
            await Match.complete_delivery(session, reverse, delivered=True)

            for user_id in (101, 202):
                account = await session.get(UserModel, user_id)
                account.current_mode = "dates"
            await session.commit()
            other_mode = await Match.reserve_delivery(session, 101, 202, "dates")
            self.assertIsNotNone(other_mode)

    async def test_mode_switch_preserves_pending_like_and_match_history(self):
        async with self.sessions() as session:
            await Match.record_decision(session, 101, 202, "fun", "like")
            user = await session.get(UserModel, 101)
            user.current_mode = "dates"
            await session.commit()
            pending = await Match.inbox_items(session, 202)
            self.assertEqual([("like", "fun")], [(item["kind"], item["mode"]) for item in pending])

            await Match.record_decision(session, 202, 101, "fun", "like")
            match = await session.scalar(select(PairMatchModel))
            self.assertEqual("fun", match.mode)
            decisions = list((await session.scalars(select(InteractionDecisionModel))).all())
            self.assertEqual(2, len(decisions))
            items = await Match.inbox_items(session, 101)
            self.assertEqual([("match", "fun")], [(item["kind"], item["mode"]) for item in items])

    async def test_pending_like_is_not_a_rediscovery_timer(self):
        async with self.sessions() as session:
            await Match.record_decision(session, 101, 202, "fun", "like")
            decision = await session.scalar(select(InteractionDecisionModel))
            decision.created_at = datetime.now(timezone.utc) - timedelta(days=90)
            await session.commit()
            viewer = await session.get(ProfileModel, 101)
            self.assertNotIn(
                202,
                await search_profiles(session, viewer, user_mode="fun", force_shuffle=False),
            )
            decisions = list((await session.scalars(select(InteractionDecisionModel))).all())
            self.assertEqual(1, len(decisions))

    async def test_target_mode_is_rechecked_before_delivery(self):
        async with self.sessions() as session:
            target = await session.get(UserModel, 202)
            target.current_mode = "dates"
            await session.commit()
            self.assertIsNone(await Match.reserve_delivery(session, 101, 202, "fun"))

    async def test_ranked_but_undelivered_candidate_has_no_view_event(self):
        async with self.sessions() as session:
            viewer = await session.get(ProfileModel, 101)
            self.assertIn(
                202,
                await search_profiles(session, viewer, user_mode="fun", force_shuffle=False),
            )
            self.assertEqual(
                0,
                len(list((await session.scalars(select(DiscoveryDeliveryEventModel))).all())),
            )

    async def test_global_block_excludes_both_directions(self):
        async with self.sessions() as session:
            self.assertTrue(await User.block(session, 101, 202))
            created, match_id = await Match.record_decision(session, 101, 202, "fun", "like")
            self.assertFalse(created)
            self.assertIsNone(match_id)
            viewer = await session.get(ProfileModel, 101)
            for mode in ("fun", "dates", "friends"):
                for user_id in (101, 202):
                    account = await session.get(UserModel, user_id)
                    account.current_mode = mode
                await session.commit()
                self.assertIsNone(await Match.reserve_delivery(session, 101, 202, mode))
                self.assertIsNone(await Match.reserve_delivery(session, 202, 101, mode))
                viewer = await session.get(ProfileModel, 101)
                self.assertNotIn(
                    202,
                    await search_profiles(session, viewer, user_mode=mode, force_shuffle=False),
                )
            await User.unblock(session, 101, 202)
            for user_id in (101, 202):
                account = await session.get(UserModel, user_id)
                account.current_mode = "fun"
            await session.commit()
            self.assertIsNotNone(await Match.reserve_delivery(session, 101, 202, "fun"))

    async def test_concurrent_reciprocal_likes_create_one_match(self):
        async def like(actor, target):
            async with self.sessions() as session:
                return await Match.record_decision(session, actor, target, "friends", "like")

        await asyncio.gather(like(101, 202), like(202, 101))
        async with self.sessions() as session:
            matches = list((await session.scalars(select(PairMatchModel))).all())
            self.assertEqual(1, len(matches))
            self.assertEqual("friends", matches[0].mode)


class LegacyMatchingMigrationTests(unittest.TestCase):
    def test_mode_backfill_and_accepted_match_preservation(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE users (id INTEGER PRIMARY KEY, current_mode TEXT)")
            )
            connection.execute(
                text(
                    "CREATE TABLE matchs (id INTEGER PRIMARY KEY, sender_id INTEGER, "
                    "receiver_id INTEGER, status INTEGER, created_at DATETIME, updated_at DATETIME)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE pair_matches (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "user_low_id INTEGER NOT NULL, user_high_id INTEGER NOT NULL, "
                    "mode TEXT NOT NULL, "
                    "created_at DATETIME, updated_at DATETIME, "
                    "UNIQUE(user_low_id, user_high_id, mode))"
                )
            )
            connection.execute(text("INSERT INTO users VALUES (101, 'fun'), (202, NULL)"))
            connection.execute(
                text(
                    "INSERT INTO matchs VALUES "
                    "(1, 101, 202, 2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
                    "(2, 202, 101, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            ensure_mode_aware_matching_columns(connection)
            backfill_legacy_pair_matches(connection)
            modes = connection.execute(text("SELECT id, mode FROM matchs ORDER BY id")).all()
            match = connection.execute(
                text("SELECT user_low_id, user_high_id, mode FROM pair_matches")
            ).one()
        engine.dispose()
        self.assertEqual([(1, "legacy"), (2, "legacy")], modes)
        self.assertEqual((101, 202, "legacy"), match)


if __name__ == "__main__":
    unittest.main()
