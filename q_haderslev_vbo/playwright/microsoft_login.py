"""Fælles og robust Microsoft-login via en eksisterende Playwright-side.

Modulet ejer ikke browser, context eller page og bruger ikke BrowserSession.
Den kaldende kode opretter en Playwright Page og sender den til
login_via_microsoft().

I normal drift kan login hentes fra en Automation Server credential.
I lokale tests kan email og password sendes direkte.
"""

from __future__ import annotations

import logging
from time import monotonic
from typing import Any

from automation_server_client import AutomationServer, Credential
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

MICROSOFT_LOGIN_HOSTS = (
    "login.microsoftonline.com",
    "login.live.com",
)

USERNAME_SELECTORS = (
    'input#i0116[name="loginfmt"]',
    'input[name="loginfmt"][type="email"]',
    'input[type="email"][autocomplete*="username"]',
    'input[placeholder="Mail eller telefon"]',
    'input[aria-label*="mailadresse"]',
)
PASSWORD_SELECTORS = (
    'input#i0118[name="passwd"]',
    'input[name="passwd"][type="password"]',
    'input[type="password"][autocomplete="current-password"]',
    'input[placeholder="Adgangskode"]',
)
SUBMIT_SELECTOR = 'input#idSIButton9[type="submit"]'
LOGIN_ERROR_SELECTOR = (
    "#usernameError:visible, #passwordError:visible, "
    "#service_exception_message:visible, #errorText:visible"
)

DEFAULT_ACTION_TIMEOUT_MS = 45_000
DEFAULT_LOGIN_TIMEOUT_MS = 180_000
DEFAULT_POLL_INTERVAL_MS = 250
DEFAULT_STABLE_TIME_MS = 750
DEFAULT_INPUT_ATTEMPTS = 8


class MicrosoftLoginError(RuntimeError):
    """Fejl under automatisk Microsoft-login."""


def is_microsoft_login_url(page: Page) -> bool:
    """Returnerer True, når siden er en kendt Microsoft-login-side."""
    if page.is_closed():
        return False
    current_url = page.url.casefold()
    return any(host in current_url for host in MICROSOFT_LOGIN_HOSTS)


async def login_via_microsoft(
    page: Page,
    credential_name: str | None = None,
    *,
    email: str | None = None,
    password: str | None = None,
    action_timeout_ms: int = DEFAULT_ACTION_TIMEOUT_MS,
    login_timeout_ms: int = DEFAULT_LOGIN_TIMEOUT_MS,
    poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS,
) -> None:
    """Logger ind på Microsoft via en eksisterende Playwright-side.

    Normal drift:
        Angiv credential_name. Login hentes fra Automation Server.

    Lokal test:
        Angiv både email og password. Automation Server kaldes ikke.

    Output:
        Ingen returværdi. Ved succes er siden redirected væk fra login.
    """
    _validate_inputs(
        page=page,
        credential_name=credential_name,
        email=email,
        password=password,
        action_timeout_ms=action_timeout_ms,
        login_timeout_ms=login_timeout_ms,
        poll_interval_ms=poll_interval_ms,
    )

    resolved_email, resolved_password = _resolve_credentials(
        credential_name=credential_name,
        email=email,
        password=password,
    )

    try:
        login_state = await _wait_for_login_state(
            page=page,
            timeout_ms=action_timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )

        if login_state == "redirected":
            logger.info(
                "Microsoft-login er ikke nødvendigt. Aktuel URL: %s",
                page.url,
            )
            return

        logger.info("Microsoft-loginformularen er synlig og klar.")

        await _fill_email_and_continue(
            page=page,
            email=resolved_email,
            timeout_ms=action_timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )
        await _fill_password_and_sign_in(
            page=page,
            password=resolved_password,
            timeout_ms=action_timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )
        await _handle_stay_signed_in_if_present(
            page=page,
            timeout_ms=action_timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )
        await _wait_until_login_redirect_is_complete(
            page=page,
            timeout_ms=login_timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )

        logger.info(
            "Microsoft-login blev gennemført. Aktuel URL: %s",
            page.url,
        )

    except MicrosoftLoginError:
        raise
    except (PlaywrightTimeoutError, PlaywrightError) as error:
        raise MicrosoftLoginError(
            "Microsoft-login fejlede: "
            f"{type(error).__name__}: {error}. Aktuel URL: {page.url}"
        ) from error


async def _wait_for_login_state(
    page: Page,
    timeout_ms: int,
    poll_interval_ms: int,
) -> str:
    """Venter på synligt mailfelt eller et færdigt redirect.

    Output:
        "username" når mailfeltet er synligt.
        "redirected" når siden stabilt har forladt Microsoft-login.
    """
    deadline = monotonic() + timeout_ms / 1000
    non_login_since: float | None = None

    while monotonic() < deadline:
        _ensure_page_open(page)

        username = await _first_visible_locator(
            page=page,
            selectors=USERNAME_SELECTORS,
        )
        if username is not None:
            await _wait_until_locator_is_stable(
                locator=username,
                stable_time_ms=DEFAULT_STABLE_TIME_MS,
                timeout_ms=min(timeout_ms, 10_000),
                poll_interval_ms=poll_interval_ms,
            )
            return "username"

        if is_microsoft_login_url(page):
            non_login_since = None
        else:
            if non_login_since is None:
                non_login_since = monotonic()
            elif monotonic() - non_login_since >= 2:
                return "redirected"

        visible_error = await _read_visible_login_error(page)
        if visible_error:
            raise MicrosoftLoginError(
                f"Microsoft viste en loginfejl: {visible_error}"
            )

        await page.wait_for_timeout(poll_interval_ms)

    raise MicrosoftLoginError(
        "Microsofts mailfelt blev ikke synligt inden timeout. "
        f"Aktuel URL: {page.url}"
    )


async def _fill_email_and_continue(
    page: Page,
    email: str,
    timeout_ms: int,
    poll_interval_ms: int,
) -> None:
    """Venter på et stabilt mailfelt, udfylder og verificerer værdien."""
    await _fill_input_robustly(
        page=page,
        selectors=USERNAME_SELECTORS,
        value=email,
        field_name="Mail eller telefon",
        timeout_ms=timeout_ms,
        poll_interval_ms=poll_interval_ms,
        secret=False,
    )

    logger.info("Mailadressen blev indsat og verificeret.")

    await _click_submit_with_value(
        page=page,
        expected_values=("Næste", "Next"),
        timeout_ms=timeout_ms,
        poll_interval_ms=poll_interval_ms,
    )


async def _fill_password_and_sign_in(
    page: Page,
    password: str,
    timeout_ms: int,
    poll_interval_ms: int,
) -> None:
    """Venter på et stabilt adgangskodefelt, udfylder og klikker Log på."""
    await _fill_input_robustly(
        page=page,
        selectors=PASSWORD_SELECTORS,
        value=password,
        field_name="Adgangskode",
        timeout_ms=timeout_ms,
        poll_interval_ms=poll_interval_ms,
        secret=True,
    )

    logger.info("Adgangskoden blev indsat og verificeret.")

    await _click_submit_with_value(
        page=page,
        expected_values=("Log på", "Sign in"),
        timeout_ms=timeout_ms,
        poll_interval_ms=poll_interval_ms,
    )


async def _fill_input_robustly(
    page: Page,
    selectors: tuple[str, ...],
    value: str,
    field_name: str,
    timeout_ms: int,
    poll_interval_ms: int,
    secret: bool,
) -> None:
    """Udfylder et dynamisk inputfelt med synligheds- og stabilitetskontrol.

    Der oprettes en ny locator ved hvert forsøg. Det håndterer, at Microsoft
    udskifter inputelementet under indlæsningen.
    """
    deadline = monotonic() + timeout_ms / 1000
    last_error: Exception | None = None

    for attempt in range(1, DEFAULT_INPUT_ATTEMPTS + 1):
        remaining_ms = int(max(0, deadline - monotonic()) * 1000)
        if remaining_ms <= 0:
            break

        _ensure_page_open(page)

        try:
            locator = await _wait_for_visible_locator(
                page=page,
                selectors=selectors,
                timeout_ms=remaining_ms,
                poll_interval_ms=poll_interval_ms,
                field_name=field_name,
            )
            await _wait_until_locator_is_stable(
                locator=locator,
                stable_time_ms=DEFAULT_STABLE_TIME_MS,
                timeout_ms=min(remaining_ms, 10_000),
                poll_interval_ms=poll_interval_ms,
            )

            # fill() udløser de input-events, Microsoft normalt forventer.
            await locator.fill(value, timeout=min(remaining_ms, 10_000))

            if await _input_has_expected_value(locator, value):
                # Værdien skal stadig være der efter en kort DOM-ro.
                await page.wait_for_timeout(DEFAULT_STABLE_TIME_MS)
                fresh_locator = await _first_visible_locator(
                    page=page,
                    selectors=selectors,
                )
                if (
                    fresh_locator is not None
                    and await _input_has_expected_value(fresh_locator, value)
                ):
                    return

            # Fallback til native value-setter for Knockout-bundne felter.
            fresh_locator = await _wait_for_visible_locator(
                page=page,
                selectors=selectors,
                timeout_ms=min(remaining_ms, 10_000),
                poll_interval_ms=poll_interval_ms,
                field_name=field_name,
            )
            await _set_input_value_natively(
                locator=fresh_locator,
                value=value,
            )
            await page.wait_for_timeout(DEFAULT_STABLE_TIME_MS)

            final_locator = await _first_visible_locator(
                page=page,
                selectors=selectors,
            )
            if (
                final_locator is not None
                and await _input_has_expected_value(final_locator, value)
            ):
                return

            visible_length = 0 if secret else len(value)
            raise MicrosoftLoginError(
                f"Feltet {field_name!r} bevarede ikke den indsatte værdi. "
                f"Forventet længde: {len(value) if secret else visible_length}."
            )

        except MicrosoftLoginError as error:
            last_error = error
        except (PlaywrightTimeoutError, PlaywrightError) as error:
            last_error = error

        logger.warning(
            "Feltet %s blev ændret eller udskiftet på forsøg %s af %s. "
            "Prøver igen med en frisk locator.",
            field_name,
            attempt,
            DEFAULT_INPUT_ATTEMPTS,
        )
        await page.wait_for_timeout(poll_interval_ms)

    raise MicrosoftLoginError(
        f"Feltet {field_name!r} kunne ikke udfyldes stabilt efter "
        f"{DEFAULT_INPUT_ATTEMPTS} forsøg. Aktuel URL: {page.url}"
    ) from last_error


async def _wait_for_visible_locator(
    page: Page,
    selectors: tuple[str, ...],
    timeout_ms: int,
    poll_interval_ms: int,
    field_name: str,
) -> Locator:
    """Venter eksplicit på den første synlige locator."""
    deadline = monotonic() + timeout_ms / 1000

    while monotonic() < deadline:
        _ensure_page_open(page)

        locator = await _first_visible_locator(
            page=page,
            selectors=selectors,
        )
        if locator is not None:
            return locator

        visible_error = await _read_visible_login_error(page)
        if visible_error:
            raise MicrosoftLoginError(
                f"Microsoft viste en fejl før feltet {field_name!r}: "
                f"{visible_error}"
            )

        await page.wait_for_timeout(poll_interval_ms)

    raise MicrosoftLoginError(
        f"Feltet {field_name!r} blev ikke synligt inden timeout. "
        f"Aktuel URL: {page.url}"
    )


async def _first_visible_locator(
    page: Page,
    selectors: tuple[str, ...],
) -> Locator | None:
    """Returnerer en frisk locator til det første synlige match."""
    for selector in selectors:
        candidates = page.locator(selector)

        try:
            count = await candidates.count()
        except PlaywrightError:
            continue

        for index in range(count):
            candidate = candidates.nth(index)
            try:
                if await candidate.is_visible() and await candidate.is_enabled():
                    return candidate
            except PlaywrightError:
                continue

    return None


async def _wait_until_locator_is_stable(
    locator: Locator,
    stable_time_ms: int,
    timeout_ms: int,
    poll_interval_ms: int,
) -> None:
    """Venter på at samme element er attached, synligt og geometrisk stabilt."""
    deadline = monotonic() + timeout_ms / 1000
    stable_since: float | None = None
    previous_box: dict[str, float] | None = None

    while monotonic() < deadline:
        try:
            if not await locator.is_visible() or not await locator.is_enabled():
                stable_since = None
                previous_box = None
            else:
                box = await locator.bounding_box()
                if box is None:
                    stable_since = None
                    previous_box = None
                elif previous_box == box:
                    if stable_since is None:
                        stable_since = monotonic()
                    elif monotonic() - stable_since >= stable_time_ms / 1000:
                        return
                else:
                    previous_box = box
                    stable_since = monotonic()
        except PlaywrightError as error:
            raise MicrosoftLoginError(
                "Microsoft udskiftede inputelementet, mens stabilitet blev kontrolleret."
            ) from error

        await locator.page.wait_for_timeout(poll_interval_ms)

    raise MicrosoftLoginError(
        "Inputelementet blev ikke stabilt inden timeout."
    )


async def _input_has_expected_value(
    locator: Locator,
    expected_value: str,
) -> bool:
    """Kontrollerer værdien uden at logge indholdet."""
    try:
        actual_value = await locator.input_value(timeout=5_000)
        return actual_value == expected_value
    except (PlaywrightTimeoutError, PlaywrightError):
        return False


async def _set_input_value_natively(
    locator: Locator,
    value: str,
) -> None:
    """Sætter inputværdi via browserens native value-setter og events."""
    await locator.evaluate(
        """
        (element, value) => {
            const descriptor = Object.getOwnPropertyDescriptor(
                HTMLInputElement.prototype,
                'value'
            );
            if (!descriptor || !descriptor.set) {
                throw new Error('Native value-setter blev ikke fundet.');
            }
            descriptor.set.call(element, value);
            element.dispatchEvent(new InputEvent('input', {
                bubbles: true,
                inputType: 'insertText',
                data: value
            }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
            element.dispatchEvent(new Event('blur', { bubbles: true }));
        }
        """,
        value,
    )


async def _click_submit_with_value(
    page: Page,
    expected_values: tuple[str, ...],
    timeout_ms: int,
    poll_interval_ms: int,
) -> None:
    """Venter på en synlig og aktiv submitknap og klikker robust."""
    deadline = monotonic() + timeout_ms / 1000
    selectors = tuple(
        f'{SUBMIT_SELECTOR}[value="{value}"]'
        for value in expected_values
    ) + (SUBMIT_SELECTOR,)
    last_error: Exception | None = None

    while monotonic() < deadline:
        button = await _first_visible_locator(
            page=page,
            selectors=selectors,
        )
        if button is None:
            await page.wait_for_timeout(poll_interval_ms)
            continue

        try:
            await _wait_until_locator_is_stable(
                locator=button,
                stable_time_ms=500,
                timeout_ms=min(10_000, timeout_ms),
                poll_interval_ms=poll_interval_ms,
            )
            await button.click(timeout=10_000)
            return
        except (MicrosoftLoginError, PlaywrightTimeoutError, PlaywrightError) as error:
            last_error = error
            await page.wait_for_timeout(poll_interval_ms)

    raise MicrosoftLoginError(
        "Microsoft-submitknappen blev ikke synlig og klikbar. "
        f"Forventede værdier: {expected_values!r}."
    ) from last_error


async def _handle_stay_signed_in_if_present(
    page: Page,
    timeout_ms: int,
    poll_interval_ms: int,
) -> None:
    """Håndterer valgfrit 'Forbliv logget på?'-trin."""
    deadline = monotonic() + min(timeout_ms, 10_000) / 1000
    selectors = (
        f'{SUBMIT_SELECTOR}[value="Ja"]',
        f'{SUBMIT_SELECTOR}[value="Yes"]',
    )

    while monotonic() < deadline:
        if not is_microsoft_login_url(page):
            return

        button = await _first_visible_locator(
            page=page,
            selectors=selectors,
        )
        if button is not None:
            try:
                await button.click(timeout=5_000)
                return
            except PlaywrightError:
                pass

        password = await _first_visible_locator(
            page=page,
            selectors=PASSWORD_SELECTORS,
        )
        if password is not None:
            return

        await page.wait_for_timeout(poll_interval_ms)


async def _wait_until_login_redirect_is_complete(
    page: Page,
    timeout_ms: int,
    poll_interval_ms: int,
) -> None:
    """Venter på stabilt redirect væk fra Microsofts login-domæne."""
    deadline = monotonic() + timeout_ms / 1000
    redirected_since: float | None = None

    while monotonic() < deadline:
        _ensure_page_open(page)

        visible_error = await _read_visible_login_error(page)
        if visible_error:
            raise MicrosoftLoginError(
                f"Microsoft afviste login: {visible_error}"
            )

        if is_microsoft_login_url(page):
            redirected_since = None
        else:
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
                return

        await page.wait_for_timeout(poll_interval_ms)

    raise MicrosoftLoginError(
        "Microsoft-login blev ikke afsluttet inden timeout. "
        f"Aktuel URL: {page.url}"
    )


async def _read_visible_login_error(page: Page) -> str:
    """Returnerer første synlige fejltekst fra Microsoft-login."""
    try:
        errors = page.locator(LOGIN_ERROR_SELECTOR)
        for index in range(await errors.count()):
            candidate = errors.nth(index)
            if await candidate.is_visible():
                text = " ".join((await candidate.inner_text()).split())
                if text:
                    return text
    except PlaywrightError:
        return ""
    return ""


def _ensure_page_open(page: Page) -> None:
    """Fejler tydeligt, hvis browserfanen er lukket."""
    if page.is_closed():
        raise MicrosoftLoginError(
            "Browserfanen blev lukket under Microsoft-login."
        )


def _resolve_credentials(
    *,
    credential_name: str | None,
    email: str | None,
    password: str | None,
) -> tuple[str, str]:
    """Vælger direkte login eller Automation Server credential."""
    direct_email = str(email or "").strip()
    direct_password = str(password or "")

    if direct_email or direct_password:
        if not direct_email:
            raise MicrosoftLoginError("email mangler ved direkte login.")
        if not direct_password:
            raise MicrosoftLoginError("password mangler ved direkte login.")
        return direct_email, direct_password

    normalized_name = str(credential_name or "").strip()
    if not normalized_name:
        raise MicrosoftLoginError(
            "Angiv credential_name eller både email og password."
        )
    return _get_credentials(normalized_name)


def _get_credentials(credential_name: str) -> tuple[str, str]:
    """Henter Microsoft-login fra Automation Server."""
    try:
        AutomationServer.from_environment()
        credential = Credential.get_credential(credential_name)
    except Exception as error:
        raise MicrosoftLoginError(
            f"Credentialen {credential_name!r} kunne ikke hentes "
            "fra Automation Server."
        ) from error

    data: Any = credential.data
    data_dict = data if isinstance(data, dict) else {}
    email = str(
        getattr(credential, "username", "")
        or data_dict.get("mail")
        or data_dict.get("email")
        or ""
    ).strip()
    password = str(
        getattr(credential, "password", "")
        or data_dict.get("password")
        or ""
    )

    if not email:
        raise MicrosoftLoginError(
            f"Credentialen {credential_name!r} mangler mailadresse."
        )
    if not password:
        raise MicrosoftLoginError(
            f"Credentialen {credential_name!r} mangler password."
        )
    return email, password


def _validate_inputs(
    *,
    page: Page,
    credential_name: str | None,
    email: str | None,
    password: str | None,
    action_timeout_ms: int,
    login_timeout_ms: int,
    poll_interval_ms: int,
) -> None:
    """Validerer loginfunktionens input."""
    if page is None or page.is_closed():
        raise MicrosoftLoginError("En åben Playwright-side skal angives.")

    has_name = bool(isinstance(credential_name, str) and credential_name.strip())
    has_email = bool(isinstance(email, str) and email.strip())
    has_password = bool(isinstance(password, str) and password)

    if not has_name and not (has_email and has_password):
        raise MicrosoftLoginError(
            "Angiv credential_name eller både email og password."
        )

    for name, value in (
        ("action_timeout_ms", action_timeout_ms),
        ("login_timeout_ms", login_timeout_ms),
        ("poll_interval_ms", poll_interval_ms),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise MicrosoftLoginError(
                f"{name} skal være et positivt heltal."
            )


__all__ = [
    "MicrosoftLoginError",
    "is_microsoft_login_url",
    "login_via_microsoft",
]
