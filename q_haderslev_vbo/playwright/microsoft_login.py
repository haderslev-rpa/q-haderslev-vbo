"""Fælles Microsoft-login via Playwright.

Modulet ejer ikke browseren og bruger ikke BrowserSession. Den kaldende kode
opretter en Playwright Page og sender den til login_via_microsoft().

Login kan hentes fra en Automation Server credential i normal drift eller
sendes direkte som email/password i en lokal test.
"""

from __future__ import annotations

import logging
from typing import Any

from automation_server_client import AutomationServer, Credential
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

MICROSOFT_LOGIN_HOSTS = (
    "login.microsoftonline.com",
    "login.live.com",
)
USERNAME_SELECTOR = "input#i0116[name='loginfmt']"
PASSWORD_SELECTOR = "input#i0118[name='passwd']"
SUBMIT_SELECTOR = "input#idSIButton9[type='submit']"
LOGIN_ERROR_SELECTOR = (
    "#usernameError:visible, #passwordError:visible, "
    "#service_exception_message:visible, #errorText:visible"
)
DEFAULT_ACTION_TIMEOUT_MS = 30_000
DEFAULT_LOGIN_TIMEOUT_MS = 120_000
DEFAULT_POLL_INTERVAL_MS = 500


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
        Angiv credential_name. Mail og adgangskode hentes fra Automation Server.

    Lokal test:
        Angiv email og password direkte. Automation Server kaldes ikke.

    Funktionen starter eller lukker ikke browser, context eller page.
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

    page.set_default_timeout(action_timeout_ms)

    try:
        login_ready = await _wait_for_login_form_or_redirect(
            page=page,
            timeout_ms=action_timeout_ms,
        )

        if not login_ready:
            logger.info(
                "Microsoft-login er ikke nødvendigt. Aktuel URL: %s",
                page.url,
            )
            return

        logger.info("Microsoft-loginformularen er klar.")

        await _fill_email_and_continue(
            page=page,
            email=resolved_email,
            timeout_ms=action_timeout_ms,
        )
        await _fill_password_and_sign_in(
            page=page,
            password=resolved_password,
            timeout_ms=action_timeout_ms,
        )
        await _handle_stay_signed_in_if_present(
            page=page,
            timeout_ms=action_timeout_ms,
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
            f"{type(error).__name__}: {error}. "
            f"Aktuel URL: {page.url}"
        ) from error


async def _wait_for_login_form_or_redirect(
    page: Page,
    timeout_ms: int,
) -> bool:
    """Venter på loginfeltet eller på, at redirect ender uden login."""
    elapsed_ms = 0
    poll_interval_ms = 250

    while elapsed_ms < timeout_ms:
        if page.is_closed():
            raise MicrosoftLoginError(
                "Browserfanen blev lukket før Microsoft-login."
            )

        username = _username_locator(page)
        try:
            if await username.count() > 0 and await username.is_visible():
                return True
        except PlaywrightError:
            pass

        if not is_microsoft_login_url(page):
            # Redirect kan kortvarigt stå på Forms før Microsoft-loginloaderen.
            # Fortsæt lidt endnu, så loginfeltet får tid til at blive monteret.
            if elapsed_ms >= 2_000:
                return False

        await page.wait_for_timeout(poll_interval_ms)
        elapsed_ms += poll_interval_ms

    return False


def _username_locator(page: Page):
    """Returnerer en robust locator til Microsofts mailfelt."""
    return page.locator(
        'input#i0116[name="loginfmt"], '
        'input[type="email"][autocomplete*="username"], '
        'input[placeholder="Mail eller telefon"]'
    ).first


async def _fill_email_and_continue(
    page: Page,
    email: str,
    timeout_ms: int,
) -> None:
    """Udfylder mailfeltet, verificerer værdien og klikker Næste."""
    username = _username_locator(page)

    try:
        await username.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
    except PlaywrightTimeoutError as error:
        raise MicrosoftLoginError(
            "Microsoft-feltet 'Mail eller telefon' blev ikke synligt. "
            f"Aktuel URL: {page.url}"
        ) from error

    await username.scroll_into_view_if_needed()
    await username.click(timeout=timeout_ms)
    await username.fill(email, timeout=timeout_ms)

    inserted_value = (await username.input_value()).strip()

    if inserted_value != email:
        # Microsofts Knockout-binding kan i enkelte visninger overskrive fill().
        # Brug den native value-setter og udsend input/change-events som fallback.
        await username.evaluate(
            """
            (element, value) => {
                const descriptor = Object.getOwnPropertyDescriptor(
                    HTMLInputElement.prototype,
                    'value'
                );
                descriptor.set.call(element, value);
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));
            }
            """,
            email,
        )
        inserted_value = (await username.input_value()).strip()

    if inserted_value != email:
        raise MicrosoftLoginError(
            "Mailadressen blev ikke indsat i Microsoft-feltet. "
            f"Feltets aktuelle længde er {len(inserted_value)} tegn."
        )

    logger.info("Mailadressen blev indsat og verificeret.")

    await _click_submit_with_value(
        page=page,
        expected_values=("Næste", "Next"),
        timeout_ms=timeout_ms,
    )


async def _fill_password_and_sign_in(
    page: Page,
    password: str,
    timeout_ms: int,
) -> None:
    """Venter på adgangskodefeltet, udfylder det og klikker Log på."""
    password_input = page.locator(PASSWORD_SELECTOR)

    try:
        await password_input.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
    except PlaywrightTimeoutError as error:
        message = await _read_visible_login_error(page)
        suffix = f" Microsoft-fejl: {message}" if message else ""
        raise MicrosoftLoginError(
            "Microsoft-feltet 'Adgangskode' blev ikke synligt "
            "efter klik på Næste."
            + suffix
        ) from error

    await password_input.fill(password)

    await _click_submit_with_value(
        page=page,
        expected_values=("Log på", "Sign in"),
        timeout_ms=timeout_ms,
    )


async def _click_submit_with_value(
    page: Page,
    expected_values: tuple[str, ...],
    timeout_ms: int,
) -> None:
    """Klikker den synlige Microsoft-submitknap med forventet værdi."""
    for value in expected_values:
        candidate = page.locator(
            f'{SUBMIT_SELECTOR}[value="{value}"]'
        ).first

        try:
            await candidate.wait_for(
                state="visible",
                timeout=timeout_ms,
            )

            if await candidate.is_enabled():
                await candidate.click(timeout=timeout_ms)
                return
        except (PlaywrightTimeoutError, PlaywrightError):
            continue

    fallback = page.locator(SUBMIT_SELECTOR).first

    try:
        await fallback.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
        await fallback.click(timeout=timeout_ms)
    except (PlaywrightTimeoutError, PlaywrightError) as error:
        raise MicrosoftLoginError(
            "Microsoft-knappen blev ikke fundet eller kunne ikke klikkes. "
            f"Forventede værdier: {expected_values!r}."
        ) from error


async def _handle_stay_signed_in_if_present(
    page: Page,
    timeout_ms: int,
) -> None:
    """Klikker Ja, hvis Microsoft viser 'Forbliv logget på?'."""
    await page.wait_for_timeout(500)

    if not is_microsoft_login_url(page):
        return

    for value in ("Ja", "Yes"):
        yes_button = page.locator(
            f'{SUBMIT_SELECTOR}[value="{value}"]'
        ).first

        try:
            if await yes_button.is_visible() and await yes_button.is_enabled():
                await yes_button.click(timeout=timeout_ms)
                return
        except PlaywrightError:
            continue


async def _wait_until_login_redirect_is_complete(
    page: Page,
    timeout_ms: int,
    poll_interval_ms: int,
) -> None:
    """Venter på redirect væk fra Microsofts login-domæne."""
    elapsed_ms = 0

    while elapsed_ms < timeout_ms:
        if page.is_closed():
            raise MicrosoftLoginError(
                "Browserfanen blev lukket under Microsoft-login."
            )

        visible_error = await _read_visible_login_error(page)
        if visible_error:
            raise MicrosoftLoginError(
                f"Microsoft afviste login: {visible_error}"
            )

        if not is_microsoft_login_url(page):
            try:
                await page.wait_for_load_state(
                    "domcontentloaded",
                    timeout=10_000,
                )
            except PlaywrightTimeoutError:
                pass
            return

        await page.wait_for_timeout(poll_interval_ms)
        elapsed_ms += poll_interval_ms

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
                text = " ".join(
                    (await candidate.inner_text()).split()
                )
                if text:
                    return text
    except PlaywrightError:
        return ""

    return ""


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
            raise MicrosoftLoginError(
                "email mangler ved direkte Microsoft-login."
            )
        if not direct_password:
            raise MicrosoftLoginError(
                "password mangler ved direkte Microsoft-login."
            )
        return direct_email, direct_password

    normalized_credential_name = str(
        credential_name or ""
    ).strip()

    if not normalized_credential_name:
        raise MicrosoftLoginError(
            "Angiv enten credential_name eller både email og password."
        )

    return _get_credentials(normalized_credential_name)


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
            f"Credentialen {credential_name!r} mangler username, "
            "data.mail eller data.email."
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
        raise MicrosoftLoginError(
            "En åben Playwright-side skal angives."
        )

    has_credential_name = bool(
        isinstance(credential_name, str)
        and credential_name.strip()
    )
    has_direct_email = bool(
        isinstance(email, str)
        and email.strip()
    )
    has_direct_password = bool(
        isinstance(password, str)
        and password
    )

    if not has_credential_name and not (
        has_direct_email and has_direct_password
    ):
        raise MicrosoftLoginError(
            "Angiv credential_name eller både email og password."
        )

    for name, value in (
        ("action_timeout_ms", action_timeout_ms),
        ("login_timeout_ms", login_timeout_ms),
        ("poll_interval_ms", poll_interval_ms),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value <= 0
        ):
            raise MicrosoftLoginError(
                f"{name} skal være et positivt heltal."
            )


__all__ = [
    "MicrosoftLoginError",
    "is_microsoft_login_url",
    "login_via_microsoft",
]
