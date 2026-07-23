"""
Ændrer et Automation Server WorkItem til NEW via API'et.

Placering i q-haderslev-vbo:
q_haderslev_vbo/automation_server/ats_itemstatus_to_new.py
"""

from automation_server_client import WorkItemStatus


def change_itemstatus_to_new(
    item,
    *,
    message: str = (
        "Defer-tidspunktet er nået. "
        "Itemet er sendt tilbage til køen."
    ),
):
    """
    Ændrer kun workitemets Automation Server-status til NEW.

    item.data og data["defer"] bliver ikke ændret.
    """
    if item is None:
        raise ValueError("item skal angives.")

    update_status = getattr(item, "update_status", None)

    if not callable(update_status):
        raise TypeError(
            "item skal have metoden update_status()."
        )

    if not isinstance(message, str) or not message.strip():
        raise ValueError(
            "message skal være en ikke-tom tekst."
        )

    return update_status(
        WorkItemStatus.NEW,
        message.strip(),
    )
