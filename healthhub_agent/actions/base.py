from abc import ABC, abstractmethod


class BaseAction(ABC):
    DESCRIPTION: str = ""
    PARAMS_SCHEMA: dict = {}  # {param_name: {type, description, required}}

    def __init__(self, page):
        self.page = page

    @abstractmethod
    async def execute(self, params: dict) -> dict:
        raise NotImplementedError

    async def wait_click(self, selector: str, timeout: int = 5000):
        await self.page.wait_for_selector(selector, timeout=timeout)
        await self.page.click(selector)

    async def wait_fill(self, selector: str, value: str, timeout: int = 5000):
        await self.page.wait_for_selector(selector, timeout=timeout)
        await self.page.fill(selector, value)

    async def nav(self, section: str):
        await self.page.evaluate(f"showSection('{section}')")
        await self.page.wait_for_timeout(600)
