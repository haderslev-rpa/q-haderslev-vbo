# q_haderslev_vbo/automation_server/ats_sharepoint.py

"""
AUTOMATION SERVER WRAPPER FOR SHAREPOINT

Brug denne fil når du:
- arbejder i en ATS-process
- vil have SharePoint-data ind i item.data["box"]["sharepoint"]

⚠️ Denne fil:
- overskriver ALTID box.sharepoint
- bevarer reference til item
"""

from q_sharepoint_api.sp_list_item import (get_sharepoint_list_item, create_update_sharepoint_list_item)


def hent_sharepoint_list_item_til_box(
    site_name,
    list_name,
    list_item_id,
    *,
    item
):
    """
    Henter SharePoint list item
    og overskriver item.data["box"]["sharepoint"].
    """

    sharepoint_data = get_sharepoint_list_item(
        site_name=site_name,
        list_name=list_name,
        list_item_id=list_item_id
    )

    _overskriv_sharepoint_i_box(item, sharepoint_data)
    return sharepoint_data


def gem_sharepoint_liste_item_fra_box(
    site_name,
    list_name,
    sharepoint_data,
    *,
    item,
    robot_kommentar: str | None = None
):
    """
    Gemmer SharePoint liste-item FRA box TIL SharePoint.

    - Læser data fra box.sharepoint
    - Gemmer i SharePoint (create/update)
    - Overskriver box.sharepoint med frisk data
    - Appender robot kommentar hvis angivet
    """

    # Kopiér data (så vi ikke muterer box direkte)
    payload = dict(sharepoint_data)

    # Tilføj robot kommentar hvis angivet
    if robot_kommentar:
        payload["Robot kommentar"] = robot_kommentar

    # Gem i SharePoint (create/update)
    saved_sharepoint_data = create_update_sharepoint_list_item(
        site_name=site_name,
        list_name=list_name,
        sharepoint_data=payload
    )

    # Overskriv box.sharepoint
    _overskriv_sharepoint_i_box(item, saved_sharepoint_data)

    return saved_sharepoint_data


# -------------------------------------------------
# 🔧 INTERN HELPER
# -------------------------------------------------

def _overskriv_sharepoint_i_box(item, sharepoint_data):
    """
    Sletter og genskaber box.sharepoint
    så det altid ligger sidst.
    """

    box = item.data.get("box", {})

    if "sharepoint" in box:
        del box["sharepoint"]

    box["sharepoint"] = sharepoint_data
    item.data["box"] = box