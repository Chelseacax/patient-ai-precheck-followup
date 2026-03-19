"""
Tool dispatcher — routes tool names to their implementations.
"""
import json
import logging

from agent.bridge import call_bridge
from agent.tools import (
    tool_get_family_members, tool_add_family_member,
    tool_get_doctors, tool_get_doctor_slots,
    tool_book_appointment, tool_get_appointments, tool_cancel_appointment,
    tool_add_medication, tool_get_medications, tool_remove_medication,
    tool_get_health_summary,
)
from extensions import db
from models import Appointment

logger = logging.getLogger(__name__)


def dispatch_tool(name: str, args, patient_id: str) -> dict:
    """Route a tool call to its implementation."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}

    # ── HealthHub browser tools ──────────────────────────────────────────────
    if name == "book_on_healthhub":
        return _handle_book_on_healthhub(args, patient_id)

    if name == "interact_with_screen":
        return call_bridge("/api/browser/action", {
            "action":   args.get("action", ""),
            "x":        args.get("x", 0),
            "y":        args.get("y", 0),
            "text":     args.get("text", ""),
            "key":      args.get("key", ""),
            "role":     args.get("role", ""),
            "selector": args.get("selector", ""),
        }, timeout=45)

    if name == "view_healthhub":
        raw = call_bridge("/api/navigate", {"page": args.get("page", "home")})
        if isinstance(raw, dict) and raw.get("on_singpass_page"):
            return {"status": "singpass_required",
                    "message": "HealthHub is showing a Singpass login screen. Please guide the user to scan the QR code."}
        return raw

    # ── DB tools ─────────────────────────────────────────────────────────────
    dispatch_map = {
        "get_family_members": lambda: tool_get_family_members(patient_id),
        "add_family_member":  lambda: tool_add_family_member(
            patient_id, args.get("name", ""), args.get("relationship", ""),
            args.get("dob", ""), args.get("notes", "")),
        "get_doctors":        lambda: tool_get_doctors(args.get("specialty")),
        "get_doctor_slots":   lambda: tool_get_doctor_slots(
            args.get("doctor_id", ""), args.get("date")),
        "book_appointment":   lambda: tool_book_appointment(
            patient_id, args.get("doctor_id", ""), args.get("slot_datetime", ""),
            args.get("reason", ""), args.get("family_member_id"), args.get("symptom_summary")),
        "get_appointments":   lambda: tool_get_appointments(
            patient_id, args.get("family_member_id")),
        "cancel_appointment": lambda: tool_cancel_appointment(
            args.get("appointment_id", ""), patient_id),
        "add_medication":     lambda: tool_add_medication(
            patient_id, args.get("name", ""), args.get("dosage", ""),
            args.get("frequency", ""), args.get("reminder_times", []),
            args.get("start_date", ""), args.get("end_date", ""),
            args.get("notes", ""), args.get("family_member_id")),
        "get_medications":    lambda: tool_get_medications(
            patient_id, args.get("family_member_id"), args.get("active_only", True)),
        "remove_medication":  lambda: tool_remove_medication(
            args.get("medication_id", ""), patient_id),
        "get_health_summary": lambda: tool_get_health_summary(
            patient_id, args.get("family_member_id")),
    }

    fn = dispatch_map.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn()
    except Exception as e:
        logger.error("Tool %s error: %s", name, e)
        return {"error": str(e)}


def _handle_book_on_healthhub(args: dict, patient_id: str) -> dict:
    """Handle the book_on_healthhub tool — automates HealthHub booking + persists to DB."""
    raw = call_bridge("/api/booking/full", {
        "institution": args.get("institution", ""),
        "specialty":   args.get("specialty", ""),
        "date":        args.get("date", ""),
        "time":        args.get("time", ""),
        "reason":      args.get("reason", ""),
    }, timeout=120)

    if not isinstance(raw, dict):
        return raw

    if raw.get("on_singpass_page") or raw.get("paused"):
        wait_result = call_bridge("/api/singpass/wait?timeout_ms=180000", {}, method="POST", timeout=200)
        if isinstance(wait_result, dict) and wait_result.get("logged_in"):
            return {"status": "singpass_ok", "message": "User has logged in via Singpass. Please retry the booking."}
        return {"status": "singpass_timeout", "message": "User did not complete Singpass login in time."}

    if raw.get("ui_mismatch"):
        step = raw.get("step", "unknown step")
        desc = raw.get("description", "selector not found")
        return {"status": "ui_mismatch",
                "message": f"Could not complete '{step}' automatically — {desc}. Tell the user and ask them to perform this step manually."}

    if raw.get("booked"):
        try:
            slot_dt = args.get("date", "") + " " + args.get("time", "")
            appt = Appointment(
                patient_id=patient_id,
                doctor_id="healthhub",
                doctor_name=args.get("institution", "HealthHub"),
                specialty=args.get("specialty", ""),
                slot_datetime=slot_dt,
                reason=args.get("reason", ""),
                symptom_summary=args.get("symptom_summary", ""),
                status="scheduled",
            )
            db.session.add(appt)
            db.session.commit()
        except Exception as e:
            logger.error("Failed to save HealthHub appointment to DB: %s", e)
            db.session.rollback()

    return raw
