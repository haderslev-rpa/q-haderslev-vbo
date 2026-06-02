"""
⚠️ VIGTIGT – LÆS FØR BRUG ⚠️

Denne klasse må ALDRIG oprettes direkte.

✅ KORREKT:
    session = BrowserSession(...)
    await session.start()
    await session.recorder.screenshot(page, "...")

❌ FORKERT:
    PlaywrightRunRecorder()
"""

from pathlib import Path
import asyncio
from playwright.async_api import Page, BrowserContext


class PlaywrightRunRecorder:
    """
    PlaywrightRunRecorder (klasse – dokumentations-hjælper)

    - screenshot()  → debug-styret
    - screenshot(always=True) → altid
    - video + trace → kun hvis start_recording() kaldes
    """

    BASE_PATH = Path("test_local_playwright")

    def __init__(self, browser_session, debug: bool):
        if browser_session is None:
            raise RuntimeError(
                "PlaywrightRunRecorder må kun oprettes via BrowserSession"
            )

        self.browser_session = browser_session
        self.debug = debug  # bool (sand/falsk)

        self.run_dir: Path | None = None

        self.record_context: BrowserContext | None = None
        self.record_task: asyncio.Task | None = None
        self.tracing_started = False
        self.recording_active = False

    # -------------------------------------------------
    # INTERN: opret mappe lazy
    # -------------------------------------------------
    def _ensure_run_dir(self):
        if self.run_dir:
            return

        run_name = self.browser_session.run_name
        self.run_dir = self.BASE_PATH / run_name
        self.run_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------
    # SCREENSHOT
    # -------------------------------------------------
    async def screenshot(
        self,
        page: Page,
        name: str,
        always: bool = False
    ):
        """
        Tager screenshot.

        - debug=True      → gem
        - always=True     → gem (uanset debug)
        - begge False     → gem ikke
        """

        if not self.debug and not always:
            return None

        self._ensure_run_dir()

        safe = name.replace(" ", "_").replace("/", "_")
        path = self.run_dir / f"{safe}.png"

        await page.screenshot(path=str(path), full_page=True)
        return path

    # -------------------------------------------------
    # START VIDEO + TRACE (kun hvis ønsket)
    # -------------------------------------------------
    async def start_recording(self, timeout_seconds: int = 10):
        if not self.debug:
            return None

        self._ensure_run_dir()

        self.record_context = await self.browser_session.browser.new_context(
            record_video_dir=str(self.run_dir)
        )

        await self.record_context.tracing.start(
            screenshots=True,
            snapshots=True,
            sources=True
        )

        self.tracing_started = True
        self.recording_active = True

        self.record_task = asyncio.create_task(
            self._auto_stop(timeout_seconds)
        )

        return self.record_context

    # -------------------------------------------------
    # INTERN: fælles afslutning
    # -------------------------------------------------
    async def _finalize(self, reason: str):
        if not self.recording_active or not self.record_context:
            return

        if self.record_task and not self.record_task.done():
            self.record_task.cancel()

        if self.tracing_started:
            try:
                trace_path = self.run_dir / f"{reason}_trace.zip"
                await self.record_context.tracing.stop(path=str(trace_path))
            except Exception:
                pass

        await self.record_context.close()

        self.record_context = None
        self.tracing_started = False
        self.recording_active = False

    async def _auto_stop(self, seconds: int):
        try:
            await asyncio.sleep(seconds)
            await self._finalize("auto_stop")
        except asyncio.CancelledError:
            pass

    async def finalize_before_browser_close(self):
        await self._finalize("final")