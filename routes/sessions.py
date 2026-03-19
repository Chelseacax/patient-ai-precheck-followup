import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from extensions import db
from models import Patient, Session, Message
from llm.client import call_llm

logger = logging.getLogger(__name__)
bp = Blueprint("sessions", __name__)


# ── System prompt builders ────────────────────────────────────────────────────

def _build_system_prompt(session_type, language, dialect, cultural_context, patient_name):
    cultural_note = f"\nCultural context: {cultural_context}\nAdapt your style to be culturally resonant.\n" if cultural_context else ""
    sea_context = """
You are operating in a Singapore / Southeast Asian healthcare setting.
Be aware of local cultural norms, dietary considerations (halal, vegetarian), traditional medicine (TCM, Jamu, Ayurveda), and naming conventions."""

    if session_type == "pre":
        return f"""You are Aria, a warm AI voice assistant conducting a VOICE PRE-CONSULTATION CHECK-IN with {patient_name} at MedBridge Clinic, Singapore.
{sea_context}
Goals: Greet warmly in {language} ({dialect}). Collect ONE piece of info per turn: chief complaint → duration/severity → medications → allergies → history. Screen for red-flag symptoms (chest pain, difficulty breathing, severe headache) — advise emergency care if present.
Language: Respond ENTIRELY in {language} ({dialect}).{cultural_note}
CRITICAL VOICE RULES: Keep EVERY response to 1–2 short sentences. Ask only ONE question per turn. No markdown or bullet points. Be warm and conversational."""

    return f"""You are MedBridge, a warm multilingual healthcare assistant conducting a POST-CONSULTATION FOLLOW-UP with {patient_name}.
{sea_context}
Goals: Greet in {language} ({dialect}). Review diagnosis and treatment plan. Explain medications plainly. Verify understanding with teach-back. Discuss follow-up and warning signs. Provide emotional support.
Language: Respond ENTIRELY in {language} ({dialect}).{cultural_note}
Keep responses concise (2–4 sentences). Use culturally familiar analogies. Be compassionate."""


def _build_summary_prompt(messages_text, session_type, language):
    return f"""Analyze this {session_type}-consultation conversation (conducted in {language}) and produce TWO summaries.

CONVERSATION:
{messages_text}

SUMMARY 1 — CLINICIAN SUMMARY (English):
• Chief Complaint(s)
• History of Present Illness
• Current Medications & Allergies
• Red Flags / Urgent Concerns
• Social/Cultural Considerations
• Patient Understanding & Adherence Risk
• Recommended Follow-up

SUMMARY 2 — PATIENT SUMMARY (in {language}): Simple, friendly, culturally appropriate recap with key action items and encouragement.

Return as JSON: {{"clinician_summary": "...", "patient_summary": "..."}}"""


def _fallback_greeting(language, name, session_type):
    kind = "check-in" if session_type == "pre" else "follow-up"
    greetings = {
        "English": f"Hello {name}! I'm here to help with your {kind}. How are you feeling today?",
        "华语 (Mandarin)": f"你好 {name}！我在这里帮助您。您今天感觉怎么样？",
        "Malay (Bahasa Melayu)": f"Selamat datang {name}! Bagaimana perasaan anda hari ini?",
        "Tamil (தமிழ்)": f"வணக்கம் {name}! இன்று எப்படி உணர்கிறீர்கள்?",
    }
    return greetings.get(language, greetings["English"])


def _translate_to_english(text, source_language):
    if not text or source_language == "English":
        return None
    try:
        result, _ = call_llm(
            messages=[
                {"role": "system", "content": (
                    f"You are a professional medical translator. "
                    f"Translate the following {source_language} text to English accurately. "
                    f"Output ONLY the English translation."
                )},
                {"role": "user", "content": text},
            ],
            max_tokens=600,
            temperature=0.15,
        )
        return result.strip() if result else None
    except Exception as e:
        logger.warning("Translation failed: %s", e)
        return None


# ── Routes ────────────────────────────────────────────────────────────────────

@bp.post("/api/sessions")
def create_session():
    data = request.json
    patient = Patient.query.get_or_404(data["patient_id"])
    language = data.get("language", patient.preferred_language)
    dialect = data.get("dialect", patient.dialect)

    session = Session(patient_id=patient.id, session_type=data["session_type"],
                      language_used=language, dialect_used=dialect)
    db.session.add(session)
    db.session.flush()

    system_prompt = _build_system_prompt(
        session.session_type, language, dialect, patient.cultural_context, patient.name)
    db.session.add(Message(session_id=session.id, role="system", content=system_prompt))

    try:
        greeting, api_key_invalid = call_llm(
            [{"role": "system", "content": system_prompt}], max_tokens=300, temperature=0.7)
        if not greeting:
            greeting = _fallback_greeting(language, patient.name, session.session_type)
    except Exception as e:
        logger.warning("LLM greeting failed: %s", e)
        greeting = _fallback_greeting(language, patient.name, session.session_type)
        api_key_invalid = False

    greeting_translated = _translate_to_english(greeting, language)
    db.session.add(Message(session_id=session.id, role="assistant", content=greeting,
                           content_translated=greeting_translated))
    db.session.commit()
    return jsonify({"session_id": session.id, "greeting": greeting,
                    "api_key_invalid": api_key_invalid}), 201


@bp.post("/api/sessions/<session_id>/message")
def send_message(session_id):
    session = Session.query.get_or_404(session_id)
    data = request.json
    user_text = data["message"]
    user_translated = _translate_to_english(user_text, session.language_used)
    db.session.add(Message(session_id=session.id, role="user", content=user_text,
                           content_translated=user_translated))

    all_messages = Message.query.filter_by(session_id=session.id).order_by(Message.created_at).all()
    conversation = [{"role": m.role, "content": m.content} for m in all_messages]
    conversation.append({"role": "user", "content": user_text})

    api_key_invalid = False
    try:
        reply, api_key_invalid = call_llm(conversation, max_tokens=400, temperature=0.7)
        if reply is None:
            reply = "[API key is invalid or expired. Please update it.]" if api_key_invalid else "[API key not configured.]"
            api_key_invalid = True
    except Exception as e:
        logger.error("LLM chat error: %s", e)
        reply = f"[Service temporarily unavailable: {str(e)[:150]}]"

    reply_translated = _translate_to_english(reply, session.language_used)
    db.session.add(Message(session_id=session.id, role="assistant", content=reply,
                           content_translated=reply_translated))
    db.session.commit()
    return jsonify({"reply": reply, "api_key_invalid": api_key_invalid})


@bp.post("/api/sessions/<session_id>/complete")
def complete_session(session_id):
    session = Session.query.get_or_404(session_id)
    all_messages = Message.query.filter_by(session_id=session.id).order_by(Message.created_at).all()

    lines = []
    for m in all_messages:
        if m.role == "system":
            continue
        speaker = "MedBridge (AI)" if m.role == "assistant" else "Patient"
        lines.append(f"{speaker}: {m.content}")
        if m.content_translated:
            lines.append(f"  [English]: {m.content_translated}")
    convo_text = "\n".join(lines)

    summary_prompt = _build_summary_prompt(convo_text, session.session_type, session.language_used)
    try:
        raw, _ = call_llm([{"role": "system", "content": summary_prompt}],
                          max_tokens=1500, temperature=0.3)
        if raw is None:
            summaries = {"clinician_summary": "Summary unavailable.", "patient_summary": ""}
        else:
            start, end = raw.find("{"), raw.rfind("}") + 1
            try:
                summaries = json.loads(raw[start:end], strict=False) if start >= 0 else {"clinician_summary": raw, "patient_summary": ""}
            except json.JSONDecodeError:
                summaries = {"clinician_summary": raw, "patient_summary": ""}
    except Exception as e:
        summaries = {"clinician_summary": f"Summary failed: {str(e)[:200]}", "patient_summary": ""}

    session.clinician_summary = summaries.get("clinician_summary", "")
    session.patient_summary = summaries.get("patient_summary", "")
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"clinician_summary": session.clinician_summary,
                    "patient_summary": session.patient_summary})


@bp.patch("/api/sessions/<session_id>")
def update_session(session_id):
    session = Session.query.get_or_404(session_id)
    data = request.get_json() or {}
    if "is_urgent" in data:
        session.is_urgent = bool(data["is_urgent"])
    db.session.commit()
    return jsonify({"id": session.id, "is_urgent": getattr(session, "is_urgent", False)})


@bp.get("/api/sessions/<session_id>")
def get_session(session_id):
    session = Session.query.get_or_404(session_id)
    patient = Patient.query.get(session.patient_id)
    all_messages = Message.query.filter_by(session_id=session.id).order_by(Message.created_at).all()
    return jsonify({
        "id": session.id, "patient_id": session.patient_id,
        "patient_name": patient.name if patient else "Unknown",
        "patient_dob": patient.date_of_birth if patient else "",
        "patient_cultural_context": patient.cultural_context if patient else "",
        "session_type": session.session_type, "status": session.status,
        "is_urgent": getattr(session, "is_urgent", False),
        "language_used": session.language_used, "dialect_used": session.dialect_used,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "clinician_summary": session.clinician_summary, "patient_summary": session.patient_summary,
        "messages": [{"id": m.id, "role": m.role, "content": m.content,
                       "content_translated": m.content_translated,
                       "created_at": m.created_at.isoformat() if m.created_at else None}
                     for m in all_messages if m.role != "system"],
    })


@bp.get("/api/sessions")
def list_sessions():
    query = Session.query.order_by(Session.created_at.desc())
    patient_id = request.args.get("patient_id")
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    results = []
    for s in query.all():
        patient = Patient.query.get(s.patient_id)
        results.append({
            "id": s.id, "patient_id": s.patient_id,
            "patient_name": patient.name if patient else "Unknown",
            "session_type": s.session_type, "status": s.status,
            "is_urgent": getattr(s, "is_urgent", False),
            "language_used": s.language_used, "dialect_used": s.dialect_used,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "has_summary": bool(s.clinician_summary),
        })
    return jsonify(results)


@bp.post("/api/translate")
def translate_text():
    data = request.json
    text = data["text"]
    target_lang = data["target_language"]
    target_dialect = data.get("dialect", "")
    prompt = f"""Translate the following medical text into {target_lang} ({target_dialect} variant).
Rules: Use simple, everyday language appropriate for a patient. Adapt cultural references for a Singapore/Southeast Asian audience. Preserve all medical information (dosages, timing, warnings).

Text to translate:
{text}"""
    try:
        translated, _ = call_llm([{"role": "system", "content": prompt}],
                                  max_tokens=600, temperature=0.3)
        if translated is None:
            return jsonify({"error": "API key not configured"}), 503
    except Exception as e:
        translated = f"[Translation failed: {str(e)[:100]}]"
    return jsonify({"translated": translated})
