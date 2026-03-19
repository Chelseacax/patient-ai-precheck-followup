from flask import Blueprint, jsonify, request
from extensions import db
from models import Patient

bp = Blueprint("patients", __name__)


@bp.post("/api/patients")
def create_patient():
    data = request.json
    patient = Patient(
        name=data["name"],
        date_of_birth=data.get("date_of_birth", ""),
        preferred_language=data.get("preferred_language", "English"),
        dialect=data.get("dialect", ""),
        cultural_context=data.get("cultural_context", ""),
    )
    db.session.add(patient)
    db.session.commit()
    return jsonify({"id": patient.id, "name": patient.name}), 201


@bp.get("/api/patients")
def list_patients():
    patients = Patient.query.order_by(Patient.created_at.desc()).all()
    return jsonify([{
        "id": p.id,
        "name": p.name,
        "date_of_birth": p.date_of_birth,
        "preferred_language": p.preferred_language,
        "dialect": p.dialect,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "session_count": len(p.sessions),
    } for p in patients])


@bp.get("/api/patients/<patient_id>")
def get_patient(patient_id):
    p = Patient.query.get_or_404(patient_id)
    return jsonify({
        "id": p.id,
        "name": p.name,
        "date_of_birth": p.date_of_birth,
        "preferred_language": p.preferred_language,
        "dialect": p.dialect,
        "cultural_context": p.cultural_context,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "sessions": [{
            "id": s.id,
            "session_type": s.session_type,
            "status": s.status,
            "language_used": s.language_used,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        } for s in p.sessions],
    })
