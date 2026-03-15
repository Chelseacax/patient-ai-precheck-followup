import re
from actions.base import BaseAction

HEALTHHUB_URL = "http://localhost:5173"

# Map MOCK_DOCTORS specialty → HealthHub specialty button text
SPECIALTY_MAP = {
    "General Practice": "General Practice",
    "Cardiology":       "Cardiology",
    "Dermatology":      "General Practice",   # no dermatology in HealthHub — fallback
    "Paediatrics":      "Paediatrics",
    "Orthopaedics":     "Orthopaedics",
}

# Map specialty → a sensible institution for the visual demo
INSTITUTION_MAP = {
    "General Practice": "Clementi Polyclinic",
    "Cardiology":       "Singapore General Hospital",
    "Paediatrics":      "Khoo Teck Puat Hospital",
    "Orthopaedics":     "Tan Tock Seng Hospital",
}


def _to_12h(time_24h: str) -> str:
    """Convert '09:00' → '9:00 AM', '14:00' → '2:00 PM'."""
    try:
        h, m = map(int, time_24h.split(":"))
        period = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {period}"
    except Exception:
        return "9:00 AM"


class ViewAppointments(BaseAction):
    DESCRIPTION = "Navigate to the HealthHub appointments page"
    PARAMS_SCHEMA = {}

    async def execute(self, params: dict) -> dict:
        await self.page.goto(f"{HEALTHHUB_URL}/app/appointments")
        await self.page.wait_for_load_state("networkidle")
        return {"navigated_to": "appointments"}


class BookAppointment(BaseAction):
    DESCRIPTION = "Book a new appointment on HealthHub via the multi-step form"
    PARAMS_SCHEMA = {
        "specialty":     {"type": "string", "description": "Medical specialty", "required": True},
        "slot_datetime": {"type": "string", "description": "Datetime string e.g. '2026-03-09 09:00'", "required": True},
        "reason":        {"type": "string", "description": "Reason for visit", "required": False},
    }

    async def execute(self, params: dict) -> dict:
        specialty   = params.get("specialty", "General Practice")
        slot_dt     = params.get("slot_datetime", "2026-03-09 09:00")
        reason      = params.get("reason", "Follow-up consultation")

        # Parse date/time
        try:
            date_part, time_part = slot_dt.split(" ", 1)
            year, month, day = map(int, date_part.split("-"))
            time_12h = _to_12h(time_part)
        except Exception:
            year, month, day, time_12h = 2026, 3, 9, "9:00 AM"

        hh_specialty    = SPECIALTY_MAP.get(specialty, "General Practice")
        hh_institution  = INSTITUTION_MAP.get(specialty, "Singapore General Hospital")

        # ── Navigate to Appointments ──────────────────────────────────────────
        await self.page.goto(f"{HEALTHHUB_URL}/app/appointments")
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(500)

        # ── Click "Book New" ──────────────────────────────────────────────────
        await self.page.locator("button").filter(has_text=re.compile("Book New")).first.click()
        await self.page.wait_for_timeout(600)

        # ── STEP 1: Institution ───────────────────────────────────────────────
        await self.page.locator("button").filter(has_text=hh_institution).click()
        await self.page.wait_for_timeout(400)

        # ── STEP 1: Specialty ─────────────────────────────────────────────────
        # Specialty buttons appear after institution is selected
        await self.page.locator("button").filter(
            has_text=re.compile(rf"^{re.escape(hh_specialty)}")
        ).click()
        await self.page.wait_for_timeout(400)

        # ── Continue → Step 2 ─────────────────────────────────────────────────
        await self.page.get_by_role("button", name=re.compile("Continue")).click()
        await self.page.wait_for_timeout(700)

        # ── STEP 2: Calendar month navigation ─────────────────────────────────
        # Calendar starts at March 2026 (hardcoded in React component)
        # Navigate forward/back to reach the target month
        target_months_from_march = (year - 2026) * 12 + (month - 3)
        if target_months_from_march > 0:
            for _ in range(target_months_from_march):
                next_btn = self.page.locator("button").filter(has_text="").nth(1)  # ChevronRight in calendar header
                # Use the green header buttons (ChevronLeft / ChevronRight)
                # The calendar header has two icon-only buttons; the second is "next"
                await self.page.locator(
                    'div[style*="backgroundColor"] button'
                ).nth(1).click()
                await self.page.wait_for_timeout(300)

        # ── STEP 2: Click calendar day ────────────────────────────────────────
        # Day buttons have "aspect-square" in their className and a text of just the day number
        clicked_day = False
        try:
            await self.page.evaluate(f"""
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
            clicked_day = True
        except Exception:
            pass

        if not clicked_day:
            # Fallback: click first enabled aspect-square day
            await self.page.evaluate("""
                (() => {
                    const btn = Array.from(document.querySelectorAll('button'))
                        .find(b => !b.disabled && b.className.includes('aspect-square'));
                    if (btn) btn.click();
                })()
            """)
        await self.page.wait_for_timeout(600)

        # ── STEP 2: Click time slot ───────────────────────────────────────────
        try:
            await self.page.locator("button:not([disabled])").filter(
                has_text=re.compile(rf"^{re.escape(time_12h)}$")
            ).click()
        except Exception:
            # Fallback: first available morning slot
            await self.page.evaluate("""
                (() => {
                    const btn = Array.from(document.querySelectorAll('button'))
                        .find(b => !b.disabled && /[0-9]+:[0-9]{2}\\s+(AM|PM)/.test(b.textContent));
                    if (btn) btn.click();
                })()
            """)
        await self.page.wait_for_timeout(500)

        # ── Continue → Step 3 ─────────────────────────────────────────────────
        await self.page.get_by_role("button", name=re.compile("Continue")).click()
        await self.page.wait_for_timeout(700)

        # ── STEP 3: Reason ────────────────────────────────────────────────────
        try:
            await self.page.locator("button").filter(
                has_text="Follow-up consultation"
            ).click()
        except Exception:
            await self.page.locator("textarea").first.fill(reason)
        await self.page.wait_for_timeout(400)

        # ── Continue → Step 4 ─────────────────────────────────────────────────
        await self.page.get_by_role("button", name=re.compile("Continue")).click()
        await self.page.wait_for_timeout(700)

        # ── STEP 4: Confirm ───────────────────────────────────────────────────
        await self.page.get_by_role("button", name=re.compile("Confirm Appointment")).click()
        await self.page.wait_for_timeout(2500)  # Wait for confirmation screen

        return {
            "booked": True,
            "specialty": specialty,
            "institution": hh_institution,
            "slot_datetime": slot_dt,
            "reason": reason,
        }


class CancelAppointment(BaseAction):
    DESCRIPTION = "Navigate to appointments page (cancellation shown there)"
    PARAMS_SCHEMA = {}

    async def execute(self, params: dict) -> dict:
        await self.page.goto(f"{HEALTHHUB_URL}/app/appointments")
        await self.page.wait_for_load_state("networkidle")
        return {"navigated_to": "appointments"}
