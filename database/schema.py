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
