from actions.base import BaseAction

HEALTHHUB_URL = "http://localhost:5173"


class ViewMedications(BaseAction):
    DESCRIPTION = "Navigate to HealthHub dashboard (medications are shown under Health Conditions)"
    PARAMS_SCHEMA = {}

    async def execute(self, params: dict) -> dict:
        # HealthHub WebApp has no dedicated medications page;
        # navigate to dashboard and highlight the Medications & Treatments nav section
        await self.page.goto(f"{HEALTHHUB_URL}/app")
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(400)
        # Click the top green nav "Medications & Treatments" to show intent
        try:
            await self.page.locator("button").filter(
                has_text="Medications & Treatments"
            ).click()
        except Exception:
            pass
        return {"navigated_to": "dashboard/medications"}
