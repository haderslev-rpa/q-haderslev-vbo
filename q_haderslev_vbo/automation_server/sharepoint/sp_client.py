# sp_client.py

import requests


class SharePointClient:
    def __init__(self, auth, tenant_name):
        self.auth = auth
        self.tenant_name = tenant_name
        self.base = "https://graph.microsoft.com/v1.0"

    # ---------------------------
    # SITE / DRIVE
    # ---------------------------

    def get_site_id(self, site_name):
        url = f"{self.base}/sites/{self.tenant_name}.sharepoint.com:/sites/{site_name}"

        r = requests.get(url, headers=self.auth.headers(), timeout=30)
        r.raise_for_status()

        return r.json()["id"]

    def get_drive_id(self, site_id):
        url = f"{self.base}/sites/{site_id}/drive"

        r = requests.get(url, headers=self.auth.headers(), timeout=30)
        r.raise_for_status()

        return r.json()["id"]

    # ---------------------------
    # FOLDERS
    # ---------------------------

    def create_folder(self, drive_id, parent_path, folder_name):
        url = f"{self.base}/drives/{drive_id}/root:/{parent_path}:/children"

        data = {
            "name": folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "fail"
        }

        r = requests.post(url, headers=self.auth.headers(), json=data, timeout=30)
        r.raise_for_status()

        return r.json()

    # ---------------------------
    # FILES
    # ---------------------------

    def upload_file(self, drive_id, folder_path, file_name, content):
        url = f"{self.base}/drives/{drive_id}/root:/{folder_path}/{file_name}:/content"

        r = requests.put(
            url,
            headers=self.auth.headers(),
            data=content,
            timeout=60
        )
        r.raise_for_status()

        return r.json()

    # ---------------------------
    # DELETE
    # ---------------------------

    def delete_item(self, drive_id, item_id):
        url = f"{self.base}/drives/{drive_id}/items/{item_id}"

        r = requests.delete(url, headers=self.auth.headers(), timeout=30)
        r.raise_for_status()
