"""
API-hjælpere til Automation Server WorkItem-objekter.

Placering i q-haderslev-vbo:
q_haderslev_vbo/automation_server/ats_workitem_api.py

Databaserækken leverer automatisk item-id, workqueue-id og reference.
Den kaldende proces skal ikke angive en workqueue.
"""

from automation_server_client import (
    AutomationServer,
    WorkItemStatus,
)


def get_workitem_object_by_database_row(
    database_item: dict,
    *,
    required_status: WorkItemStatus | None = None,
):
    """
    Henter det rigtige WorkItem-objekt gennem Automation Server API'et.

    Det tekniske item-id er den endelige identifikation.
    Reference bruges kun til at hente kandidater, fordi klientversion 0.3.0
    ikke har et dokumenteret offentligt opslag direkte via item-id.
    """
    item_id = _require_positive_int(database_item, "id")
    workqueue_id = _require_positive_int(database_item, "workqueue_id")
    reference = _require_nonempty_text(database_item, "reference")

    ats = AutomationServer.from_environment()
    workqueue = get_workqueue_object_by_id(
        ats,
        workqueue_id,
    )

    api_result = workqueue.get_item_by_reference(
        reference,
        status=required_status,
    )
    candidates = _normalize_to_list(api_result)

    matches = [
        candidate
        for candidate in candidates
        if int(candidate.id) == item_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"Forventede præcis ét API-item med id {item_id} i "
            f"workqueue {workqueue_id}, men fandt {len(matches)}."
        )

    return matches[0]


def get_workqueue_object_by_id(
    ats,
    workqueue_id: int | str,
):
    """
    Returnerer et klientklart Workqueue-objekt for det ønskede queue-id.

    Klientens interne URL, token og konfiguration sidder allerede på det
    Workqueue-objekt, som ats.workqueue() opretter fra environment.
    Objektet bruges derfor som teknisk skabelon og kopieres med itemets
    rigtige workqueue-id fra databasen.
    """
    validated_workqueue_id = _validate_positive_int(
        workqueue_id,
        "workqueue_id",
    )

    try:
        environment_workqueue = ats.workqueue()
    except Exception as error:
        raise RuntimeError(
            "Processen mangler en gyldig teknisk workqueue i environment. "
            "Angiv en monitor-kø i Automation Server-processens "
            "workqueue-felt eller ATS_WORKQUEUE_ID ved lokal debug."
        ) from error

    if environment_workqueue is None:
        raise RuntimeError(
            "ats.workqueue() returnerede ingen workqueue."
        )

    if environment_workqueue.id is None:
        raise RuntimeError(
            "Environment-workqueuen mangler id."
        )

    if int(environment_workqueue.id) == validated_workqueue_id:
        return environment_workqueue

    return _copy_workqueue_with_new_id(
        environment_workqueue,
        validated_workqueue_id,
    )


def _copy_workqueue_with_new_id(
    workqueue,
    workqueue_id: int,
):
    """Kopierer workqueuen og bevarer klientens interne API-konfiguration."""
    if hasattr(workqueue, "model_copy"):
        copied_workqueue = workqueue.model_copy(
            update={"id": workqueue_id},
            deep=False,
        )
    elif hasattr(workqueue, "copy"):
        copied_workqueue = workqueue.copy(
            update={"id": workqueue_id},
            deep=False,
        )
    else:
        raise TypeError(
            "Workqueue-objektet kan ikke kopieres med et nyt id."
        )

    if copied_workqueue.id is None or int(copied_workqueue.id) != workqueue_id:
        raise RuntimeError(
            "Den kopierede workqueue fik ikke det forventede id."
        )

    return copied_workqueue


def refresh_workitem_object_by_database_id(
    item_id: int | str,
    *,
    required_status: WorkItemStatus | None = None,
):
    """Henter en frisk databaserække og returnerer API-objektet."""
    from q_haderslev_vbo.automation_server.ats_deferred_items import (
        get_workitem_database_row_by_id,
    )

    database_item = get_workitem_database_row_by_id(item_id)

    return get_workitem_object_by_database_row(
        database_item,
        required_status=required_status,
    )


def _normalize_to_list(result) -> list:
    if result is None:
        return []

    if isinstance(result, list):
        return result

    return [result]


def _require_positive_int(data: dict, field_name: str) -> int:
    if not isinstance(data, dict):
        raise TypeError("database_item skal være en dictionary.")

    if field_name not in data:
        raise ValueError(
            f"database_item mangler feltet '{field_name}'."
        )

    return _validate_positive_int(
        data[field_name],
        field_name,
    )


def _validate_positive_int(value, field_name: str) -> int:
    if value is None or isinstance(value, bool):
        raise ValueError(
            f"{field_name} skal være et positivt helt tal."
        )

    try:
        validated_value = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{field_name} skal være et helt tal."
        ) from error

    if validated_value <= 0:
        raise ValueError(
            f"{field_name} skal være større end 0."
        )

    return validated_value


def _require_nonempty_text(data: dict, field_name: str) -> str:
    value = data.get(field_name)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"database_item mangler en gyldig '{field_name}'."
        )

    return value.strip()
