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
    """
    Logger ind via FK IDP robotformularen.

    Output:
    Funktionen returnerer ikke noget.

    Ved succes er robotformularen ikke længere synlig.
    Ved fejl tages et screenshot, og RuntimeError bliver kastet.
    """

    # Vent på at IDP-siden har indlæst formularen.
    await page.wait_for_selector(
        "#customerid",
        state="attached",
        timeout=60_000,
    )

    robot_btn = page.locator(
        "button[data-login-method='login-robot']"
    )

    if (
        await robot_btn.count() > 0
        and await robot_btn.is_visible()
    ):
        await robot_btn.click()

    # Vent på at inputfeltet er synligt.
    await page.wait_for_selector(
        "#customerid",
        state="visible",
        timeout=60_000,
    )

    # Udfyld loginoplysninger.
    await page.fill(
        "#customerid",
        CUSTOMER_ID,
    )

    await page.fill(
        "#robotupn",
        IDP_GUID,
    )

    await page.fill(
        "#apikey",
        API_KEY,
    )

    robot_form = page.locator("#robotForm")

    print("⏳ Login indsendes. Venter på viderestilling...")

    # Vent på navigationen samtidig med submit.
    try:
        async with page.expect_navigation(
            wait_until="domcontentloaded",
            timeout=60_000,
        ):
            await page.evaluate(
                "() => document.querySelector('#robotForm').submit()"
            )
    except Exception:
        print(
            "⚠️ Navigationen nåede ikke domcontentloaded inden timeout. "
            "Kontrollerer loginresultatet alligevel."
        )

    # Vent dynamisk på at robotformularen forsvinder.
    # Funktionen fortsætter straks, når formularen er skjult eller fjernet.
    try:
        await robot_form.wait_for(
            state="hidden",
            timeout=30_000,
        )
    except Exception:
        await session.recorder.screenshot(
            page,
            "FEJL_login",
        )

        raise RuntimeError(
            "❌ Login på FK IDP fejlede. "
            "Robotformularen er stadig synlig efter ventetiden."
        )

    print(f"🌐 URL efter login: {page.url}")
    print("✅ FK IDP login gennemført")


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
    await _login_robot(page, session)

    # ✅ FIX: async screenshot → SKAL awaites
    await session.recorder.screenshot(page, "IDP_efter_login")
