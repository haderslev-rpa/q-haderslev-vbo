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


def gem_sharepoint_list_item_til_box(
    site_name,
    list_name,
    sharepoint_data,
    *,
    item
):
    """
    Opretter/opdaterer SharePoint list item
    og overskriver item.data["box"]["sharepoint"].
    """

    saved_sharepoint_data = create_update_sharepoint_list_item(
        site_name=site_name,
        list_name=list_name,
        sharepoint_data=sharepoint_data
    )

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