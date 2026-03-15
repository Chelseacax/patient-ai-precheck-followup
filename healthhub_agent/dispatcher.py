import asyncio
import base64
import re
from typing import Optional

from playwright.async_api import async_playwright

from actions import REGISTRY

HEALTHHUB_URL = "http://localhost:5173"

INSTITUTIONS = [
    "Singapore General Hospital",
    "National University Hospital",
    "Khoo Teck Puat Hospital",
    "Tan Tock Seng Hospital",
    "Clementi Polyclinic",
    "Buona Vista Polyclinic",
    "Jurong Polyclinic",
]

SPECIALTIES = [
    "Cardiology",
    "Eye Clinic",
    "General Practice",
    "Neurology",
    "Dental",
    "Orthopaedics",
    "Paediatrics",
    "Vaccination",
]

REASONS = [
    "Follow-up consultation",
    "Acute pain or discomfort",
    "Routine check-up",
    "Prescription renewal",
    "Flu jab / Vaccination",
    "Pre-surgery assessment",
    "Specialist referral",
    "Lab test results review",
]


class Dispatcher:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._lock = asyncio.Lock()
        self._ready = False
        self._action_count = 0

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def action_count(self) -> int:
        return self._action_count

    async def current_url(self) -> str:
        if self._page:
            return self._page.url
        return ""

    async def start_browser(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=False,
            args=["--window-size=1280,800"],
            slow_mo=500,   # slower so every click is visible
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800}
        )
        self._page = await self._context.new_page()

        await self._page.goto(HEALTHHUB_URL)
        await self._page.wait_for_load_state("networkidle")
        await self._page.evaluate("localStorage.setItem('hh_auth', '1')")
        await self._page.goto(f"{HEALTHHUB_URL}/app")
        await self._page.wait_for_load_state("networkidle")
        self._ready = True

    async def stop_browser(self):
        self._ready = False
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def screenshot_b64(self) -> str:
        if not self._page:
            return ""
        try:
            data = await self._page.screenshot(type="jpeg", quality=75)
            return base64.b64encode(data).decode()
        except Exception:
            self._ready = False
            return ""

    async def _ensure_browser(self):
        """Restart browser if it was closed."""
        if not self._ready:
            try:
                await self.stop_browser()
            except Exception:
                pass
            await self.start_browser()

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

    # ── Navigation ──────────────────────────────────────────────────────────────

    async def navigate_healthhub(self, page: str) -> dict:
        await self._ensure_browser()
        urls = {
            "home":         f"{HEALTHHUB_URL}/app",
            "appointments": f"{HEALTHHUB_URL}/app/appointments",
            "medications":  f"{HEALTHHUB_URL}/app/medications",
            "lab-reports":  f"{HEALTHHUB_URL}/app/lab-reports",
            "profile":      f"{HEALTHHUB_URL}/app/profile",
        }
        async with self._lock:
            url = urls.get(page, f"{HEALTHHUB_URL}/app")
            await self._page.goto(url)
            await self._page.wait_for_load_state("networkidle")
            await self._page.wait_for_timeout(500)
            return {"navigated_to": page, "url": url}

    # ── Full Booking Automation ─────────────────────────────────────────────────

    async def book_on_healthhub(
        self,
        institution: str,
        specialty: str,
        date: str,       # "YYYY-MM-DD"
        time: str,       # e.g. "14:00" or "2:00 PM"
        reason: str,
    ) -> dict:
        """
        Run the ENTIRE HealthHub booking form automatically.
        Clicks every step: institution → specialty → Continue → date → time →
        Continue → reason → Continue → Confirm Appointment.
        Screenshots stream to the frontend throughout.
        """
        await self._ensure_browser()
        async with self._lock:
            self._action_count += 1

            # Parse date
            try:
                year, month, day = map(int, date.split("-"))
            except Exception:
                year, month, day = 2026, 3, 20

            # Match inputs to known values
            inst   = self._fuzzy_match(institution, INSTITUTIONS)
            spec   = self._fuzzy_match(specialty, SPECIALTIES)
            rsn    = self._fuzzy_match(reason, REASONS)
            time12 = self._normalize_time(time)

            # ── 1. Appointments page ──────────────────────────────────────────
            await self._page.goto(f"{HEALTHHUB_URL}/app/appointments")
            await self._page.wait_for_load_state("networkidle")
            await self._page.wait_for_timeout(600)

            # ── 2. Click "Book New" ───────────────────────────────────────────
            await self._page.locator("button").filter(
                has_text=re.compile(r"Book\s+New", re.IGNORECASE)
            ).first.click()
            await self._page.wait_for_timeout(800)

            # ── 3. Click institution ──────────────────────────────────────────
            await self._page.locator("button").filter(has_text=inst).first.click()
            await self._page.wait_for_timeout(600)

            # ── 4. Click specialty ────────────────────────────────────────────
            # Specialty buttons have CSS class "relative" (for VAX badge positioning);
            # institution buttons do NOT have "relative", preventing false matches
            # like "General Practice" accidentally clicking "Singapore General Hospital".
            await self._page.locator("button.relative").filter(
                has_text=re.compile(re.escape(spec), re.IGNORECASE)
            ).first.click()
            await self._page.wait_for_timeout(600)

            # ── 5. Continue → calendar ────────────────────────────────────────
            await self._page.locator("button:not([disabled])").filter(
                has_text=re.compile("Continue", re.IGNORECASE)
            ).first.click(timeout=10000)
            await self._page.wait_for_timeout(900)

            # ── 6. Navigate calendar to correct month ─────────────────────────
            # Calendar starts at March 2026
            months_to_advance = (year - 2026) * 12 + (month - 3)
            for _ in range(max(0, months_to_advance)):
                # Next-month chevron: second icon-button inside the calendar header
                await self._page.evaluate("""
                    () => {
                        const btns = Array.from(document.querySelectorAll('button'));
                        const chevrons = btns.filter(b =>
                            b.textContent.trim() === '' ||
                            b.innerHTML.includes('ChevronRight') ||
                            b.innerHTML.includes('svg')
                        );
                        if (chevrons.length >= 2) chevrons[1].click();
                    }
                """)
                await self._page.wait_for_timeout(400)

            # ── 7. Click calendar day ─────────────────────────────────────────
            # Use Playwright locator (reliably triggers React's onClick handler)
            try:
                await self._page.locator(
                    "button.aspect-square:not([disabled])"
                ).filter(has_text=re.compile(rf"^{day}$")).first.click(timeout=5000)
            except Exception:
                # Fallback: page.evaluate in case locator can't find it
                await self._page.evaluate(f"""
                    (() => {{
                        const btns = Array.from(document.querySelectorAll('button'));
                        const target = btns.find(b =>
                            !b.disabled &&
                            b.textContent.trim() === '{day}' &&
                            b.className.includes('aspect-square')
                        );
                        if (target) target.click();
                    }})()
                """)
            # Wait for time slots section to appear
            try:
                await self._page.wait_for_selector(
                    "text=Available Slots", timeout=3000
                )
            except Exception:
                pass
            await self._page.wait_for_timeout(400)

            # ── 8. Click time slot ────────────────────────────────────────────
            period = "PM" if "PM" in time12 else "AM"
            hour = time12.split(":")[0]
            clicked = False

            # Strategy 1: exact text match
            try:
                await self._page.locator("button:not([disabled])").filter(
                    has_text=re.compile(re.escape(time12), re.IGNORECASE)
                ).first.click(timeout=2000)
                clicked = True
            except Exception:
                pass

            # Strategy 2: same hour, same period (e.g. requested 10:00 AM → 10:30 AM)
            if not clicked:
                try:
                    await self._page.locator("button:not([disabled])").filter(
                        has_text=re.compile(
                            rf"{re.escape(hour)}:\d{{2}}\s*{period}", re.IGNORECASE
                        )
                    ).first.click(timeout=2000)
                    clicked = True
                except Exception:
                    pass

            # Strategy 3: any slot in same period (AM or PM)
            if not clicked:
                try:
                    await self._page.locator("button:not([disabled])").filter(
                        has_text=re.compile(
                            rf"\d{{1,2}}:\d{{2}}\s*{period}", re.IGNORECASE
                        )
                    ).first.click(timeout=2000)
                    clicked = True
                except Exception:
                    pass

            # Strategy 4: absolute fallback — first any available time slot
            if not clicked:
                try:
                    await self._page.locator("button:not([disabled])").filter(
                        has_text=re.compile(r"\d{1,2}:\d{2}\s*(AM|PM)", re.IGNORECASE)
                    ).first.click(timeout=2000)
                except Exception:
                    pass

            await self._page.wait_for_timeout(600)

            # ── 9. Continue → reason ──────────────────────────────────────────
            # Wait for Continue to become enabled (date + slot both selected)
            await self._page.locator(
                "button:not([disabled])"
            ).filter(
                has_text=re.compile("Continue", re.IGNORECASE)
            ).first.click(timeout=10000)
            await self._page.wait_for_timeout(900)

            # ── 10. Click reason chip ─────────────────────────────────────────
            try:
                await self._page.locator("button").filter(
                    has_text=re.compile(re.escape(rsn.split()[0]), re.IGNORECASE)
                ).first.click(timeout=3000)
            except Exception:
                try:
                    await self._page.locator("textarea").first.fill(reason)
                except Exception:
                    pass
            await self._page.wait_for_timeout(500)

            # ── 11. Continue → confirmation ───────────────────────────────────
            await self._page.locator("button:not([disabled])").filter(
                has_text=re.compile("Continue", re.IGNORECASE)
            ).first.click(timeout=10000)
            await self._page.wait_for_timeout(900)

            # ── 12. Confirm Appointment ───────────────────────────────────────
            await self._page.get_by_role(
                "button", name=re.compile("Confirm Appointment", re.IGNORECASE)
            ).click()
            await self._page.wait_for_timeout(2500)

            return {
                "booked": True,
                "institution": inst,
                "specialty": spec,
                "date": date,
                "time": time12,
                "reason": rsn,
            }

    # ── Helpers ─────────────────────────────────────────────────────────────────

    def _fuzzy_match(self, user_input: str, options: list) -> str:
        inp = user_input.lower().strip()
        # Exact substring match
        for opt in options:
            if inp in opt.lower() or opt.lower() in inp:
                return opt
        # Word-level match
        words = inp.split()
        for opt in options:
            if any(w in opt.lower() for w in words if len(w) > 2):
                return opt
        return options[0]

    def _normalize_time(self, value: str) -> str:
        """Convert user time input to '9:00 AM' format."""
        value = value.strip()
        m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", value, re.IGNORECASE)
        if m:
            h = int(m.group(1))
            mins = m.group(2) or "00"
            period = (m.group(3) or "").upper()
            if not period:
                if h >= 12:
                    period = "PM"
                    if h > 12:
                        h -= 12
                else:
                    period = "AM"
            elif period == "PM" and h < 12:
                pass  # keep h as-is for display
            return f"{h}:{mins} {period}"
        return value


dispatcher = Dispatcher()
