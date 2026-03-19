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
import re
from datetime import datetime, timezone

from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI, AuthenticationError
from dotenv import load_dotenv
from services.meralion_client import MeralionError, transcribe_audio_bytes, check_reachable as meralion_reachable
try:
    from google.cloud import texttospeech
except Exception:
    texttospeech = None
import base64
import requests as http_requests

load_dotenv()

app = Flask(__name__, static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///medbridge.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
CORS(app)
app.json.sort_keys = False   # preserve insertion order for language dropdown

db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# LLM Client — MERaLion only
# ---------------------------------------------------------------------------

_llm_client = None
LLM_MODEL = os.getenv("LLM_MODEL", "")


def _resolve_provider():
    """Resolve LLM provider prioritize OpenRouter/OpenAI for vision support."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    sealion_key = os.getenv("SEALION_API_KEY", "")
    groq_key = os.getenv("GROQ_API_KEY", "")

    if openrouter_key:
        return {
            "type": "openai", "name": "OpenRouter",
            "api_key": openrouter_key,
            "base_url": "https://openrouter.ai/api/v1",
            "model": os.getenv("LLM_MODEL", "meta-llama/llama-3.2-90b-vision-instruct"),
        }
    if openai_key:
        return {
            "type": "openai", "name": "OpenAI",
            "api_key": openai_key,
            "base_url": None,
            "model": os.getenv("LLM_MODEL", "gpt-4o"),
        }
    if sealion_key:
        return {
            "type": "openai_compat", "name": "SEA-LION",
            "api_key": sealion_key,
            "base_url": "https://api.sea-lion.ai/v1",
            "model": os.getenv("LLM_MODEL", "aisingapore/Qwen-SEA-LION-v4-32B-IT"),
        }
    if groq_key:
        return {
            "type": "openai_compat", "name": "Groq",
            "api_key": groq_key,
            "base_url": "https://api.groq.com/openai/v1",
            "model": os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        }
    return None


def _strip_images(messages: list) -> list:
    """Remove image objects from messages for models that do not support vision."""
    clean = []
    for m in messages:
        if isinstance(m.get("content"), list):
            text_parts = [p["text"] for p in m["content"] if p.get("type") == "text"]
            clean.append({**m, "content": "\n".join(text_parts)})
        else:
            clean.append(m)
    return clean

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

    # ---- MERaLion (OpenAI-compatible) ----
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
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower() or "insufficient_quota" in str(e).lower():
            if provider and provider["name"] in ["OpenAI", "OpenRouter"]:
                app.logger.warning(f"{provider['name']} quota exceeded. Falling back.")
                if provider["name"] == "OpenAI":
                    os.environ["OPENAI_API_KEY"] = ""
                else:
                    os.environ["OPENROUTER_API_KEY"] = ""
                return call_llm(_strip_images(messages), max_tokens, temperature)
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
    slot_datetime = db.Column(db.String(20), nullable=False)   # "YYYY-MM-DD HH:MM"
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default="scheduled")     # scheduled | cancelled
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
    messages = db.relationship("AgentMessage", backref="agent_session", lazy=True, order_by="AgentMessage.created_at")


class AgentMessage(db.Model):
    __tablename__ = "agent_message"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey("agent_session.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)   # user | assistant | tool
    content = db.Column(db.Text)
    tool_name = db.Column(db.String(80))
    tool_result_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Language & Cultural Configuration — Singapore / Southeast Asia
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES = {
    # --- Singapore Official Languages ---
    "English": {
        "dialects": ["Standard Singapore English", "Singlish"],
        "code": "en",
        "group": "Singapore Official Languages",
    },
    "华语 (Mandarin)": {
        "dialects": ["新加坡华语 (Singapore Mandarin)", "标准普通话 (Standard Mandarin)"],
        "code": "zh",
        "group": "Singapore Official Languages",
    },
    "Malay (Bahasa Melayu)": {
        "dialects": ["Standard Bahasa Melayu", "Bazaar Melayu / Pasar Melayu", "Informal / Colloquial Malay"],
        "code": "ms",
        "group": "Singapore Official Languages",
    },
    "Tamil (தமிழ்)": {
        "dialects": ["Singapore Tamil (சிங்கப்பூர் தமிழ்)", "Standard Tamil (நிலைத்தமிழ்)"],
        "code": "ta",
        "group": "Singapore Official Languages",
    },
    # --- Singapore Chinese Dialects ---
    # Cantonese and Hokkien are exposed for speech capture.
    # Note: Hokkien has limited written-form standardization, so downstream LLM quality may vary.
    "广东话 (Cantonese)": {
        "dialects": ["新加坡广东话 (Singapore Cantonese)", "香港广东话 (Hong Kong Cantonese)"],
        "code": "zh-cantonese",
        "group": "Singapore Chinese Dialects",
    },
    "福建话 (Hokkien)": {
        "dialects": ["Singapore Hokkien", "Taiwanese Hokkien"],
        "code": "nan",
        "group": "Singapore Chinese Dialects",
    },
    # --- Southeast Asian Languages ---
    "Hindi (हिन्दी)": {
        "dialects": ["Standard Hindi", "Colloquial Hindi"],
        "code": "hi",
        "group": "Southeast Asian Languages",
    },
    "Tagalog (Filipino)": {
        "dialects": ["Standard Filipino", "Taglish"],
        "code": "tl",
        "group": "Southeast Asian Languages",
    },
    "Vietnamese (Tiếng Việt)": {
        "dialects": ["Northern Vietnamese", "Southern Vietnamese"],
        "code": "vi",
        "group": "Southeast Asian Languages",
    },
    "Thai (ภาษาไทย)": {
        "dialects": ["Central Thai", "Informal Thai"],
        "code": "th",
        "group": "Southeast Asian Languages",
    },
    "Bahasa Indonesia": {
        "dialects": ["Formal Indonesian", "Informal / Colloquial"],
        "code": "id",
        "group": "Southeast Asian Languages",
    },
    "Burmese (မြန်မာဘာသာ)": {
        "dialects": ["Standard Burmese", "Colloquial Burmese"],
        "code": "my",
        "group": "Southeast Asian Languages",
    },
    "Bengali (বাংলা)": {
        "dialects": ["Standard Bengali", "Bangladeshi Bengali"],
        "code": "bn",
        "group": "Southeast Asian Languages",
    },
    "Khmer (ភាសាខ្មែរ)": {
        "dialects": ["Standard Khmer", "Colloquial Khmer"],
        "code": "km",
        "group": "Southeast Asian Languages",
    },
}

# All remaining languages (including Cantonese) are supported well enough by
# SEA-LION for English translation. Keep this frozenset as a safety valve.
LANGUAGES_SKIP_ENGLISH_TRANSLATION = frozenset()


def _detect_language_heuristic(text):
    """
    Lightweight language/dialect detector for first-utterance routing.
    Returns (language, dialect, confidence, reason).
    """
    raw = (text or "").strip()
    lower = raw.lower()
    if not raw:
        return "English", "Standard Singapore English", 0.35, "empty input fallback"

    # Script-based detection first
    if re.search(r"[\u0B80-\u0BFF]", raw):
        return "Tamil (தமிழ்)", "Singapore Tamil (சிங்கப்பூர் தமிழ்)", 0.95, "Tamil script detected"
    if re.search(r"[\u0900-\u097F]", raw):
        return "Hindi (हिन्दी)", "Colloquial Hindi", 0.9, "Devanagari script detected"
    if re.search(r"[\u1000-\u109F]", raw):
        return "Burmese (မြန်မာဘာသာ)", "Colloquial Burmese", 0.9, "Burmese script detected"
    if re.search(r"[\u0980-\u09FF]", raw):
        return "Bengali (বাংলা)", "Standard Bengali", 0.9, "Bengali script detected"
    if re.search(r"[\u1780-\u17FF]", raw):
        return "Khmer (ភាសាខ្មែរ)", "Standard Khmer", 0.9, "Khmer script detected"
    if re.search(r"[\u0E00-\u0E7F]", raw):
        return "Thai (ภาษาไทย)", "Informal Thai", 0.9, "Thai script detected"

    # Chinese script, with rough Cantonese hints
    if re.search(r"[\u4E00-\u9FFF]", raw):
        cantonese_markers = ("佢", "冇", "咩", "嘅", "喺", "哋", "咗")
        if any(marker in raw for marker in cantonese_markers):
            return "广东话 (Cantonese)", "新加坡广东话 (Singapore Cantonese)", 0.86, "Chinese script with Cantonese markers"
        return "华语 (Mandarin)", "新加坡华语 (Singapore Mandarin)", 0.82, "Chinese script detected"

    # Latin-script lexical hints
    malay_markers = (
        "saya", "awak", "anda", "tak", "tidak", "sakit", "kepala",
        "perut", "demam", "batuk", "doktor", "klinik", "lah",
    )
    singlish_markers = (
        "lah", "leh", "lor", "meh", "sia", "sian", "can or not",
        "alamak", "auntie", "uncle", "shiok",
    )
    hokkien_markers = ("aiya", "bo pian", "paiseh", "kancheong")

    malay_score = sum(1 for marker in malay_markers if marker in lower)
    singlish_score = sum(1 for marker in singlish_markers if marker in lower)
    hokkien_score = sum(1 for marker in hokkien_markers if marker in lower)

    if hokkien_score >= 2:
        return "福建话 (Hokkien)", "Singapore Hokkien", 0.66, "Hokkien lexical markers"
    if malay_score >= 2 and malay_score >= singlish_score:
        return "Malay (Bahasa Melayu)", "Informal / Colloquial Malay", 0.78, "Malay lexical markers"
    if singlish_score >= 1:
        return "English", "Singlish", 0.74, "Singlish particles/markers"

    return "English", "Standard Singapore English", 0.52, "default English fallback"


def _detect_language_with_llm(text):
    """
    LLM-assisted detector for mixed-code utterances.
    Returns dict or None on failure.
    """
    prompt = (
        "Detect the dominant spoken language and dialect for this Singapore healthcare utterance. "
        "Pick ONLY from these language keys and dialect values:\n"
        f"{json.dumps(SUPPORTED_LANGUAGES, ensure_ascii=False)}\n\n"
        "Return JSON only:\n"
        "{\"language\":\"...\",\"dialect\":\"...\",\"confidence\":0.0,\"is_mixed\":true,\"reason\":\"...\"}\n"
        "If mixed language, pick the dominant language the assistant should respond in."
    )
    try:
        raw, _ = call_llm(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            max_tokens=220,
            temperature=0.0,
        )
        if not raw:
            return None
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start < 0 or end <= start:
            return None
        parsed = json.loads(raw[start:end], strict=False)
        language = parsed.get("language")
        dialect = parsed.get("dialect", "")
        if language not in SUPPORTED_LANGUAGES:
            return None
        if dialect and dialect not in SUPPORTED_LANGUAGES[language].get("dialects", []):
            dialect = SUPPORTED_LANGUAGES[language].get("dialects", [""])[0]
        confidence = parsed.get("confidence", 0.0)
        try:
            confidence = float(confidence)
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        return {
            "language": language,
            "dialect": dialect,
            "confidence": confidence,
            "reason": parsed.get("reason", "llm classification"),
            "is_mixed": bool(parsed.get("is_mixed", False)),
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Mock Doctor Data
# ---------------------------------------------------------------------------

MOCK_DOCTORS = [
    {
        "id": "dr_lim",
        "name": "Dr. Lim Wei Jie",
        "specialty": "General Practice",
        "institution": "Clementi Polyclinic",
        "slots": [
            {"slot_id": "dr_lim_01", "datetime": "2026-03-16 09:00"},
            {"slot_id": "dr_lim_02", "datetime": "2026-03-16 11:00"},
            {"slot_id": "dr_lim_03", "datetime": "2026-03-17 09:00"},
            {"slot_id": "dr_lim_04", "datetime": "2026-03-17 14:00"},
            {"slot_id": "dr_lim_05", "datetime": "2026-03-18 10:00"},
            {"slot_id": "dr_lim_06", "datetime": "2026-03-18 15:00"},
            {"slot_id": "dr_lim_07", "datetime": "2026-03-19 09:00"},
            {"slot_id": "dr_lim_08", "datetime": "2026-03-19 11:00"},
            {"slot_id": "dr_lim_09", "datetime": "2026-03-20 10:00"},
            {"slot_id": "dr_lim_10", "datetime": "2026-03-20 14:00"},
            {"slot_id": "dr_lim_11", "datetime": "2026-03-23 09:00"},
            {"slot_id": "dr_lim_12", "datetime": "2026-03-23 11:00"},
            {"slot_id": "dr_lim_13", "datetime": "2026-03-24 09:00"},
            {"slot_id": "dr_lim_14", "datetime": "2026-03-24 14:00"},
            {"slot_id": "dr_lim_15", "datetime": "2026-03-25 10:00"},
            {"slot_id": "dr_lim_16", "datetime": "2026-03-26 09:00"},
            {"slot_id": "dr_lim_17", "datetime": "2026-03-27 10:00"},
            {"slot_id": "dr_lim_18", "datetime": "2026-03-30 09:00"},
            {"slot_id": "dr_lim_19", "datetime": "2026-04-01 10:00"},
            {"slot_id": "dr_lim_20", "datetime": "2026-04-03 14:00"},
        ],
    },
    {
        "id": "dr_tan",
        "name": "Dr. Tan Mei Ling",
        "specialty": "General Practice",
        "institution": "Bukit Batok Polyclinic",
        "slots": [
            {"slot_id": "dr_tan_01", "datetime": "2026-03-16 10:00"},
            {"slot_id": "dr_tan_02", "datetime": "2026-03-16 14:00"},
            {"slot_id": "dr_tan_03", "datetime": "2026-03-17 10:00"},
            {"slot_id": "dr_tan_04", "datetime": "2026-03-17 15:00"},
            {"slot_id": "dr_tan_05", "datetime": "2026-03-18 09:00"},
            {"slot_id": "dr_tan_06", "datetime": "2026-03-19 14:00"},
            {"slot_id": "dr_tan_07", "datetime": "2026-03-20 09:00"},
            {"slot_id": "dr_tan_08", "datetime": "2026-03-23 10:00"},
            {"slot_id": "dr_tan_09", "datetime": "2026-03-24 10:00"},
            {"slot_id": "dr_tan_10", "datetime": "2026-03-25 14:00"},
            {"slot_id": "dr_tan_11", "datetime": "2026-03-26 10:00"},
            {"slot_id": "dr_tan_12", "datetime": "2026-03-27 09:00"},
            {"slot_id": "dr_tan_13", "datetime": "2026-03-30 14:00"},
            {"slot_id": "dr_tan_14", "datetime": "2026-04-01 09:00"},
            {"slot_id": "dr_tan_15", "datetime": "2026-04-06 10:00"},
        ],
    },
    {
        "id": "dr_siti",
        "name": "Dr. Siti Rahimah",
        "specialty": "Cardiology",
        "institution": "Singapore General Hospital",
        "slots": [
            {"slot_id": "dr_siti_01", "datetime": "2026-03-16 10:00"},
            {"slot_id": "dr_siti_02", "datetime": "2026-03-16 14:00"},
            {"slot_id": "dr_siti_03", "datetime": "2026-03-17 10:00"},
            {"slot_id": "dr_siti_04", "datetime": "2026-03-18 14:00"},
            {"slot_id": "dr_siti_05", "datetime": "2026-03-19 10:00"},
            {"slot_id": "dr_siti_06", "datetime": "2026-03-20 10:00"},
            {"slot_id": "dr_siti_07", "datetime": "2026-03-23 14:00"},
            {"slot_id": "dr_siti_08", "datetime": "2026-03-24 10:00"},
            {"slot_id": "dr_siti_09", "datetime": "2026-03-25 14:00"},
            {"slot_id": "dr_siti_10", "datetime": "2026-03-26 10:00"},
            {"slot_id": "dr_siti_11", "datetime": "2026-03-27 14:00"},
            {"slot_id": "dr_siti_12", "datetime": "2026-03-30 10:00"},
            {"slot_id": "dr_siti_13", "datetime": "2026-04-01 14:00"},
            {"slot_id": "dr_siti_14", "datetime": "2026-04-06 10:00"},
            {"slot_id": "dr_siti_15", "datetime": "2026-04-08 14:00"},
        ],
    },
    {
        "id": "dr_rajan",
        "name": "Dr. Rajan Pillai",
        "specialty": "Dermatology",
        "institution": "National Skin Centre",
        "slots": [
            {"slot_id": "dr_rajan_01", "datetime": "2026-03-16 09:00"},
            {"slot_id": "dr_rajan_02", "datetime": "2026-03-16 15:00"},
            {"slot_id": "dr_rajan_03", "datetime": "2026-03-17 11:00"},
            {"slot_id": "dr_rajan_04", "datetime": "2026-03-18 09:00"},
            {"slot_id": "dr_rajan_05", "datetime": "2026-03-19 15:00"},
            {"slot_id": "dr_rajan_06", "datetime": "2026-03-20 11:00"},
            {"slot_id": "dr_rajan_07", "datetime": "2026-03-23 09:00"},
            {"slot_id": "dr_rajan_08", "datetime": "2026-03-24 15:00"},
            {"slot_id": "dr_rajan_09", "datetime": "2026-03-25 11:00"},
            {"slot_id": "dr_rajan_10", "datetime": "2026-03-26 09:00"},
            {"slot_id": "dr_rajan_11", "datetime": "2026-03-27 15:00"},
            {"slot_id": "dr_rajan_12", "datetime": "2026-03-30 11:00"},
            {"slot_id": "dr_rajan_13", "datetime": "2026-04-01 09:00"},
            {"slot_id": "dr_rajan_14", "datetime": "2026-04-06 15:00"},
            {"slot_id": "dr_rajan_15", "datetime": "2026-04-08 11:00"},
        ],
    },
    {
        "id": "dr_chen",
        "name": "Dr. Chen Xiu Ying",
        "specialty": "Paediatrics",
        "institution": "Khoo Teck Puat Hospital",
        "slots": [
            {"slot_id": "dr_chen_01", "datetime": "2026-03-16 09:00"},
            {"slot_id": "dr_chen_02", "datetime": "2026-03-16 14:00"},
            {"slot_id": "dr_chen_03", "datetime": "2026-03-17 09:00"},
            {"slot_id": "dr_chen_04", "datetime": "2026-03-17 15:00"},
            {"slot_id": "dr_chen_05", "datetime": "2026-03-18 10:00"},
            {"slot_id": "dr_chen_06", "datetime": "2026-03-19 09:00"},
            {"slot_id": "dr_chen_07", "datetime": "2026-03-19 14:00"},
            {"slot_id": "dr_chen_08", "datetime": "2026-03-20 09:00"},
            {"slot_id": "dr_chen_09", "datetime": "2026-03-23 10:00"},
            {"slot_id": "dr_chen_10", "datetime": "2026-03-24 14:00"},
            {"slot_id": "dr_chen_11", "datetime": "2026-03-25 09:00"},
            {"slot_id": "dr_chen_12", "datetime": "2026-03-26 14:00"},
            {"slot_id": "dr_chen_13", "datetime": "2026-03-27 10:00"},
            {"slot_id": "dr_chen_14", "datetime": "2026-03-30 09:00"},
            {"slot_id": "dr_chen_15", "datetime": "2026-04-01 14:00"},
        ],
    },
    {
        "id": "dr_farhan",
        "name": "Dr. Muhammad Farhan",
        "specialty": "Orthopaedics",
        "institution": "Tan Tock Seng Hospital",
        "slots": [
            {"slot_id": "dr_farhan_01", "datetime": "2026-03-16 14:00"},
            {"slot_id": "dr_farhan_02", "datetime": "2026-03-17 10:00"},
            {"slot_id": "dr_farhan_03", "datetime": "2026-03-18 09:00"},
            {"slot_id": "dr_farhan_04", "datetime": "2026-03-18 15:00"},
            {"slot_id": "dr_farhan_05", "datetime": "2026-03-19 10:00"},
            {"slot_id": "dr_farhan_06", "datetime": "2026-03-20 14:00"},
            {"slot_id": "dr_farhan_07", "datetime": "2026-03-23 09:00"},
            {"slot_id": "dr_farhan_08", "datetime": "2026-03-24 10:00"},
            {"slot_id": "dr_farhan_09", "datetime": "2026-03-25 14:00"},
            {"slot_id": "dr_farhan_10", "datetime": "2026-03-26 10:00"},
            {"slot_id": "dr_farhan_11", "datetime": "2026-03-27 09:00"},
            {"slot_id": "dr_farhan_12", "datetime": "2026-03-30 14:00"},
            {"slot_id": "dr_farhan_13", "datetime": "2026-04-01 10:00"},
            {"slot_id": "dr_farhan_14", "datetime": "2026-04-06 09:00"},
            {"slot_id": "dr_farhan_15", "datetime": "2026-04-08 14:00"},
        ],
    },
]


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
# Agent Tool Functions
# ---------------------------------------------------------------------------

def tool_get_family_members(patient_id):
    members = FamilyMember.query.filter_by(patient_id=patient_id).all()
    return [{"id": m.id, "name": m.name, "relationship": m.relationship,
             "date_of_birth": m.date_of_birth or "", "notes": m.notes or ""} for m in members]


def tool_add_family_member(patient_id, name, relationship, dob="", notes=""):
    member = FamilyMember(patient_id=patient_id, name=name, relationship=relationship,
                          date_of_birth=dob or None, notes=notes or None)
    db.session.add(member)
    db.session.commit()
    return {"id": member.id, "name": member.name, "relationship": member.relationship}


def tool_get_doctors(specialty=None):
    if specialty:
        spec_lower = specialty.lower()
        doctors = [d for d in MOCK_DOCTORS if spec_lower in d["specialty"].lower()]
    else:
        doctors = MOCK_DOCTORS
    return [{"id": d["id"], "name": d["name"], "specialty": d["specialty"]} for d in doctors]


def tool_get_doctor_slots(doctor_id, date=None):
    doctor = next((d for d in MOCK_DOCTORS if d["id"] == doctor_id), None)
    if not doctor:
        return {"error": f"Doctor '{doctor_id}' not found"}
    booked = {a.slot_datetime for a in Appointment.query.filter_by(
        doctor_id=doctor_id, status="scheduled").all()}
    today = datetime.now().strftime("%Y-%m-%d")
    slots = [s for s in doctor["slots"] if s["datetime"] >= today]  # only future slots
    if date:
        slots = [s for s in slots if s["datetime"].startswith(date)]
    available = [s for s in slots if s["datetime"] not in booked]
    return {
        "doctor_name": doctor["name"],
        "specialty": doctor["specialty"],
        "institution": doctor.get("institution", ""),
        "available_slots": available,
    }


def tool_book_appointment(patient_id, doctor_id, slot_datetime, reason, family_member_id=None):
    doctor = next((d for d in MOCK_DOCTORS if d["id"] == doctor_id), None)
    if not doctor:
        return {"error": f"Doctor '{doctor_id}' not found"}
    # Check not already booked
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
        status="scheduled",
    )
    db.session.add(appt)
    db.session.commit()
    for_whom = ""
    if family_member_id:
        fm = FamilyMember.query.get(family_member_id)
        if fm:
            for_whom = f" for {fm.name}"
    return {"appointment_id": appt.id, "doctor": doctor["name"], "specialty": doctor["specialty"],
            "datetime": slot_datetime, "reason": reason, "for": for_whom.strip()}


def tool_get_appointments(patient_id, family_member_id=None):
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


def tool_cancel_appointment(appointment_id, patient_id):
    appt = Appointment.query.filter_by(id=appointment_id, patient_id=patient_id).first()
    if not appt:
        return {"error": "Appointment not found or not authorized"}
    appt.status = "cancelled"
    db.session.commit()
    return {"cancelled": True, "appointment_id": appointment_id, "doctor": appt.doctor_name,
            "datetime": appt.slot_datetime}


def tool_add_medication(patient_id, name, dosage, frequency, reminder_times,
                        start_date="", end_date="", notes="", family_member_id=None):
    if isinstance(reminder_times, list):
        reminder_json = json.dumps(reminder_times)
    else:
        reminder_json = reminder_times if reminder_times else "[]"
    med = Medication(
        patient_id=patient_id,
        family_member_id=family_member_id or None,
        name=name,
        dosage=dosage,
        frequency=frequency,
        reminder_times=reminder_json,
        start_date=start_date or None,
        end_date=end_date or None,
        notes=notes or None,
        is_active=True,
    )
    db.session.add(med)
    db.session.commit()
    return {"medication_id": med.id, "name": name, "dosage": dosage, "frequency": frequency,
            "reminder_times": json.loads(reminder_json)}


def tool_get_medications(patient_id, family_member_id=None, active_only=True):
    query = Medication.query.filter_by(patient_id=patient_id)
    if active_only:
        query = query.filter_by(is_active=True)
    if family_member_id:
        query = query.filter_by(family_member_id=family_member_id)
    meds = query.all()
    result = []
    for m in meds:
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


def tool_remove_medication(medication_id, patient_id):
    med = Medication.query.filter_by(id=medication_id, patient_id=patient_id).first()
    if not med:
        return {"error": "Medication not found or not authorized"}
    med.is_active = False
    db.session.commit()
    return {"removed": True, "medication_id": medication_id, "name": med.name}


def tool_get_health_summary(patient_id, family_member_id=None):
    appts = tool_get_appointments(patient_id, family_member_id)
    meds = tool_get_medications(patient_id, family_member_id, active_only=True)
    family = tool_get_family_members(patient_id)
    # Past consultations (pre-consultation sessions)
    past_sessions = Session.query.filter_by(patient_id=patient_id, session_type="pre",
                                             status="completed").order_by(Session.created_at.desc()).limit(5).all()
    consultations = [{"date": s.created_at.strftime("%Y-%m-%d") if s.created_at else "",
                      "language": s.language_used or ""} for s in past_sessions]
    return {"upcoming_appointments": appts, "active_medications": meds,
            "family_members": family, "past_consultations": consultations}


# ---------------------------------------------------------------------------
# Agent Tool Definitions (OpenAI function-calling format)
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
                "name": {"type": "string", "description": "Full name of the family member"},
                "relationship": {"type": "string", "description": "e.g. son, daughter, mother, father, spouse"},
                "dob": {"type": "string", "description": "Date of birth YYYY-MM-DD (optional)"},
                "notes": {"type": "string", "description": "Any additional notes (optional)"},
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
                "specialty": {"type": "string", "description": "Filter by specialty (optional), e.g. Cardiology, General Practice"},
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
                "date": {"type": "string", "description": "Filter by date YYYY-MM-DD (optional)"},
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
                "doctor_id": {"type": "string", "description": "Doctor ID from get_doctors"},
                "slot_datetime": {"type": "string", "description": "Exact datetime string YYYY-MM-DD HH:MM from get_doctor_slots"},
                "reason": {"type": "string", "description": "Reason for appointment"},
                "family_member_id": {"type": "string", "description": "Family member ID if booking for a dependant (omit if booking for self)"},
            },
            "required": ["doctor_id", "slot_datetime", "reason"],
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
                "name": {"type": "string", "description": "Medication name"},
                "dosage": {"type": "string", "description": "e.g. 500mg"},
                "frequency": {"type": "string", "description": "e.g. twice daily, once at night"},
                "reminder_times": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of reminder times in HH:MM format, e.g. [\"08:00\", \"20:00\"]",
                },
                "start_date": {"type": "string", "description": "Start date YYYY-MM-DD (optional)"},
                "end_date": {"type": "string", "description": "End date YYYY-MM-DD (optional)"},
                "notes": {"type": "string", "description": "Additional notes (optional)"},
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
                "active_only": {"type": "boolean", "description": "Return only active medications (default true)"},
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
        "description": "Get a full health overview: upcoming appointments, active medications, family members, past consultations",
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
        "name": "book_on_healthhub",
        "description": (
            "Automate the ENTIRE HealthHub booking form — clicks every step "
            "(hospital, department, date, time, reason, confirm) automatically "
            "while the patient watches in the live panel. "
            "Call this only once you have collected ALL 5 booking details from the patient."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "institution": {
                    "type": "string",
                    "description": (
                        "Hospital or polyclinic name. Must be one of: "
                        "Singapore General Hospital, National University Hospital, "
                        "Khoo Teck Puat Hospital, Tan Tock Seng Hospital, "
                        "Clementi Polyclinic, Buona Vista Polyclinic, Jurong Polyclinic"
                    ),
                },
                "specialty": {
                    "type": "string",
                    "description": (
                        "Department. Must be one of: "
                        "Cardiology, Eye Clinic, General Practice, Neurology, "
                        "Dental, Orthopaedics, Paediatrics, Vaccination"
                    ),
                },
                "date": {
                    "type": "string",
                    "description": "Appointment date in YYYY-MM-DD format, e.g. '2026-03-20'",
                },
                "time": {
                    "type": "string",
                    "description": "Appointment time, e.g. '09:00' or '14:00' or '9:00 AM'",
                },
                "reason": {
                    "type": "string",
                    "description": (
                        "Visit reason. Must be one of: "
                        "Follow-up consultation, Acute pain or discomfort, "
                        "Routine check-up, Prescription renewal, Flu jab / Vaccination, "
                        "Pre-surgery assessment, Specialist referral, Lab test results review"
                    ),
                },
            },
            "required": ["institution", "specialty", "date", "time", "reason"],
        },
    }},
    {"type": "function", "function": {
        "name": "view_healthhub",
        "description": (
            "Navigate the HealthHub browser to show the patient their appointments, "
            "medications, or lab reports on the live panel."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "string",
                    "description": "Page to open: appointments | medications | lab-reports | home",
                },
            },
            "required": ["page"],
        },
    }},
    {"type": "function", "function": {
        "name": "interact_with_screen",
        "description": (
            "Perform an atomic browser action on the current HealthHub screen. "
            "Prefer 'click_text' over 'click' — it finds elements by their visible label/text and is reliable on the live site. "
            "Use 'read_page' to list all visible interactive elements (links, buttons) and the current URL before deciding what to click. "
            "Use 'scroll' to scroll the page or a specific element down to reveal more content. "
            "OBSERVATION LAYER: after every 'click_text' or 'click', you MUST immediately call 'read_page' again to observe any UI changes (e.g. dropdown options that appeared, new fields that loaded). Parse those options before speaking to the user. "
            "Use 'click' (x, y) ONLY as a last resort when no text label is available."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["click_text", "read_page", "scroll", "click", "type", "press", "clear_modals"],
                    "description": "'click_text' clicks by text label; 'read_page' lists visible interactive elements and current URL; 'scroll' scrolls the page down to reveal more options; 'click' clicks x/y; 'type' types text; 'press' presses key."
                },
                "text":     {"type": "string",  "description": "For click_text: the visible label of the element to click (e.g. 'Login via Singpass'). For type: the text to type."},
                "role":     {"type": "string",  "description": "Optional ARIA role to narrow click_text search: button | link | menuitem | tab | option"},
                "selector": {"type": "string",  "description": "Optional CSS selector for direct targeting (overrides text search)"},
                "x":        {"type": "number",  "description": "X pixel for raw click action"},
                "y":        {"type": "number",  "description": "Y pixel for raw click action"},
                "key":      {"type": "string",  "description": "Key name for press action, e.g. Enter, Tab, Escape"},
                "distance": {"type": "number",  "description": "Pixels to scroll for the scroll action (default 600)"},
                "direction":{"type": "string",  "description": "Scroll direction: 'down' (default) or 'up'. Use 'up' when the target was previously visible or is likely above the current viewport."}
            },
            "required": ["action"]
        }
    }},
]

# Tool names list for fallback prompt injection
_TOOL_NAMES_DESC = "\n".join(
    f"- {t['function']['name']}: {t['function']['description']}" for t in AGENT_TOOLS
)


# ---------------------------------------------------------------------------
# Agentic Loop
# ---------------------------------------------------------------------------

def call_llm_with_tools(messages, tools=None, max_tokens=500, temperature=0.7):
    """Call LLM with optional tool definitions. Returns full response object."""
    global LLM_MODEL, _llm_client
    provider = _resolve_provider()
    if not provider:
        return None

    LLM_MODEL = provider["model"]
    oa_kwargs = {"api_key": provider["api_key"]}
    if provider.get("base_url"):
        oa_kwargs["base_url"] = provider["base_url"]
    if _llm_client is None or _llm_client.api_key != provider["api_key"]:
        _llm_client = OpenAI(**oa_kwargs)

    kwargs = dict(model=provider["model"], messages=messages,
                  max_tokens=max_tokens, temperature=temperature)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    try:
        return _llm_client.chat.completions.create(**kwargs)
    except Exception as e:
        app.logger.warning("call_llm_with_tools error: %s", e)
        if "429" in str(e) or "quota" in str(e).lower() or "insufficient_quota" in str(e).lower():
            if provider and provider["name"] in ["OpenAI", "OpenRouter"]:
                app.logger.warning(f"{provider['name']} quota exceeded in tools. Falling back.")
                if provider["name"] == "OpenAI":
                    os.environ["OPENAI_API_KEY"] = ""
                else:
                    os.environ["OPENROUTER_API_KEY"] = ""
                return call_llm_with_tools(_strip_images(messages), tools, max_tokens, temperature)
        return None


def _extract_json_tool_call(text):
    """Extract tool call JSON from <tool_call>{...}</tool_call> in model output."""
    import re
    match = re.search(r"<tool_call>(.*?)</tool_call>", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1).strip())
    except Exception:
        return None


HEALTHHUB_BRIDGE_BASE = "http://localhost:7001"

import requests as _bridge_requests


def _call_bridge(path, payload=None, method="POST", timeout=45):
    """Synchronous call to the Playwright bridge. Returns JSON dict or error dict."""
    try:
        url = f"{HEALTHHUB_BRIDGE_BASE}{path}"
        if method == "POST":
            resp = _bridge_requests.post(url, json=payload or {}, timeout=timeout)
        else:
            resp = _bridge_requests.get(url, timeout=timeout)
        return resp.json()
    except Exception as e:
        app.logger.warning("Bridge call %s failed: %s", path, e)
        return {"error": f"HealthHub browser not reachable: {e}"}


def dispatch_tool(name, args, patient_id):
    """Route tool name to its implementation, injecting patient_id for auth."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}

    # ── HealthHub browser tools (call bridge directly, no DB) ──────────────
    if name == "book_on_healthhub":
        raw = _call_bridge("/api/booking/full", {
            "institution": args.get("institution", ""),
            "specialty":   args.get("specialty", ""),
            "date":        args.get("date", ""),
            "time":        args.get("time", ""),
            "reason":      args.get("reason", ""),
        }, timeout=120)

        if isinstance(raw, dict):
            # Singpass wall — trigger a long-poll wait then indicate to agent
            if raw.get("on_singpass_page") or raw.get("paused"):
                # Ask agent bridge to wait for Singpass login (up to 3 min)
                wait_result = _call_bridge("/api/singpass/wait?timeout_ms=180000", {}, method="POST", timeout=200)
                if isinstance(wait_result, dict) and wait_result.get("logged_in"):
                    return {"status": "singpass_ok", "message": "User has logged in via Singpass. Please retry the booking."}
                return {"status": "singpass_timeout", "message": "User did not complete Singpass login in time. Please ask them to try again."}
            # UI mismatch — don't crash, give the agent a clear explanation
            if raw.get("ui_mismatch"):
                step = raw.get("step", "unknown step")
                desc = raw.get("description", "selector not found")
                return {
                    "status": "ui_mismatch",
                    "message": (
                        f"Could not complete '{step}' automatically — "
                        f"{desc}. Tell the user what happened and ask them to perform this step manually on the browser screen."
                    ),
                }
        return raw

    if name == "interact_with_screen":
        return _call_bridge("/api/browser/action", {
            "action":   args.get("action", ""),
            "x":        args.get("x", 0),
            "y":        args.get("y", 0),
            "text":     args.get("text", ""),
            "key":      args.get("key", ""),
            "role":     args.get("role", ""),
            "selector": args.get("selector", ""),
        }, timeout=45)

    if name == "view_healthhub":
        raw = _call_bridge("/api/navigate", {"page": args.get("page", "home")})
        if isinstance(raw, dict) and raw.get("on_singpass_page"):
            return {"status": "singpass_required", "message": "HealthHub is showing a Singpass login screen. Please guide the user to scan the QR code."}
        return raw


    # ── DB tools ──────────────────────────────────────────────────────────
    dispatch_map = {
        "get_family_members": lambda: tool_get_family_members(patient_id),
        "add_family_member": lambda: tool_add_family_member(
            patient_id, args.get("name", ""), args.get("relationship", ""),
            args.get("dob", ""), args.get("notes", "")),
        "get_doctors": lambda: tool_get_doctors(args.get("specialty")),
        "get_doctor_slots": lambda: tool_get_doctor_slots(
            args.get("doctor_id", ""), args.get("date")),
        "book_appointment": lambda: tool_book_appointment(
            patient_id, args.get("doctor_id", ""), args.get("slot_datetime", ""),
            args.get("reason", ""), args.get("family_member_id")),
        "get_appointments": lambda: tool_get_appointments(
            patient_id, args.get("family_member_id")),
        "cancel_appointment": lambda: tool_cancel_appointment(
            args.get("appointment_id", ""), patient_id),
        "add_medication": lambda: tool_add_medication(
            patient_id, args.get("name", ""), args.get("dosage", ""),
            args.get("frequency", ""), args.get("reminder_times", []),
            args.get("start_date", ""), args.get("end_date", ""),
            args.get("notes", ""), args.get("family_member_id")),
        "get_medications": lambda: tool_get_medications(
            patient_id, args.get("family_member_id"), args.get("active_only", True)),
        "remove_medication": lambda: tool_remove_medication(
            args.get("medication_id", ""), patient_id),
        "get_health_summary": lambda: tool_get_health_summary(
            patient_id, args.get("family_member_id")),
    }
    fn = dispatch_map.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        result = fn()
    except Exception as e:
        app.logger.error("Tool %s error: %s", name, e)
        return {"error": str(e)}
    return result


_PLACEHOLDER_PATTERNS = re.compile(
    r"\bone moment\b|\blet me check\b|\blet me look\b|\bli'll check\b|"
    r"\bplease wait\b|\bfetching\b|\blooking up\b|\bchecking\b|\bstandby\b",
    re.IGNORECASE
)


def run_agent(messages, patient_id, max_iter=12):
    """
    Agentic loop: LLM → tool_calls → execute → results → LLM (repeat).
    Returns final text response.
    """
    msgs = list(messages)
    last_text = ""
    tool_called_this_run = False
    scroll_retries = 0  # tracks automatic scroll attempts after not-found errors
    MAX_SCROLL_RETRIES = 4

    def _inject_screenshot(msg_list):
        try:
            state = _call_bridge("/api/browser/state", method="GET", timeout=5)
            if isinstance(state, dict) and state.get("image"):
                content = [
                    {"type": "text", "text": "Screenshot of current HealthHub screen:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{state['image']}"}}
                ]
                # If Singpass login is detected, append explicit context
                if state.get("on_singpass_page"):
                    content.append({"type": "text", "text": "[SYSTEM: The browser is currently showing a Singpass login page with a QR code. Guide the user to open their Singpass app and scan the QR code on screen. Wait for them to complete login before proceeding.]"})
                msg_list.append({"role": "user", "content": content})
        except Exception:
            pass

    _inject_screenshot(msgs)

    global _GLOBAL_STOP_FLAG
    _GLOBAL_STOP_FLAG = False

    for iteration in range(max_iter):
        if _GLOBAL_STOP_FLAG:
            return "Execution stopped by user."
        resp = call_llm_with_tools(msgs, AGENT_TOOLS, max_tokens=600)
        if resp is None:
            return last_text or "[AI service unavailable. Please check your API key.]"

        choice = resp.choices[0]
        msg = choice.message

        # Primary path: native tool_calls
        if msg.tool_calls:
            tool_called_this_run = True
            msgs.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                result = dispatch_tool(tc.function.name, tc.function.arguments, patient_id)
                result_str = json.dumps(result, ensure_ascii=False)
                msgs.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })
                # ── Strategic Tool Chaining: auto-scroll on not-found errors ──
                _err = result.get("error", "") if isinstance(result, dict) else ""
                _not_found = _err and any(x in _err.lower() for x in [
                    "not found", "could not find", "no element", "no match",
                    "timed out", "unable to find",
                ])
                if _not_found and scroll_retries < MAX_SCROLL_RETRIES:
                    scroll_retries += 1
                    # Auto-perform a scroll so the next iteration has fresh content
                    _call_bridge("/api/browser/action",
                                 {"action": "scroll", "distance": 600}, timeout=10)
                    msgs.append({"role": "user",
                                 "content": (
                                     f"[SYSTEM – Auto-scroll #{scroll_retries}/{MAX_SCROLL_RETRIES}] "
                                     "The element was not found. I have scrolled the page down "
                                     "to reveal more content. Call read_page again to get "
                                     "the updated list of visible elements before attempting "
                                     "to click. Do NOT ask the user to do anything yet."
                                 )})
            _inject_screenshot(msgs)
            continue

        text = msg.content or ""
        last_text = text

        # Fallback path: parse <tool_call> from content
        parsed = _extract_json_tool_call(text)
        if parsed:
            tool_called_this_run = True
            tool_name = parsed.get("tool") or parsed.get("name") or parsed.get("function", "")
            tool_args = parsed.get("params") or parsed.get("arguments") or parsed.get("args") or {}
            result = dispatch_tool(tool_name, tool_args, patient_id)
            result_str = json.dumps(result, ensure_ascii=False)
            clean_text = re.sub(r"<tool_call>.*?</tool_call>", "", text, flags=re.DOTALL).strip()
            if clean_text:
                msgs.append({"role": "assistant", "content": clean_text})
            msgs.append({"role": "user", "content": f"Tool result for {tool_name}: {result_str}"})
            _inject_screenshot(msgs)
            continue

        # Detect placeholder responses: model said "one moment / let me check" but called no tool
        if not tool_called_this_run and _PLACEHOLDER_PATTERNS.search(text):
            msgs.append({"role": "assistant", "content": text})
            msgs.append({"role": "user", "content":
                "Please call the appropriate tool now to get the actual information."})
            continue

        # No tool calls — return final response
        return text

    return last_text


# ---------------------------------------------------------------------------
# Agent System Prompt
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT_TEMPLATE = """You are Aria, a proactive AI health assistant at MedBridge, Singapore.
You have a live view of the patient's HealthHub browser panel — you control it.
Today is {today}. Patient: {patient_name}. Respond entirely in {language}.

CRITICAL RULES:
- Call tools IMMEDIATELY. Never say "Give me a moment" without calling a tool first.
- Do NOT expose JSON, technical errors, or internal details to the user.
- OBSERVATION LAYER: After EVERY click_text or click, immediately call `interact_with_screen(action="read_page")` to observe the updated screen before deciding the next action or speaking to the user.

== GOLDEN RULE: TRY BEFORE YOU ASK ==
Never tell the user "I can't find X" unless ALL four checks are done:
1. SCROLL DOWN: `interact_with_screen(action="scroll", direction="down", distance=600)` then `read_page`. Repeat up to 4 times.
2. SCROLL UP: If you previously saw the target and may have scrolled past it, use `direction="up", distance=400` to scroll back.
3. SUB-MENUS: Click any "See More", "Show All", "Filter", or tab that is visible.
4. VERIFY URL: Confirm via `read_page` you are on the correct page (e.g. /appointments). If not, navigate first.
5. CONFIRM NEGATIVE: Only give up when "No records found" or "No results" text is visible on screen.
Implicit Actions: go all the way to the final record (e.g. for vaccination records: navigate → scroll → click "View Details" → read and report). Never stop at a list.

== VIEWPORT-AWARE SCROLLING ==
You must reason about the vertical position of elements before deciding scroll direction:
- If the target was visible in a PREVIOUS screenshot or was interacted with recently, it is likely ABOVE the current viewport. Use `direction="up"`.
- If the target has not been seen yet, use `direction="down"`.
- For the Screening / Symptom form: after selecting a symptom, the answer buttons ("Yes" / "No" / "Confirm") are typically JUST BELOW the symptom label. Analyze the full vertical context of the form section — scroll DOWN a short distance (150–300px) before assuming the button is missing.

== eServices NAVIGATION ==
You start on https://eservices.healthhub.sg/.
- Do NOT wait. Call `read_page` then immediately `click_text` the relevant service tile ("Appointments", "Immunisation", "Medication", "Health Records").
- After tile click, observe the screen (call `read_page`) and handle the Singpass flow if required.

== BOOKING AN APPOINTMENT — STRICT 8-STEP EXECUTION ==

--- PHASE 1: ENTRY & DISCOVERY ---

Step 1 — Navigate:
  Call `view_healthhub(page="appointments")`. Do NOT ask the user for any details yet.
  Call `read_page` to observe the screen.

Step 2 — Hospital Search:
  Locate the hospital the user specified on the page.
  If NOT visible: call `interact_with_screen(action="scroll", direction="down", distance=600)` then `read_page`.
  Repeat scrolling until the hospital appears or you have scrolled 4 times with no result.
  If you scrolled past it (hospital was visible earlier), use `direction="up", distance=400`.
  NEVER ask the user to find the hospital themselves.

Step 3 — Polyclinic Trigger (if user wants a polyclinic):
  Find and click the 'Book polyclinic appointment' button using `click_text`.
  Immediately call `read_page` to observe the polyclinic landing page.

--- PHASE 2: CONFIGURATION ---

Step 4 — Landing Page Identification:
  Call `read_page` to identify the 'doctor consult' and 'location' fields on the polyclinic page.

Step 5 — Reason Discovery (Observation mandatory):
  Click the 'doctor consult' field using `click_text`.
  IMMEDIATELY call `read_page` after clicking. Parse every option that appeared in the dropdown.
  List these options to the user and ask: "Which of these is the reason for your visit?"
  Do not guess or invent options — only list what `read_page` returned.

Step 6 — Location Selection (Observation mandatory):
  After reason is set, click the 'location' field using `click_text`.
  IMMEDIATELY call `read_page`. Parse all polyclinics shown.
  If the user already mentioned a polyclinic (e.g. "Clementi Polyclinic"), select it automatically using `click_text`.
  If not mentioned: list the visible options and ask the user.
  Dropdown Exhaustion: if the polyclinic is not in the first view, scroll the dropdown using
    `interact_with_screen(action="scroll", distance=400)` then `read_page`. Repeat up to 5 times.

--- PHASE 3: FINALIZATION ---

Step 7 — Date Selection:
  Find and click the 'Continue' button using `click_text`.
  Call `read_page` to observe the next screen.
  Locate the datepicker. Set it to the user's requested date using `click_text` on the date.

Step 8 — Relentless Time Search:
  Scan the visible timeslots using `read_page`.
  If the requested time is not visible: click 'load more time slots' (or equivalent) using `click_text`.
  After each click, call `read_page` and check if the timeslot appeared.
  Repeat until the slot is found OR the 'load more' button disappears from the page.
  If still not found after exhaustion, tell the user which time slots ARE available.

Step 9 — Verbal Confirmation:
  BEFORE submitting, call `read_page` to verify the summary shown on screen.
  Summarize the booking to the user (hospital, reason, location, date, time) and ask:
  "Shall I confirm this booking?"
  Only proceed to click the final Confirm/Submit button after explicit user approval.

== SMART NO-BUTTON SEARCH (Screening / Symptom Forms) ==
When filling out a symptom screening form (e.g. polyclinic pre-consultation questions):
1. VISUAL ANCHOR: After the symptom question text is visible, treat it as an anchor. The answer buttons ("Yes", "No", "Confirm") are always directly adjacent — below or to the right of that text.
2. Try `click_text(text="No")` or `click_text(text="Confirm")` immediately after observing the symptom text via `read_page`.
3. If not found: micro-scroll DOWN 200px (`action="scroll", direction="down", distance=200`) and try again.
4. If still not found: micro-scroll UP 200px (`action="scroll", direction="up", distance=200`) to check if it is above the current viewport.
5. Only after both 200px passes fail: scroll 600px down and re-read.
6. Never ask the user to click "No" themselves — exhaust all bidirectional micro-scrolls first.

== SINGPASS LOGIN ==
If you see a "Login via Singpass", "Log in", "Sign in", or "Continue with Singpass" button:
- `click_text` it to initiate. Do NOT type credentials.
- When the QR code appears, tell the patient:
  "I can see we need to log in with Singpass. Please open your Singpass app and scan the QR code on the screen. Let me know once you're done!"
- Wait for confirmation before continuing.

== OTHER ACTIONS ==
- Appointments / medications / records: use `view_healthhub(page=...)` then `read_page` to narrate.
- Add family members: `add_family_member`.
- Full overview: `get_health_summary`."""


def _build_agent_system_prompt(language, patient_name):
    today = datetime.now().strftime("%Y-%m-%d")
    return AGENT_SYSTEM_PROMPT_TEMPLATE.format(
        language=language, today=today, patient_name=patient_name
    )


# ---------------------------------------------------------------------------
# API Routes — Languages
# ---------------------------------------------------------------------------

@app.route("/api/languages", methods=["GET"])
def get_languages():
    return jsonify(SUPPORTED_LANGUAGES)


@app.route("/api/language/detect", methods=["POST"])
def detect_language():
    """
    Detect dominant language/dialect from first utterance.
    """
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    h_lang, h_dialect, h_conf, h_reason = _detect_language_heuristic(text)
    detected = {
        "language": h_lang,
        "dialect": h_dialect,
        "confidence": h_conf,
        "reason": h_reason,
        "is_mixed": False,
        "engine": "heuristic",
    }

    llm_detected = _detect_language_with_llm(text)
    if llm_detected and llm_detected.get("confidence", 0) >= max(0.60, h_conf - 0.05):
        detected = {
            **llm_detected,
            "engine": "llm",
        }

    language = detected["language"]
    language_code = SUPPORTED_LANGUAGES.get(language, {}).get("code", "en")
    return jsonify({
        "language": language,
        "dialect": detected.get("dialect", ""),
        "language_code": language_code,
        "confidence": detected.get("confidence", 0.0),
        "is_mixed": bool(detected.get("is_mixed", False)),
        "reason": detected.get("reason", ""),
        "engine": detected.get("engine", "heuristic"),
    })


@app.route("/api/voice/health", methods=["GET"])
def voice_health():
    """Quick check: can we reach MERaLiON STT?"""
    reachable = meralion_reachable()
    return jsonify({"meralion_available": reachable})


def _normalize_tts_language(language_code):
    """
    Normalize requested language code to Google TTS-supported variants.
    """
    code = (language_code or "en-SG").strip()
    overrides = {
        "zh-SG": "cmn-CN",
        "zh-cantonese": "yue-HK",
        "yue-SG": "yue-HK",
        "nan": "cmn-CN",      # No native Hokkien voice in Google TTS
        "nan-SG": "cmn-CN",   # fallback to Mandarin
        "nan-TW": "cmn-CN",   # fallback to Mandarin
    }
    return overrides.get(code, code)


@app.route("/api/tts", methods=["POST"])
def text_to_speech():
    """
<<<<<<< HEAD
    Synthesize speech using Google Cloud Text-to-Speech.
    Supports two auth methods (checked in order):
      1. GOOGLE_TTS_API_KEY in .env  → uses REST API (no gcloud login needed)
      2. ADC via gcloud auth application-default login → uses Python client library
=======
    Synthesize speech using OpenAI TTS if OPENAI_API_KEY is present (much more realistic),
    otherwise fallback to Google Cloud Text-to-Speech.
>>>>>>> d958c9bc (agent needs alot of promting to work)
    """
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        try:
            client = OpenAI(api_key=openai_key)
            # Use 'nova' or 'alloy' for incredibly realistic conversational voice
            response = client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=text
            )
            return Response(
                response.content,
                mimetype="audio/mpeg",
                headers={"Cache-Control": "no-store"},
            )
        except Exception as e:
            app.logger.warning("OpenAI TTS failed, falling back to Google: %s", e)

    # Fallback: Google Cloud TTS
    if texttospeech is None:
        return jsonify({"error": "google-cloud-texttospeech package is not installed."}), 500

    language_code = _normalize_tts_language(data.get("language_code", "en-SG"))
    # Use higher quality voices if standard is requested
    voice_name = (data.get("voice_name") or "").strip() or None
    if not voice_name and language_code == "en-SG":
        voice_name = "en-SG-Neural2-A"
    
    speaking_rate = data.get("speaking_rate", 0.92)
    pitch = data.get("pitch", 0.0)

    try:
        speaking_rate = float(speaking_rate)
        pitch = float(pitch)
    except (TypeError, ValueError):
        return jsonify({"error": "speaking_rate and pitch must be numbers"}), 400

<<<<<<< HEAD
    speaking_rate = max(0.25, min(4.0, speaking_rate))
    pitch = max(-20.0, min(20.0, pitch))

    api_key = os.getenv("GOOGLE_TTS_API_KEY", "").strip()
=======
    try:
        client = texttospeech.TextToSpeechClient()
        voice_kwargs = {"language_code": language_code}
        if voice_name:
            voice_kwargs["name"] = voice_name
>>>>>>> d958c9bc (agent needs alot of promting to work)

    if api_key:
        # --- Method 1: REST API with API Key (no gcloud login needed) ---
        try:
            voice_payload = {
                "languageCode": language_code,
                "ssmlGender": "FEMALE",
            }
            if voice_name:
                voice_payload["name"] = voice_name

<<<<<<< HEAD
            payload = {
                "input": {"text": text},
                "voice": voice_payload,
                "audioConfig": {
                    "audioEncoding": "MP3",
                    "speakingRate": speaking_rate,
                    "pitch": pitch,
                },
            }
            resp = http_requests.post(
                f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}",
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            audio_content = base64.b64decode(resp.json()["audioContent"])
            return Response(
                audio_content,
                mimetype="audio/mpeg",
                headers={"Cache-Control": "no-store"},
            )
        except Exception as e:
            app.logger.error("Google TTS (API key) error: %s", e)
            return jsonify({"error": f"Google TTS failed: {str(e)[:250]}"}), 502

    else:
        # --- Method 2: ADC via gcloud auth application-default login ---
        if texttospeech is None:
            return jsonify({"error": "Set GOOGLE_TTS_API_KEY in .env or install google-cloud-texttospeech and run gcloud auth application-default login."}), 500
        try:
            client = texttospeech.TextToSpeechClient()
            voice_kwargs = {
                "language_code": language_code,
                "ssml_gender": texttospeech.SsmlVoiceGender.FEMALE,
            }
            if voice_name:
                voice_kwargs["name"] = voice_name

            response = client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=text),
                voice=texttospeech.VoiceSelectionParams(**voice_kwargs),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3,
                    speaking_rate=speaking_rate,
                    pitch=pitch,
                ),
            )
            return Response(
                response.audio_content,
                mimetype="audio/mpeg",
                headers={"Cache-Control": "no-store"},
            )
        except Exception as e:
            app.logger.error("Google TTS (ADC) error: %s", e)
            return jsonify({"error": f"Google TTS failed: {str(e)[:250]}"}), 502
=======
        return Response(
            response.audio_content,
            mimetype="audio/mpeg",
            headers={"Cache-Control": "no-store"},
        )
    except Exception as e:
        app.logger.error("Google TTS error: %s", e)
        
        # Ultimate Fallback: gTTS
        try:
            from gtts import gTTS
            import io
            app.logger.info("Using gTTS fallback.")
            tts_res = gTTS(text=text, lang="en", tld="sg")
            fp = io.BytesIO()
            tts_res.write_to_fp(fp)
            return Response(
                fp.getvalue(),
                mimetype="audio/mpeg",
                headers={"Cache-Control": "no-store"}
            )
        except Exception as gtts_e:
            app.logger.error("gTTS fallback failed: %s", gtts_e)
            return jsonify({"error": f"TTS completely failed: {str(e)[:250]}"}), 502
>>>>>>> d958c9bc (agent needs alot of promting to work)


@app.route("/api/voice", methods=["POST"])
def voice_to_text():
    """
    Transcribe uploaded audio via MERaLiON STT.

    Expects multipart/form-data:
      - audio: uploaded file
      - language (optional): language hint
    """
    audio_file = request.files.get("audio")
    if not audio_file:
        return jsonify({"error": "Missing audio file. Use multipart/form-data with field 'audio'."}), 400

    audio_bytes = audio_file.read()
    if not audio_bytes:
        return jsonify({"error": "Uploaded audio file is empty."}), 400

    filename = (audio_file.filename or "voice.wav").strip() or "voice.wav"
    content_type = audio_file.mimetype or "audio/wav"
    language = (request.form.get("language", "") or "").strip() or None

    try:
        result = transcribe_audio_bytes(
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=content_type,
            language=language,
        )
    except MeralionError as e:
        message = str(e)
        app.logger.error("MERaLiON STT error: %s", message)
        status = 503 if "not configured" in message.lower() else 502
        return jsonify({"error": message}), status
    except Exception as e:
        app.logger.error("Unexpected MERaLiON STT error: %s", e)
        return jsonify({"error": "Voice transcription failed unexpectedly."}), 500

    transcript = (
        (result.get("text") if isinstance(result, dict) else None)
        or (result.get("transcript") if isinstance(result, dict) else None)
        or ""
    ).strip()
    if not transcript:
        return jsonify({"error": "MERaLiON returned no transcript.", "result": result}), 502

    return jsonify({"text": transcript, "result": result})


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
        "广东话 (Cantonese)": f"你好 {name}！歡迎。我喺度幫你{'睇醫生之前登記' if pre else '睇完醫生之後跟進'}。你今日覺得點樣？",
        "Hindi (हिन्दी)": f"नमस्ते {name}! स्वागत है। मैं आपकी {'जाँच-पूर्व पंजीकरण' if pre else 'परामर्श के बाद अनुवर्ती'} में मदद के लिए यहाँ हूँ। आज आप कैसा महसूस कर रहे हैं?",
        "Vietnamese (Tiếng Việt)": f"Xin chào {name}! Chào mừng bạn. Tôi ở đây để giúp bạn với {'đăng ký trước khám' if pre else 'theo dõi sau khám'}. Hôm nay bạn cảm thấy thế nào?",
        "Thai (ภาษาไทย)": f"สวัสดีค่ะ/ครับ {name}! ยินดีต้อนรับ ฉันอยู่ที่นี่เพื่อช่วยคุณ{'ลงทะเบียนก่อนพบแพทย์' if pre else 'ติดตามผลหลังพบแพทย์'} วันนี้คุณรู้สึกอย่างไรบ้าง?",
        "Tagalog (Filipino)": f"Kumusta {name}! Maligayang pagdating. Nandito ako para tulungan ka sa iyong {'pre-consultation check-in' if pre else 'post-consultation follow-up'}. Kamusta ang pakiramdam mo ngayon?",
    }
    return greetings.get(language, greetings["English"])


# ---------------------------------------------------------------------------
# API Routes — Agent
# ---------------------------------------------------------------------------

_GLOBAL_STOP_FLAG = False

@app.route("/api/agent/stop", methods=["POST"])
def agent_stop():
    global _GLOBAL_STOP_FLAG
    _GLOBAL_STOP_FLAG = True
    return jsonify({"status": "stopping_agent"})

@app.route("/api/agent/start", methods=["POST"])
def agent_start():
    data = request.json or {}
    patient_id = data.get("patient_id")
    language = data.get("language", "English")
    patient_name = data.get("patient_name", "")

    if not patient_id:
        return jsonify({"error": "patient_id required"}), 400

    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    agent_session = AgentSession(patient_id=patient_id, language_used=language)
    db.session.add(agent_session)
    db.session.flush()

    system_prompt = _build_agent_system_prompt(language, patient.name)
    messages = [{"role": "system", "content": system_prompt}]

    # Generate greeting
    try:
        resp = call_llm_with_tools(messages, max_tokens=150, temperature=0.8)
        if resp:
            greeting = resp.choices[0].message.content or ""
        else:
            greeting = f"Hello {patient.name}! I'm Aria, your health assistant. How can I help you today?"
    except Exception:
        greeting = f"Hello {patient.name}! I'm Aria, your health assistant. How can I help you today?"

    # Save greeting message
    greeting_msg = AgentMessage(session_id=agent_session.id, role="assistant", content=greeting)
    db.session.add(greeting_msg)
    db.session.commit()

    # Auto-navigate HealthHub to home page (non-blocking)
    import threading
    def _open_hh():
        try:
            _call_bridge("/api/navigate", {"page": "home"})
        except Exception:
            pass
    threading.Thread(target=_open_hh, daemon=True).start()

    return jsonify({"session_id": agent_session.id, "greeting": greeting}), 201


@app.route("/api/agent/sessions/<session_id>/message", methods=["POST"])
def agent_message(session_id):
    agent_session = AgentSession.query.get_or_404(session_id)
    data = request.json or {}
    user_text = data.get("message", "").strip()
    if not user_text:
        return jsonify({"error": "message required"}), 400

    patient = Patient.query.get(agent_session.patient_id)
    patient_name = patient.name if patient else ""

    # Save user message
    user_msg = AgentMessage(session_id=session_id, role="user", content=user_text)
    db.session.add(user_msg)

    # Rebuild conversation for agent
    system_prompt = _build_agent_system_prompt(
        agent_session.language_used or "English", patient_name)
    messages = [{"role": "system", "content": system_prompt}]

    history = AgentMessage.query.filter_by(session_id=session_id).order_by(
        AgentMessage.created_at).all()
    for m in history:
        if m.role in ("user", "assistant"):
            messages.append({"role": m.role, "content": m.content or ""})

    messages.append({"role": "user", "content": user_text})

    # Run agentic loop
    try:
        reply = run_agent(messages, agent_session.patient_id)
    except Exception as e:
        app.logger.error("Agent error: %s", e)
        reply = "[Service temporarily unavailable. Please try again.]"

    # Save assistant reply
    asst_msg = AgentMessage(session_id=session_id, role="assistant", content=reply)
    db.session.add(asst_msg)
    db.session.commit()

    return jsonify({"reply": reply})


@app.route("/api/agent/sessions/<session_id>", methods=["GET"])
def agent_get_session(session_id):
    agent_session = AgentSession.query.get_or_404(session_id)
    messages = AgentMessage.query.filter_by(session_id=session_id).order_by(
        AgentMessage.created_at).all()
    return jsonify({
        "id": agent_session.id,
        "patient_id": agent_session.patient_id,
        "language_used": agent_session.language_used,
        "created_at": agent_session.created_at.isoformat() if agent_session.created_at else None,
        "messages": [{"role": m.role, "content": m.content or "",
                      "created_at": m.created_at.isoformat() if m.created_at else None}
                     for m in messages if m.role in ("user", "assistant")],
    })


# ---------------------------------------------------------------------------
# API Routes — Family Members
# ---------------------------------------------------------------------------

@app.route("/api/family", methods=["GET"])
def list_family():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id required"}), 400
    return jsonify(tool_get_family_members(patient_id))


@app.route("/api/family", methods=["POST"])
def create_family_member():
    data = request.json or {}
    patient_id = data.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id required"}), 400
    result = tool_add_family_member(patient_id, data.get("name", ""),
                                    data.get("relationship", ""),
                                    data.get("dob", ""), data.get("notes", ""))
    return jsonify(result), 201


# ---------------------------------------------------------------------------
# API Routes — Appointments
# ---------------------------------------------------------------------------

@app.route("/api/appointments", methods=["GET"])
def list_appointments():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id required"}), 400
    family_member_id = request.args.get("family_member_id")
    return jsonify(tool_get_appointments(patient_id, family_member_id))


# ---------------------------------------------------------------------------
# API Routes — Medications
# ---------------------------------------------------------------------------

@app.route("/api/medications", methods=["GET"])
def list_medications():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id required"}), 400
    family_member_id = request.args.get("family_member_id")
    active_only = request.args.get("active_only", "true").lower() != "false"
    return jsonify(tool_get_medications(patient_id, family_member_id, active_only))


# ---------------------------------------------------------------------------
# API Routes — Health Summary
# ---------------------------------------------------------------------------

@app.route("/api/health-summary", methods=["GET"])
def health_summary():
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id required"}), 400
    family_member_id = request.args.get("family_member_id")
    return jsonify(tool_get_health_summary(patient_id, family_member_id))


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
    # Migrate old appointment table if it has the wrong schema (from old booking system)
    try:
        cols = [row[1] for row in db.session.execute(
            db.text("PRAGMA table_info(appointment)")).fetchall()]
        if cols and "patient_id" not in cols:
            # Old booking-system schema — rename it out of the way and recreate
            db.session.execute(db.text("ALTER TABLE appointment RENAME TO old_booking_appointment"))
            db.session.commit()
    except Exception:
        db.session.rollback()

    db.create_all()

    # Add is_urgent to session if DB existed before (SQLite)
    try:
        db.session.execute(db.text("ALTER TABLE session ADD COLUMN is_urgent BOOLEAN DEFAULT 0"))
        db.session.commit()
    except Exception:
        db.session.rollback()
    # Ensure all new tables exist (idempotent via create_all above)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app.run(debug=True, port=port)
