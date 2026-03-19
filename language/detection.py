"""
Language detection — heuristic (fast) + LLM-assisted (accurate).
"""
import re
import json
import logging

from language.config import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)


def _heuristic(text: str) -> dict:
    """Fast script + lexical-marker detection. Returns detection dict."""
    raw = (text or "").strip()
    lower = raw.lower()

    if not raw:
        return _result("English", "Standard Singapore English", 0.35, "empty input fallback")

    # Script-based detection
    script_map = [
        (r"[\u0B80-\u0BFF]", "Tamil (தமிழ்)",       "Singapore Tamil (சிங்கப்பூர் தமிழ்)", 0.95, "Tamil script"),
        (r"[\u0900-\u097F]", "Hindi (हिन्दी)",        "Colloquial Hindi",                     0.90, "Devanagari script"),
        (r"[\u1000-\u109F]", "Burmese (မြန်မာဘာသာ)", "Colloquial Burmese",                   0.90, "Burmese script"),
        (r"[\u0980-\u09FF]", "Bengali (বাংলা)",        "Standard Bengali",                     0.90, "Bengali script"),
        (r"[\u1780-\u17FF]", "Khmer (ភាសាខ្មែរ)",      "Standard Khmer",                       0.90, "Khmer script"),
        (r"[\u0E00-\u0E7F]", "Thai (ภาษาไทย)",         "Informal Thai",                        0.90, "Thai script"),
    ]
    for pattern, lang, dialect, conf, reason in script_map:
        if re.search(pattern, raw):
            return _result(lang, dialect, conf, reason)

    # Chinese — Cantonese vs Mandarin
    if re.search(r"[\u4E00-\u9FFF]", raw):
        if any(m in raw for m in ("佢", "冇", "咩", "嘅", "喺", "哋", "咗")):
            return _result("广东话 (Cantonese)", "新加坡广东话 (Singapore Cantonese)", 0.86, "Chinese + Cantonese markers")
        return _result("华语 (Mandarin)", "新加坡华语 (Singapore Mandarin)", 0.82, "Chinese script")

    # Latin-script lexical hints
    malay_markers   = ("saya", "awak", "anda", "tak", "tidak", "sakit", "kepala",
                       "perut", "demam", "batuk", "doktor", "klinik", "lah")
    singlish_markers = ("lah", "leh", "lor", "meh", "sia", "sian", "can or not",
                        "alamak", "auntie", "uncle", "shiok")
    hokkien_markers  = ("aiya", "bo pian", "paiseh", "kancheong")

    malay_score    = sum(1 for m in malay_markers   if m in lower)
    singlish_score = sum(1 for m in singlish_markers if m in lower)
    hokkien_score  = sum(1 for m in hokkien_markers  if m in lower)

    if hokkien_score >= 2:
        return _result("福建话 (Hokkien)", "Singapore Hokkien", 0.66, "Hokkien markers")
    if malay_score >= 2 and malay_score >= singlish_score:
        return _result("Malay (Bahasa Melayu)", "Informal / Colloquial Malay", 0.78, "Malay markers")
    if singlish_score >= 1:
        return _result("English", "Singlish", 0.74, "Singlish markers")

    return _result("English", "Standard Singapore English", 0.52, "default fallback")


def _llm_detect(text: str) -> dict | None:
    """LLM-assisted detection for mixed-code utterances."""
    from llm.client import call_llm  # local import to avoid circular dependency at module load

    prompt = (
        "Detect the dominant spoken language and dialect for this Singapore healthcare utterance. "
        "Pick ONLY from these language keys and dialect values:\n"
        f"{json.dumps(SUPPORTED_LANGUAGES, ensure_ascii=False)}\n\n"
        'Return JSON only:\n{"language":"...","dialect":"...","confidence":0.0,"is_mixed":true,"reason":"..."}\n'
        "If mixed language, pick the dominant language the assistant should respond in."
    )
    try:
        raw, _ = call_llm(
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text}],
            max_tokens=220,
            temperature=0.0,
        )
        if not raw:
            return None
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start < 0 or end <= start:
            return None
        parsed = json.loads(raw[start:end], strict=False)
        language = parsed.get("language")
        dialect  = parsed.get("dialect", "")
        if language not in SUPPORTED_LANGUAGES:
            return None
        if dialect and dialect not in SUPPORTED_LANGUAGES[language].get("dialects", []):
            dialect = SUPPORTED_LANGUAGES[language].get("dialects", [""])[0]
        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.0) or 0.0)))
        return _result(language, dialect, confidence, parsed.get("reason", "llm"),
                       is_mixed=bool(parsed.get("is_mixed", False)), engine="llm")
    except Exception:
        return None


def detect_language(text: str) -> dict:
    """
    Detect dominant language/dialect. Returns detection dict with keys:
    language, dialect, language_code, confidence, is_mixed, reason, engine.
    """
    h = _heuristic(text)
    llm = _llm_detect(text)

    detected = h
    if llm and llm.get("confidence", 0) >= max(0.60, h["confidence"] - 0.05):
        detected = llm

    language = detected["language"]
    language_code = SUPPORTED_LANGUAGES.get(language, {}).get("code", "en")
    return {**detected, "language_code": language_code}


def _result(language, dialect, confidence, reason, is_mixed=False, engine="heuristic") -> dict:
    return {
        "language":   language,
        "dialect":    dialect,
        "confidence": confidence,
        "reason":     reason,
        "is_mixed":   is_mixed,
        "engine":     engine,
    }
