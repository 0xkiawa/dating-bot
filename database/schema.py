from sqlalchemy import inspect, text


def ensure_profile_match_columns(connection) -> None:
    """Add the matching-preference columns to databases created by older releases."""
    columns = {
        column["name"] for column in inspect(connection).get_columns("profiles")
    }
    additions = {
        "preferred_age_min": "INTEGER",
        "preferred_age_max": "INTEGER",
        "preferred_distance_km": "INTEGER",
        "interests": "JSON NOT NULL DEFAULT '[]'",
        "dating_intent": "VARCHAR(20) NOT NULL DEFAULT 'open'",
    }

    for name, definition in additions.items():
        if name not in columns:
            connection.execute(
                text(f"ALTER TABLE profiles ADD COLUMN {name} {definition}")
            )


def ensure_user_consent_columns(connection) -> None:
    """Add consent tracking fields to databases created by older releases."""
    columns = {column["name"] for column in inspect(connection).get_columns("users")}
    additions = {
        "consent_version": "VARCHAR(64)",
        "consented_at": "TIMESTAMP WITH TIME ZONE",
    }

    for name, definition in additions.items():
        if name not in columns:
            connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {definition}"))


def ensure_mode_aware_matching_columns(connection) -> None:
    """Upgrade old installs in place without deleting any swipe history."""
    tables = set(inspect(connection).get_table_names())
    if "matchs" not in tables:
        return

    columns = {column["name"] for column in inspect(connection).get_columns("matchs")}
    if "mode" not in columns:
        connection.execute(text("ALTER TABLE matchs ADD COLUMN mode VARCHAR(20)"))

    # The old table had no interaction mode. A user's current mode does not
    # reliably reveal the mode at swipe time, so preserve this history as legacy.
    connection.execute(text("UPDATE matchs SET mode = 'legacy' WHERE mode IS NULL"))


def backfill_legacy_pair_matches(connection) -> None:
    """Expose accepted pre-migration Likes as matches with an explicit mode."""
    tables = set(inspect(connection).get_table_names())
    if not {"matchs", "pair_matches"}.issubset(tables):
        return
    connection.execute(
        text(
            "INSERT INTO pair_matches (user_low_id, user_high_id, mode, created_at, updated_at) "
            "SELECT CASE WHEN sender_id < receiver_id THEN sender_id ELSE receiver_id END, "
            "CASE WHEN sender_id < receiver_id THEN receiver_id ELSE sender_id END, "
            "COALESCE(mode, 'legacy'), COALESCE(created_at, CURRENT_TIMESTAMP), "
            "COALESCE(updated_at, CURRENT_TIMESTAMP) FROM matchs "
            "WHERE status = 2 "
            "ON CONFLICT (user_low_id, user_high_id, mode) DO NOTHING"
        )
    )
