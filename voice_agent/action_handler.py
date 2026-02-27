"""
action_handler.py
-----------------
Pure Python DB actions — NO LLM calls.

All functions receive the SQLAlchemy `db` object as a parameter so this
module has no direct dependency on app.py at import time.
"""

import uuid
from datetime import datetime, timezone


def find_matching_slots(db, specialty: str | None, preferred_date: str | None,
                        preferred_time: str | None) -> list:
    """
    Find available AppointmentSlot rows matching the patient's preferences.

    Matching is intentionally fuzzy:
    - specialty: case-insensitive substring match (e.g. "heart" matches "Cardiology")
    - preferred_date / preferred_time: stored as free text, matched via string contains
      (exact scheduling is out of scope for this demo — a real system would parse dates)

    Returns a list of AppointmentSlot ORM objects (max 5), ordered by slot_datetime.
    """
    from app import AppointmentSlot  # lazy import

    query = AppointmentSlot.query.filter_by(is_available=True)

    # Specialty synonym map for common lay terms
    SPECIALTY_SYNONYMS = {
        "heart": "cardiology",
        "cardiac": "cardiology",
        "skin": "dermatology",
        "rash": "dermatology",
        "acne": "dermatology",
        "bone": "orthopaedics",
        "joint": "orthopaedics",
        "knee": "orthopaedics",
        "back": "orthopaedics",
        "general": "general practice",
        "gp": "general practice",
        "cough": "general practice",
        "fever": "general practice",
        "flu": "general practice",
        "cold": "general practice",
    }

    if specialty:
        normalized_specialty = SPECIALTY_SYNONYMS.get(specialty.lower(), specialty.lower())
        query = query.filter(
            AppointmentSlot.specialty.ilike(f"%{normalized_specialty}%")
        )

    slots = query.order_by(AppointmentSlot.slot_datetime).limit(5).all()

    # Time-of-day filtering (morning / afternoon) — applied in Python after DB fetch
    if preferred_time and slots:
        time_lower = preferred_time.lower()
        if "morning" in time_lower or "am" in time_lower:
            slots = [s for s in slots if s.slot_datetime.hour < 12] or slots
        elif "afternoon" in time_lower or "pm" in time_lower:
            slots = [s for s in slots if s.slot_datetime.hour >= 12] or slots

    return slots


def execute_booking(db, booking_session_id: str, slot_id: str) -> str:
    """
    Confirm the booking: mark the slot as taken, update BookingSession state.

    Returns a short booking reference string (e.g. "BK-A1B2C3D4").
    """
    from app import AppointmentSlot, BookingSession  # lazy import

    slot = AppointmentSlot.query.get(slot_id)
    if slot is None or not slot.is_available:
        raise ValueError(f"Slot {slot_id} is not available")

    bk_session = BookingSession.query.get(booking_session_id)
    if bk_session is None:
        raise ValueError(f"BookingSession {booking_session_id} not found")

    slot.is_available = False
    bk_session.state = "confirmed"
    bk_session.appointment_slot_id = slot_id
    bk_session.completed_at = datetime.now(timezone.utc)
    db.session.commit()

    # Booking reference: "BK-" + first 8 chars of slot UUID, uppercased
    return f"BK-{slot_id.replace('-', '')[:8].upper()}"


def cancel_booking(db, booking_session_id: str) -> None:
    """Mark the BookingSession as cancelled (slot remains available)."""
    from app import BookingSession  # lazy import

    bk_session = BookingSession.query.get(booking_session_id)
    if bk_session:
        bk_session.state = "cancelled"
        bk_session.completed_at = datetime.now(timezone.utc)
        db.session.commit()
