"""
dispatcher.py — Resilient Playwright bridge for the LIVE healthhub.sg site.

Key design principles:
- All selectors use ARIA roles or text-based matching (no brittle CSS classes)
- Singpass detection pauses the agent and prompts the user via the chat
- A modal-clearing pass runs before every major interaction
- Graceful UI-mismatch errors returned instead of Python exceptions
- Screenshots stream continuously via /api/browser/state
"""

import asyncio
import base64
import re
from typing import Optional

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

from actions import REGISTRY

# ── Production URLs ────────────────────────────────────────────────────────────
HEALTHHUB_BASE = "https://eservices.healthhub.sg"

# Real navigation targets on the live site
PAGE_URLS = {
    "home":         HEALTHHUB_BASE,
    "appointments": f"{HEALTHHUB_BASE}/appointments",
    "medications":  f"{HEALTHHUB_BASE}/medications",
    "lab-reports":  f"{HEALTHHUB_BASE}/health-records",
    "profile":      f"{HEALTHHUB_BASE}/profile",
    "dashboard":    f"{HEALTHHUB_BASE}/dashboard",
    "immunisation": f"{HEALTHHUB_BASE}/immunisation",
}

# Singpass login page signals
SINGPASS_URL_TOKENS  = ["singpass.gov.sg", "id.gov.sg", "api.myinfo.gov.sg"]
SINGPASS_TEXT_TOKENS = ["singpass", "scan qr", "qr code", "log in with singpass",
                        "login with singpass", "authenticate with singpass"]

# Modals / overlays that block interaction on live site
MODAL_DISMISS_TEXTS = [
    "Accept", "Agree", "I Agree", "OK", "Got it", "Close",
    "Continue", "Accept All", "I Accept", "Dismiss",
]


class Dispatcher:
    def __init__(self):
        self._playwright = None
        self._browser    = None
        self._context    = None
        self._page       = None
        self._lock       = asyncio.Lock()
        self._ready      = False
        self._action_count = 0

    # ── Properties ──────────────────────────────────────────────────────────────

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def action_count(self) -> int:
        return self._action_count

    async def current_url(self) -> str:
        return self._page.url if self._page else ""

    # ── Lifecycle ────────────────────────────────────────────────────────────────

    async def start_browser(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=False,
            args=["--window-size=1280,900", "--no-sandbox"],
            slow_mo=200,
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        self._page = await self._context.new_page()

        # Navigate to live HealthHub home
        await self._page.goto(HEALTHHUB_BASE)
        await self._safe_wait_for_load()
        self._ready = True

    async def stop_browser(self):
        self._ready = False
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _ensure_browser(self):
        if not self._ready:
            try:
                await self.stop_browser()
            except Exception:
                pass
            await self.start_browser()

    # ── Helpers ──────────────────────────────────────────────────────────────────

    async def _safe_wait_for_load(self, state="networkidle", timeout=15000):
        """Wait for page load, but don't crash on timeout."""
        try:
            await self._page.wait_for_load_state(state, timeout=timeout)
        except PWTimeout:
            pass
        await self._page.wait_for_timeout(500)

    async def _clear_modals(self):
        """
        Dismiss any Terms/Privacy/Cookie pop-ups that block interaction on live site.
        Tries each dismiss text silently.
        """
        for text in MODAL_DISMISS_TEXTS:
            try:
                btn = self._page.get_by_role("button", name=re.compile(text, re.IGNORECASE))
                if await btn.first.is_visible():
                    await btn.first.click(timeout=1500)
                    await self._page.wait_for_timeout(400)
            except Exception:
                pass

    async def _try_click(self, locator_fn, description: str, timeout=6000) -> dict:
        """
        Attempt a click. Returns {"success": True} or {"ui_mismatch": True, "description": ...}
        instead of raising an exception.
        """
        try:
            loc = locator_fn()
            await loc.first.wait_for(state="visible", timeout=timeout)
            await loc.first.click(timeout=timeout)
            return {"success": True}
        except Exception as e:
            return {
                "ui_mismatch": True,
                "description": description,
                "error": str(e)[:200],
            }

    def _normalize_time(self, value: str) -> str:
        value = value.strip()
        m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", value, re.IGNORECASE)
        if m:
            h = int(m.group(1))
            mins = m.group(2) or "00"
            period = (m.group(3) or "").upper()
            if not period:
                period = "PM" if h >= 12 else "AM"
                if h > 12:
                    h -= 12
            return f"{h}:{mins} {period}"
        return value

    def _fuzzy_match(self, user_input: str, options: list) -> str:
        inp = user_input.lower().strip()
        for opt in options:
            if inp in opt.lower() or opt.lower() in inp:
                return opt
        words = inp.split()
        for opt in options:
            if any(w in opt.lower() for w in words if len(w) > 2):
                return opt
        return options[0]

    # ── Screenshots ──────────────────────────────────────────────────────────────

    async def screenshot_b64(self) -> str:
        if not self._page:
            return ""
        try:
            data = await self._page.screenshot(type="jpeg", quality=75)
            return base64.b64encode(data).decode()
        except Exception:
            return ""

    # ── Singpass Detection ───────────────────────────────────────────────────────

    async def is_singpass_page(self) -> bool:
        """Return True if the current page is a Singpass QR login screen."""
        if not self._page:
            return False
        try:
            url = self._page.url.lower()
            if any(tok in url for tok in SINGPASS_URL_TOKENS):
                return True
            # Also scan page text content (handles embeds)
            content = (await self._page.content()).lower()
            hits = sum(1 for tok in SINGPASS_TEXT_TOKENS if tok in content)
            return hits >= 2  # Require 2 signals to avoid false positives
        except Exception:
            return False

    async def wait_for_post_singpass(self, timeout_ms: int = 180_000) -> bool:
        """
        Poll until the browser leaves the Singpass domain (user completed login).
        Returns True if login detected within timeout, False otherwise.
        """
        deadline = asyncio.get_event_loop().time() + timeout_ms / 1000
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(2)
            if not await self.is_singpass_page():
                # Back on HealthHub — give the page a moment to settle
                await self._safe_wait_for_load()
                return True
        return False

    async def get_page_state(self) -> dict:
        """Full state snapshot: screenshot + URL + Singpass flag."""
        url         = await self.current_url()
        on_singpass = await self.is_singpass_page()
        screenshot  = await self.screenshot_b64()
        return {
            "url":             url,
            "on_singpass_page": on_singpass,
            "image":           screenshot,
        }

    # ── Action Registry ──────────────────────────────────────────────────────────

    def validate(self, action_name: str, params: dict) -> Optional[str]:
        if action_name not in REGISTRY:
            return f"Unknown action '{action_name}'. Available: {list(REGISTRY.keys())}"
        schema = REGISTRY[action_name].PARAMS_SCHEMA
        for param_name, meta in schema.items():
            if meta.get("required") and param_name not in params:
                return f"Missing required parameter '{param_name}'"
        return None

    async def execute(self, action_name: str, params: dict) -> dict:
        async with self._lock:
            self._action_count += 1
            action = REGISTRY[action_name](self._page)
            return await action.execute(params)

    # ── Navigation ───────────────────────────────────────────────────────────────

    async def navigate_healthhub(self, page: str) -> dict:
        await self._ensure_browser()
        url = PAGE_URLS.get(page, HEALTHHUB_BASE)

        async with self._lock:
            await self._page.goto(url)
            await self._safe_wait_for_load()
            await self._clear_modals()
            on_singpass = await self.is_singpass_page()
            return {
                "navigated_to":    page,
                "url":             url,
                "on_singpass_page": on_singpass,
            }

    # ── Live-Site Booking ─────────────────────────────────────────────────────────

    async def book_on_healthhub(
        self,
        institution: str,
        specialty:   str,
        date:        str,    # "YYYY-MM-DD"
        time:        str,
        reason:      str,
    ) -> dict:
        """
        Navigate to the live HealthHub booking flow.
        Uses ARIA/text selectors exclusively.
        Returns a graceful ui_mismatch dict instead of raising on failures.
        The VLM agent in app.py handles interactive form steps via screenshots.
        """
        await self._ensure_browser()
        async with self._lock:
            self._action_count += 1

            # Dismiss any modals first
            await self._clear_modals()

            booking_url = f"{HEALTHHUB_BASE}/appointments/book"
            await self._page.goto(booking_url)
            await self._safe_wait_for_load()

            # If Singpass wall appears, return early — agent must wait for user
            if await self.is_singpass_page():
                return {
                    "on_singpass_page": True,
                    "paused": True,
                    "message": (
                        "Singpass login required. "
                        "Please guide user to scan the QR code, then retry."
                    ),
                }

            # Clear any fresh modals after navigation
            await self._clear_modals()

            # --- Step 1: Find and click a "Book Appointment" / "New Booking" button ---
            new_booking = await self._try_click(
                lambda: self._page.get_by_role(
                    "button", name=re.compile(r"book.*(appointment|new)", re.IGNORECASE)
                ).or_(
                    self._page.get_by_text(re.compile(r"book appointment", re.IGNORECASE))
                ),
                description="Book Appointment button not found on live site",
            )
            if new_booking.get("ui_mismatch"):
                return {**new_booking, "step": "find_book_button"}
            await self._page.wait_for_timeout(800)

            # --- Step 2: Select institution ----------------------------------------
            inst_result = await self._try_click(
                lambda: self._page.get_by_role(
                    "button", name=re.compile(re.escape(institution.split()[0]), re.IGNORECASE)
                ).or_(
                    self._page.get_by_text(re.compile(re.escape(institution), re.IGNORECASE))
                ),
                description=f"Institution '{institution}' button not found",
            )
            if inst_result.get("ui_mismatch"):
                return {**inst_result, "step": "select_institution"}
            await self._page.wait_for_timeout(600)

            # --- Step 3: Select specialty -------------------------------------------
            spec_result = await self._try_click(
                lambda: self._page.get_by_role(
                    "button", name=re.compile(re.escape(specialty), re.IGNORECASE)
                ).or_(
                    self._page.get_by_text(re.compile(re.escape(specialty), re.IGNORECASE))
                ),
                description=f"Specialty '{specialty}' button not found",
            )
            if spec_result.get("ui_mismatch"):
                return {**spec_result, "step": "select_specialty"}
            await self._page.wait_for_timeout(600)

            # --- Step 4: Continue to calendar ---------------------------------------
            cont1 = await self._try_click(
                lambda: self._page.get_by_role(
                    "button", name=re.compile("continue", re.IGNORECASE)
                ).filter(lambda b: not b.is_disabled()),
                description="Continue button (institution→calendar) not found",
                timeout=10000,
            )
            if cont1.get("ui_mismatch"):
                # Soft fail: live site might auto-advance
                pass
            await self._page.wait_for_timeout(900)

            # --- Step 5: Click date -------------------------------------------------
            try:
                year, month, day = map(int, date.split("-"))
            except Exception:
                year, month, day = 2026, 3, 20

            date_result = await self._try_click(
                lambda: self._page.get_by_role(
                    "button", name=re.compile(rf"^{day}$")
                ).filter(lambda b: not b.is_disabled()),
                description=f"Date day '{day}' not found in calendar",
                timeout=5000,
            )
            if date_result.get("ui_mismatch"):
                return {**date_result, "step": "select_date"}
            await self._page.wait_for_timeout(600)

            # --- Step 6: Click time slot -------------------------------------------
            time12    = self._normalize_time(time)
            period    = "PM" if "PM" in time12 else "AM"
            hour_part = time12.split(":")[0]

            time_clicked = False
            for pattern in [
                re.escape(time12),
                rf"{re.escape(hour_part)}:\d{{2}}\s*{period}",
                rf"\d{{1,2}}:\d{{2}}\s*{period}",
            ]:
                res = await self._try_click(
                    lambda p=pattern: self._page.get_by_role(
                        "button", name=re.compile(p, re.IGNORECASE)
                    ),
                    description=f"Time slot matching '{pattern}'",
                    timeout=3000,
                )
                if not res.get("ui_mismatch"):
                    time_clicked = True
                    break

            if not time_clicked:
                return {
                    "ui_mismatch": True,
                    "step": "select_time",
                    "description": f"No available time slot found near '{time}'",
                }
            await self._page.wait_for_timeout(600)

            # --- Step 7: Continue to reason ----------------------------------------
            await self._try_click(
                lambda: self._page.get_by_role(
                    "button", name=re.compile("continue", re.IGNORECASE)
                ),
                description="Continue button (date→reason) not found",
                timeout=10000,
            )
            await self._page.wait_for_timeout(900)

            # --- Step 8: Select/fill reason ----------------------------------------
            reason_result = await self._try_click(
                lambda: self._page.get_by_role(
                    "button", name=re.compile(re.escape(reason.split()[0]), re.IGNORECASE)
                ).or_(
                    self._page.get_by_text(re.compile(re.escape(reason), re.IGNORECASE))
                ),
                description=f"Reason '{reason}' chip not found",
                timeout=3000,
            )
            if reason_result.get("ui_mismatch"):
                # Fallback: type in a textarea
                try:
                    ta = self._page.get_by_role("textbox")
                    await ta.first.fill(reason, timeout=3000)
                except Exception:
                    pass
            await self._page.wait_for_timeout(500)

            # --- Step 9: Continue to confirmation ----------------------------------
            await self._try_click(
                lambda: self._page.get_by_role(
                    "button", name=re.compile("continue", re.IGNORECASE)
                ),
                description="Continue button (reason→confirm) not found",
                timeout=10000,
            )
            await self._page.wait_for_timeout(900)

            # --- Step 10: Confirm Appointment ----------------------------------------
            confirm_result = await self._try_click(
                lambda: self._page.get_by_role(
                    "button", name=re.compile(r"confirm.*(appointment)?", re.IGNORECASE)
                ),
                description="Confirm Appointment button not found",
                timeout=10000,
            )
            if confirm_result.get("ui_mismatch"):
                return {**confirm_result, "step": "confirm"}

            await self._page.wait_for_timeout(3000)

            # Post-login check (HealthHub may redirect after booking)
            if await self.is_singpass_page():
                return {
                    "on_singpass_page": True,
                    "paused": True,
                    "message": "Singpass re-authentication required. Please scan the QR code.",
                }

            return {
                "booked":      True,
                "institution": institution,
                "specialty":   specialty,
                "date":        date,
                "time":        time12,
                "reason":      reason,
            }


dispatcher = Dispatcher()
