"""
Agent tool implementations (DB operations) and OpenAI function-calling schemas.
"""
import json
import logging
from datetime import datetime

from extensions import db
from models import FamilyMember, Appointment, Medication, Session
from data.doctors import MOCK_DOCTORS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def tool_get_family_members(patient_id: str) -> list:
    members = FamilyMember.query.filter_by(patient_id=patient_id).all()
    return [{"id": m.id, "name": m.name, "relationship": m.relationship,
             "date_of_birth": m.date_of_birth or "", "notes": m.notes or ""} for m in members]


def tool_add_family_member(patient_id: str, name: str, relationship: str,
                           dob: str = "", notes: str = "") -> dict:
    member = FamilyMember(patient_id=patient_id, name=name, relationship=relationship,
                          date_of_birth=dob or None, notes=notes or None)
    db.session.add(member)
    db.session.commit()
    return {"id": member.id, "name": member.name, "relationship": member.relationship}


def tool_get_doctors(specialty: str = None) -> list:
    if specialty:
        doctors = [d for d in MOCK_DOCTORS if specialty.lower() in d["specialty"].lower()]
    else:
        doctors = MOCK_DOCTORS
    return [{"id": d["id"], "name": d["name"], "specialty": d["specialty"]} for d in doctors]


def tool_get_doctor_slots(doctor_id: str, date: str = None) -> dict:
    doctor = next((d for d in MOCK_DOCTORS if d["id"] == doctor_id), None)
    if not doctor:
        return {"error": f"Doctor '{doctor_id}' not found"}
    booked = {a.slot_datetime for a in Appointment.query.filter_by(
        doctor_id=doctor_id, status="scheduled").all()}
    today = datetime.now().strftime("%Y-%m-%d")
    slots = [s for s in doctor["slots"] if s["datetime"] >= today]
    if date:
        slots = [s for s in slots if s["datetime"].startswith(date)]
    available = [s for s in slots if s["datetime"] not in booked]
    return {
        "doctor_name": doctor["name"],
        "specialty": doctor["specialty"],
        "institution": doctor.get("institution", ""),
        "available_slots": available,
    }


def tool_book_appointment(patient_id: str, doctor_id: str, slot_datetime: str,
                          reason: str, family_member_id: str = None,
                          symptom_summary: str = None) -> dict:
    doctor = next((d for d in MOCK_DOCTORS if d["id"] == doctor_id), None)
    if not doctor:
        return {"error": f"Doctor '{doctor_id}' not found"}
    existing = Appointment.query.filter_by(doctor_id=doctor_id, slot_datetime=slot_datetime,
                                           status="scheduled").first()
    if existing:
        return {"error": f"Slot {slot_datetime} is already booked"}
    appt = Appointment(
        patient_id=patient_id,
        family_member_id=family_member_id or None,
        doctor_id=doctor_id,
        doctor_name=doctor["name"],
        specialty=doctor["specialty"],
        slot_datetime=slot_datetime,
        reason=reason,
        symptom_summary=symptom_summary,
        status="scheduled",
    )
    db.session.add(appt)
    db.session.commit()
    for_whom = ""
    if family_member_id:
        fm = FamilyMember.query.get(family_member_id)
        if fm:
            for_whom = fm.name
    return {"appointment_id": appt.id, "doctor": doctor["name"], "specialty": doctor["specialty"],
            "datetime": slot_datetime, "reason": reason, "for": for_whom or "self"}


def tool_get_appointments(patient_id: str, family_member_id: str = None) -> list:
    query = Appointment.query.filter_by(patient_id=patient_id, status="scheduled")
    if family_member_id:
        query = query.filter_by(family_member_id=family_member_id)
    appts = query.order_by(Appointment.slot_datetime).all()
    result = []
    for a in appts:
        fm_name = ""
        if a.family_member_id:
            fm = FamilyMember.query.get(a.family_member_id)
            if fm:
                fm_name = fm.name
        result.append({"id": a.id, "doctor": a.doctor_name, "specialty": a.specialty,
                        "datetime": a.slot_datetime, "reason": a.reason or "",
                        "for": fm_name or "self"})
    return result


def tool_cancel_appointment(appointment_id: str, patient_id: str) -> dict:
    appt = Appointment.query.filter_by(id=appointment_id, patient_id=patient_id).first()
    if not appt:
        return {"error": "Appointment not found or not authorized"}
    appt.status = "cancelled"
    db.session.commit()
    return {"cancelled": True, "appointment_id": appointment_id, "doctor": appt.doctor_name,
            "datetime": appt.slot_datetime}


def tool_add_medication(patient_id: str, name: str, dosage: str, frequency: str,
                        reminder_times, start_date: str = "", end_date: str = "",
                        notes: str = "", family_member_id: str = None) -> dict:
    reminder_json = json.dumps(reminder_times) if isinstance(reminder_times, list) else (reminder_times or "[]")
    med = Medication(
        patient_id=patient_id, family_member_id=family_member_id or None,
        name=name, dosage=dosage, frequency=frequency,
        reminder_times=reminder_json,
        start_date=start_date or None, end_date=end_date or None,
        notes=notes or None, is_active=True,
    )
    db.session.add(med)
    db.session.commit()
    return {"medication_id": med.id, "name": name, "dosage": dosage, "frequency": frequency,
            "reminder_times": json.loads(reminder_json)}


def tool_get_medications(patient_id: str, family_member_id: str = None,
                         active_only: bool = True) -> list:
    query = Medication.query.filter_by(patient_id=patient_id)
    if active_only:
        query = query.filter_by(is_active=True)
    if family_member_id:
        query = query.filter_by(family_member_id=family_member_id)
    result = []
    for m in query.all():
        fm_name = ""
        if m.family_member_id:
            fm = FamilyMember.query.get(m.family_member_id)
            if fm:
                fm_name = fm.name
        try:
            reminders = json.loads(m.reminder_times or "[]")
        except Exception:
            reminders = []
        result.append({"id": m.id, "name": m.name, "dosage": m.dosage or "",
                        "frequency": m.frequency or "", "reminder_times": reminders,
                        "start_date": m.start_date or "", "end_date": m.end_date or "",
                        "notes": m.notes or "", "for": fm_name or "self"})
    return result


def tool_remove_medication(medication_id: str, patient_id: str) -> dict:
    med = Medication.query.filter_by(id=medication_id, patient_id=patient_id).first()
    if not med:
        return {"error": "Medication not found or not authorized"}
    med.is_active = False
    db.session.commit()
    return {"removed": True, "medication_id": medication_id, "name": med.name}


def tool_get_health_summary(patient_id: str, family_member_id: str = None) -> dict:
    appts = tool_get_appointments(patient_id, family_member_id)
    meds = tool_get_medications(patient_id, family_member_id, active_only=True)
    family = tool_get_family_members(patient_id)
    past_sessions = Session.query.filter_by(
        patient_id=patient_id, session_type="pre", status="completed"
    ).order_by(Session.created_at.desc()).limit(5).all()
    consultations = [{"date": s.created_at.strftime("%Y-%m-%d") if s.created_at else "",
                      "language": s.language_used or ""} for s in past_sessions]
    return {"upcoming_appointments": appts, "active_medications": meds,
            "family_members": family, "past_consultations": consultations}


# ---------------------------------------------------------------------------
# OpenAI function-calling schemas (AGENT_TOOLS)
# ---------------------------------------------------------------------------

AGENT_TOOLS = [
    {"type": "function", "function": {
        "name": "get_family_members",
        "description": "List the patient's registered family members or dependants",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "add_family_member",
        "description": "Add a new family member or dependant to the patient's account",
        "parameters": {
            "type": "object",
            "properties": {
                "name":         {"type": "string", "description": "Full name of the family member"},
                "relationship": {"type": "string", "description": "e.g. son, daughter, mother, father, spouse"},
                "dob":          {"type": "string", "description": "Date of birth YYYY-MM-DD (optional)"},
                "notes":        {"type": "string", "description": "Any additional notes (optional)"},
            },
            "required": ["name", "relationship"],
        },
    }},
    {"type": "function", "function": {
        "name": "get_doctors",
        "description": "List available doctors, optionally filtered by specialty",
        "parameters": {
            "type": "object",
            "properties": {
                "specialty": {"type": "string", "description": "e.g. Cardiology, General Practice (optional)"},
            },
            "required": [],
        },
    }},
    {"type": "function", "function": {
        "name": "get_doctor_slots",
        "description": "Get available appointment slots for a specific doctor",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "string", "description": "Doctor ID from get_doctors"},
                "date":      {"type": "string", "description": "Filter by date YYYY-MM-DD (optional)"},
            },
            "required": ["doctor_id"],
        },
    }},
    {"type": "function", "function": {
        "name": "book_appointment",
        "description": "Book a doctor appointment for the patient or a family member",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id":        {"type": "string", "description": "Doctor ID from get_doctors"},
                "slot_datetime":    {"type": "string", "description": "Exact datetime YYYY-MM-DD HH:MM from get_doctor_slots"},
                "reason":           {"type": "string", "description": "Reason for appointment"},
                "symptom_summary":  {"type": "string", "description": "Structured symptom summary: chief complaint, duration, severity, associated symptoms"},
                "family_member_id": {"type": "string", "description": "Family member ID if booking for a dependant (optional)"},
            },
            "required": ["doctor_id", "slot_datetime", "reason", "symptom_summary"],
        },
    }},
    {"type": "function", "function": {
        "name": "get_appointments",
        "description": "List the patient's upcoming scheduled appointments",
        "parameters": {
            "type": "object",
            "properties": {
                "family_member_id": {"type": "string", "description": "Filter by family member (optional)"},
            },
            "required": [],
        },
    }},
    {"type": "function", "function": {
        "name": "cancel_appointment",
        "description": "Cancel a scheduled appointment",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string", "description": "Appointment ID to cancel"},
            },
            "required": ["appointment_id"],
        },
    }},
    {"type": "function", "function": {
        "name": "add_medication",
        "description": "Add a medication with dosage, frequency and reminder times",
        "parameters": {
            "type": "object",
            "properties": {
                "name":             {"type": "string", "description": "Medication name"},
                "dosage":           {"type": "string", "description": "e.g. 500mg"},
                "frequency":        {"type": "string", "description": "e.g. twice daily"},
                "reminder_times":   {"type": "array", "items": {"type": "string"},
                                     "description": 'Reminder times HH:MM, e.g. ["08:00","20:00"]'},
                "start_date":       {"type": "string", "description": "Start date YYYY-MM-DD (optional)"},
                "end_date":         {"type": "string", "description": "End date YYYY-MM-DD (optional)"},
                "notes":            {"type": "string", "description": "Additional notes (optional)"},
                "family_member_id": {"type": "string", "description": "Family member ID if for a dependant (optional)"},
            },
            "required": ["name", "dosage", "frequency", "reminder_times"],
        },
    }},
    {"type": "function", "function": {
        "name": "get_medications",
        "description": "List the patient's active medications",
        "parameters": {
            "type": "object",
            "properties": {
                "family_member_id": {"type": "string", "description": "Filter by family member (optional)"},
                "active_only":      {"type": "boolean", "description": "Return only active medications (default true)"},
            },
            "required": [],
        },
    }},
    {"type": "function", "function": {
        "name": "remove_medication",
        "description": "Remove (deactivate) a medication from the patient's list",
        "parameters": {
            "type": "object",
            "properties": {
                "medication_id": {"type": "string", "description": "Medication ID to remove"},
            },
            "required": ["medication_id"],
        },
    }},
    {"type": "function", "function": {
        "name": "get_health_summary",
        "description": "Full health overview: upcoming appointments, active medications, family members, past consultations",
        "parameters": {
            "type": "object",
            "properties": {
                "family_member_id": {"type": "string", "description": "Filter by family member (optional)"},
            },
            "required": [],
        },
    }},
    # ── HealthHub Browser Tools ──────────────────────────────────────────────
    {"type": "function", "function": {
        "name": "view_healthhub",
        "description": "Navigate the HealthHub browser to show appointments, medications, lab reports, or immunisation records on the live panel.",
        "parameters": {
            "type": "object",
            "properties": {
                "page": {"type": "string",
                         "description": "Page to open: appointments | medications | lab-reports | immunisation | home"},
            },
            "required": ["page"],
        },
    }},
    {"type": "function", "function": {
        "name": "interact_with_screen",
        "description": (
            "Perform an atomic browser action on the current HealthHub screen. "
            "'read_page' returns: interactive_elements (list of {text, x, y} with pixel coordinates) "
            "and page_text (all visible text via DOM tree walker). "
            "Use 'click' with x,y coordinates from interactive_elements as the PRIMARY method for Yes/No buttons. "
            "Use 'click_text' for navigation links and labelled buttons where text is unique. "
            "After every click, call 'read_page' to observe UI changes before deciding next step. "
            "'clear_modals' uses JavaScript to find and close any popup/overlay including SVG-icon close buttons."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action":    {"type": "string",
                              "enum": ["click_text", "read_page", "scroll", "click", "type", "press", "clear_modals"],
                              "description": "Browser action to perform"},
                "text":      {"type": "string",  "description": "For click_text: element label. For type: text to type."},
                "role":      {"type": "string",  "description": "Optional ARIA role: button | link | menuitem | tab | option"},
                "selector":  {"type": "string",  "description": "Optional CSS selector for direct targeting"},
                "x":         {"type": "number",  "description": "X pixel for raw click"},
                "y":         {"type": "number",  "description": "Y pixel for raw click"},
                "key":       {"type": "string",  "description": "Key name for press action, e.g. Enter, Escape"},
                "distance":  {"type": "number",  "description": "Pixels to scroll (default 600)"},
                "direction": {"type": "string",  "description": "Scroll direction: 'down' (default) or 'up'"},
            },
            "required": ["action"],
        },
    }},
    {"type": "function", "function": {
        "name": "book_on_healthhub",
        "description": (
            "Automate the ENTIRE HealthHub booking form automatically. "
            "Call only after collecting ALL booking details from the patient."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "institution":      {"type": "string", "description": "Hospital or polyclinic name"},
                "specialty":        {"type": "string", "description": "Department/specialty"},
                "date":             {"type": "string", "description": "Date YYYY-MM-DD"},
                "time":             {"type": "string", "description": "Time e.g. '09:00'"},
                "reason":           {"type": "string", "description": "Visit reason"},
                "symptom_summary":  {"type": "string", "description": "Structured symptom summary from Phase A"},
            },
            "required": ["institution", "specialty", "date", "time", "reason", "symptom_summary"],
        },
    }},
]
