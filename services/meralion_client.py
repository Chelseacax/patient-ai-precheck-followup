import os
from typing import Optional

import requests


BASE_URL = "https://meralion.imda.gov.sg/api"


class MeralionError(Exception):
    """Raised when a MERaLiON API operation fails."""


def _headers() -> dict:
    api_key = os.getenv("MERALION_API_KEY", "").strip()
    if not api_key:
        raise MeralionError("MERALION_API_KEY is not configured.")
    return {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }


def get_upload_url(filename: str, filesize: int, content_type: str) -> dict:
    payload = {
        "fileName": filename,
        "fileSize": filesize,
        "contentType": content_type,
    }
    response = requests.post(
        f"{BASE_URL}/upload-url",
        headers=_headers(),
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        raise MeralionError(
            f"Failed to get upload URL ({response.status_code}): {response.text[:300]}"
        )
    data = response.json()
    if "uploadUrl" not in data or "fileKey" not in data:
        raise MeralionError("MERaLiON upload URL response missing uploadUrl/fileKey.")
    return data


def upload_audio(upload_url: str, audio_bytes: bytes, content_type: str = "audio/wav") -> None:
    response = requests.put(
        upload_url,
        data=audio_bytes,
        headers={"Content-Type": content_type},
        timeout=120,
    )
    if response.status_code >= 400:
        raise MeralionError(
            f"Failed to upload audio ({response.status_code}): {response.text[:300]}"
        )


def transcribe(file_key: str, language: Optional[str] = None) -> dict:
    payload = {"fileKey": file_key}
    if language:
        payload["language"] = language
    response = requests.post(
        f"{BASE_URL}/transcribe",
        headers=_headers(),
        json=payload,
        timeout=120,
    )
    if response.status_code >= 400:
        raise MeralionError(
            f"Failed to transcribe audio ({response.status_code}): {response.text[:300]}"
        )
    return response.json()


def transcribe_audio_bytes(
    audio_bytes: bytes,
    filename: str = "voice.wav",
    content_type: str = "audio/wav",
    language: Optional[str] = None,
) -> dict:
    upload_data = get_upload_url(filename, len(audio_bytes), content_type)
    upload_audio(upload_data["uploadUrl"], audio_bytes, content_type=content_type)
    return transcribe(upload_data["fileKey"], language=language)
