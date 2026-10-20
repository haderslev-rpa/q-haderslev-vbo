"""Lokal test af Microsoft-login med Email og Password fra .env."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

from q_haderslev_vbo.playwright.microsoft_login import (
    is_microsoft_login_url,
    login_via_microsoft,
)

logger = logging.getLogger(__name__)

DEFAULT_TEST_URL = "https://forms.cloud.microsoft/"
NAVIGATION_TIMEOUT_MS = 120_000
LOGIN_TIMEOUT_MS = 120_000
ACTION_TIMEOUT_MS = 30_000


def load_test_settings() -> tuple[str, str, str]:
    """Henter Email, Password og valgfri MICROSOFT_TEST_URL fra .env."""
    repository_root = Path(__file__).resolve().parent.parent
    env_path = repository_root / ".env"

    if not env_path.is_file():
        raise RuntimeError(
            f".env blev ikke fundet: {env_path}"
        )

    load_dotenv(
        dotenv_path=env_path,
        override=True,
    )

    email = os.getenv("Email", "").strip()
    password = os.getenv("Password", "")
    test_url = os.getenv(
        "MICROSOFT_TEST_URL",
        DEFAULT_TEST_URL,
    ).strip()

    missing: list[str] = []

    if not email:
        missing.append("Email")
    if not password:
        missing.append("Password")

    if missing:
        raise RuntimeError(
            ".env mangler følgende værdi(er): "
            + ", ".join(missing)
        )

    if not test_url.startswith(("https://", "http://")):
        raise RuntimeError(
            "MICROSOFT_TEST_URL skal begynde med http:// eller https://."
        )

    return email, password, test_url


async def main() -> None:
    """Starter en synlig browser og tester Microsoft-login."""
    email, password, test_url = load_test_settings()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=False,
            channel="chromium",
            args=["--window-size=1920,1080"],
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="da-DK",
            ignore_https_errors=True,
        )
        page = await context.new_page()
        page.set_default_navigation_timeout(
            NAVIGATION_TIMEOUT_MS
        )

        try:
            print("Åbner Microsoft-test-URL...")

            await page.goto(
                test_url,
                wait_until="domcontentloaded",
                timeout=NAVIGATION_TIMEOUT_MS,
            )

            print(f"URL efter navigation: {page.url}")

            print(
                "Venter på Microsoft-loginformular eller færdigt redirect."
            )

            # Kald altid hjælperen. Hjælperen venter selv på mailfeltet og
            # returnerer kun uden login, hvis redirect ender på målsiden.
            await login_via_microsoft(
                page=page,
                email=email,
                password=password,
                action_timeout_ms=ACTION_TIMEOUT_MS,
                login_timeout_ms=LOGIN_TIMEOUT_MS,
            )

            if is_microsoft_login_url(page):
                raise RuntimeError(
                    "Browseren står stadig på Microsoft-login-siden."
                )

            print("Microsoft-login-testen blev gennemført.")
            print(f"Aktuel URL: {page.url}")
            print(
                "Tryk Enter i terminalen for at lukke browseren."
            )

            await asyncio.to_thread(input)

        except Exception:
            logger.exception(
                "Microsoft-login-testen fejlede."
            )

            if not page.is_closed():
                screenshot_path = (
                    repository_root()
                    / "microsoft_login_test_error.png"
                )
                await page.screenshot(
                    path=str(screenshot_path),
                    full_page=True,
                )
                logger.info(
                    "Fejlscreenshot gemt: %s",
                    screenshot_path,
                )
            raise

        finally:
            await context.close()
            await browser.close()


def repository_root() -> Path:
    """Returnerer repositoryets rodmappe."""
    return Path(__file__).resolve().parent.parent


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s [%(levelname)s] "
            "%(name)s: %(message)s"
        ),
        force=True,
    )

    asyncio.run(main())
