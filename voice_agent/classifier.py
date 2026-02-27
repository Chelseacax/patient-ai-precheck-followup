"""
classifier.py
-------------
Classifies a normalized English utterance into an intent and extracts
appointment-booking slots as structured JSON.

Uses call_llm() at temperature=0.0 for fully deterministic output.
LLM output is parsed — it NEVER directly triggers any action.
"""

import json
import logging

logger = logging.getLogger(__name__)

_DEFAULT_RESULT = {
    "intent": "unclear",
    "slots": {
        "doctor_name": None,
        "specialty": None,
        "preferred_date": None,
        "preferred_time": None,
        "urgency": False,
    },
}

_SYSTEM_PROMPT = """You are an intent classifier for a Singapore healthcare appointment booking system.

Given a patient's utterance (already normalized to standard English), extract:

1. intent — one of:
   - "book_appointment"    : patient wants to book / schedule an appointment
   - "reschedule"          : patient wants to change an existing appointment
   - "cancel_appointment"  : patient wants to cancel an existing appointment
   - "check_availability"  : patient asking about available slots / doctors
   - "unclear"             : cannot determine intent

2. slots — extract whatever is mentioned:
   - doctor_name    : string or null  (e.g. "Dr. Tan", "Dr. Lee")
   - specialty      : string or null  (e.g. "Cardiology", "General Practice", "skin", "heart")
   - preferred_date : string or null  (e.g. "next Monday", "3 March", "this week", "tomorrow")
   - preferred_time : string or null  (e.g. "morning", "10am", "afternoon", "after 2pm")
   - urgency        : boolean         (true if patient says urgent, emergency, ASAP, pain, etc.)

Respond with ONLY valid JSON in this exact format — no markdown, no explanation:
{
  "intent": "<intent>",
  "slots": {
    "doctor_name": <string or null>,
    "specialty": <string or null>,
    "preferred_date": <string or null>,
    "preferred_time": <string or null>,
    "urgency": <true or false>
  }
}"""


def classify(normalized_text: str) -> dict:
    """
    Classify intent and extract slots from a normalized English utterance.

    Parameters
    ----------
    normalized_text : str
        Standard English text produced by normalizer.normalize()

    Returns
    -------
    dict with keys: intent (str), slots (dict)
    Never raises — returns _DEFAULT_RESULT on any failure.
    """
    from app import call_llm  # lazy import

    if not normalized_text or not normalized_text.strip():
        return dict(_DEFAULT_RESULT)

    result, api_key_invalid = call_llm(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": normalized_text},
        ],
        max_tokens=300,
        temperature=0.0,
    )

    if not result:
        logger.warning("classifier: empty LLM response, returning unclear")
        return dict(_DEFAULT_RESULT)

    # Extract JSON from response (handles any surrounding text)
    start = result.find("{")
    end = result.rfind("}") + 1
    if start < 0 or end <= start:
        logger.warning("classifier: no JSON found in response: %s", result[:200])
        return dict(_DEFAULT_RESULT)

    try:
        parsed = json.loads(result[start:end])
        # Validate and fill in missing fields
        intent = parsed.get("intent", "unclear")
        if intent not in ("book_appointment", "reschedule", "cancel_appointment",
                          "check_availability", "unclear"):
            intent = "unclear"

        raw_slots = parsed.get("slots", {})
        slots = {
            "doctor_name": raw_slots.get("doctor_name") or None,
            "specialty": raw_slots.get("specialty") or None,
            "preferred_date": raw_slots.get("preferred_date") or None,
            "preferred_time": raw_slots.get("preferred_time") or None,
            "urgency": bool(raw_slots.get("urgency", False)),
        }
        return {"intent": intent, "slots": slots}

    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("classifier: JSON parse error: %s | raw: %s", exc, result[:200])
        return dict(_DEFAULT_RESULT)
