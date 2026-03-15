from actions.base import BaseAction

HEALTHHUB_URL = "http://localhost:5173"

SECTION_URLS = {
    "dashboard":    f"{HEALTHHUB_URL}/app",
    "appointments": f"{HEALTHHUB_URL}/app/appointments",
    "lab":          f"{HEALTHHUB_URL}/app/lab-reports",
    "payments":     f"{HEALTHHUB_URL}/app/payments",
    "profile":      f"{HEALTHHUB_URL}/app/profile",
}


class Login(BaseAction):
    DESCRIPTION = "Log in to HealthHub (sets auth token and navigates to dashboard)"
    PARAMS_SCHEMA = {}

    async def execute(self, params: dict) -> dict:
        await self.page.goto(HEALTHHUB_URL)
        await self.page.wait_for_load_state("networkidle")
        await self.page.evaluate("localStorage.setItem('hh_auth', '1')")
        await self.page.goto(f"{HEALTHHUB_URL}/app")
        await self.page.wait_for_load_state("networkidle")
        return {"logged_in": True}


class NavigateTo(BaseAction):
    DESCRIPTION = "Navigate to a HealthHub section"
    PARAMS_SCHEMA = {
        "section": {
            "type": "string",
            "description": "Section: dashboard, appointments, lab, payments, profile",
            "required": True,
        }
    }

    async def execute(self, params: dict) -> dict:
        section = params["section"]
        url = SECTION_URLS.get(section, f"{HEALTHHUB_URL}/app")
        await self.page.goto(url)
        await self.page.wait_for_load_state("networkidle")
        return {"navigated_to": section}


class GoBack(BaseAction):
    DESCRIPTION = "Navigate back"
    PARAMS_SCHEMA = {}

    async def execute(self, params: dict) -> dict:
        await self.page.go_back()
        await self.page.wait_for_load_state("networkidle")
        return {"went_back": True}
