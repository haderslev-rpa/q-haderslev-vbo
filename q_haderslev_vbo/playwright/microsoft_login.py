"""Fælles Microsoft-login via Playwright og Automation Server credentials."""

from __future__ import annotations

import logging
from typing import Any

from automation_server_client import AutomationServer, Credential
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from q_haderslev_vbo.playwright.browser_session import BrowserSession

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
    session: BrowserSession,
    credential_name: str,
    *,
    action_timeout_ms: int = DEFAULT_ACTION_TIMEOUT_MS,
    login_timeout_ms: int = DEFAULT_LOGIN_TIMEOUT_MS,
    poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS,
) -> None:
    """Logger ind på Microsoft med en valgt Automation Server credential.

    credential_name gør hjælperen genbrugelig til flere robotbrugere. Mail og
    adgangskode læses først fra credential.username/password. Hvis username er
    tomt, accepteres data['mail'] eller data['email']. Adgangskoden logges aldrig.

    BrowserSession bruges til fejl-screenshot på samme måde som de øvrige
    fælles Playwright-loginhelpers.
    """
    _validate_inputs(
        page=page,
        session=session,
        credential_name=credential_name,
        action_timeout_ms=action_timeout_ms,
        login_timeout_ms=login_timeout_ms,
        poll_interval_ms=poll_interval_ms,
    )

    recorder = getattr(session, "recorder", None)
    set_page = getattr(recorder, "set_page", None)
    if callable(set_page):
        set_page(page)

    email, password = _get_credentials(credential_name.strip())
    original_timeout = page.timeout_settings.timeout() if hasattr(page, "timeout_settings") else None
    page.set_default_timeout(action_timeout_ms)

    try:
        if not is_microsoft_login_url(page):
            logger.info("Microsoft-login er ikke nødvendigt. Aktuel URL: %s", page.url)
            return

        logger.info("Microsoft-login startes med credentialen %s.", credential_name.strip())
        await _fill_email_and_continue(page=page, email=email, timeout_ms=action_timeout_ms)
        await _fill_password_and_sign_in(page=page, password=password, timeout_ms=action_timeout_ms)
        await _handle_stay_signed_in_if_present(page=page, timeout_ms=action_timeout_ms)
        await _wait_until_login_redirect_is_complete(
            page=page,
            timeout_ms=login_timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )
        logger.info("Microsoft-login blev gennemført. Aktuel URL: %s", page.url)
    except MicrosoftLoginError:
        await _take_error_screenshot(session=session, page=page)
        raise
    except (PlaywrightTimeoutError, PlaywrightError) as error:
        await _take_error_screenshot(session=session, page=page)
        raise MicrosoftLoginError(
            f"Microsoft-login fejlede: {type(error).__name__}: {error}. "
            f"Aktuel URL: {page.url}"
        ) from error
    finally:
        if isinstance(original_timeout, (int, float)) and original_timeout > 0:
            page.set_default_timeout(original_timeout)


async def _fill_email_and_continue(page: Page, email: str, timeout_ms: int) -> None:
    username = page.locator(USERNAME_SELECTOR)
    try:
        await username.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeoutError as error:
        raise MicrosoftLoginError(
            "Microsoft-feltet 'Mail eller telefon' blev ikke synligt."
        ) from error

    await username.fill(email)
    next_button = page.locator(SUBMIT_SELECTOR).filter(has=page.locator("xpath=.")).first
    await _click_submit_with_value(
        page=page,
        expected_values=("Næste", "Next"),
        timeout_ms=timeout_ms,
        fallback=next_button,
    )


async def _fill_password_and_sign_in(page: Page, password: str, timeout_ms: int) -> None:
    password_input = page.locator(PASSWORD_SELECTOR)
    try:
        await password_input.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeoutError as error:
        message = await _read_visible_login_error(page)
        suffix = f" Microsoft-fejl: {message}" if message else ""
        raise MicrosoftLoginError(
            "Microsoft-feltet 'Adgangskode' blev ikke synligt efter valg af Næste."
            + suffix
        ) from error

    await password_input.fill(password)
    await _click_submit_with_value(
        page=page,
        expected_values=("Log på", "Sign in"),
        timeout_ms=timeout_ms,
        fallback=page.locator(SUBMIT_SELECTOR).first,
    )


async def _click_submit_with_value(
    page: Page,
    expected_values: tuple[str, ...],
    timeout_ms: int,
    fallback,
) -> None:
    for value in expected_values:
        candidate = page.locator(f'{SUBMIT_SELECTOR}[value="{value}"]').first
        try:
            if await candidate.is_visible() and await candidate.is_enabled():
                await candidate.click(timeout=timeout_ms)
                return
        except PlaywrightError:
            continue

    try:
        await fallback.wait_for(state="visible", timeout=timeout_ms)
        await fallback.click(timeout=timeout_ms)
    except (PlaywrightTimeoutError, PlaywrightError) as error:
        raise MicrosoftLoginError(
            f"Microsoft-knappen {expected_values!r} blev ikke fundet eller kunne ikke klikkes."
        ) from error


async def _handle_stay_signed_in_if_present(page: Page, timeout_ms: int) -> None:
    """Håndterer valgfrit 'Forbliv logget på?'-trin uden at kræve det."""
    try:
        await page.wait_for_timeout(500)
        if not is_microsoft_login_url(page):
            return
        yes_button = page.locator(f'{SUBMIT_SELECTOR}[value="Ja"], {SUBMIT_SELECTOR}[value="Yes"]').first
        if await yes_button.is_visible():
            await yes_button.click(timeout=timeout_ms)
    except PlaywrightError:
        logger.debug("Valgfrit 'Forbliv logget på?'-trin blev ikke håndteret.", exc_info=True)


async def _wait_until_login_redirect_is_complete(
    page: Page,
    timeout_ms: int,
    poll_interval_ms: int,
) -> None:
    elapsed_ms = 0
    while elapsed_ms < timeout_ms:
        if page.is_closed():
            raise MicrosoftLoginError("Browserfanen blev lukket under Microsoft-login.")
        visible_error = await _read_visible_login_error(page)
        if visible_error:
            raise MicrosoftLoginError(f"Microsoft afviste login: {visible_error}")
        if not is_microsoft_login_url(page):
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=10_000)
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


def _get_credentials(credential_name: str) -> tuple[str, str]:
    try:
        AutomationServer.from_environment()
        credential = Credential.get_credential(credential_name)
    except Exception as error:
        raise MicrosoftLoginError(
            f"Credentialen {credential_name!r} kunne ikke hentes fra Automation Server."
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
            f"Credentialen {credential_name!r} mangler username, data.mail eller data.email."
        )
    if not password:
        raise MicrosoftLoginError(f"Credentialen {credential_name!r} mangler password.")
    return email, password


def _validate_inputs(
    *,
    page: Page,
    session: BrowserSession,
    credential_name: str,
    action_timeout_ms: int,
    login_timeout_ms: int,
    poll_interval_ms: int,
) -> None:
    if page is None or page.is_closed():
        raise MicrosoftLoginError("En åben Playwright-side skal angives.")
    if session is None:
        raise MicrosoftLoginError("BrowserSession skal angives.")
    if not isinstance(credential_name, str) or not credential_name.strip():
        raise MicrosoftLoginError("credential_name skal være en ikke-tom tekst.")
    for name, value in (
        ("action_timeout_ms", action_timeout_ms),
        ("login_timeout_ms", login_timeout_ms),
        ("poll_interval_ms", poll_interval_ms),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise MicrosoftLoginError(f"{name} skal være et positivt heltal.")


async def _take_error_screenshot(session: BrowserSession, page: Page) -> None:
    try:
        if not page.is_closed():
            await session.screenshot(page, "microsoft_login_error", always=True)
    except Exception:
        logger.warning("Screenshot af Microsoft-loginfejlen kunne ikke gemmes.", exc_info=True)


__all__ = [
    "MicrosoftLoginError",
    "is_microsoft_login_url",
    "login_via_microsoft",
]
