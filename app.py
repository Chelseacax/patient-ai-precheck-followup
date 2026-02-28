"""
MedBridge – Multilingual Healthcare Communication Platform
===========================================================
Singapore / Southeast Asian Context

Dual-portal design:
  • Patient Portal  – Pre/post-consultation chat in patient's preferred language
  • Doctor Portal   – Clinical summaries, bilingual transcripts, translation review
  • Voice Appointment Booking – AI voice agent for booking appointments
"""

import os
import json
import uuid
from datetime import datetime, timezone

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI, AuthenticationError
try:
    import anthropic as _anthropic_sdk
except ImportError:
    _anthropic_sdk = None
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///medbridge.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
CORS(app)
app.json.sort_keys = False   # preserve insertion order for language dropdown

db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# LLM Client — supports Claude (Anthropic), SEA-LION, Groq, OpenAI
# Priority order: ANTHROPIC_API_KEY > SEALION_API_KEY > GROQ_API_KEY > OPENAI_API_KEY
# ---------------------------------------------------------------------------

_llm_client = None   # cached OpenAI-compatible client
LLM_MODEL = os.getenv("LLM_MODEL", "")


def _resolve_provider():
    """Detect which provider to use based on available env vars."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    sealion_key   = os.getenv("SEALION_API_KEY", "")
    groq_key      = os.getenv("GROQ_API_KEY", "")
    openai_key    = os.getenv("OPENAI_API_KEY", "")

    if anthropic_key:
        return {
            "type": "anthropic", "name": "Claude",
            "api_key": anthropic_key,
            "model": os.getenv("LLM_MODEL", "claude-sonnet-4-5"),
        }
    if sealion_key:
        return {
            "type": "openai_compat", "name": "SEA-LION",
            "api_key": sealion_key,
            "base_url": "https://api.sea-lion.ai/v1",
            "model": os.getenv("LLM_MODEL", "aisingapore/gemma3-12b-it"),
        }
    if groq_key:
        return {
            "type": "openai_compat", "name": "Groq",
            "api_key": groq_key,
            "base_url": "https://api.groq.com/openai/v1",
            "model": os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        }
    if openai_key:
        return {
            "type": "openai_compat", "name": "OpenAI",
            "api_key": openai_key,
            "base_url": None,
            "model": os.getenv("LLM_MODEL", "gpt-4o"),
        }
    return None


def call_llm(messages, max_tokens=500, temperature=0.7):
    """
    Unified LLM call for all providers.

    Returns (text, api_key_invalid):
      - (str,  False) on success
      - (None, True)  if the API key was rejected (auth error)
      - (None, False) if no provider is configured
    Raises other exceptions for transient/unexpected errors.
    """
    global LLM_MODEL, _llm_client
    provider = _resolve_provider()
    if not provider:
        return None, False

    LLM_MODEL = provider["model"]

    # ---- Anthropic Claude ----
    if provider["type"] == "anthropic":
        if _anthropic_sdk is None:
            app.logger.error("anthropic package not installed – run: pip install anthropic")
            return None, False

        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        chat_msgs  = [m for m in messages if m["role"] != "system"]

        # Anthropic requires at least one user message and must start with user
        if not chat_msgs:
            chat_msgs = [{"role": "user", "content": "Begin."}]
        elif chat_msgs[0]["role"] != "user":
            chat_msgs.insert(0, {"role": "user", "content": "."})

        kwargs = {
            "model": provider["model"],
            "messages": chat_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_msg:
            kwargs["system"] = system_msg

        try:
            client = _anthropic_sdk.Anthropic(api_key=provider["api_key"])
            resp = client.messages.create(**kwargs)
            return resp.content[0].text, False
        except _anthropic_sdk.AuthenticationError:
            return None, True
        except Exception:
            raise

    # ---- OpenAI-compatible (SEA-LION / Groq / OpenAI) ----
    oa_kwargs = {"api_key": provider["api_key"]}
    if provider.get("base_url"):
        oa_kwargs["base_url"] = provider["base_url"]
    if _llm_client is None or _llm_client.api_key != provider["api_key"]:
        _llm_client = OpenAI(**oa_kwargs)
    try:
        resp = _llm_client.chat.completions.create(
            model=provider["model"],
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content, False
    except AuthenticationError:
        return None, True
    except Exception:
        raise


def get_llm_client():
    """Legacy helper – returns an OpenAI-compatible client or None for Anthropic."""
    provider = _resolve_provider()
    if not provider or provider["type"] == "anthropic":
        return None
    global LLM_MODEL, _llm_client
    LLM_MODEL = provider["model"]
    kwargs = {"api_key": provider["api_key"]}
    if provider.get("base_url"):
        kwargs["base_url"] = provider["base_url"]
    if _llm_client is None or _llm_client.api_key != provider["api_key"]:
        _llm_client = OpenAI(**kwargs)
    return _llm_client


# ---------------------------------------------------------------------------
# Database Models
# ---------------------------------------------------------------------------

class Patient(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    date_of_birth = db.Column(db.String(10))
    preferred_language = db.Column(db.String(50), default="English")
    dialect = db.Column(db.String(80), default="")
    cultural_context = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sessions = db.relationship("Session", backref="patient", lazy=True, order_by="Session.created_at.desc()")


class Session(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = db.Column(db.String(36), db.ForeignKey("patient.id"), nullable=False)
    session_type = db.Column(db.String(20), nullable=False)   # "pre" or "post"
    status = db.Column(db.String(20), default="in_progress")   # in_progress | completed
    is_urgent = db.Column(db.Boolean, default=False)           # flag for priority handling
    language_used = db.Column(db.String(50))
    dialect_used = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)
    messages = db.relationship("Message", backref="session", lazy=True, order_by="Message.created_at")
    clinician_summary = db.Column(db.Text)
    patient_summary = db.Column(db.Text)


class Message(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey("session.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)   # system | assistant | user
    content = db.Column(db.Text, nullable=False)
    content_translated = db.Column(db.Text)            # English translation for doctor
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Language & Cultural Configuration — Singapore / Southeast Asia
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES = {
    # --- Singapore Official Languages ---
    "English": {
        "dialects": ["Standard Singapore English", "Singlish"],
        "code": "en",
    },
    "华语 (Mandarin)": {
        "dialects": ["新加坡华语 (Singapore Mandarin)", "标准普通话 (Standard Mandarin)"],
        "code": "zh",
    },
    "Malay (Bahasa Melayu)": {
        "dialects": ["Standard Bahasa Melayu", "Bazaar Malay / Pasar Melayu", "Informal / Colloquial Malay"],
        "code": "ms",
    },
    "Tamil (தமிழ்)": {
        "dialects": ["Singapore Tamil (சிங்கப்பூர் தமிழ்)", "Standard Tamil (நிலைத்தமிழ்)"],
        "code": "ta",
    },
    # --- Singapore Chinese Dialects ---
    "福建话 (Hokkien)": {
        "dialects": ["新加坡福建话 (Singapore Hokkien)", "槟城福建话 (Penang Hokkien)"],
        "code": "zh-hokkien",
    },
    "潮州话 (Teochew)": {
        "dialects": ["新加坡潮州话 (Singapore Teochew)"],
        "code": "zh-teochew",
    },
    "广东话 (Cantonese)": {
        "dialects": ["新加坡广东话 (Singapore Cantonese)", "香港广东话 (Hong Kong Cantonese)"],
        "code": "zh-cantonese",
    },
    "客家话 (Hakka)": {
        "dialects": ["新加坡客家话 (Singapore Hakka)"],
        "code": "zh-hakka",
    },
    "海南话 (Hainanese)": {
        "dialects": ["新加坡海南话 (Singapore Hainanese)"],
        "code": "zh-hainanese",
    },
    # --- Southeast Asian Languages ---
    "Hindi (हिन्दी)": {
        "dialects": ["Standard Hindi", "Colloquial Hindi"],
        "code": "hi",
    },
    "Tagalog (Filipino)": {
        "dialects": ["Standard Filipino", "Taglish"],
        "code": "tl",
    },
    "Vietnamese (Tiếng Việt)": {
        "dialects": ["Northern Vietnamese", "Southern Vietnamese"],
        "code": "vi",
    },
    "Thai (ภาษาไทย)": {
        "dialects": ["Central Thai", "Informal Thai"],
        "code": "th",
    },
    "Bahasa Indonesia": {
        "dialects": ["Formal Indonesian", "Informal / Colloquial"],
        "code": "id",
    },
    "Burmese (မြန်မာဘာသာ)": {
        "dialects": ["Standard Burmese", "Colloquial Burmese"],
        "code": "my",
    },
    "Bengali (বাংলা)": {
        "dialects": ["Standard Bengali", "Bangladeshi Bengali"],
        "code": "bn",
    },
    "Khmer (ភាសាខ្មែរ)": {
        "dialects": ["Standard Khmer", "Colloquial Khmer"],
        "code": "km",
    },
}

# Languages/dialects that typical LLMs do not support well for translation.
# For these we do not generate an English translation (doctor sees original only).
LANGUAGES_SKIP_ENGLISH_TRANSLATION = frozenset({
    "福建话 (Hokkien)",
    "潮州话 (Teochew)",
    "广东话 (Cantonese)",
    "客家话 (Hakka)",
    "海南话 (Hainanese)",
})


# ---------------------------------------------------------------------------
# Translation Helper
# ---------------------------------------------------------------------------

def _translate_to_english(text, source_language):
    """Translate text to English for the doctor's review.

    Returns the English translation string, or None if translation is
    skipped (e.g. English, or language/dialect not supported by LLM).
    """
    if not text or source_language == "English":
        return None
    if source_language in LANGUAGES_SKIP_ENGLISH_TRANSLATION:
        return None
    try:
        result, _ = call_llm(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a professional medical translator. "
                        f"Translate the following {source_language} text to English accurately. "
                        f"Preserve all medical terminology, dosages, and details precisely. "
                        f"Output ONLY the English translation — no commentary, no preamble."
                    ),
                },
                {"role": "user", "content": text},
            ],
            max_tokens=600,
            temperature=0.15,
        )
        return result.strip() if result else None
    except Exception as e:
        app.logger.warning("Translation to English failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# System Prompt Builders
# ---------------------------------------------------------------------------

def _build_system_prompt(session_type, language, dialect, cultural_context, patient_name):
    """Build the system prompt for the AI conversation engine."""

    cultural_note = ""
    if cultural_context:
        cultural_note = f"""
Cultural context provided by patient: {cultural_context}
Adapt your communication style, examples, and metaphors to be culturally resonant.
"""

    sea_context = """
You are operating in a Singapore / Southeast Asian healthcare setting.
Be aware of:
- Local cultural norms (respect for elders, family-centered decision-making, modesty preferences)
- Dietary considerations (halal dietary laws, vegetarianism for religious reasons, traditional food references)
- Traditional and complementary medicine usage (TCM, Jamu, Ayurveda) — ask respectfully, don't dismiss
- Common local health concerns and terminology
- Naming conventions (family name first for Chinese names, etc.)
"""

    if session_type == "pre":
        return f"""You are Aria, a warm and empathetic AI voice assistant conducting
a VOICE PRE-CONSULTATION CHECK-IN with {patient_name} at MedBridge Clinic, Singapore.
{sea_context}
Your goals:
1. Greet {patient_name} warmly in {language} ({dialect} dialect/variant).
2. Collect ONE piece of information per turn: chief complaint → symptom details (duration, severity) → current medications → allergies → relevant history.
3. Ask about pain levels (1–10 scale), onset, and any worsening or alleviating factors.
4. Screen for urgent red-flag symptoms (chest pain, difficulty breathing, severe headache, fainting, etc.) — if present, advise the patient to seek emergency care immediately.
5. Use simple everyday words — this is a VOICE conversation. No lists or bullet points.
6. Be culturally sensitive and warm throughout.
7. When you have gathered enough information, say a brief confirmation summary.

Language: Respond ENTIRELY in {language} ({dialect} dialect/variant).
{cultural_note}
CRITICAL VOICE RULES:
- Keep EVERY response to 1–2 short sentences maximum. This conversation will be read aloud.
- Ask only ONE question per turn.
- Never use markdown, bullet points, or numbered lists.
- Be warm, natural, and conversational — like a caring nurse on the phone."""

    else:   # post
        return f"""You are MedBridge, a warm, empathetic multilingual healthcare assistant conducting
a POST-CONSULTATION FOLLOW-UP with {patient_name}.
{sea_context}
Your goals:
1. Greet the patient warmly in {language} ({dialect} dialect/variant).
2. Review what the doctor discussed: diagnosis, treatment plan, medications prescribed.
3. Explain each medication: purpose, dosage, timing, common side effects — in plain, culturally appropriate language.
4. Verify understanding using teach-back: ask the patient to repeat key instructions.
5. Discuss follow-up appointments, warning signs to watch for, lifestyle recommendations.
6. Address any concerns or questions the patient has.
7. Provide emotional support and encouragement for adherence.

Language: Respond ENTIRELY in {language} ({dialect} dialect/variant).
{cultural_note}
IMPORTANT: Keep responses concise (2-4 sentences). Use analogies or comparisons familiar to the patient's culture when explaining medical concepts. Always be compassionate."""


def _build_summary_prompt(messages_text, session_type, language):
    """Build a prompt for generating clinician & patient summaries."""
    return f"""Analyze this {session_type}-consultation conversation and produce TWO summaries.
The conversation was conducted in {language}. English translations are provided where available.

CONVERSATION:
{messages_text}

---

SUMMARY 1 — CLINICIAN SUMMARY (in English):
Produce a structured clinical summary with these exact section headers:
• **Chief Complaint(s)**
• **History of Present Illness** (onset, duration, severity, alleviating/aggravating factors)
• **Current Medications & Allergies**
• **Red Flags / Urgent Concerns** (if any)
• **Social/Cultural Considerations** (relevant to care in Singapore/SEA context)
• **Patient Understanding & Adherence Risk** (assess health literacy, potential barriers)
• **Recommended Follow-up**

Use standard medical terminology. Be concise but thorough.

SUMMARY 2 — PATIENT SUMMARY (in {language}):
Write a simple, friendly summary for the patient in {language} that:
- Recaps what was discussed
- Lists key action items (medications, appointments, warning signs)
- Uses simple, culturally appropriate language
- Includes encouragement

Return as JSON: {{"clinician_summary": "...", "patient_summary": "..."}}"""


# ---------------------------------------------------------------------------
# API Routes — Languages
# ---------------------------------------------------------------------------

@app.route("/api/languages", methods=["GET"])
def get_languages():
    return jsonify(SUPPORTED_LANGUAGES)


# ---------------------------------------------------------------------------
# API Routes — API Key Configuration
# ---------------------------------------------------------------------------

@app.route("/api/config/status", methods=["GET"])
def config_status():
    """Check whether an LLM API key is configured and valid."""
    provider = _resolve_provider()
    if not provider:
        return jsonify({"api_key_set": False, "api_key_valid": False, "api_key_preview": "", "model": ""})

    key = provider["api_key"]
    api_key_valid = True

    if provider["type"] == "anthropic":
        if _anthropic_sdk is None:
            api_key_valid = False
        else:
            try:
                test_client = _anthropic_sdk.Anthropic(api_key=key)
                list(test_client.models.list())
            except _anthropic_sdk.AuthenticationError:
                api_key_valid = False
            except Exception:
                api_key_valid = True   # transient error — assume valid
    else:
        try:
            oa_kwargs = {"api_key": key}
            if provider.get("base_url"):
                oa_kwargs["base_url"] = provider["base_url"]
            test_client = OpenAI(**oa_kwargs)
            test_client.models.list()
        except AuthenticationError:
            api_key_valid = False
        except Exception:
            api_key_valid = True   # transient error — assume valid

    return jsonify({
        "api_key_set": True,
        "api_key_valid": api_key_valid,
        "api_key_preview": f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "",
        "model": provider["model"],
        "provider": provider["name"],
    })


@app.route("/api/config/apikey", methods=["POST"])
def set_api_key():
    """
    Set an LLM API key at runtime.

    Auto-detects provider from key prefix:
      sk-ant-...  → Anthropic (Claude)
      gsk_...     → Groq
      sl-...      → SEA-LION
      (other)     → OpenAI

    Optionally pass {"provider": "sealion"} to force SEA-LION detection
    when the key has no recognisable prefix.
    """
    data = request.json
    key = data.get("api_key", "").strip()
    provider_hint = data.get("provider", "").lower()
    if not key:
        return jsonify({"error": "API key cannot be empty"}), 400

    # Determine provider
    if key.startswith("sk-ant-") or provider_hint == "anthropic":
        env_var      = "ANTHROPIC_API_KEY"
        provider_type = "anthropic"
    elif key.startswith("gsk_") or provider_hint == "groq":
        env_var      = "GROQ_API_KEY"
        provider_type = "groq"
    elif key.startswith("sl-") or provider_hint == "sealion":
        env_var      = "SEALION_API_KEY"
        provider_type = "sealion"
    else:
        env_var      = "OPENAI_API_KEY"
        provider_type = "openai"

    # Validate key
    if provider_type == "anthropic":
        if _anthropic_sdk is None:
            return jsonify({"error": "anthropic package not installed. Run: pip install anthropic"}), 500
        try:
            test_client = _anthropic_sdk.Anthropic(api_key=key)
            list(test_client.models.list())
        except _anthropic_sdk.AuthenticationError:
            return jsonify({"error": "Invalid Anthropic API key."}), 400
        except Exception as e:
            return jsonify({"error": f"Could not validate key: {str(e)[:200]}"}), 400
    else:
        base_url = {
            "groq":    "https://api.groq.com/openai/v1",
            "sealion": "https://api.sea-lion.ai/v1",
            "openai":  None,
        }[provider_type]
        try:
            oa_kwargs = {"api_key": key}
            if base_url:
                oa_kwargs["base_url"] = base_url
            test_client = OpenAI(**oa_kwargs)
            test_client.models.list()
        except Exception as e:
            return jsonify({"error": f"Invalid API key: {str(e)[:200]}"}), 400

    os.environ[env_var] = key
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    _update_env_file(env_path, env_var, key)

    global _llm_client
    _llm_client = None

    return jsonify({"success": True, "api_key_preview": f"{key[:8]}...{key[-4:]}"})


def _update_env_file(path, var_name, var_value):
    """Create or update a variable in the .env file."""
    lines = []
    found = False
    if os.path.exists(path):
        with open(path, "r") as f:
            for line in f:
                if line.strip().startswith(f"{var_name}="):
                    lines.append(f"{var_name}={var_value}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"{var_name}={var_value}\n")
    with open(path, "w") as f:
        f.writelines(lines)


# ---------------------------------------------------------------------------
# API Routes — Patients
# ---------------------------------------------------------------------------

@app.route("/api/patients", methods=["POST"])
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


@app.route("/api/patients", methods=["GET"])
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


@app.route("/api/patients/<patient_id>", methods=["GET"])
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


# ---------------------------------------------------------------------------
# API Routes — Sessions
# ---------------------------------------------------------------------------

@app.route("/api/sessions", methods=["POST"])
def create_session():
    data = request.json
    patient = Patient.query.get_or_404(data["patient_id"])
    language = data.get("language", patient.preferred_language)
    dialect = data.get("dialect", patient.dialect)

    session = Session(
        patient_id=patient.id,
        session_type=data["session_type"],
        language_used=language,
        dialect_used=dialect,
    )
    db.session.add(session)
    db.session.flush()

    system_prompt = _build_system_prompt(
        session.session_type, language, dialect,
        patient.cultural_context, patient.name,
    )
    sys_msg = Message(session_id=session.id, role="system", content=system_prompt)
    db.session.add(sys_msg)

    # Generate initial greeting
    api_key_invalid = False
    try:
        greeting, api_key_invalid = call_llm(
            messages=[{"role": "system", "content": system_prompt}],
            max_tokens=300,
            temperature=0.7,
        )
        if not greeting:
            greeting = _fallback_greeting(language, patient.name, session.session_type)
    except Exception as e:
        app.logger.warning("LLM call failed for greeting: %s", e)
        greeting = _fallback_greeting(language, patient.name, session.session_type)

    # Translate greeting to English for doctor portal
    greeting_translated = _translate_to_english(greeting, language)

    asst_msg = Message(
        session_id=session.id,
        role="assistant",
        content=greeting,
        content_translated=greeting_translated,
    )
    db.session.add(asst_msg)
    db.session.commit()

    return jsonify({
        "session_id": session.id,
        "greeting": greeting,
        "api_key_invalid": api_key_invalid,
    }), 201


@app.route("/api/sessions/<session_id>/message", methods=["POST"])
def send_message(session_id):
    session = Session.query.get_or_404(session_id)
    data = request.json
    user_text = data["message"]

    # Translate user message to English for doctor
    user_translated = _translate_to_english(user_text, session.language_used)

    user_msg = Message(
        session_id=session.id,
        role="user",
        content=user_text,
        content_translated=user_translated,
    )
    db.session.add(user_msg)

    # Build conversation history for AI
    all_messages = Message.query.filter_by(session_id=session.id).order_by(Message.created_at).all()
    conversation = [{"role": m.role, "content": m.content} for m in all_messages]
    conversation.append({"role": "user", "content": user_text})

    # Get AI response
    api_key_invalid = False
    try:
        reply, api_key_invalid = call_llm(conversation, max_tokens=400, temperature=0.7)
        if reply is None:
            if api_key_invalid:
                reply = "[API key is invalid or expired. Please update it.]"
            else:
                reply = "[API key not configured. Please set your API key using the settings panel.]"
                api_key_invalid = True
    except Exception as e:
        app.logger.error("LLM chat error: %s", e)
        reply = f"[Translation service temporarily unavailable. Error: {str(e)[:150]}]"

    # Translate AI reply to English for doctor
    reply_translated = _translate_to_english(reply, session.language_used)

    asst_msg = Message(
        session_id=session.id,
        role="assistant",
        content=reply,
        content_translated=reply_translated,
    )
    db.session.add(asst_msg)
    db.session.commit()

    return jsonify({"reply": reply, "api_key_invalid": api_key_invalid})


@app.route("/api/sessions/<session_id>/complete", methods=["POST"])
def complete_session(session_id):
    session = Session.query.get_or_404(session_id)

    all_messages = Message.query.filter_by(session_id=session.id).order_by(Message.created_at).all()

    # Build conversation text with translations for the summary prompt
    lines = []
    for m in all_messages:
        if m.role == "system":
            continue
        speaker = "MedBridge (AI)" if m.role == "assistant" else "Patient"
        lines.append(f"{speaker}: {m.content}")
        if m.content_translated:
            lines.append(f"  [English Translation]: {m.content_translated}")
    convo_text = "\n".join(lines)

    summary_prompt = _build_summary_prompt(convo_text, session.session_type, session.language_used)

    try:
        raw, _ = call_llm(
            messages=[{"role": "system", "content": summary_prompt}],
            max_tokens=1500,
            temperature=0.3,
        )
        if raw is None:
            summaries = {"clinician_summary": "Summary unavailable — API key is not configured.", "patient_summary": ""}
        else:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    summaries = json.loads(raw[start:end], strict=False)
                except json.JSONDecodeError:
                    summaries = {"clinician_summary": raw, "patient_summary": ""}
            else:
                summaries = {"clinician_summary": raw, "patient_summary": ""}
    except Exception as e:
        app.logger.error("LLM summary error: %s", e)
        summaries = {
            "clinician_summary": f"Summary generation failed: {str(e)[:200]}",
            "patient_summary": "",
        }

    session.clinician_summary = summaries.get("clinician_summary", "")
    session.patient_summary = summaries.get("patient_summary", "")
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({
        "clinician_summary": session.clinician_summary,
        "patient_summary": session.patient_summary,
    })


@app.route("/api/sessions/<session_id>", methods=["PATCH"])
def update_session(session_id):
    """Update session fields (e.g. is_urgent for priority handling)."""
    session = Session.query.get_or_404(session_id)
    data = request.get_json() or {}
    if "is_urgent" in data:
        session.is_urgent = bool(data["is_urgent"])
    db.session.commit()
    return jsonify({
        "id": session.id,
        "is_urgent": getattr(session, "is_urgent", False),
    })


@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    session = Session.query.get_or_404(session_id)
    patient = Patient.query.get(session.patient_id)
    all_messages = Message.query.filter_by(session_id=session.id).order_by(Message.created_at).all()

    return jsonify({
        "id": session.id,
        "patient_id": session.patient_id,
        "patient_name": patient.name if patient else "Unknown",
        "patient_dob": patient.date_of_birth if patient else "",
        "patient_cultural_context": patient.cultural_context if patient else "",
        "session_type": session.session_type,
        "status": session.status,
        "is_urgent": getattr(session, "is_urgent", False),
        "language_used": session.language_used,
        "dialect_used": session.dialect_used,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "clinician_summary": session.clinician_summary,
        "patient_summary": session.patient_summary,
        "messages": [{
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "content_translated": m.content_translated,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        } for m in all_messages if m.role != "system"],
    })


@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    query = Session.query.order_by(Session.created_at.desc())
    patient_id = request.args.get("patient_id")
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    sessions = query.all()
    results = []
    for s in sessions:
        patient = Patient.query.get(s.patient_id)
        results.append({
            "id": s.id,
            "patient_id": s.patient_id,
            "patient_name": patient.name if patient else "Unknown",
            "session_type": s.session_type,
            "status": s.status,
            "is_urgent": getattr(s, "is_urgent", False),
            "language_used": s.language_used,
            "dialect_used": s.dialect_used,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "has_summary": bool(s.clinician_summary),
        })
    return jsonify(results)


# ---------------------------------------------------------------------------
# Translate on Demand (optional utility endpoint)
# ---------------------------------------------------------------------------

@app.route("/api/translate", methods=["POST"])
def translate_text():
    data = request.json
    text = data["text"]
    target_lang = data["target_language"]
    target_dialect = data.get("dialect", "")

    prompt = f"""Translate the following medical text into {target_lang} ({target_dialect} variant).
Rules:
- Use simple, everyday language appropriate for a patient with limited health literacy.
- Adapt cultural references, idioms, and examples to be familiar to a Singapore/Southeast Asian audience.
- If there's no direct translation for a medical term, explain the concept instead.
- Preserve all critical medical information (dosages, timing, warnings).

Text to translate:
{text}"""

    try:
        translated, _ = call_llm(
            messages=[{"role": "system", "content": prompt}],
            max_tokens=600,
            temperature=0.3,
        )
        if translated is None:
            return jsonify({"error": "API key not configured"}), 503
    except Exception as e:
        translated = f"[Translation failed: {str(e)[:100]}]"

    return jsonify({"translated": translated})


# ---------------------------------------------------------------------------
# Fallback Greetings (when API is unavailable)
# ---------------------------------------------------------------------------

def _fallback_greeting(language, name, session_type):
    kind = "check-in" if session_type == "pre" else "follow-up"
    pre = session_type == "pre"
    greetings = {
        "English": f"Hello {name}! Welcome. I'm here to help with your {kind}. How are you feeling today?",
        "华语 (Mandarin)": f"你好 {name}！欢迎。我在这里帮助您进行{'问诊前登记' if pre else '就诊后随访'}。您今天感觉怎么样？",
        "Malay (Bahasa Melayu)": f"Selamat datang {name}! Saya di sini untuk membantu anda dengan {'pendaftaran pra-konsultasi' if pre else 'tindakan susulan'}. Bagaimana perasaan anda hari ini?",
        "Tamil (தமிழ்)": f"வணக்கம் {name}! வரவேற்கிறோம். உங்கள் {'முன்-ஆலோசனை பதிவு' if pre else 'பின்-ஆலோசனை தொடர்'}க்கு நான் உதவ இருக்கிறேன். இன்று எப்படி உணர்கிறீர்கள்?",
        "福建话 (Hokkien)": f"你好 {name}！歡迎。我在這裡幫助你{'看醫生之前登記' if pre else '看完醫生後跟進'}。你今天感覺怎樣？",
        "潮州话 (Teochew)": f"你好 {name}！歡迎。我在這裡幫助你{'看醫生之前登記' if pre else '看完醫生後跟進'}。你今日感覺怎樣？",
        "广东话 (Cantonese)": f"你好 {name}！歡迎。我喺度幫你{'睇醫生之前登記' if pre else '睇完醫生之後跟進'}。你今日覺得點樣？",
        "客家话 (Hakka)": f"你好 {name}！歡迎。我在這裡幫你{'看醫生之前登記' if pre else '看完醫生後跟進'}。你今日感覺怎樣？",
        "海南话 (Hainanese)": f"你好 {name}！歡迎。我在這裡幫你{'看醫生之前登記' if pre else '看完醫生後跟進'}。你今日身體怎樣？",
        "Hindi (हिन्दी)": f"नमस्ते {name}! स्वागत है। मैं आपकी {'जाँच-पूर्व पंजीकरण' if pre else 'परामर्श के बाद अनुवर्ती'} में मदद के लिए यहाँ हूँ। आज आप कैसा महसूस कर रहे हैं?",
        "Vietnamese (Tiếng Việt)": f"Xin chào {name}! Chào mừng bạn. Tôi ở đây để giúp bạn với {'đăng ký trước khám' if pre else 'theo dõi sau khám'}. Hôm nay bạn cảm thấy thế nào?",
        "Thai (ภาษาไทย)": f"สวัสดีค่ะ/ครับ {name}! ยินดีต้อนรับ ฉันอยู่ที่นี่เพื่อช่วยคุณ{'ลงทะเบียนก่อนพบแพทย์' if pre else 'ติดตามผลหลังพบแพทย์'} วันนี้คุณรู้สึกอย่างไรบ้าง?",
        "Tagalog (Filipino)": f"Kumusta {name}! Maligayang pagdating. Nandito ako para tulungan ka sa iyong {'pre-consultation check-in' if pre else 'post-consultation follow-up'}. Kamusta ang pakiramdam mo ngayon?",
    }
    return greetings.get(language, greetings["English"])


# ---------------------------------------------------------------------------
# Serve Frontend
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)


# ---------------------------------------------------------------------------
# Init DB & Run
# ---------------------------------------------------------------------------

with app.app_context():
    db.create_all()
    # Add is_urgent to session if DB existed before (SQLite)
    try:
        db.session.execute(db.text("ALTER TABLE session ADD COLUMN is_urgent BOOLEAN DEFAULT 0"))
        db.session.commit()
    except Exception:
        db.session.rollback()
    # Ensure booking tables exist (idempotent via create_all above)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app.run(debug=True, port=port)
