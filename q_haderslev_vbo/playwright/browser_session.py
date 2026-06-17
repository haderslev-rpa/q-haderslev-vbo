from playwright.async_api import async_playwright, Page
from datetime import datetime
import os
import subprocess
from pathlib import Path

from q_haderslev_vbo.playwright.playwright_run_recorder import PlaywrightRunRecorder


class BrowserSession:
    """
    BrowserSession (klasse – skabelon for objekt)

    Ansvar:
    - Browser lifecycle
    - Context (med evt. video)
    - Pages
    - Simple helper-metoder
    """

    def __init__(
        self,
        headless: bool = True,
        debug: bool = False,
        video: bool = False,
        force_new: bool = False
    ):
        self.headless = headless
        self.debug = debug
        self.video = video
        self.force_new = force_new

        # Playwright
        self.pw = None
        self.browser = None
        self.context = None

        # Metadata
        self.github_repo_name = None
        self.session_id = None
        self.run_timestamp = None
        self.run_name = None

        # Recorder (kun screenshots)
        self.recorder = None

    # -------------------------------------------------
    # START
    # -------------------------------------------------
    async def start(self):
        """
        Starter browser
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
    # NEW PAGE
    # -------------------------------------------------
    async def new_page(self) -> Page:
        """
        Opretter ny page (browser fane)

        ✅ Video hvis debug=True AND video=True
        """

        if not self.context:
            run_dir = Path("tests_local_playwright") / self.run_name
            run_dir.mkdir(parents=True, exist_ok=True)

            if self.debug and self.video:
                self.context = await self.browser.new_context(
                    record_video_dir=str(run_dir)
                )
            else:
                self.context = await self.browser.new_context()

        return await self.context.new_page()

    # -------------------------------------------------
    # SCREENSHOT (nem API)
    # -------------------------------------------------
    async def screenshot(self, page: Page, name: str):
        """
        Wrapper til screenshot (billede)
        """
        if self.recorder:
            await self.recorder.screenshot(page, name)

    # -------------------------------------------------
    # CLOSE PAGE
    # -------------------------------------------------
    async def close_page(self, page: Page):
        if not page.is_closed():
            await page.close()

    # -------------------------------------------------
    # CLOSE OTHER TABS
    # -------------------------------------------------
    async def close_all_other_tabs(
        self,
        active_page: Page,
        print_log: bool = False
    ) -> None:
        """
        Lukker alle faner undtagen aktiv
        """

        if not self.context:
            return

        if print_log:
            print(f"[Playwright] Antal faner FØR cleanup: {len(self.context.pages)}")

        for p in self.context.pages:
            if p != active_page and not p.is_closed():
                try:
                    await p.close()
                except Exception:
                    pass

        if print_log:
            print(f"[Playwright] Antal faner EFTER cleanup: {len(self.context.pages)}")

    # -------------------------------------------------
    # CLOSE SESSION
    # -------------------------------------------------
    async def close(self):
        """
        Lukker ALT
        ✅ Gemmer video automatisk
        """

        if self.context:
            await self.context.close()

        if self.browser:
            await self.browser.close()

        if self.pw:
            await self.pw.stop()

    # -------------------------------------------------
    # HELPERS
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