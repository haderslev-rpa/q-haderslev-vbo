from pathlib import Path
import asyncio
from playwright.async_api import Page, BrowserContext


class PlaywrightRunRecorder:
    """
    PlaywrightRunRecorder (klasse – dokumentations-hjælper)

    ⚠️ Må IKKE bruges direkte i RPA-kode
    """

    BASE_PATH = Path("tests_local_playwright")

    def __init__(self, browser_session, debug: bool):
        self.browser_session = browser_session
        self.debug = debug

        self.run_dir = None
        self._record_context: BrowserContext | None = None
        self._record_task: asyncio.Task | None = None
        self._recording_active = False

    # ---------- interne helpers ----------

    def _ensure_run_dir(self):
        if self.run_dir:
            return
        self.run_dir = self.BASE_PATH / self.browser_session.run_name
        self.run_dir.mkdir(parents=True, exist_ok=True)

    async def _close_recording(self, reason: str):
        """
        ⚠️ PRIVAT – må kun kaldes af BrowserSession
        Stopper video + trace korrekt
        """
        if not self._recording_active or not self._record_context:
            return

        if self._record_task:
            self._record_task.cancel()

        try:
            trace_path = self.run_dir / f"{reason}_trace.zip"
            await self._record_context.tracing.stop(path=str(trace_path))
        except Exception:
            pass

        await self._record_context.close()

        self._record_context = None
        self._recording_active = False

    # ---------- offentlige metoder ----------

    async def screenshot(self, page: Page, name: str, always: bool = False):
        if not self.debug and not always:
            return

        self._ensure_run_dir()
        path = self.run_dir / f"{name.replace(' ', '_')}.png"
        await page.screenshot(path=str(path), full_page=True)

    async def start_recording(self, timeout_seconds: int = 10):
        if not self.debug:
            return None

        self._ensure_run_dir()

        self._record_context = await self.browser_session.browser.new_context(
            record_video_dir=str(self.run_dir)
        )

        await self._record_context.tracing.start(
            screenshots=True,
            snapshots=True,
            sources=True
        )

        self._recording_active = True
        self._record_task = asyncio.create_task(
            asyncio.sleep(timeout_seconds)
        )

        return self._record_context