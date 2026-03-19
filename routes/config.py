import os
import logging

from flask import Blueprint, jsonify, request
from openai import OpenAI, AuthenticationError

from llm.provider import resolve_provider

logger = logging.getLogger(__name__)
bp = Blueprint("config", __name__)


def _update_env_file(path: str, var_name: str, var_value: str):
    lines, found = [], False
    if os.path.exists(path):
        with open(path) as f:
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


@bp.get("/api/config/status")
def config_status():
    provider = resolve_provider()
    if not provider:
        return jsonify({"api_key_set": False, "api_key_valid": False, "api_key_preview": "", "model": ""})

    key = provider["api_key"]
    api_key_valid = True
    try:
        kwargs = {"api_key": key}
        if provider.get("base_url"):
            kwargs["base_url"] = provider["base_url"]
        OpenAI(**kwargs).models.list()
    except AuthenticationError:
        api_key_valid = False
    except Exception:
        pass  # transient error — assume valid

    return jsonify({
        "api_key_set": True,
        "api_key_valid": api_key_valid,
        "api_key_preview": f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "",
        "model": provider["model"],
        "provider": provider["name"],
    })


@bp.post("/api/config/apikey")
def set_api_key():
    data = request.json
    key = data.get("api_key", "").strip()
    provider_hint = data.get("provider", "").lower()
    if not key:
        return jsonify({"error": "API key cannot be empty"}), 400

    if key.startswith("gsk_") or provider_hint == "groq":
        env_var, base_url = "GROQ_API_KEY", "https://api.groq.com/openai/v1"
    elif key.startswith("sl-") or provider_hint == "sealion":
        env_var, base_url = "SEALION_API_KEY", "https://api.sea-lion.ai/v1"
    elif provider_hint == "openrouter":
        env_var, base_url = "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1"
    else:
        env_var, base_url = "OPENAI_API_KEY", None

    try:
        kwargs = {"api_key": key}
        if base_url:
            kwargs["base_url"] = base_url
        OpenAI(**kwargs).models.list()
    except Exception as e:
        return jsonify({"error": f"Invalid API key: {str(e)[:200]}"}), 400

    os.environ[env_var] = key
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    _update_env_file(env_path, env_var, key)

    # Reset LLM client so next call picks up the new key
    import llm.client as _lc
    _lc._llm_client = None

    return jsonify({"success": True, "api_key_preview": f"{key[:8]}...{key[-4:]}"})
