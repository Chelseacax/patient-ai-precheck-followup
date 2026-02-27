"""
confirmer.py
------------
Pure Python confirmation logic — NO LLM calls.

Responsibilities:
- Build a human-readable confirmation message from extracted slots + matched DB slot
- Detect yes/no responses from the patient via keyword matching
"""

# Keywords that count as a confirmation
_CONFIRM_KEYWORDS = {
    "yes", "yeah", "yep", "yup", "ya", "ok", "okay", "sure", "correct",
    "confirm", "confirmed", "right", "go ahead", "proceed", "book it",
    "book", "that's right", "sounds good", "good",
    # Malay
    "boleh", "bagus", "betul", "ya betul",
    # Mandarin / dialect romanised
    "dui", "hao", "ke yi",
    # Common short affirmatives
    "y", "k",
}

# Keywords that count as a cancellation
_CANCEL_KEYWORDS = {
    "no", "nope", "nah", "cancel", "stop", "wrong", "not right",
    "change", "different", "another", "try again", "start over",
    # Malay
    "tidak", "tak", "salah", "batal",
    # Mandarin romanised
    "bu", "bu dui", "bu yao",
    "n",
}


class BookingConfirmer:
    """Stateless helper for building confirmation messages and detecting responses."""

    def prepare_confirmation(self, slots: dict, matched_slots: list) -> str:
        """
        Build a spoken confirmation prompt.

        Parameters
        ----------
        slots : dict
            Extracted slots from classifier (doctor_name, specialty, preferred_date, etc.)
        matched_slots : list
            AppointmentSlot ORM objects found by action_handler.find_matching_slots()

        Returns
        -------
        str  — 1-2 sentence confirmation prompt for TTS
        """
        if not matched_slots:
            # No exact match — tell the patient what we understood and ask to clarify
            parts = []
            if slots.get("specialty"):
                parts.append(slots["specialty"])
            if slots.get("doctor_name"):
                parts.append(f"with {slots['doctor_name']}")
            if slots.get("preferred_date"):
                parts.append(f"on {slots['preferred_date']}")
            if slots.get("preferred_time"):
                parts.append(f"in the {slots['preferred_time']}")

            if parts:
                desc = " ".join(parts)
                return (
                    f"I'm sorry, I couldn't find an available slot for {desc}. "
                    "Could you try a different date or specialty?"
                )
            return (
                "I couldn't find any matching slots. "
                "Could you tell me which specialty or doctor you'd like to see?"
            )

        # Use the first matched slot as the suggested booking
        slot = matched_slots[0]
        slot_date = slot.slot_datetime.strftime("%A, %d %B")
        slot_time = slot.slot_datetime.strftime("%I:%M %p")

        return (
            f"I found a slot with {slot.doctor_name} ({slot.specialty}) "
            f"on {slot_date} at {slot_time}. "
            "Shall I confirm this booking? Please say yes or no."
        )

    def is_confirmation(self, normalized_text: str) -> bool:
        """Return True if the text expresses agreement/confirmation."""
        text = normalized_text.lower().strip().rstrip(".")
        # Exact match on full text
        if text in _CONFIRM_KEYWORDS:
            return True
        # Starts-with check for short affirmatives followed by punctuation/space
        for kw in _CONFIRM_KEYWORDS:
            if text.startswith(kw + " ") or text.startswith(kw + ","):
                return True
        return False

    def is_cancellation(self, normalized_text: str) -> bool:
        """Return True if the text expresses rejection/cancellation."""
        text = normalized_text.lower().strip().rstrip(".")
        if text in _CANCEL_KEYWORDS:
            return True
        for kw in _CANCEL_KEYWORDS:
            if text.startswith(kw + " ") or text.startswith(kw + ","):
                return True
        return False
