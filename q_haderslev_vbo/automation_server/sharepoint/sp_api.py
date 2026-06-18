# sp_api.py

from automation_server_client import AutomationServer, Credential

from q_haderslev_vbo.automation_server.sharepoint.sp_auth import SharePointAuth
from q_haderslev_vbo.automation_server.sharepoint.sp_client import SharePointClient


# INIT (miljø (opsætning))
AutomationServer.from_environment()

# Hent credentials (hemmelige data)
_cred = Credential.get_credential("API_SHAREPOINT")
_cfg = _cred.data

_client = None


def get_client():
    global _client

    if _client:
        return _client

    auth = SharePointAuth(
        tenant_id=_cfg["tenant_id"],
        client_id=_cfg["client_id"],
        client_secret=_cred.password,
        scope=_cfg.get("scope", "https://graph.microsoft.com/.default")
    )

    _client = SharePointClient(auth, _cfg["tenant_name"])

    return _client