"""
Henter databaseopsætning fra Automation Server credentials.
"""

from automation_server_client import AutomationServer, Credential


DATABASE_CONFIG_CREDENTIAL = "ATS_DATABASE"
DATABASE_LOGIN_CREDENTIAL = "ATS_DATABASE_RAPPORTERING"

_DATABASE_SETTINGS_CACHE = None


def get_database_settings() -> dict:
    """
    Henter databaseopsætning fra credentials.

    Bruger cache, så credentials kun hentes én gang
    under samme proceskørsel.
    """

    global _DATABASE_SETTINGS_CACHE

    if _DATABASE_SETTINGS_CACHE is not None:
        return _DATABASE_SETTINGS_CACHE

    # Initialiserer Automation Server-klienten.
    AutomationServer.from_environment()

    config_credential = Credential.get_credential(
        DATABASE_CONFIG_CREDENTIAL
    )
    login_credential = Credential.get_credential(
        DATABASE_LOGIN_CREDENTIAL
    )

    config = config_credential.data or {}

    host = config.get("host")
    port = config.get("port")
    database = config.get("database")

    if not host:
        raise ValueError(
            "ATS_DATABASE mangler 'host' i Data JSON."
        )

    if not port:
        raise ValueError(
            "ATS_DATABASE mangler 'port' i Data JSON."
        )

    if not database:
        raise ValueError(
            "ATS_DATABASE mangler 'database' i Data JSON."
        )

    if not login_credential.username:
        raise ValueError(
            "ATS_DATABASE_RAPPORTERING mangler username."
        )

    if not login_credential.password:
        raise ValueError(
            "ATS_DATABASE_RAPPORTERING mangler password."
        )

    _DATABASE_SETTINGS_CACHE = {
        "host": host,
        "port": int(port),
        "database": database,
        "user": login_credential.username,
        "password": login_credential.password,
    }

    return _DATABASE_SETTINGS_CACHE