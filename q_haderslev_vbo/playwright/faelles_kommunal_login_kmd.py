"""Fælles og robust loginvalg til KMD Insight.

Modulet ejer ikke browser, context eller page.

Den kaldende proces skal:
1. Hente HTTP-credentials med get_kmd_http_credentials().
2. Oprette BrowserSession med disse HTTP-credentials.
3. Oprette en Playwright Page.
4. Kalde login_via_faelles_kommunal_kmd().
"""

from __future__ import annotations

import logging
from time import monotonic
from typing import Any

from automation_server_client import AutomationServer, Credential
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from q_haderslev_vbo.playwright.browser_session import HttpCredentials


logger = logging.getLogger(__name__)


KMD_INSIGHT_URL = "https://insight.kmd.dk/BO/BI"

HADERSLEV_KOMMUNE_NAVN = "Haderslev Kommune - AD"

HADERSLEV_KOMMUNE_ADFS = (
    "http://adfs3.udcit.dk/adfs/services/trust"
)

FORVENTET_BRUGERNAVN = "DIRXLIS"

NAVIGATION_TIMEOUT_MS = 120_000
ACTION_TIMEOUT_MS = 60_000
REDIRECT_TIMEOUT_MS = 180_000
POLL_INTERVAL_MS = 500


class KmdInsightLoginError(RuntimeError):
    """Fejl under valg af kommune eller login til KMD Insight."""


def get_kmd_http_credentials(
    credential_name: str,
    expected_username: str = FORVENTET_BRUGERNAVN,
) -> HttpCredentials:
    """Henter KMD-login fra en Automation Server-credential.

    Returnerer et dictionary, som kan sendes direkte til
    BrowserSession(http_credentials=...).
    """
    normalized_credential_name = str(credential_name or "").strip()

    if not normalized_credential_name:
        raise KmdInsightLoginError(
            "credential_name skal angives."
        )

    try:
        AutomationServer.from_environment()
        credential = Credential.get_credential(
            normalized_credential_name
        )
    except Exception as error:
        raise KmdInsightLoginError(
            f"Credentialen {normalized_credential_name!r} "
            "kunne ikke hentes fra Automation Server."
        ) from error

    data: Any = credential.data
    data_dict = data if isinstance(data, dict) else {}

    username = str(
        getattr(credential, "username", "")
        or data_dict.get("username")
        or data_dict.get("user")
        or ""
    ).strip()

    password = str(
        getattr(credential, "password", "")
        or data_dict.get("password")
        or ""
    )

    if not username:
        raise KmdInsightLoginError(
            f"Credentialen {normalized_credential_name!r} "
            "mangler brugernavn."
        )

    if not password:
        raise KmdInsightLoginError(
            f"Credentialen {normalized_credential_name!r} "
            "mangler adgangskode."
        )

    normalized_expected_username = str(
        expected_username or ""
    ).strip()

    if (
        normalized_expected_username
        and username.casefold()
        != normalized_expected_username.casefold()
    ):
        raise KmdInsightLoginError(
            f"Credentialen {normalized_credential_name!r} bruger "
            f"{username!r}, men KMD Insight kræver "
            f"{normalized_expected_username!r}."
        )

    return {
        "username": username,
        "password": password,
    }


async def login_via_faelles_kommunal_kmd(
    page: Page,
    session=None,
    start_url: str = KMD_INSIGHT_URL,
    kommune_navn: str = HADERSLEV_KOMMUNE_NAVN,
    kommune_adfs: str = HADERSLEV_KOMMUNE_ADFS,
    navigation_timeout_ms: int = NAVIGATION_TIMEOUT_MS,
    action_timeout_ms: int = ACTION_TIMEOUT_MS,
    redirect_timeout_ms: int = REDIRECT_TIMEOUT_MS,
    poll_interval_ms: int = POLL_INTERVAL_MS,
) -> None:
    """Vælger kommune og starter login til KMD Insight.

    Ved succes befinder den eksisterende Playwright-side sig på den
    side, KMD viderestiller til efter kommunevalget.
    """
    _validate_login_inputs(
        page=page,
        start_url=start_url,
        kommune_navn=kommune_navn,
        kommune_adfs=kommune_adfs,
        navigation_timeout_ms=navigation_timeout_ms,
        action_timeout_ms=action_timeout_ms,
        redirect_timeout_ms=redirect_timeout_ms,
        poll_interval_ms=poll_interval_ms,
    )

    page.set_default_timeout(action_timeout_ms)
    page.set_default_navigation_timeout(
        navigation_timeout_ms
    )

    logger.info(
        "Åbner KMD Insight og vælger kommunen %s.",
        kommune_navn,
    )

    try:
        await page.goto(
            start_url,
            wait_until="domcontentloaded",
            timeout=navigation_timeout_ms,
        )

        await _take_screenshot(
            session=session,
            page=page,
            name="KMD_Insight_foer_kommunevalg",
        )

        login_side_url = page.url

        await _vaelg_kommune(
            page=page,
            kommune_navn=kommune_navn,
            kommune_adfs=kommune_adfs,
            action_timeout_ms=action_timeout_ms,
        )

        await _take_screenshot(
            session=session,
            page=page,
            name="KMD_Insight_kommune_valgt",
        )

        await _klik_login(
            page=page,
            action_timeout_ms=action_timeout_ms,
        )

        logger.info(
            "Kommune er valgt. Venter på viderestilling fra KMD."
        )

        await _wait_for_login_redirect(
            page=page,
            login_side_url=login_side_url,
            timeout_ms=redirect_timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )

        await _take_screenshot(
            session=session,
            page=page,
            name="KMD_Insight_efter_login",
        )

        logger.info(
            "KMD Insight-login blev gennemført. Aktuel URL: %s",
            page.url,
        )

    except KmdInsightLoginError:
        await _take_screenshot(
            session=session,
            page=page,
            name="FEJL_KMD_Insight_login",
        )
        raise

    except PlaywrightTimeoutError as error:
        await _take_screenshot(
            session=session,
            page=page,
            name="FEJL_KMD_Insight_timeout",
        )
        raise KmdInsightLoginError(
            "KMD Insight-login overskred den tilladte ventetid. "
            f"Aktuel URL: {page.url}"
        ) from error

    except PlaywrightError as error:
        await _take_screenshot(
            session=session,
            page=page,
            name="FEJL_KMD_Insight_Playwright",
        )
        raise KmdInsightLoginError(
            "Playwright fejlede under KMD Insight-login. "
            f"Aktuel URL: {page.url}"
        ) from error


async def _vaelg_kommune(
    page: Page,
    kommune_navn: str,
    kommune_adfs: str,
    action_timeout_ms: int,
) -> None:
    """Skriver kommunen i Choices.js-feltet og vælger resultatet.

    Output:
        Funktionen returnerer ikke noget.

        Ved succes er den ønskede kommune valgt i KMD-feltet.
        Log-in-knappen klikkes efterfølgende af _klik_login().
    """
    choices_container = page.locator(".choices").first

    try:
        await choices_container.wait_for(
            state="visible",
            timeout=action_timeout_ms,
        )
    except PlaywrightTimeoutError as error:
        raise KmdInsightLoginError(
            "Kommunefeltet blev ikke fundet på KMD-siden."
        ) from error

    logger.info(
        "Åbner kommunefeltet og søger efter %s.",
        kommune_navn,
    )

    await choices_container.click()

    search_input = choices_container.locator(
        'input.choices__input, '
        'input[type="search"], '
        'input[type="text"]'
    ).last

    try:
        await search_input.wait_for(
            state="visible",
            timeout=action_timeout_ms,
        )

        await search_input.fill("Haderslev Kommune")

    except PlaywrightTimeoutError as error:
        raise KmdInsightLoginError(
            "Søgefeltet i kommunedropdownen blev ikke fundet."
        ) from error

    kommune_option = page.get_by_role(
        "option",
        name=kommune_navn,
        exact=True,
    ).last

    try:
        await kommune_option.wait_for(
            state="visible",
            timeout=action_timeout_ms,
        )

        await kommune_option.click()

    except PlaywrightTimeoutError as error:
        raise KmdInsightLoginError(
            f"Kommunen {kommune_navn!r} blev ikke fundet, "
            "efter der blev skrevet 'Haderslev Kommune' i feltet."
        ) from error

    valgt_kommune = page.locator(
        ".choices__item[data-item]",
        has_text=kommune_navn,
    ).first

    try:
        await valgt_kommune.wait_for(
            state="visible",
            timeout=action_timeout_ms,
        )
    except PlaywrightTimeoutError as error:
        raise KmdInsightLoginError(
            f"KMD-feltet viste ikke {kommune_navn!r} "
            "efter kommunevalget."
        ) from error

    logger.info(
        "Kommunen %s er valgt i KMD-feltet.",
        kommune_navn,
    )

async def _wait_for_selected_kommune(
    choices_container,
    kommune_navn: str,
    kommune_adfs: str,
    timeout_ms: int,
) -> None:
    """Kontrollerer den valgte værdi i Choices.js-komponenten.

    Output:
        Funktionen returnerer, når kommunens navn eller ADFS-værdi
        findes på det synlige data-item i Choices.js-feltet.
    """
    selected_item = choices_container.locator(
        ".choices__inner .choices__item[data-item]"
    ).first

    deadline = monotonic() + timeout_ms / 1000

    while monotonic() < deadline:
        try:
            if (
                await selected_item.count() > 0
                and await selected_item.is_visible()
            ):
                selected_text = (
                    await selected_item.inner_text()
                ).strip()

                selected_value = (
                    await selected_item.get_attribute(
                        "data-value"
                    )
                    or ""
                ).strip()

                korrekt_tekst = (
                    selected_text.casefold()
                    == kommune_navn.casefold()
                )

                korrekt_value = (
                    selected_value == kommune_adfs
                )

                if korrekt_tekst or korrekt_value:
                    logger.info(
                        "Choices.js viser nu: tekst=%r, value=%r.",
                        selected_text,
                        selected_value,
                    )
                    return

        except PlaywrightError:
            pass

        await choices_container.page.wait_for_timeout(250)

    current_text = ""
    current_value = ""

    try:
        if await selected_item.count() > 0:
            current_text = (
                await selected_item.inner_text()
            ).strip()

            current_value = (
                await selected_item.get_attribute(
                    "data-value"
                )
                or ""
            ).strip()
    except PlaywrightError:
        pass

    raise KmdInsightLoginError(
        f"KMD-dropdownen blev ikke ændret til {kommune_navn!r}. "
        f"Feltet viser stadig tekst={current_text!r}, "
        f"value={current_value!r}."
    )

async def _wait_for_selected_kommune(
    page: Page,
    kommune_navn: str,
    kommune_adfs: str,
    timeout_ms: int,
) -> None:
    """Kontrollerer, at Choices.js viser den valgte kommune."""
    selected_by_value = page.locator(
        ".choices__item[data-item]"
        f'[data-value="{kommune_adfs}"]'
    ).first

    selected_by_text = page.locator(
        ".choices__item[data-item]",
        has_text=kommune_navn,
    ).first

    deadline = monotonic() + timeout_ms / 1000

    while monotonic() < deadline:
        _ensure_page_open(page)

        for selected_item in (
            selected_by_value,
            selected_by_text,
        ):
            try:
                if (
                    await selected_item.count() > 0
                    and await selected_item.is_visible()
                ):
                    return
            except PlaywrightError:
                continue

        await page.wait_for_timeout(250)

    raise KmdInsightLoginError(
        f"KMD-dropdownen bekræftede ikke valget af "
        f"{kommune_navn!r}."
    )


async def _klik_login(
    page: Page,
    action_timeout_ms: int,
) -> None:
    """Finder og klikker på KMD-sidens Log-in-knap."""
    login_button = page.get_by_role(
        "button",
        name="Log-in",
        exact=True,
    ).first

    if await login_button.count() == 0:
        login_button = page.get_by_role(
            "link",
            name="Log-in",
            exact=True,
        ).first

    if await login_button.count() == 0:
        login_button = page.locator(
            'button:has-text("Log-in"), '
            'input[type="submit"][value="Log-in"], '
            'a:has-text("Log-in")'
        ).first

    try:
        await login_button.wait_for(
            state="visible",
            timeout=action_timeout_ms,
        )
        await login_button.click()
    except PlaywrightTimeoutError as error:
        raise KmdInsightLoginError(
            "Log-in-knappen blev ikke fundet på KMD-siden."
        ) from error


async def _wait_for_login_redirect(
    page: Page,
    login_side_url: str,
    timeout_ms: int,
    poll_interval_ms: int,
) -> None:
    """Venter, indtil KMD har viderestillet væk fra login-siden."""
    deadline = monotonic() + timeout_ms / 1000
    redirected_since: float | None = None

    while monotonic() < deadline:
        _ensure_page_open(page)

        current_url = page.url

        if current_url and current_url != login_side_url:
            if redirected_since is None:
                redirected_since = monotonic()
            elif monotonic() - redirected_since >= 1:
                try:
                    await page.wait_for_load_state(
                        "domcontentloaded",
                        timeout=10_000,
                    )
                except PlaywrightTimeoutError:
                    pass

                logger.info(
                    "KMD viderestillede til %s.",
                    current_url,
                )
                return
        else:
            redirected_since = None

        await page.wait_for_timeout(poll_interval_ms)

    raise KmdInsightLoginError(
        "KMD afsluttede ikke viderestillingen inden timeout. "
        f"Aktuel URL: {page.url}"
    )


async def _take_screenshot(
    session,
    page: Page,
    name: str,
) -> None:
    """Tager screenshot, hvis BrowserSession har en recorder."""
    if session is None:
        return

    recorder = getattr(session, "recorder", None)

    if recorder is None:
        return

    try:
        await recorder.screenshot(
            page,
            name,
        )
    except Exception as error:
        logger.warning(
            "Screenshot %s kunne ikke gemmes: %s",
            name,
            error,
        )


def _ensure_page_open(page: Page) -> None:
    """Fejler tydeligt, hvis browserfanen er lukket."""
    if page.is_closed():
        raise KmdInsightLoginError(
            "Browserfanen blev lukket under KMD-login."
        )


def _validate_login_inputs(
    *,
    page: Page,
    start_url: str,
    kommune_navn: str,
    kommune_adfs: str,
    navigation_timeout_ms: int,
    action_timeout_ms: int,
    redirect_timeout_ms: int,
    poll_interval_ms: int,
) -> None:
    """Validerer input til KMD-loginfunktionen."""
    if page is None or page.is_closed():
        raise KmdInsightLoginError(
            "En åben Playwright-side skal angives."
        )

    if not str(start_url or "").startswith(
        ("https://", "http://")
    ):
        raise KmdInsightLoginError(
            "start_url skal begynde med http:// eller https://."
        )

    if not str(kommune_navn or "").strip():
        raise KmdInsightLoginError(
            "kommune_navn skal angives."
        )

    if not str(kommune_adfs or "").strip():
        raise KmdInsightLoginError(
            "kommune_adfs skal angives."
        )

    for name, value in (
        ("navigation_timeout_ms", navigation_timeout_ms),
        ("action_timeout_ms", action_timeout_ms),
        ("redirect_timeout_ms", redirect_timeout_ms),
        ("poll_interval_ms", poll_interval_ms),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value <= 0
        ):
            raise KmdInsightLoginError(
                f"{name} skal være et positivt heltal."
            )


__all__ = [
    "HADERSLEV_KOMMUNE_ADFS",
    "HADERSLEV_KOMMUNE_NAVN",
    "KMD_INSIGHT_URL",
    "KmdInsightLoginError",
    "get_kmd_http_credentials",
    "login_via_faelles_kommunal_kmd",
]