import os
from typing import Optional

import requests
from requests import RequestException


DEFAULT_BASE_URLS = (
    "https://meralion.imda.gov.sg/api",
    "https://api.meralion.imda.gov.sg/api",
)


class MeralionError(Exception):
    """Raised when a MERaLiON API operation fails."""


def _base_urls() -> list[str]:
    env_url = os.getenv("MERALION_BASE_URL", "").strip()
    if env_url:
        return [env_url.rstrip("/")]
    return [u.rstrip("/") for u in DEFAULT_BASE_URLS]


def _headers() -> dict:
    api_key = os.getenv("MERALION_API_KEY", "").strip()
    if not api_key:
        raise MeralionError("MERALION_API_KEY is not configured.")
    return {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }


def _post_json_with_fallback(path: str, payload: dict, timeout: int) -> tuple[dict, str]:
    last_network_error = None
    for base_url in _base_urls():
        try:
            response = requests.post(
                f"{base_url}{path}",
                headers=_headers(),
                json=payload,
                timeout=timeout,
            )
        except RequestException as e:
            last_network_error = f"{base_url}{path} -> {e}"
            continue

        if response.status_code >= 400:
            raise MeralionError(
                f"MERaLiON API error at {base_url}{path} ({response.status_code}): "
                f"{response.text[:300]}"
            )
        try:
            return response.json(), base_url
        except ValueError:
            raise MeralionError(
                f"MERaLiON returned non-JSON response at {base_url}{path}: {response.text[:300]}"
            )

    raise MeralionError(
        "Unable to reach MERaLiON API host. "
        "Check internet/DNS/VPN and set MERALION_BASE_URL if your endpoint differs. "
        f"Last error: {last_network_error}"
    )


def get_upload_url(filename: str, filesize: int, content_type: str) -> tuple[dict, str]:
    payload = {
        "fileName": filename,
        "fileSize": filesize,
        "contentType": content_type,
    }
    data, base_url = _post_json_with_fallback("/upload-url", payload, timeout=30)
    if "uploadUrl" not in data or "fileKey" not in data:
        raise MeralionError("MERaLiON upload URL response missing uploadUrl/fileKey.")
    return data, base_url


def upload_audio(upload_url: str, audio_bytes: bytes, content_type: str = "audio/wav") -> None:
    try:
        response = requests.put(
            upload_url,
            data=audio_bytes,
            headers={"Content-Type": content_type},
            timeout=120,
        )
    except RequestException as e:
        raise MeralionError(f"Failed to upload audio to pre-signed URL: {e}") from e
    if response.status_code >= 400:
        raise MeralionError(
            f"Failed to upload audio ({response.status_code}): {response.text[:300]}"
        )


def transcribe(file_key: str, language: Optional[str] = None, base_url: Optional[str] = None) -> dict:
    payload = {"fileKey": file_key}
    if language:
        payload["language"] = language
    if base_url:
        try:
            response = requests.post(
                f"{base_url.rstrip('/')}/transcribe",
                headers=_headers(),
                json=payload,
                timeout=120,
            )
        except RequestException as e:
            raise MeralionError(f"Failed to call MERaLiON transcribe endpoint: {e}") from e
        if response.status_code >= 400:
            raise MeralionError(
                f"MERaLiON API error at {base_url.rstrip('/')}/transcribe "
                f"({response.status_code}): {response.text[:300]}"
            )
        try:
            return response.json()
        except ValueError:
            raise MeralionError(
                f"MERaLiON returned non-JSON transcribe response: {response.text[:300]}"
            )

    data, _ = _post_json_with_fallback("/transcribe", payload, timeout=120)
    return data


def check_reachable() -> bool:
    """Quick connectivity check — returns True if any MERaLiON host responds."""
    for base_url in _base_urls():
        try:
            r = requests.get(base_url, timeout=5)
            return True
        except RequestException:
            continue
    return False


def transcribe_audio_bytes(
    audio_bytes: bytes,
    filename: str = "voice.wav",
    content_type: str = "audio/wav",
    language: Optional[str] = None,
) -> dict:
    upload_data, base_url = get_upload_url(filename, len(audio_bytes), content_type)
    upload_audio(upload_data["uploadUrl"], audio_bytes, content_type=content_type)
    return transcribe(upload_data["fileKey"], language=language, base_url=base_url)
