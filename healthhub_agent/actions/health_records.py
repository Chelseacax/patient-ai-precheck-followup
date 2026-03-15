from actions.base import BaseAction

HEALTHHUB_URL = "http://localhost:5173"


class ViewHealthRecords(BaseAction):
    DESCRIPTION = "Navigate to HealthHub lab reports / health records page"
    PARAMS_SCHEMA = {}

    async def execute(self, params: dict) -> dict:
        await self.page.goto(f"{HEALTHHUB_URL}/app/lab-reports")
        await self.page.wait_for_load_state("networkidle")
        return {"navigated_to": "lab-reports"}


class ViewLabResults(BaseAction):
    DESCRIPTION = "Navigate to HealthHub lab reports page"
    PARAMS_SCHEMA = {}

    async def execute(self, params: dict) -> dict:
        await self.page.goto(f"{HEALTHHUB_URL}/app/lab-reports")
        await self.page.wait_for_load_state("networkidle")
        return {"navigated_to": "lab-reports"}
