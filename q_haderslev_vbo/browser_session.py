from playwright.async_api import async_playwright, Page
from datetime import datetime
import os
import subprocess

from q_haderslev_vbo.pw_run_recorder import PlaywrightRunRecorder


class BrowserSession:
    """
    BrowserSession (klasse – skabelon for objekt)

    STANDARD-ANSVAR (RPA):
    - Én browser pr. job
    - Mange items pr. browser
    - Luk fane = item færdig
    - Luk session = job færdig / fatal fejl
    """

    def __init__(self, headless: bool = True, debug: bool = False, force_new: bool = False):
        self.headless = headless
        self.debug = debug
        self.force_new = force_new  # (bruges senere – forberedt nu)

        # Playwright
        self.pw = None
        self.browser = None
        self.context = None

        # Run-metadata
        self.github_repo_name = None
        self.session_id = None
        self.run_timestamp = None
        self.run_name = None

        # Recorder (intern – RPA-kode må ikke bruge den)
        self.recorder = None

    # -------------------------------------------------
    # START BROWSERSESSION
    # -------------------------------------------------
    async def start(self):
        """
        Starter browser og recorder.
        """
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=self.headless)

        self.github_repo_name = self._find_github_repo_name()
        self.session_id = self._find_session_id()
        self.run_timestamp = self._generate_timestamp()
        self.run_name = self._generate_run_name()

        self.recorder = PlaywrightRunRecorder(
            browser_session=self,
            debug=self.debug
        )

    # -------------------------------------------------
    # NY FANE
    # -------------------------------------------------
    async def new_page(self) -> Page:
        """
        Opretter ny browser-fane (Page).
        """
        if not self.context:
            self.context = await self.browser.new_context()
        return await self.context.new_page()

    # -------------------------------------------------
    # LUK ÉN FANE (STANDARD ITEM-AFSLUTNING)
    # -------------------------------------------------
    async def close_page(self, page: Page):
        """
        Lukker én fane korrekt:
        - stopper recorder (hvis aktiv)
        - lukker fanen
        """
        if self.recorder:
            await self.recorder._close_recording("page_closed")  # intern oprydning

        if not page.is_closed():
            await page.close()

    # -------------------------------------------------
    # LUK ALLE ANDRE FANER
    # -------------------------------------------------
    async def close_other_pages(self, keep_page: Page):
        """
        Lukker alle faner undtagen den angivne.
        """
        if not self.context:
            return

        for p in self.context.pages:
            if p != keep_page and not p.is_closed():
                await p.close()

    # -------------------------------------------------
    # LUK ALT (JOB FÆRDIG / FATAL FEJL)
    # -------------------------------------------------
    async def close(self):
        """
        Lukker ALT korrekt:
        - stopper recorder
        - lukker alle faner
        - lukker browser
        - stopper Playwright
        """
        if self.recorder:
            await self.recorder._close_recording("session_closed")

        if self.context:
            await self.context.close()

        if self.browser:
            await self.browser.close()

        if self.pw:
            await self.pw.stop()

    # -------------------------------------------------
    # METADATA HELPERS
    # -------------------------------------------------
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