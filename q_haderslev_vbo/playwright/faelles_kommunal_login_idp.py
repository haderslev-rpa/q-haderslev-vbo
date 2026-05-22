from automation_server_client import AutomationServer, Credential
from playwright.sync_api import Page
from q_haderslev_vbo.playwright.playwright_debughelper import PlaywrightDebugHelper

# ==============================
# Konstanter (intern viden)
# ==============================
IDP_URL = "https://idp.prod.soloidp.dk/fkrobot/prepare"

dbg = PlaywrightDebugHelper(debug=False)

# ==============================
# Intern robot-login
# ==============================
def _login_robot(page: Page):
    page.wait_for_selector("#customerid", state="attached", timeout=60000)

    robot_btn = page.locator("button[data-login-method='login-robot']")
    if robot_btn.count() > 0 and robot_btn.is_visible():
        robot_btn.click()

    page.wait_for_selector("#customerid:visible", timeout=60000)

    page.fill("#customerid", CUSTOMER_ID)
    page.fill("#robotupn", IDP_GUID)
    page.fill("#apikey", API_KEY)

    page.evaluate("() => document.querySelector('#robotForm').submit()")

    page.wait_for_load_state("domcontentloaded")
    page.wait_for_load_state("networkidle")

    if page.locator("#robotForm").count() > 0:
        dbg.screenshot(page, "FEJL_login")
        raise RuntimeError("Login på FK IDP fejlede")

# ==============================
# Public API
# ==============================
def login_via_faelles_kommunal_idp(
    page: Page,
    credential_name: str,
    debug: bool = False
):
    """
    Logger på Fælleskommunal IDP via robot-login.
    """
    global dbg, CUSTOMER_ID, API_KEY, IDP_GUID

    dbg = PlaywrightDebugHelper(debug=debug)

    AutomationServer.from_environment()

    credential = Credential.get_credential(credential_name)
    cfg = credential.data

    IDP_GUID = cfg.get("idp_guid")
    CUSTOMER_ID = cfg.get("customer id")
    API_KEY = cfg.get("api key")

    assert IDP_GUID, "idp_guid mangler"
    assert CUSTOMER_ID, "customer id mangler"
    assert API_KEY, "api key mangler"

    page.goto(IDP_URL)
    page.wait_for_load_state("domcontentloaded")

    dbg.screenshot(page, "IDP_før_login")
    _login_robot(page)
    dbg.screenshot(page, "IDP_efter_login")