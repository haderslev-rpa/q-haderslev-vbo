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
    - Holde run-metadata
    - Holde debug-tilstand
    - EJE RunRecorder
    """

    def __init__(self, headless: bool = True, debug: bool = False):
        self.headless = headless
        self.debug = debug  # ✅ debug gemmes ét sted

        # Playwright
        self.pw = None
        self.browser = None
        self.context = None

        # Run-metadata
        self.github_repo_name = None
        self.session_id = None
        self.run_timestamp = None
        self.run_name = None

        # Recorder
        self.recorder = None

    async def start(self):
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=self.headless)

        # Metadata
        self.github_repo_name = self._find_github_repo_name()
        self.session_id = self._find_session_id()
        self.run_timestamp = self._generate_timestamp()
        self.run_name = self._generate_run_name()

        # ✅ Recorder får debug-tilstand her
        self.recorder = PlaywrightRunRecorder(
            browser_session=self,
            debug=self.debug
        )

    async def new_page(self) -> Page:
        self.context = await self.browser.new_context()
        return await self.context.new_page()

    async def close(self):
        if self.recorder:
            await self.recorder.finalize_before_browser_close()

        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.pw:
            await self.pw.stop()

    # ---------- metadata helpers ----------

    def _generate_timestamp(self) -> str:
        return datetime.now().strftime("%d-%m-%Y %H-%M")

    def _generate_run_name(self) -> str:
        if self.session_id:
            return f"{self.run_timestamp} (session {self.session_id})"
        return self.run_timestamp

    def _find_session_id(self):
        return os.getenv("AUTOMATION_SESSION_ID")

    def _find_github_repo_name(self):
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