"""
Kontrollerer om en reference findes i en bestemt Automation Server-kø.

Funktionen læser kun fra databasen.
Funktionen ændrer ikke workitems.
"""

from q_haderslev_vbo.automation_server.ats_database_connection import (
    get_connection,
)


# Statusværdierne er verificeret direkte i ATS-databasen.
WORKITEM_STATUS_NEW = "NEW"
WORKITEM_STATUS_IN_PROGRESS = "IN_PROGRESS"
WORKITEM_STATUS_COMPLETED = "COMPLETED"
WORKITEM_STATUS_FAILED = "FAILED"
WORKITEM_STATUS_PENDING_USER_ACTION = "PENDING_USER_ACTION"


def is_item_in_queue(
    queue_id: int | str,
    item_reference: str,
    *,
    new: bool = False,
    in_progress: bool = False,
    completed: bool = False,
    failed: bool = False,
    pending_user_action: bool = False,
) -> bool:
    """
    Kontrollerer om et workitem findes i en bestemt kø.

    Parametre:
        queue_id:
            Id på Automation Server-køen.

        item_reference:
            Referencen på det item, der skal findes.

        new:
            Søg efter status NEW.

        in_progress:
            Søg efter status IN_PROGRESS.

        completed:
            Søg efter status COMPLETED.

        failed:
            Søg efter status FAILED.

        pending_user_action:
            Søg efter status PENDING_USER_ACTION.

    Hvis ingen status er valgt:
        Søges der i alle fem workitem-statusser.

    Returnerer:
        True, hvis mindst ét matchende item findes.
        False, hvis intet matchende item findes.
    """

    validated_queue_id = _validate_queue_id(queue_id)

    validated_item_reference = _validate_item_reference(
        item_reference
    )

    selected_statuses = _build_status_filter(
        new=new,
        in_progress=in_progress,
        completed=completed,
        failed=failed,
        pending_user_action=pending_user_action,
    )

    connection = None

    try:
        connection = get_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM public.workitem
                    WHERE workqueue_id = %s
                      AND reference = %s
                      AND status::text = ANY(%s)
                );
                """,
                (
                    validated_queue_id,
                    validated_item_reference,
                    selected_statuses,
                ),
            )

            result = cursor.fetchone()

        if result is None:
            raise RuntimeError(
                "Databasen returnerede ikke et resultat."
            )

        return bool(result[0])

    finally:
        if connection is not None:
            connection.close()


def _validate_queue_id(queue_id: int | str) -> int:
    """
    Kontrollerer queue_id og returnerer et helt tal.
    """

    if queue_id is None:
        raise ValueError(
            "queue_id skal angives og må ikke være None."
        )

    if isinstance(queue_id, bool):
        raise ValueError(
            "queue_id skal være et helt tal og må ikke være bool."
        )

    if isinstance(queue_id, str) and not queue_id.strip():
        raise ValueError(
            "queue_id skal angives og må ikke være blank."
        )

    try:
        validated_queue_id = int(queue_id)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "queue_id skal være et helt tal eller tekst med et helt tal."
        ) from error

    if validated_queue_id <= 0:
        raise ValueError(
            "queue_id skal være større end 0."
        )

    return validated_queue_id


def _validate_item_reference(item_reference: str) -> str:
    """
    Kontrollerer item_reference.
    """

    if item_reference is None:
        raise ValueError(
            "item_reference skal angives og må ikke være None."
        )

    if not isinstance(item_reference, str):
        raise TypeError(
            "item_reference skal være tekst."
        )

    validated_item_reference = item_reference.strip()

    if not validated_item_reference:
        raise ValueError(
            "item_reference skal angives og må ikke være blank."
        )

    return validated_item_reference


def _build_status_filter(
    *,
    new: bool,
    in_progress: bool,
    completed: bool,
    failed: bool,
    pending_user_action: bool,
) -> list:
    """
    Bygger listen over statusser, der skal søges efter.
    """

    status_choices = {
        WORKITEM_STATUS_NEW: new,
        WORKITEM_STATUS_IN_PROGRESS: in_progress,
        WORKITEM_STATUS_COMPLETED: completed,
        WORKITEM_STATUS_FAILED: failed,
        WORKITEM_STATUS_PENDING_USER_ACTION: pending_user_action,
    }

    selected_statuses = [
        status
        for status, is_selected in status_choices.items()
        if is_selected
    ]

    # Ingen valgt status betyder alle statusser.
    if not selected_statuses:
        return list(status_choices.keys())

    return selected_statuses
