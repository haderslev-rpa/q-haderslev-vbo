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

    Ved succes er browseren sendt videre fra IDP-siden.
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

        # Giv robotformularen tid til at blive vist efter klik.
        await page.wait_for_timeout(2_000)

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

    # Lille pause så IDP-siden kan registrere inputværdierne.
    await page.wait_for_timeout(1_000)

    # Indsend formularen.
    await page.evaluate(
        "() => document.querySelector('#robotForm').submit()"
    )

    print("⏳ Login indsendt. Venter på viderestilling...")

    # FASIT og IDP kan være langsomme efter submit.
    await page.wait_for_timeout(10_000)

    # Vent på eventuel navigation.
    try:
        await page.wait_for_load_state(
            "domcontentloaded",
            timeout=60_000,
        )
    except Exception:
        print(
            "⚠️ Siden nåede ikke domcontentloaded inden timeout. "
            "Kontrollerer loginresultatet alligevel."
        )

    # Ekstra buffer til langsom viderestilling fra IDP til FASIT.
    await page.wait_for_timeout(10_000)

    print(f"🌐 URL efter login: {page.url}")

    robot_form = page.locator("#robotForm")

    # Det er ikke en fejl, at formularen stadig findes skjult i DOM'en.
    # Det er kun en fejl, hvis formularen fortsat er synlig.
    robot_form_visible = False

    if await robot_form.count() > 0:
        robot_form_visible = await robot_form.is_visible()

    if robot_form_visible:
        await session.recorder.screenshot(
            page,
            "FEJL_login",
        )

        raise RuntimeError(
            "❌ Login på FK IDP fejlede. "
            "Robotformularen er stadig synlig efter ventetiden."
        )

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
