"""
LLM client — unified call functions for all providers.
"""
import os
import logging

from openai import OpenAI, AuthenticationError

from llm.provider import resolve_provider, strip_images, PROVIDER_ENV_KEYS

logger = logging.getLogger(__name__)

_llm_client: OpenAI | None = None


def _get_client(provider: dict) -> OpenAI:
    global _llm_client
    kwargs = {"api_key": provider["api_key"]}
    if provider.get("base_url"):
        kwargs["base_url"] = provider["base_url"]
    if _llm_client is None or _llm_client.api_key != provider["api_key"]:
        _llm_client = OpenAI(**kwargs)
    return _llm_client


def _is_quota_error(err: str) -> bool:
    return (
        "429" in err or "402" in err or "quota" in err or
        "insufficient_quota" in err or "credit" in err or
        ("token" in err and "limit" in err)
    )


def _disable_provider(provider: dict):
    """Clear the provider's API key so the next call falls back."""
    env_key = PROVIDER_ENV_KEYS.get(provider["name"])
    if env_key:
        os.environ[env_key] = ""
        logger.warning("%s quota/credit exceeded — disabling and falling back.", provider["name"])


def call_llm(messages: list, max_tokens=500, temperature=0.7):
    """
    Simple LLM call (no tools). Returns (text, api_key_invalid).

    Returns:
      (str, False)   on success
      (None, True)   if the API key was rejected
      (None, False)  if no provider is configured
    """
    provider = resolve_provider()
    if not provider:
        return None, False

    if not provider.get("vision", True):
        messages = strip_images(messages)

    client = _get_client(provider)
    try:
        resp = client.chat.completions.create(
            model=provider["model"],
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content, False
    except AuthenticationError:
        return None, True
    except Exception as e:
        err = str(e).lower()
        if _is_quota_error(err):
            _disable_provider(provider)
            return call_llm(strip_images(messages), max_tokens, temperature)
        raise


def call_llm_with_tools(messages: list, tools=None, max_tokens=1200, temperature=0.7):
    """
    LLM call with optional function-calling tools. Returns full response object or None.
    """
    provider = resolve_provider()
    if not provider:
        return None

    if not provider.get("vision", True):
        messages = strip_images(messages)

    client = _get_client(provider)
    kwargs = dict(
        model=provider["model"],
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    try:
        return client.chat.completions.create(**kwargs)
    except Exception as e:
        err = str(e).lower()
        if _is_quota_error(err):
            _disable_provider(provider)
            return call_llm_with_tools(strip_images(messages), tools, max_tokens, temperature)
        logger.warning("call_llm_with_tools error: %s", e)
        return None
