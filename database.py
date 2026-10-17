import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DATABASE = "calibrations.db"


def _now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS calibrations (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                calibration_type TEXT    NOT NULL,
                value            REAL    NOT NULL,
                timestamp        TEXT    NOT NULL,
                username         TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tags (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT    NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS tags_calibrations (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_id         INTEGER NOT NULL REFERENCES tags(id),
                calibration_id INTEGER NOT NULL REFERENCES calibrations(id),
                time_added     TEXT    NOT NULL,
                time_removed   TEXT
            );
        """)


def seed_db(records):
    now = _now()
    with get_db() as conn:
        conn.executemany(
            "INSERT INTO calibrations (calibration_type, value, timestamp, username) VALUES (?, ?, ?, ?)",
            [(r["calibration_type"], r["value"], now, r["username"]) for r in records],
        )


# ---------------------------------------------------------------------------
# Calibrations
# ---------------------------------------------------------------------------

def create_calibration(calibration_type, value, username):
    now = _now()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO calibrations (calibration_type, value, timestamp, username) VALUES (?, ?, ?, ?)",
            (calibration_type, value, now, username),
        )
        return {
            "id": cursor.lastrowid,
            "calibration_type": calibration_type,
            "value": value,
            "timestamp": now,
            "username": username,
        }


def get_calibrations(user=None, cal_type=None, tag=None, start=None, end=None):
    query = "SELECT DISTINCT c.* FROM calibrations c"
    params = []

    if tag:
        query += (
            " JOIN tags_calibrations tc ON tc.calibration_id = c.id"
            " JOIN tags t ON t.id = tc.tag_id"
        )

    conditions = []
    if user:
        conditions.append("c.username = ?")
        params.append(user)
    if cal_type:
        conditions.append("c.calibration_type = ?")
        params.append(cal_type)
    if tag:
        conditions.append("t.name = ?")
        params.append(tag)
        conditions.append("tc.time_removed IS NULL")
    if start:
        conditions.append("c.timestamp >= ?")
        params.append(start)
    if end:
        conditions.append("c.timestamp <= ?")
        params.append(end)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY c.timestamp DESC"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Tag associations
# ---------------------------------------------------------------------------

def add_to_tag(cal_id, tag_name):
    """
    Add calibration to a tag. Creates the tag if it does not exist.
    Returns (result_dict, error_str) where error_str is None on success.
    Errors: "calibration_not_found", "already_in_tag"
    """
    now = _now()
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM calibrations WHERE id = ?", (cal_id,)).fetchone():
            return None, "calibration_not_found"

        tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
        if tag_row:
            tag_id = tag_row["id"]
        else:
            tag_id = conn.execute(
                "INSERT INTO tags (name) VALUES (?)", (tag_name,)
            ).lastrowid

        active = conn.execute(
            "SELECT 1 FROM tags_calibrations"
            " WHERE tag_id = ? AND calibration_id = ? AND time_removed IS NULL",
            (tag_id, cal_id),
        ).fetchone()
        if active:
            return None, "already_in_tag"

        conn.execute(
            "INSERT INTO tags_calibrations (tag_id, calibration_id, time_added) VALUES (?, ?, ?)",
            (tag_id, cal_id, now),
        )
        return {"calibration_id": cal_id, "tag": tag_name, "time_added": now}, None


def remove_from_tag(cal_id, tag_name):
    """
    Remove active association between a calibration and a tag.
    Returns (success_bool, error_str).
    Errors: "not_found" (tag doesn't exist or calibration is not currently in it)
    """
    now = _now()
    with get_db() as conn:
        tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
        if not tag_row:
            return False, "not_found"

        result = conn.execute(
            "UPDATE tags_calibrations SET time_removed = ?"
            " WHERE tag_id = ? AND calibration_id = ? AND time_removed IS NULL",
            (now, tag_row["id"], cal_id),
        )
        if result.rowcount == 0:
            return False, "not_found"

        return True, None


def get_tags_for_calibration(cal_id):
    """
    Return all tag associations (active and historical) for a calibration.
    Returns None if the calibration does not exist.
    """
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM calibrations WHERE id = ?", (cal_id,)).fetchone():
            return None

        rows = conn.execute(
            """
            SELECT t.name, tc.time_added, tc.time_removed
            FROM tags_calibrations tc
            JOIN tags t ON t.id = tc.tag_id
            WHERE tc.calibration_id = ?
            ORDER BY tc.time_added DESC
            """,
            (cal_id,),
        ).fetchall()
        return [dict(row) for row in rows]
