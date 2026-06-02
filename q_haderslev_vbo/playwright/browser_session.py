from playwright.async_api import async_playwright, Page, Error
from datetime import datetime
import os
import subprocess


class BrowserSession:
    """
    BrowserSession (klasse – skabelon for objekt)

    Ansvar:
    - Starte Playwright
    - Starte browser og context
    - Finde run-navn og metadata
    - INGEN mapper
    - INGEN filer
    """

    def __init__(self, headless: bool = True):
        self.headless = headless

        # Playwright-objekter (browser-ting)
        self.pw = None
        self.browser = None
        self.context = None

        # Run-metadata (kun hukommelse)
        self.github_repo_name: str | None = None
        self.session_id: str | None = None
        self.run_timestamp: str | None = None
        self.run_name: str | None = None

    async def start(self):
        """Starter Playwright og finder metadata"""

        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context()

        # Find metadata
        self.github_repo_name = self._find_github_repo_name()
        self.session_id = self._find_session_id()
        self.run_timestamp = self._generate_timestamp()
        self.run_name = self._generate_run_name()

    async def new_page(self) -> Page:
        return await self.context.new_page()

    async def ensure_page_alive(self, page: Page | None) -> Page:
        if page is None:
            return await self.new_page()
        try:
            await page.title()
            return page
        except Error:
            return await self.new_page()

    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.pw:
            await self.pw.stop()

    # ---------------- METADATA ----------------

    def _generate_timestamp(self) -> str:
        """Dansk dato + tid"""
        return datetime.now().strftime("%d-%m-%Y %H-%M")

    def _generate_run_name(self) -> str:
        """Sammensæt run-navn"""
        if self.session_id:
            return f"{self.run_timestamp} (session {self.session_id})"
        return self.run_timestamp

    def _find_session_id(self) -> str | None:
        """Automation Server session-id (env)"""
        return os.getenv("AUTOMATION_SESSION_ID")

    def _find_github_repo_name(self) -> str:
        """
        GitHub repo-navn:
        1) ENV: GITHUB_REPO_NAME
        2) git config
        3) fallback
        """
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