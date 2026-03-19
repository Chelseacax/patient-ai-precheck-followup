from flask import Blueprint, jsonify, request

from models import Patient, Appointment, FamilyMember
from agent.tools import (
    tool_get_family_members, tool_add_family_member,
    tool_get_appointments, tool_get_medications, tool_get_health_summary,
)

bp = Blueprint("health", __name__)


@bp.get("/api/family")
def list_family():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id required"}), 400
    return jsonify(tool_get_family_members(patient_id))


@bp.post("/api/family")
def create_family_member():
    data = request.json or {}
    patient_id = data.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id required"}), 400
    result = tool_add_family_member(patient_id, data.get("name", ""),
                                    data.get("relationship", ""),
                                    data.get("dob", ""), data.get("notes", ""))
    return jsonify(result), 201


@bp.get("/api/appointments")
def list_appointments():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id required"}), 400
    return jsonify(tool_get_appointments(patient_id, request.args.get("family_member_id")))


@bp.get("/api/medications")
def list_medications():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id required"}), 400
    active_only = request.args.get("active_only", "true").lower() != "false"
    return jsonify(tool_get_medications(patient_id, request.args.get("family_member_id"), active_only))


@bp.get("/api/health-summary")
def health_summary():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id required"}), 400
    return jsonify(tool_get_health_summary(patient_id, request.args.get("family_member_id")))


@bp.get("/api/doctor/appointments")
def doctor_appointments():
    appts = Appointment.query.order_by(Appointment.created_at.desc()).all()
    results = []
    for a in appts:
        patient = Patient.query.get(a.patient_id)
        fm_name = ""
        if a.family_member_id:
            fm = FamilyMember.query.get(a.family_member_id)
            if fm:
                fm_name = fm.name
        results.append({
            "id": a.id, "patient_id": a.patient_id,
            "patient_name": patient.name if patient else "Unknown",
            "doctor_name": a.doctor_name, "specialty": a.specialty,
            "slot_datetime": a.slot_datetime, "reason": a.reason or "",
            "symptom_summary": a.symptom_summary or "", "status": a.status,
            "for": fm_name or "self",
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return jsonify(results)
