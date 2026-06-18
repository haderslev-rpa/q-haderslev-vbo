# sp_auth.py

import time
import requests


class SharePointAuth:
    def __init__(self, tenant_id, client_id, client_secret, scope):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret

        self.scope = scope

        self._token = None
        self._expiry = 0

    def _get_token(self):
        if self._token and time.time() < (self._expiry - 300):
            return self._token

        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scope
        }

        r = requests.post(url, data=data, timeout=30)
        r.raise_for_status()

        token = r.json()

        self._token = token["access_token"]
        self._expiry = time.time() + int(token.get("expires_in", 3600))

        return self._token

    def headers(self):
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json"
        }
