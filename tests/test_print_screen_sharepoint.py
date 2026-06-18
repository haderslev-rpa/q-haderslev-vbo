import asyncio

from q_haderslev_vbo.playwright.browser_session import BrowserSession


async def main():
    # ---------------------------------------------
    # ✅ Start browser (objekt – konkret instans af klasse)
    # ---------------------------------------------
    session = BrowserSession(headless=False, debug=True)

    await session.start()
    page = await session.new_page()

    try:
        # ---------------------------------------------
        # ✅ Åbn Google
        # ---------------------------------------------
        await page.goto("https://www.google.com")

        # ---------------------------------------------
        # ✅ Screenshot 1
        # ---------------------------------------------
        await session.screenshot(page, "Google_1", always=True)

        # ---------------------------------------------
        # ✅ Screenshot 2
        # ---------------------------------------------
        await session.screenshot(page, "Google_2", always=True)

        # ---------------------------------------------
        # ✅ Screenshot 3
        # ---------------------------------------------
        await session.screenshot(page, "Google_3", always=True)

    finally:
        # ---------------------------------------------
        # ✅ Luk browser (robust cleanup)
        # ---------------------------------------------
        await session.close_page(page)
        await session.close()


# ---------------------------------------------
# ✅ Kør program
# ---------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
