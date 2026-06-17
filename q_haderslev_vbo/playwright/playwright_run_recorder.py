from pathlib import Path
from playwright.async_api import Page


class PlaywrightRunRecorder:
    """
    Simpel recorder (klasse – skabelon for objekt)

    Ansvar:
    - Screenshots (billeder)
    """

    BASE_PATH = Path("tests_local_playwright")

    def __init__(self, browser_session, debug: bool):
        self.browser_session = browser_session
        self.debug = debug
        self.run_dir = None

    def _ensure_run_dir(self):
        if self.run_dir:
            return

        self.run_dir = self.BASE_PATH / self.browser_session.run_name
        self.run_dir.mkdir(parents=True, exist_ok=True)

    async def screenshot(self, page: Page, name: str):
        """
        Gemmer screenshot
        """

        if not self.debug:
            return

        self._ensure_run_dir()

        safe_name = name.replace(" ", "_").replace("/", "_")
        path = self.run_dir / f"{safe_name}.png"

        await page.screenshot(path=str(path), full_page=True)