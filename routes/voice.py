import base64
import logging

import requests as http_requests
from flask import Blueprint, jsonify, request, Response
from openai import OpenAI

from services.meralion_client import MeralionError, transcribe_audio_bytes, check_reachable as meralion_reachable

try:
    from google.cloud import texttospeech as _gc_tts
except Exception:
    _gc_tts = None

import os

logger = logging.getLogger(__name__)
bp = Blueprint("voice", __name__)

# Best female voice per language code
_TTS_VOICE_MAP = {
    "cmn-CN": "cmn-CN-Wavenet-D",
    "yue-HK": "yue-HK-Standard-A",
    "en-US":  "en-US-Neural2-F",
    "en-GB":  "en-GB-Neural2-A",
    "ms-MY":  "ms-MY-Wavenet-A",
    "ta-SG":  "ta-IN-Wavenet-A",
    "ta-IN":  "ta-IN-Wavenet-A",
    "hi-IN":  "hi-IN-Wavenet-A",
    "ko-KR":  "ko-KR-Neural2-A",
    "ja-JP":  "ja-JP-Neural2-B",
    "vi-VN":  "vi-VN-Neural2-A",
    "fr-FR":  "fr-FR-Neural2-A",
    "es-ES":  "es-ES-Neural2-A",
    "pt-BR":  "pt-BR-Neural2-A",
}

_LANG_CODE_OVERRIDES = {
    "zh-SG": "cmn-CN",
    "zh-CN": "cmn-CN",
    "zh-cantonese": "yue-HK",
    "yue-SG": "yue-HK",
}


def _normalize_lang_code(code: str) -> str:
    code = (code or "en-SG").strip()
    return _LANG_CODE_OVERRIDES.get(code, code)


@bp.get("/api/voice/health")
def voice_health():
    return jsonify({"meralion_available": meralion_reachable()})


@bp.post("/api/tts")
def text_to_speech():
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    # Try OpenAI TTS first
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        try:
            client = OpenAI(api_key=openai_key)
            response = client.audio.speech.create(model="tts-1", voice="nova", input=text)
            return Response(response.content, mimetype="audio/mpeg",
                            headers={"Cache-Control": "no-store"})
        except Exception as e:
            logger.warning("OpenAI TTS failed, falling back: %s", e)

    # Google Cloud TTS
    language_code = _normalize_lang_code(data.get("language_code", "en-SG"))
    voice_name = (data.get("voice_name") or "").strip() or _TTS_VOICE_MAP.get(language_code)
    speaking_rate = max(0.25, min(4.0, float(data.get("speaking_rate", 0.92) or 0.92)))
    pitch = max(-20.0, min(20.0, float(data.get("pitch", 0.0) or 0.0)))

    api_key = os.getenv("GOOGLE_TTS_API_KEY", "").strip()
    if api_key:
        try:
            voice_payload = {"languageCode": language_code, "ssmlGender": "FEMALE"}
            if voice_name:
                voice_payload["name"] = voice_name
            resp = http_requests.post(
                f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}",
                json={"input": {"text": text}, "voice": voice_payload,
                      "audioConfig": {"audioEncoding": "MP3",
                                      "speakingRate": speaking_rate, "pitch": pitch}},
                timeout=10,
            )
            resp.raise_for_status()
            audio_content = base64.b64decode(resp.json()["audioContent"])
            return Response(audio_content, mimetype="audio/mpeg",
                            headers={"Cache-Control": "no-store"})
        except Exception as e:
            logger.error("Google TTS (API key) error: %s", e)

    if _gc_tts is not None:
        try:
            client = _gc_tts.TextToSpeechClient()
            voice_kwargs = {"language_code": language_code,
                            "ssml_gender": _gc_tts.SsmlVoiceGender.FEMALE}
            if voice_name:
                voice_kwargs["name"] = voice_name
            response = client.synthesize_speech(
                input=_gc_tts.SynthesisInput(text=text),
                voice=_gc_tts.VoiceSelectionParams(**voice_kwargs),
                audio_config=_gc_tts.AudioConfig(
                    audio_encoding=_gc_tts.AudioEncoding.MP3,
                    speaking_rate=speaking_rate, pitch=pitch),
            )
            return Response(response.audio_content, mimetype="audio/mpeg",
                            headers={"Cache-Control": "no-store"})
        except Exception as e:
            logger.error("Google TTS (ADC) error: %s", e)

    # Ultimate fallback: gTTS
    try:
        import io
        from gtts import gTTS
        gtts_lang = language_code.split("-")[0] if "-" in language_code else language_code
        if gtts_lang not in gTTS.LANGUAGES:
            gtts_lang = "en"
        tts_res = gTTS(text=text, lang=gtts_lang, tld="sg")
        fp = io.BytesIO()
        tts_res.write_to_fp(fp)
        return Response(fp.getvalue(), mimetype="audio/mpeg", headers={"Cache-Control": "no-store"})
    except Exception as e:
        logger.error("gTTS fallback failed: %s", e)
        return jsonify({"error": "TTS completely failed."}), 502


@bp.post("/api/voice")
def voice_to_text():
    audio_file = request.files.get("audio")
    if not audio_file:
        return jsonify({"error": "Missing audio file."}), 400
    audio_bytes = audio_file.read()
    if not audio_bytes:
        return jsonify({"error": "Uploaded audio file is empty."}), 400

    filename = (audio_file.filename or "voice.wav").strip() or "voice.wav"
    content_type = audio_file.mimetype or "audio/wav"
    language = (request.form.get("language", "") or "").strip() or None

    try:
        result = transcribe_audio_bytes(audio_bytes=audio_bytes, filename=filename,
                                        content_type=content_type, language=language)
    except MeralionError as e:
        message = str(e)
        status = 503 if "not configured" in message.lower() else 502
        return jsonify({"error": message}), status
    except Exception as e:
        return jsonify({"error": "Voice transcription failed unexpectedly."}), 500

    transcript = (
        (result.get("text") if isinstance(result, dict) else None)
        or (result.get("transcript") if isinstance(result, dict) else None)
        or ""
    ).strip()
    if not transcript:
        return jsonify({"error": "MERaLiON returned no transcript.", "result": result}), 502
    return jsonify({"text": transcript, "result": result})
