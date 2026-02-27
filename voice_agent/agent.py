"""
agent.py
--------
Orchestrator — the single entry point called from Flask routes.

Pipeline:
  raw_text
    → normalizer.normalize()          [MERaLion: dialect → standard English]
    → classifier.classify()           [LLM: intent + slot JSON]
    → action_handler.find_matching_slots()   [pure Python DB query]
    → confirmer.prepare_confirmation()       [pure Python string builder]
    → returns dict (response_text, state, requires_confirmation, available_slots)

The LLM NEVER directly modifies the database.
Only explicit /confirm and /cancel Flask routes call action_handler write functions.
"""

import json
import logging

from voice_agent.normalizer import normalize
from voice_agent.classifier import classify
from voice_agent.confirmer import BookingConfirmer
import voice_agent.action_handler as action_handler

logger = logging.getLogger(__name__)
_confirmer = BookingConfirmer()

# Clarification prompts for unclear intents
_CLARIFY_PROMPT = (
    "I'm not sure I understood that. "
    "Could you tell me which doctor or specialty you'd like to book, "
    "and when you'd like to come in?"
)

_RESCHEDULE_PROMPT = (
    "I can see you'd like to reschedule. "
    "Please contact our clinic directly to reschedule an existing appointment."
)

_CANCEL_PROMPT = (
    "I can see you'd like to cancel. "
    "Please contact our clinic directly to cancel an existing appointment."
)


def process_message(db, booking_session_id: str, raw_text: str,
                    language: str = "English", dialect: str = "") -> dict:
    """
    Process one voice message turn in the booking conversation.

    Parameters
    ----------
    db              : Flask-SQLAlchemy db object (passed from Flask route)
    booking_session_id : str  — BookingSession primary key
    raw_text        : str     — raw voice transcript from Web Speech API
    language        : str     — patient's selected language
    dialect         : str     — patient's selected dialect

    Returns
    -------
    dict:
        response_text       : str   — spoken response for TTS (1-2 sentences)
        state               : str   — current BookingSession state
        requires_confirmation: bool — True when waiting for yes/no
        available_slots     : list[dict] | None — slot options (when confirming)
        normalized_input    : str   — what the normalizer understood (for UI display)
        extracted_slots     : dict | None
        booking_ref         : str | None — set only after confirmed
    """
    from app import BookingSession  # lazy import

    bk_session = BookingSession.query.get(booking_session_id)
    if bk_session is None:
        return _error_response("Booking session not found.")

    state = bk_session.state

    # ------------------------------------------------------------------ #
    # CONFIRMING STATE — patient is responding yes/no to a proposed slot  #
    # ------------------------------------------------------------------ #
    if state == "confirming":
        normalized = normalize(raw_text, language, dialect)

        if _confirmer.is_confirmation(normalized):
            # Execute booking — slot_id stored in extracted_slots
            try:
                slots_data = json.loads(bk_session.extracted_slots or "{}")
                slot_id = slots_data.get("_matched_slot_id")
                if not slot_id:
                    return _response(
                        "I'm sorry, I lost track of the slot. Let's start again — which doctor would you like to see?",
                        state="collecting",
                    )
                booking_ref = action_handler.execute_booking(db, booking_session_id, slot_id)
                slot = _slot_to_dict(_get_slot(db, slot_id))
                return _response(
                    f"Great news! Your appointment is confirmed. Your booking reference is {booking_ref}. "
                    f"See you at {slot['slot_time']} on {slot['slot_date']}.",
                    state="confirmed",
                    booking_ref=booking_ref,
                    confirmed_slot=slot,
                )
            except Exception as exc:
                logger.error("execute_booking failed: %s", exc)
                return _error_response(
                    "Sorry, I had trouble confirming that slot. Please try again."
                )

        elif _confirmer.is_cancellation(normalized):
            action_handler.cancel_booking(db, booking_session_id)
            return _response(
                "No problem, I've cancelled that booking. Feel free to start a new booking whenever you're ready.",
                state="cancelled",
            )

        else:
            # Patient said something unclear — re-ask
            return _response(
                "I didn't quite catch that. Please say yes to confirm, or no to cancel.",
                state="confirming",
                requires_confirmation=True,
            )

    # ------------------------------------------------------------------ #
    # COLLECTING STATE — gathering appointment preferences                 #
    # ------------------------------------------------------------------ #
    if state == "collecting":
        normalized = normalize(raw_text, language, dialect)
        classified = classify(normalized)
        intent = classified["intent"]
        slots = classified["slots"]

        if intent in ("book_appointment", "check_availability"):
            matched_slots = action_handler.find_matching_slots(
                db,
                specialty=slots.get("specialty"),
                preferred_date=slots.get("preferred_date"),
                preferred_time=slots.get("preferred_time"),
            )

            confirmation_msg = _confirmer.prepare_confirmation(slots, matched_slots)

            if matched_slots:
                # Save matched slot id so /confirm route can act on it
                slots_to_save = dict(slots)
                slots_to_save["_matched_slot_id"] = matched_slots[0].id
                bk_session.state = "confirming"
            else:
                slots_to_save = dict(slots)

            bk_session.normalized_input = normalized
            bk_session.extracted_slots = json.dumps(slots_to_save)
            db.session.commit()

            return _response(
                confirmation_msg,
                state=bk_session.state,
                requires_confirmation=bool(matched_slots),
                available_slots=[_slot_to_dict(s) for s in matched_slots],
                normalized_input=normalized,
                extracted_slots=slots,
            )

        elif intent == "reschedule":
            return _response(_RESCHEDULE_PROMPT, state="collecting")

        elif intent == "cancel_appointment":
            return _response(_CANCEL_PROMPT, state="collecting")

        else:  # unclear
            return _response(_CLARIFY_PROMPT, state="collecting", normalized_input=normalized)

    # ------------------------------------------------------------------ #
    # Terminal states                                                      #
    # ------------------------------------------------------------------ #
    if state in ("confirmed", "cancelled"):
        return _response(
            "This booking session has already been completed. Please start a new booking.",
            state=state,
        )

    return _error_response("Unknown booking session state.")


# --------------------------------------------------------------------------- #
# Private helpers                                                               #
# --------------------------------------------------------------------------- #

def _response(text: str, state: str = "collecting", requires_confirmation: bool = False,
              available_slots=None, normalized_input: str = "", extracted_slots=None,
              booking_ref: str | None = None, confirmed_slot: dict | None = None) -> dict:
    return {
        "response_text": text,
        "state": state,
        "requires_confirmation": requires_confirmation,
        "available_slots": available_slots,
        "normalized_input": normalized_input,
        "extracted_slots": extracted_slots,
        "booking_ref": booking_ref,
        "confirmed_slot": confirmed_slot,
    }


def _error_response(text: str) -> dict:
    return _response(text, state="error")


def _get_slot(db, slot_id: str):
    from app import AppointmentSlot
    return AppointmentSlot.query.get(slot_id)


def _slot_to_dict(slot) -> dict:
    if slot is None:
        return {}
    return {
        "id": slot.id,
        "doctor_name": slot.doctor_name,
        "specialty": slot.specialty,
        "slot_date": slot.slot_datetime.strftime("%A, %d %B %Y"),
        "slot_time": slot.slot_datetime.strftime("%I:%M %p"),
        "slot_datetime_iso": slot.slot_datetime.isoformat(),
        "is_available": slot.is_available,
    }
