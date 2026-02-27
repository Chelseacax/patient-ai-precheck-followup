"""
normalizer.py
-------------
Converts dialect-influenced / mixed-language voice input into standard English
so downstream intent classification can work reliably.

Uses MERaLion via the shared call_llm() function (lazy-imported to avoid
circular imports with app.py).
"""


def normalize(raw_text: str, language: str = "English", dialect: str = "") -> str:
    """
    Normalize dialect/mixed-language text to standard English.

    Parameters
    ----------
    raw_text : str
        Raw transcribed text (may contain Singlish, Malay-English mix,
        Chinese dialect phrases, etc.)
    language : str
        Patient's selected language (e.g. "English", "Malay (Bahasa Melayu)")
    dialect : str
        Patient's selected dialect variant (e.g. "Singlish", "Taglish")

    Returns
    -------
    str
        Standard English text with all appointment details preserved.
        Falls back to raw_text if the LLM call fails.
    """
    from app import call_llm  # lazy import — avoids circular import at module load

    if not raw_text or not raw_text.strip():
        return raw_text

    lang_label = language
    if dialect:
        lang_label = f"{language} ({dialect})"

    system_prompt = (
        "You are a dialect normalizer for a Singapore healthcare appointment system.\n"
        f"The patient is speaking {lang_label}.\n"
        "Convert the input to clear, standard English.\n"
        "Rules:\n"
        "- Preserve ALL appointment details exactly: doctor names, specialties, dates, times, symptoms.\n"
        "- Remove filler words (lah, leh, mah, wor, lor, kan, nah) but keep the meaning.\n"
        "- If the input mixes languages, translate everything to English.\n"
        "- Output ONLY the normalized English text — no explanations, no labels."
    )

    result, api_key_invalid = call_llm(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_text},
        ],
        max_tokens=200,
        temperature=0.1,
    )

    if result and result.strip():
        return result.strip()
    return raw_text  # fallback: return original if LLM fails
