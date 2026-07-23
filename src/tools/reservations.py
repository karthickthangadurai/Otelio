"""Reservation service. All booking rules live here — not in the prompt."""

import re
import secrets
from datetime import datetime, date

from src.db import get_connection
from src.config import ROOM_TYPES, DEFAULT_ROOM_TYPE, HOTEL_ID, ROOM_INVENTORY


NOT_FOUND = {"ok": False, "error": "No reservation found with that ID and email."}


def _valid_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _availability_error(conn, room_type, check_in, check_out, exclude_id=None):
    """Return an error dict if that room type is sold out for the dates, else None."""
    sql = (
        "SELECT COUNT(*) AS n FROM reservations "
        "WHERE room_type = ? AND status = 'active' "
        "AND check_in < ? AND check_out > ?"
    )
    params = [room_type, check_out, check_in]
    if exclude_id:
        sql += " AND reservation_id != ?"
        params.append(exclude_id)
    booked = conn.execute(sql, params).fetchone()["n"]
    capacity = ROOM_INVENTORY.get(room_type, 0)
    if booked >= capacity:
        return {
            "ok": False,
            "error": (
                f"No {room_type} rooms available for {check_in} to {check_out}. "
                f"Sold out ({capacity} total)."
            ),
        }
    return None


def create_reservation(guest_name, email, check_in, check_out,
                       room_type=DEFAULT_ROOM_TYPE):
    
    """Create a reservation.

    Only call once the guest has given all four: name, email, check-in,
    check-out. Ask for anything missing. Never invent values.

    Args:
        guest_name: Guest's full name.
        email: Guest's email address.
        check_in: Arrival date, YYYY-MM-DD.
        check_out: Departure date, YYYY-MM-DD, after check_in.
        room_type: "standard", "deluxe", or "suite".

    Returns:
        Reservation ID and details, or an error message.
    """
        
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
        sold_out = _availability_error(conn, room_type, check_in, check_out)
        if sold_out:
            return sold_out
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

    """Look up one reservation.

    Requires both the reservation ID and the email it was booked under; ask for
    whichever is missing. Returns a single reservation only — bulk listing is
    not possible.

    Args:
        reservation_id: Booking reference, e.g. "RES-A3F8C1".
        email: Email on the reservation.

    Returns:
        Reservation details, or a not-found message.
    """
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


def list_reservations(email):
    """List all reservations for one guest email."""
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""):
        return {"ok": False, "error": "A valid email address is required."}

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT reservation_id, guest_name, check_in, check_out, room_type, status "
            "FROM reservations WHERE email = ? ORDER BY check_in",
            (email.strip().lower(),),
        ).fetchall()
    finally:
        conn.close()

    return {
        "ok": True,
        "count": len(rows),
        "reservations": [
            {
                "reservation_id": r["reservation_id"],
                "guest_name": r["guest_name"],
                "check_in": r["check_in"],
                "check_out": r["check_out"],
                "room_type": r["room_type"],
                "status": r["status"],
            }
            for r in rows
        ],
    }


def modify_reservation(reservation_id, email, check_in=None, check_out=None,
                       room_type=None):
    """Update dates and/or room type on an active reservation.

    Requires reservation ID and email. Pass only the fields the guest wants to
    change. Ask for anything missing. Never invent values.
    """
    if check_in is None and check_out is None and room_type is None:
        return {"ok": False, "error": "Provide at least one of: check_in, check_out, room_type."}

    rid = reservation_id.strip().upper()
    em = email.strip().lower()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM reservations WHERE reservation_id = ? AND email = ?",
            (rid, em),
        ).fetchone()
        if row is None:
            return NOT_FOUND
        if row["status"] == "cancelled":
            return {"ok": False, "error": "Cannot modify a cancelled reservation."}

        new_in = check_in if check_in is not None else row["check_in"]
        new_out = check_out if check_out is not None else row["check_out"]
        new_room = room_type if room_type is not None else row["room_type"]

        ci, co = _valid_date(new_in), _valid_date(new_out)
        if not ci or not co:
            return {"ok": False, "error": "Dates must be in YYYY-MM-DD format."}
        if ci < date.today():
            return {"ok": False, "error": "Check-in date cannot be in the past."}
        if co <= ci:
            return {"ok": False, "error": "Check-out must be after check-in."}
        if new_room not in ROOM_TYPES:
            return {"ok": False, "error": f"Room type must be one of: {', '.join(sorted(ROOM_TYPES))}."}

        sold_out = _availability_error(conn, new_room, new_in, new_out, exclude_id=rid)
        if sold_out:
            return sold_out

        conn.execute(
            "UPDATE reservations SET check_in = ?, check_out = ?, room_type = ? "
            "WHERE reservation_id = ?",
            (new_in, new_out, new_room, rid),
        )
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "reservation_id": rid, "check_in": new_in,
            "check_out": new_out, "room_type": new_room, "status": "active"}


def cancel_reservation(reservation_id, email):

    """Cancel a reservation.

    Requires both the reservation ID and the email it was booked under. Confirm
    with the guest before calling.

    Args:
        reservation_id: Booking reference, e.g. "RES-A3F8C1".
        email: Email on the reservation.

    Returns:
        Cancellation confirmation, or a not-found message.
    """
    
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