from pathlib import Path
import asyncio
from playwright.async_api import Page, BrowserContext
from q_haderslev_vbo.playwright.browser_session import BrowserSession


class PlaywrightRunRecorder:
    """
    PlaywrightRunRecorder (klasse – dokumentations-hjælper)

    Ansvar:
    - Screenshots (print-screen)
    - Video (start/stop)
    - Trace (debug)
    - Auto-stop
    - Exception-sikker lukning
    - Lazy mappe-oprettelse
    - SharePoint-upload (SENERE – kommenteret)
    """

    BASE_PATH = Path("test_local_playwright")

    # ---------------------------
    # SHAREPOINT (KUN DOKUMENTATION)
    # ---------------------------
    # DEFAULT_SITE = "Automatisering"
    #
    # TANKEN HER:
    # - GitHub repo-navn → SharePoint hovedmappe
    # - run_name → undermappe
    #
    # Eksempel:
    # Automatisering/
    # └── advis-vedr-arbejdsskader/
    #     └── 20-12-2026 10-00 (session 111)/
    #
    # SENERE:
    # if files:
    #     drive_id, folder_id, file_urls = upload_temp_files(
    #         sp_client,
    #         site_name,
    #         BASE_PATH,
    #         files
    #     )

    def __init__(self, browser_session: BrowserSession):
        self.browser_session = browser_session

        self.run_dir: Path | None = None
        self.record_context: BrowserContext | None = None
        self.record_task: asyncio.Task | None = None
        self.tracing_started = False

    # ---------------------------
    # INTERN: opret mappe lazy
    # ---------------------------
    def _ensure_run_dir(self):
        if self.run_dir:
            return

        run_name = self.browser_session.run_name
        if not run_name:
            raise RuntimeError("BrowserSession er ikke startet")

        self.run_dir = self.BASE_PATH / run_name
        self.run_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------
    # SCREENSHOT (ALTID TILLADT)
    # ---------------------------
    async def screenshot(self, page: Page, name: str):
        """
        Tager print-screen
        Virker både med og uden debug
        """
        self._ensure_run_dir()

        safe_name = name.replace(" ", "_").replace("/", "_")
        path = self.run_dir / f"{safe_name}.png"

        await page.screenshot(path=str(path), full_page=True)
        return path

    # ---------------------------
    # START VIDEO + TRACE
    # ---------------------------
    async def start_recording(self, timeout_seconds: int = 10):
        """
        Starter video + tracing
        """
        self._ensure_run_dir()

        self.record_context = await self.browser_session.browser.new_context(
            record_video_dir=str(self.run_dir)
        )

        # Tracing (debug – ekstra info)
        await self.record_context.tracing.start(
            screenshots=True,
            snapshots=True,
            sources=True
        )
        self.tracing_started = True

        # Auto-stop timer
        self.record_task = asyncio.create_task(
            self._auto_stop(timeout_seconds)
        )

        return self.record_context

    # ---------------------------
    # STOP (NORMAL)
    # ---------------------------
    async def stop_recording_clean(self, name: str = "finished"):
        if not self.record_context:
            return

        if self.record_task and not self.record_task.done():
            self.record_task.cancel()

        if self.tracing_started:
            try:
                trace_path = self.run_dir / f"{name}_trace.zip"
                await self.record_context.tracing.stop(path=str(trace_path))
            except Exception:
                pass

        await self.record_context.close()
        self.record_context = None

    # ---------------------------
    # STOP VED EXCEPTION
    # ---------------------------
    async def stop_recording_on_error(self):
        """
        Bruges ved fejl:
        - Video er vigtigst
        - Ingen tracing.stop (kan give 0 KB video)
        """
        if not self.record_context:
            return

        await self.record_context.close()
        self.record_context = None

    # ---------------------------
    # AUTO STOP
    # ---------------------------
    async def _auto_stop(self, seconds: int):
        try:
            await asyncio.sleep(seconds)
            await self.stop_recording_clean("auto_timeout")
        except asyncio.CancelledError:
            pass