from flask import Blueprint, jsonify, request
from language.config import SUPPORTED_LANGUAGES
from language.detection import detect_language

bp = Blueprint("languages", __name__)


@bp.get("/api/languages")
def get_languages():
    return jsonify(SUPPORTED_LANGUAGES)


@bp.post("/api/language/detect")
def detect_language_route():
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    result = detect_language(text)
    return jsonify(result)
