"""Reservation service. All booking rules live here — not in the prompt."""

import re
import secrets
from datetime import datetime, date

from src.db import get_connection
from src.config import ROOM_TYPES, DEFAULT_ROOM_TYPE, HOTEL_ID


NOT_FOUND = {"ok": False, "error": "No reservation found with that ID and email."}


def _valid_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def create_reservation(guest_name, email, check_in, check_out,
                       room_type=DEFAULT_ROOM_TYPE):
    if not guest_name or not guest_name.strip():
        return {"ok": False, "error": "Guest name is required."}
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""):
        return {"ok": False, "error": "A valid email address is required."}

    ci, co = _valid_date(check_in), _valid_date(check_out)
    if not ci or not co:
        return {"ok": False, "error": "Dates must be in YYYY-MM-DD format."}
    if ci < date.today():
        return {"ok": False, "error": "Check-in date cannot be in the past."}
    if co <= ci:
        return {"ok": False, "error": "Check-out must be after check-in."}
    if room_type not in ROOM_TYPES:
        return {"ok": False, "error": f"Room type must be one of: {', '.join(sorted(ROOM_TYPES))}."}

    rid = f"RES-{secrets.token_hex(3).upper()}"
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO reservations VALUES (?,?,?,?,?,?,?,?,?)",
            (rid, HOTEL_ID, guest_name.strip(), email.strip().lower(),
             check_in, check_out, room_type, "active",
             datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "reservation_id": rid, "check_in": check_in,
            "check_out": check_out, "room_type": room_type}


def get_reservation(reservation_id, email):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM reservations WHERE reservation_id = ? AND email = ?",
            (reservation_id.strip().upper(), email.strip().lower()),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return NOT_FOUND
    return {"ok": True, "reservation_id": row["reservation_id"],
            "guest_name": row["guest_name"], "check_in": row["check_in"],
            "check_out": row["check_out"], "room_type": row["room_type"],
            "status": row["status"]}


def cancel_reservation(reservation_id, email):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT status FROM reservations WHERE reservation_id = ? AND email = ?",
            (reservation_id.strip().upper(), email.strip().lower()),
        ).fetchone()
        if row is None:
            return NOT_FOUND
        if row["status"] == "cancelled":
            return {"ok": True, "reservation_id": reservation_id,
                    "status": "cancelled", "note": "This reservation was already cancelled."}
        conn.execute(
            "UPDATE reservations SET status = 'cancelled' WHERE reservation_id = ?",
            (reservation_id.strip().upper(),),
        )
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "reservation_id": reservation_id, "status": "cancelled"}