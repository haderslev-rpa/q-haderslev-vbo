from pathlib import Path
from playwright.async_api import Page
from q_haderslev_vbo.automation_server.sharepoint.sp_api import get_client


class PlaywrightRunRecorder:
    """
    Simpel recorder (klasse – skabelon for objekt)

    Ansvar:
    - Screenshots (billeder)
    - Upload til SharePoint
    """

    BASE_PATH = Path("tests_local_playwright")

    def __init__(self, browser_session, debug: bool, always: bool = False):
        self.browser_session = browser_session
        self.debug = debug
        self.always = always  # global force
        self.run_dir = None

        # SharePoint state (cache – midlertidig lagring)
        self._sp_initialized = False
        self._sp_drive_id = None
        self._sp_folder_path = None

    # -------------------------------------------------
    # LOCAL FOLDER
    # -------------------------------------------------
    def _ensure_run_dir(self):
        if self.run_dir:
            return

        self.run_dir = self.BASE_PATH / self.browser_session.run_name
        self.run_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------
    # SHAREPOINT HELPERS
    # -------------------------------------------------
    def _safe_create_folder(self, client, drive_id, parent, name):
        try:
            return client.create_folder(drive_id, parent, name)

        except Exception as e:
            msg = str(e)

            if "already exists" in msg or "409" in msg:
                print(f"ℹ️ Mappe findes allerede: {name}")
            else:
                print(f"⚠️ FEJL ved oprettelse af mappe '{name}': {e}")

            return None

    def _normalize_repo_name(self, name: str) -> str:
        if not name:
            return "unknown"

        return name.replace(".git", "").strip()

    def _init_sharepoint(self):
        if self._sp_initialized:
            return

        print("🔧 Initialiserer SharePoint...")

        client = get_client()
        site_name = "Automatisering"

        # 1. hent ids
        site_id = client.get_site_id(site_name)
        drive_id = client.get_drive_id(site_id)

        self._sp_drive_id = drive_id

        # 2. struktur
        base = "playwright_run_recorder"

        raw_repo = self.browser_session.github_repo_name or "unknown"
        repo = self._normalize_repo_name(raw_repo)

        run = (
            self.browser_session.run_timestamp
            .replace(":", "")
            .replace("/", "-")
        )

        print(f"📁 SharePoint struktur: {base}/{repo}/{run}")

        # opret mapper (hvis ikke findes)
        self._safe_create_folder(client, drive_id, base, repo)
        self._safe_create_folder(client, drive_id, f"{base}/{repo}", run)

        # gem path
        self._sp_folder_path = f"{base}/{repo}/{run}"

        self._sp_initialized = True

        print("✅ SharePoint klar")

    # -------------------------------------------------
    # SCREENSHOT
    # -------------------------------------------------
    async def screenshot(self, page: Page, name: str, always: bool = False):
        """
        Gemmer screenshot lokalt + uploader til SharePoint

        always = True → tager billede uanset debug
        """

        # ✅ NY LOGIK (det vigtigste)
        if not self.debug and not self.always and not always:
            return

        # lokal mappe
        self._ensure_run_dir()

        safe_name = name.replace(" ", "_").replace("/", "_")
        path = self.run_dir / f"{safe_name}.png"

        # 1. gem lokalt
        await page.screenshot(path=str(path), full_page=True)
        print("📸 Screenshot gemt lokalt:", path)

        # 2. upload
        try:
            self._init_sharepoint()

            client = get_client()

            with open(path, "rb") as f:
                client.upload_file(
                    self._sp_drive_id,
                    self._sp_folder_path,
                    f"{safe_name}.png",
                    f.read()
                )

            print("☁️ Uploaded til SharePoint:", safe_name)

        except Exception as e:
            print("⚠️ SharePoint upload fejlede:", e)