"""
SQLAlchemy database models for MedBridge.
"""
import uuid
from datetime import datetime, timezone

from extensions import db


class Patient(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    date_of_birth = db.Column(db.String(10))
    preferred_language = db.Column(db.String(50), default="English")
    dialect = db.Column(db.String(80), default="")
    cultural_context = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sessions = db.relationship("Session", backref="patient", lazy=True,
                               order_by="Session.created_at.desc()")


class Session(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey("patient.id"), nullable=False)
    session_type = db.Column(db.String(20), nullable=False)   # "pre" or "post"
    status = db.Column(db.String(20), default="in_progress")
    is_urgent = db.Column(db.Boolean, default=False)
    language_used = db.Column(db.String(50))
    dialect_used = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)
    clinician_summary = db.Column(db.Text)
    patient_summary = db.Column(db.Text)
    messages = db.relationship("Message", backref="session", lazy=True,
                               order_by="Message.created_at")


class Message(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey("session.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)   # system | assistant | user
    content = db.Column(db.Text, nullable=False)
    content_translated = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class FamilyMember(db.Model):
    __tablename__ = "family_member"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey("patient.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    relationship = db.Column(db.String(50), nullable=False)
    date_of_birth = db.Column(db.String(10))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Appointment(db.Model):
    __tablename__ = "appointment"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey("patient.id"), nullable=False)
    family_member_id = db.Column(db.String(36), db.ForeignKey("family_member.id"), nullable=True)
    doctor_id = db.Column(db.String(50), nullable=False)
    doctor_name = db.Column(db.String(120), nullable=False)
    specialty = db.Column(db.String(80), nullable=False)
    slot_datetime = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.Text)
    symptom_summary = db.Column(db.Text)
    status = db.Column(db.String(20), default="scheduled")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Medication(db.Model):
    __tablename__ = "medication"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey("patient.id"), nullable=False)
    family_member_id = db.Column(db.String(36), db.ForeignKey("family_member.id"), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    dosage = db.Column(db.String(80))
    frequency = db.Column(db.String(80))
    reminder_times = db.Column(db.Text)   # JSON array e.g. '["08:00","20:00"]'
    start_date = db.Column(db.String(10))
    end_date = db.Column(db.String(10))
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class AgentSession(db.Model):
    __tablename__ = "agent_session"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey("patient.id"), nullable=False)
    language_used = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    messages = db.relationship("AgentMessage", backref="agent_session", lazy=True,
                               order_by="AgentMessage.created_at")


class AgentMessage(db.Model):
    __tablename__ = "agent_message"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey("agent_session.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)   # user | assistant | tool
    content = db.Column(db.Text)
    tool_name = db.Column(db.String(80))
    tool_result_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
