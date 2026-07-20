"""SQLite connection + schema for reservations."""

import sqlite3
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id  TEXT PRIMARY KEY,
    hotel_id        TEXT NOT NULL,
    guest_name      TEXT NOT NULL,
    email           TEXT NOT NULL,
    check_in        TEXT NOT NULL,
    check_out       TEXT NOT NULL,
    room_type       TEXT NOT NULL DEFAULT 'standard',
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL
);
"""

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # rows behave like dicts: row["email"]
    conn.execute(SCHEMA)
    return conn