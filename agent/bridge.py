"""
HTTP client for the HealthHub Playwright bridge (port 7001).
"""
import logging
import requests

logger = logging.getLogger(__name__)

BRIDGE_BASE = "http://localhost:7001"


def call_bridge(path: str, payload: dict = None, method: str = "POST", timeout: int = 45) -> dict:
    """Synchronous call to the Playwright bridge. Returns JSON dict or error dict."""
    try:
        url = f"{BRIDGE_BASE}{path}"
        if method == "POST":
            resp = requests.post(url, json=payload or {}, timeout=timeout)
        else:
            resp = requests.get(url, timeout=timeout)
        return resp.json()
    except Exception as e:
        logger.warning("Bridge call %s failed: %s", path, e)
        return {"error": f"HealthHub browser not reachable: {e}"}
