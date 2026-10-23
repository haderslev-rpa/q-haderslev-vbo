from datetime import datetime
import os
from pathlib import Path
import subprocess
from typing import TypedDict

from playwright.async_api import (
    BrowserContext,
    Page,
    async_playwright,
)

from q_haderslev_vbo.playwright.playwright_run_recorder import (
    PlaywrightRunRecorder,
)


class HttpCredentials(TypedDict):
    """
    Struktur for HTTP-loginoplysninger.

    Output:
        Bruges som input til BrowserSession.

    Eksempel:
        {
            "username": "brugernavn",
            "password": "adgangskode",
        }
    """

    username: str
    password: str


class BrowserSession:
    """
    BrowserSession er den fælles Playwright-browser-session.

    Ansvar:
    - Browser lifecycle
    - BrowserContext med eventuelle HTTP-credentials
    - Videooptagelse ved lokal debugging
    - Oprettelse og lukning af sider
    - Screenshots via PlaywrightRunRecorder
    - Metadata om proceskørslen

    HTTP-credentials:
        Hvis http_credentials bliver sendt med, anvendes oplysningerne,
        når Playwright opretter BrowserContext.

        Hvis http_credentials er None, bliver BrowserContext oprettet
        uden HTTP-loginoplysninger.
    """

    def __init__(
        self,
        headless: bool = True,
        debug: bool = False,
        video: bool = False,
        force_new: bool = False,
        http_credentials: HttpCredentials | None = None,
        use_regular_chromium: bool = False,
    ):
        """
        Opretter en BrowserSession.

        Args:
            headless:
                True starter browseren uden synligt vindue.
                False åbner et synligt browservindue.

            debug:
                Aktiverer lokal dokumentation såsom screenshots.

            video:
                Aktiverer video, når både debug og video er True.

            force_new:
                Bevares som indstilling til processer, der kræver
                en ny browsersession.

            http_credentials:
                Valgfrit dictionary med HTTP-brugernavn og adgangskode.

                Eksempel:
                    {
                        "username": "brugernavn",
                        "password": "adgangskode",
                    }

                Hvis værdien er None, sendes der ingen HTTP-credentials
                til Playwright.

            use_regular_chromium:
                False bevarer Playwrights normale valg af browser.
                True bruger den almindelige Chromium-executable.

        Output:
            Opretter et BrowserSession-objekt.

            Browseren startes først, når start() kaldes.
            BrowserContext oprettes først, når new_page() kaldes.
        """

        self.headless = headless
        self.debug = debug
        self.video = video
        self.force_new = force_new
        self.http_credentials = http_credentials
        self.use_regular_chromium = use_regular_chromium

        # Playwright
        self.pw = None
        self.browser = None
        self.context: BrowserContext | None = None

        # Metadata
        self.github_repo_name = None
        self.session_id = None
        self.run_timestamp = None
        self.run_name = None

        # Recorder bruges blandt andet til screenshots.
        self.recorder = None

    # -------------------------------------------------
    # START
    # -------------------------------------------------

    async def start(self) -> None:
        """
        Starter Playwright og Chromium.

        Output:
            Starter browseren, men opretter endnu ikke en side.

            BrowserContext bliver oprettet ved det første kald til
            new_page(). Det er dér eventuelle HTTP-credentials bliver
            sendt til Playwright.
        """

        if self.pw is not None or self.browser is not None:
            raise RuntimeError(
                "BrowserSession er allerede startet."
            )

        self.pw = await async_playwright().start()

        try:
            if self.use_regular_chromium:
                self.browser = await self.pw.chromium.launch(
                    headless=self.headless,
                    executable_path=(
                        self.pw.chromium.executable_path
                    ),
                    args=[
                        "--disable-infobars",
                        "--disable-notifications",
                        "--disable-extensions",
                    ],
                )
            else:
                self.browser = await self.pw.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--disable-infobars",
                        "--disable-notifications",
                        "--disable-extensions",
                    ],
                )

        except Exception:
            await self.pw.stop()
            self.pw = None
            raise

        self.github_repo_name = self._find_github_repo_name()
        self.session_id = self._find_session_id()
        self.run_timestamp = self._generate_timestamp()
        self.run_name = self._generate_run_name()

        self.recorder = PlaywrightRunRecorder(
            browser_session=self,
            debug=self.debug,
        )

    # -------------------------------------------------
    # NEW PAGE
    # -------------------------------------------------

    async def new_page(self) -> Page:
        """
        Opretter en ny Playwright-side med RPA-standardindstillinger.

        Output:
            Returnerer et Playwright Page-objekt.

            Den første gang funktionen kaldes, bliver BrowserContext
            oprettet. Hvis HTTP-credentials er angivet på sessionen,
            bliver credentials sendt med ved oprettelsen.

            Efterfølgende kald opretter nye sider i den samme context.
        """

        if self.browser is None:
            raise RuntimeError(
                "BrowserSession er ikke startet. "
                "Kald await session.start() før session.new_page()."
            )

        if self.context is None:
            run_dir = (
                Path("tests_local_playwright")
                / self.run_name
            )

            run_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            context_kwargs = {
                # Stabilt layout til RPA-processer.
                "viewport": {
                    "width": 1920,
                    "height": 1080,
                },
                # Undgå fejl fra interne SSL-certifikater.
                "ignore_https_errors": True,
                # Dansk brugergrænseflade, hvor det understøttes.
                "locale": "da-DK",
            }

            if self.debug and self.video:
                context_kwargs["record_video_dir"] = str(
                    run_dir
                )

            # HTTP-credentials kan kun angives, når contexten
            # oprettes. Hvis værdien er None, sendes intet med.
            if self.http_credentials is not None:
                self._validate_http_credentials(
                    self.http_credentials
                )

                context_kwargs["http_credentials"] = (
                    self.http_credentials
                )

            self.context = await self.browser.new_context(
                **context_kwargs
            )

        return await self.context.new_page()

    # -------------------------------------------------
    # SCREENSHOT
    # -------------------------------------------------

    async def screenshot(
        self,
        page: Page,
        name: str,
        always: bool = False,
    ) -> None:
        """
        Gemmer et screenshot via PlaywrightRunRecorder.

        Args:
            page:
                Den Playwright-side, der skal fotograferes.

            name:
                Navnet på screenshotet.

            always:
                Hvis True, forsøges screenshot gemt uafhængigt af den
                normale debug-indstilling.

        Output:
            Funktionen returnerer ikke et resultat.
            Screenshotet håndteres af PlaywrightRunRecorder.
        """

        if self.recorder:
            await self.recorder.screenshot(
                page,
                name,
                always=always,
            )

    # -------------------------------------------------
    # CLOSE PAGE
    # -------------------------------------------------

    async def close_page(
        self,
        page: Page,
    ) -> None:
        """
        Lukker én Playwright-side.

        Args:
            page:
                Den side, der skal lukkes.

        Output:
            Funktionen returnerer ikke et resultat.
            En allerede lukket side ignoreres.
        """

        if not page.is_closed():
            await page.close()

    # -------------------------------------------------
    # CLOSE OTHER TABS
    # -------------------------------------------------

    async def close_all_other_tabs(
        self,
        active_page: Page,
        print_log: bool = False,
    ) -> None:
        """
        Lukker alle faner undtagen den aktive side.

        Args:
            active_page:
                Den side, som skal forblive åben.

            print_log:
                Hvis True, udskrives antallet af faner før og efter.

        Output:
            Funktionen returnerer ikke et resultat.
        """

        if self.context is None:
            return

        if print_log:
            print(
                "[Playwright] Antal faner FØR cleanup: "
                f"{len(self.context.pages)}"
            )

        for page in self.context.pages:
            if (
                page != active_page
                and not page.is_closed()
            ):
                try:
                    await page.close()
                except Exception:
                    pass

        if print_log:
            print(
                "[Playwright] Antal faner EFTER cleanup: "
                f"{len(self.context.pages)}"
            )

    # -------------------------------------------------
    # CLOSE SESSION
    # -------------------------------------------------

    async def close(self) -> None:
        """
        Lukker BrowserContext, browser og Playwright.

        Output:
            Funktionen returnerer ikke et resultat.

            Hvis video er aktiveret, færdiggør Playwright videoen,
            når BrowserContext bliver lukket.
        """

        if self.context is not None:
            try:
                await self.context.close()
            finally:
                self.context = None

        if self.browser is not None:
            try:
                await self.browser.close()
            finally:
                self.browser = None

        if self.pw is not None:
            try:
                await self.pw.stop()
            finally:
                self.pw = None

    # -------------------------------------------------
    # VALIDATION
    # -------------------------------------------------

    @staticmethod
    def _validate_http_credentials(
        http_credentials: HttpCredentials,
    ) -> None:
        """
        Kontrollerer HTTP-loginoplysningerne.

        Args:
            http_credentials:
                Dictionary med username og password.

        Output:
            Funktionen returnerer ikke data, hvis begge værdier findes.

        Raises:
            ValueError:
                Hvis username eller password mangler.

        Sikkerhed:
            Loginoplysningerne bliver ikke udskrevet.
        """

        username = http_credentials.get("username")
        password = http_credentials.get("password")

        if not username:
            raise ValueError(
                "http_credentials mangler 'username'."
            )

        if not password:
            raise ValueError(
                "http_credentials mangler 'password'."
            )

    # -------------------------------------------------
    # HELPERS
    # -------------------------------------------------

    def _generate_timestamp(self) -> str:
        """
        Opretter tidspunktet for kørslen.

        Output:
            Returnerer et tidspunkt som tekst på formen:
            '08-09-2026 14-30'.
        """

        return datetime.now().strftime(
            "%d-%m-%Y %H-%M"
        )

    def _generate_run_name(self) -> str:
        """
        Opretter navnet på den aktuelle kørsel.

        Output:
            Returnerer tidspunkt og eventuelt automation session-id.
        """

        if self.session_id:
            return (
                f"{self.run_timestamp} "
                f"(session {self.session_id})"
            )

        return self.run_timestamp

    def _find_session_id(self) -> str | None:
        """
        Finder Automation Server-sessionens id.

        Output:
            Returnerer AUTOMATION_SESSION_ID fra miljøvariablerne.
            Returnerer None, hvis værdien ikke findes.
        """

        return os.getenv("AUTOMATION_SESSION_ID")

    def _find_github_repo_name(self) -> str:
        """
        Finder navnet på det aktuelle Git-repository.

        Output:
            Returnerer GITHUB_REPO_NAME, hvis miljøvariablen findes.

            Ellers forsøges repository-navnet fundet via Git.

            Returnerer 'local-debug', hvis det ikke kan findes.
        """

        env_name = os.getenv("GITHUB_REPO_NAME")

        if env_name:
            return env_name

        try:
            result = subprocess.check_output(
                [
                    "git",
                    "config",
                    "--get",
                    "remote.origin.url",
                ],
                stderr=subprocess.DEVNULL,
            ).decode().strip()

            return (
                result
                .split("/")[-1]
                .replace(".git", "")
            )

        except Exception:
            return "local-debug"
