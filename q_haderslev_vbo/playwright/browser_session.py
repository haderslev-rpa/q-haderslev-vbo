from playwright.async_api import async_playwright, Page, Error
from datetime import datetime
import os
import subprocess

from q_haderslev_vbo.playwright.playwright_run_recorder import PlaywrightRunRecorder


class BrowserSession:
    """
    BrowserSession (klasse – skabelon for objekt)

    Ansvar:
    - Starte Playwright
    - Starte browser
    - Holde run-metadata
    - EJE RunRecorder
    - Lukke ALT korrekt

    ✅ ENTRY-POINT for AL Playwright-brug
    """

    def __init__(self, headless: bool = True):
        self.headless = headless

        # Playwright-objekter
        self.pw = None
        self.browser = None
        self.context = None

        # Run-metadata
        self.github_repo_name: str | None = None
        self.session_id: str | None = None
        self.run_timestamp: str | None = None
        self.run_name: str | None = None

        # Recorder (oprettes automatisk)
        self.recorder: PlaywrightRunRecorder | None = None

    # -------------------------------------------------
    # START
    # -------------------------------------------------
    async def start(self):
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=self.headless)

        # Run-navn (bruges til mappenavn)
        self.github_repo_name = self._find_github_repo_name()
        self.session_id = self._find_session_id()
        self.run_timestamp = self._generate_timestamp()
        self.run_name = self._generate_run_name()

        # ✅ Recorder oprettes HER (må ikke gøres andre steder)
        self.recorder = PlaywrightRunRecorder(self)

    # -------------------------------------------------
    # PAGE
    # -------------------------------------------------
    async def new_page(self) -> Page:
        self.context = await self.browser.new_context()
        return await self.context.new_page()

    async def ensure_page_alive(self, page: Page | None) -> Page:
        if page is None:
            return await self.new_page()
        try:
            await page.title()
            return page
        except Error:
            return await self.new_page()

    # -------------------------------------------------
    # CLOSE (DET VIGTIGE STED)
    # -------------------------------------------------
    async def close(self):
        """
        Lukker ALT i korrekt rækkefølge:
        1) Recorder finaliserer (trace/video)
        2) Context lukkes
        3) Browser lukkes
        4) Playwright stoppes
        """

        if self.recorder:
            await self.recorder.finalize_before_browser_close()

        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.pw:
            await self.pw.stop()

    # ---------------- METADATA ----------------

    def _generate_timestamp(self) -> str:
        return datetime.now().strftime("%d-%m-%Y %H-%M")

    def _generate_run_name(self) -> str:
        if self.session_id:
            return f"{self.run_timestamp} (session {self.session_id})"
        return self.run_timestamp

    def _find_session_id(self) -> str | None:
        return os.getenv("AUTOMATION_SESSION_ID")

    def _find_github_repo_name(self) -> str:
        env_name = os.getenv("GITHUB_REPO_NAME")
        if env_name:
            return env_name

        try:
            result = subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            return result.split("/")[-1].replace(".git", "")
        except Exception:
            return "local-debug"
