import logging
import threading

from flask import Blueprint, jsonify, request

from extensions import db
from models import Patient, AgentSession, AgentMessage
from agent.loop import run_agent, set_stop_flag
from agent.prompts import build_agent_system_prompt
from agent.bridge import call_bridge
from llm.client import call_llm_with_tools

logger = logging.getLogger(__name__)
bp = Blueprint("agent", __name__)


@bp.post("/api/agent/stop")
def agent_stop():
    set_stop_flag(True)
    return jsonify({"status": "stopping_agent"})


@bp.post("/api/agent/start")
def agent_start():
    data = request.json or {}
    patient_id = data.get("patient_id")
    language = data.get("language", "English")

    if not patient_id:
        return jsonify({"error": "patient_id required"}), 400
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    agent_session = AgentSession(patient_id=patient_id, language_used=language)
    db.session.add(agent_session)
    db.session.flush()

    system_prompt = build_agent_system_prompt(language, patient.name)
    messages = [{"role": "system", "content": system_prompt}]

    try:
        resp = call_llm_with_tools(messages, max_tokens=150, temperature=0.8)
        greeting = resp.choices[0].message.content or "" if resp else ""
    except Exception:
        greeting = ""
    if not greeting:
        greeting = f"Hello {patient.name}! I'm Aria, your health assistant. How can I help you today?"

    db.session.add(AgentMessage(session_id=agent_session.id, role="assistant", content=greeting))
    db.session.commit()

    # Open HealthHub in background
    threading.Thread(target=lambda: call_bridge("/api/navigate", {"page": "home"}), daemon=True).start()

    return jsonify({"session_id": agent_session.id, "greeting": greeting}), 201


@bp.post("/api/agent/sessions/<session_id>/message")
def agent_message(session_id):
    agent_session = AgentSession.query.get_or_404(session_id)
    data = request.json or {}
    user_text = data.get("message", "").strip()
    if not user_text:
        return jsonify({"error": "message required"}), 400

    patient = Patient.query.get(agent_session.patient_id)
    patient_name = patient.name if patient else ""

    db.session.add(AgentMessage(session_id=session_id, role="user", content=user_text))

    # Rebuild full conversation for the agent
    system_prompt = build_agent_system_prompt(agent_session.language_used or "English", patient_name)
    messages = [{"role": "system", "content": system_prompt}]
    history = AgentMessage.query.filter_by(session_id=session_id).order_by(AgentMessage.created_at).all()
    for m in history:
        if m.role in ("user", "assistant"):
            messages.append({"role": m.role, "content": m.content or ""})
    messages.append({"role": "user", "content": user_text})

    try:
        reply = run_agent(messages, agent_session.patient_id)
    except Exception as e:
        logger.error("Agent error: %s", e)
        reply = "[Service temporarily unavailable. Please try again.]"

    db.session.add(AgentMessage(session_id=session_id, role="assistant", content=reply))
    db.session.commit()
    return jsonify({"reply": reply})


@bp.get("/api/agent/sessions/<session_id>")
def agent_get_session(session_id):
    agent_session = AgentSession.query.get_or_404(session_id)
    messages = AgentMessage.query.filter_by(session_id=session_id).order_by(AgentMessage.created_at).all()
    return jsonify({
        "id": agent_session.id,
        "patient_id": agent_session.patient_id,
        "language_used": agent_session.language_used,
        "created_at": agent_session.created_at.isoformat() if agent_session.created_at else None,
        "messages": [{"role": m.role, "content": m.content or "",
                       "created_at": m.created_at.isoformat() if m.created_at else None}
                     for m in messages if m.role in ("user", "assistant")],
    })
