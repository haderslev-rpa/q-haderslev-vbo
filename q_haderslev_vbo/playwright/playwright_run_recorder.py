"""
⚠️ VIGTIGT – LÆS FØR BRUG ⚠️

Denne klasse (PlaywrightRunRecorder) må ALDRIG oprettes direkte.

kald istedet filen browser_session.py og brug BrowserSession til at starte Playwright og oprette recorderen.

✅ KORREKT BRUG:
    session = BrowserSession()
    await session.start()
    recorder = session.recorder

❌ FORKERT BRUG:
    recorder = PlaywrightRunRecorder()              # ❌
    recorder = PlaywrightRunRecorder(None)          # ❌
    python playwright_run_recorder.py               # ❌

ÅRSAG:
- Recorderen kræver BrowserSession som ejer
- BrowserSession bestemmer:
  - run-navn (mappenavn)
  - browser-livscyklus
  - hvornår trace/video skal stoppes
- Recorderen er KUN et værktøj, ikke et entry-point
"""

from pathlib import Path
import asyncio
from playwright.async_api import Page, BrowserContext


class PlaywrightRunRecorder:
    """
    PlaywrightRunRecorder (klasse – dokumentations-hjælper)

    Ansvar:
    - Screenshots (print-screen)
    - Video (start/stop)
    - Trace (debug)
    - Automatisk oprydning
    - Lazy mappe-oprettelse

    ⚠️ Må kun bruges via BrowserSession ⚠️
    """

    BASE_PATH = Path("test_local_playwright")

    def __init__(self, browser_session):
        # ---------------------------
        # BESKYTTELSE MOD FORKERT BRUG
        # ---------------------------
        if browser_session is None:
            raise RuntimeError(
                "PlaywrightRunRecorder må kun oprettes via BrowserSession"
            )

        self.browser_session = browser_session  # objekt (ejer)
        self.run_dir: Path | None = None

        # Recording-state
        self.record_context: BrowserContext | None = None
        self.record_task: asyncio.Task | None = None
        self.tracing_started: bool = False
        self.recording_active: bool = False

    # -------------------------------------------------
    # LAZY MAPPE-OPRETTELSE
    # -------------------------------------------------
    def _ensure_run_dir(self):
        if self.run_dir:
            return

        run_name = self.browser_session.run_name
        if not run_name:
            raise RuntimeError("BrowserSession er ikke startet")

        # ✅ Mappenavnet kommer KUN fra BrowserSession
        self.run_dir = self.BASE_PATH / run_name
        self.run_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------
    # SCREENSHOT (ALTID TILLADT)
    # -------------------------------------------------
    async def screenshot(self, page: Page, name: str):
        self._ensure_run_dir()

        safe = name.replace(" ", "_").replace("/", "_")
        path = self.run_dir / f"{safe}.png"

        await page.screenshot(path=str(path), full_page=True)
        return path

    # -------------------------------------------------
    # START VIDEO + TRACE (VALGFRIT)
    # -------------------------------------------------
    async def start_recording(self, timeout_seconds: int = 10):
        """
        Starter video + trace.
        Trace gemmes KUN hvis denne funktion kaldes.
        """
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

        # Auto-stop (sikker)
        self.record_task = asyncio.create_task(
            self._auto_stop(timeout_seconds)
        )

        return self.record_context

    # -------------------------------------------------
    # INTERN FÆLLES FINALIZE
    # -------------------------------------------------
    async def _finalize(self, reason: str):
        if not self.recording_active or not self.record_context:
            return

        if self.record_task and not self.record_task.done():
            self.record_task.cancel()

        # ✅ Trace skrives FØR browser lukkes
        if self.tracing_started:
            try:
                trace_path = self.run_dir / f"{reason}_trace.zip"
                await self.record_context.tracing.stop(path=str(trace_path))
            except Exception:
                # Trace må ALDRIG ødelægge video
                pass

        # ✅ Luk context → video flushes
        await self.record_context.close()

        self.record_context = None
        self.tracing_started = False
        self.recording_active = False

    # -------------------------------------------------
    # AUTO STOP
    # -------------------------------------------------
    async def _auto_stop(self, seconds: int):
        try:
            await asyncio.sleep(seconds)
            await self._finalize("auto_stop")
        except asyncio.CancelledError:
            pass

    # -------------------------------------------------
    # STOP VED FEJL
    # -------------------------------------------------
    async def stop_recording_on_error(self):
        await self._finalize("exception")

    # -------------------------------------------------
    # KALDES AF BrowserSession.close()
    # -------------------------------------------------
    async def finalize_before_browser_close(self):
        await self._finalize("final")