from automation_server_client import AutomationServer, Credential
from q_haderslev_vbo.playwright.browser_session import BrowserSession
# ==============================
# Konstanter
# ==============================
IDP_URL = "https://idp.prod.soloidp.dk/fkrobot/prepare"

# Global debug helper (overskrives i runtime)


# Global credentials (sættes ved runtime)
CUSTOMER_ID = None
API_KEY = None
IDP_GUID = None


# ==============================
# Intern robot-login (ASYNC)
# ==============================
async def _login_robot(page, session):
    await page.wait_for_selector("#customerid", state="attached", timeout=60000)

    robot_btn = page.locator("button[data-login-method='login-robot']")

    if await robot_btn.count() > 0 and await robot_btn.is_visible():
        await robot_btn.click()

    await page.wait_for_selector("#customerid:visible", timeout=60000)

    await page.fill("#customerid", CUSTOMER_ID)
    await page.fill("#robotupn", IDP_GUID)
    await page.fill("#apikey", API_KEY)

    # Submit form
    await page.evaluate("() => document.querySelector('#robotForm').submit()")

    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_load_state("networkidle")

    # Valider login
    if await page.locator("#robotForm").count() > 0:
        # ✅ FIX: async screenshot → SKAL awaites
        await session.recorder.screenshot(page, "FEJL_login")
        raise RuntimeError("❌ Login på FK IDP fejlede")


# ==============================
# Public API (ASYNC)
# ==============================
async def login_via_faelles_kommunal_idp(
    page,
    credential_name: str,
    session
):
    """
    Logger på Fælleskommunal IDP via robot-login.
    """
    global dbg, CUSTOMER_ID, API_KEY, IDP_GUID

    # Init Automation Server
    AutomationServer.from_environment()

    credential = Credential.get_credential(credential_name)
    cfg = credential.data

    IDP_GUID = cfg.get("idp_guid")
    CUSTOMER_ID = cfg.get("customer id")
    API_KEY = cfg.get("api key")

    assert IDP_GUID, "❌ idp_guid mangler"
    assert CUSTOMER_ID, "❌ customer id mangler"
    assert API_KEY, "❌ api key mangler"

    # Gå til IDP
    await page.goto(IDP_URL)
    await page.wait_for_load_state("domcontentloaded")

    # ✅ FIX: async screenshot → SKAL awaites
    await session.recorder.screenshot(page, "IDP_før_login")

    # Login flow
    await _login_robot(page)

    # ✅ FIX: async screenshot → SKAL awaites
    await session.recorder.screenshot(page, "IDP_efter_login")