"""
LLM provider resolution — determines which API to use based on available keys.

Priority: OpenRouter (vision) → Groq (function calling) → SEA-LION → OpenAI
"""
import os


def resolve_provider() -> dict | None:
    """Return provider config dict or None if no keys are configured."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    groq_key = os.getenv("GROQ_API_KEY", "")
    sealion_key = os.getenv("SEALION_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")

    if openrouter_key:
        return {
            "name": "OpenRouter",
            "api_key": openrouter_key,
            "base_url": "https://openrouter.ai/api/v1",
            "model": os.getenv("LLM_MODEL", "openai/gpt-4o"),
            "vision": True,
        }
    # Groq before SEA-LION: llama-3.3-70b supports native function calling.
    # SEA-LION does not support native tool_calls and is kept as last resort.
    if groq_key:
        return {
            "name": "Groq",
            "api_key": groq_key,
            "base_url": "https://api.groq.com/openai/v1",
            "model": "llama-3.3-70b-versatile",
            "vision": False,
        }
    if sealion_key:
        return {
            "name": "SEA-LION",
            "api_key": sealion_key,
            "base_url": "https://api.sea-lion.ai/v1",
            "model": "aisingapore/Qwen-SEA-LION-v4-32B-IT",
            "vision": False,
        }
    if openai_key:
        raw_model = os.getenv("LLM_MODEL", "gpt-4o")
        model = raw_model.split("/", 1)[-1] if "/" in raw_model else raw_model
        return {
            "name": "OpenAI",
            "api_key": openai_key,
            "base_url": None,
            "model": model,
            "vision": True,
        }
    return None


def strip_images(messages: list) -> list:
    """Remove image_url parts from messages for models that don't support vision."""
    clean = []
    for m in messages:
        if isinstance(m.get("content"), list):
            text_parts = [p["text"] for p in m["content"] if p.get("type") == "text"]
            clean.append({**m, "content": "\n".join(text_parts)})
        else:
            clean.append(m)
    return clean


# Env-var names for each provider (used during quota-exceeded fallback)
PROVIDER_ENV_KEYS = {
    "OpenRouter": "OPENROUTER_API_KEY",
    "Groq":       "GROQ_API_KEY",
    "SEA-LION":   "SEALION_API_KEY",
    "OpenAI":     "OPENAI_API_KEY",
}
