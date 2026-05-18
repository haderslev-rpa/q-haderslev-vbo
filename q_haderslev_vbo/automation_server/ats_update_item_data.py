from datetime import datetime
from zoneinfo import ZoneInfo


def update_item_data(
    data_json: dict,
    *,
    box_updates: dict = None,
    status: str = None,
    status_code: str = None,
    state: str = None,
    defer: str = None,
    item=None,
    persist: bool = False
):
    """
    Opdaterer JSON-data for et work item.

    PARAMETRE
    ----------
    data_json : dict
        Eksisterende data (item.data)
 
    EKSEMPEL
    --------
    update_item_data(
        data,
        status="Completed",
        status_code="Behandlet færdig",
        state="Completed",
        defer="2026-05-20T10:00:00Z"
    )
    """

    # 1. Struktur
    data_json.setdefault("box", {})
    data_json.setdefault("status", {})
    data_json.setdefault("state", [])
    data_json.setdefault("defer", None)

    # 2. Box
    if box_updates:
        data_json["box"].update(box_updates)

    # 3. Status (kræver begge)
    if status or status_code:
        if not (status and status_code):
            raise ValueError("Du skal angive både 'status' og 'status_code'")

        data_json["status"]["status"] = status
        data_json["status"]["status_code"] = status_code

    # 4. State (historik i dansk tid)
    if state:
        now = datetime.now(ZoneInfo("Europe/Copenhagen"))
        timestamp = now.strftime("%d-%m-%Y %H:%M:%S")

        entry = f"{state} {timestamp}"
        data_json["state"].append(entry)

    # 5. Defer (UTC)
    if defer:
        data_json["defer"] = defer

    # 6. Persist
    if persist:
        if item is None:
            raise ValueError("persist=True kræver 'item'")
        item.data = data_json

    return data_json