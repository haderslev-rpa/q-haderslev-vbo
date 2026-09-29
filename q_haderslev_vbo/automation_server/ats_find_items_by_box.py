"""Generelle, læsende opslag i item.data["box"] i Automation Server.

Placering i q-haderslev-vbo:
q_haderslev_vbo/automation_server/ats_find_items_by_box.py

Funktionerne læser kun fra PostgreSQL.
Funktionerne ændrer aldrig WorkItems direkte i databasen.

Offentlige funktioner:
- get_workitems_by_box_value()
- get_one_workitem_by_box_value()
- is_box_value_in_queue()

Eksempler på box_path:
- "memo_message_uuid"
- "recipient.id"
- "submissions[].memo_message_uuid"
- "sharepoint.item_id"
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from q_haderslev_vbo.automation_server.ats_database_connection import (
    get_connection,
)


WORKITEM_STATUS_NEW = "NEW"
WORKITEM_STATUS_IN_PROGRESS = "IN_PROGRESS"
WORKITEM_STATUS_COMPLETED = "COMPLETED"
WORKITEM_STATUS_FAILED = "FAILED"
WORKITEM_STATUS_PENDING_USER_ACTION = "PENDING_USER_ACTION"

ALL_WORKITEM_STATUSES = (
    WORKITEM_STATUS_NEW,
    WORKITEM_STATUS_IN_PROGRESS,
    WORKITEM_STATUS_COMPLETED,
    WORKITEM_STATUS_FAILED,
    WORKITEM_STATUS_PENDING_USER_ACTION,
)

DEFAULT_LIMIT = 50
MAX_LIMIT = 1000

# Et feltnavn må indeholde bogstaver, tal og underscore.
# [] må kun stå efter et feltnavn og betyder "alle elementer i listen".
_BOX_PATH_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\[\])?"
    r"(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[\])?)*$"
)


def get_workitems_by_box_value(
    queue_id: int | str,
    box_path: str,
    value: Any,
    *,
    statuses: list[str] | tuple[str, ...] | None = None,
    start_datetime: datetime | str | None = None,
    end_datetime: datetime | str | None = None,
    updated_at: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Find WorkItems med en bestemt værdi i data["box"].

    Parametre:
        queue_id:
            Det tekniske ID på Automation Server-køen.

        box_path:
            Stien under data["box"].

            Eksempler:
            - "memo_message_uuid"
            - "recipient.id"
            - "submissions[].memo_message_uuid"

            [] betyder, at alle elementer i listen undersøges.

        value:
            Den værdi, som feltet skal være præcis lig med.
            Tekst, tal, bool og None understøttes.

        statuses:
            Valgfri liste med ATS-statusser.
            None betyder alle kendte WorkItem-statusser.

        start_datetime:
            Valgfrit inkluderet starttidspunkt.
            Tidspunktet skal indeholde tidszone.

        end_datetime:
            Valgfrit inkluderet sluttidspunkt.
            Tidspunktet skal indeholde tidszone.

        updated_at:
            False bruger created_at til tidsfilteret.
            True bruger updated_at.

        limit:
            Maksimalt antal rækker. Standard er 50.
            Tilladte værdier er 1 til 1000.

    Output:
        En dictionary på formen:

        {
            "count": 1,
            "exists": True,
            "box_path": "memo_message_uuid",
            "value": "abc-123",
            "datetime_field": "created_at",
            "items": [
                {
                    "id": 123,
                    "data": {...},
                    "reference": "...",
                    "status": "PENDING_USER_ACTION",
                    "workqueue_id": 13,
                    ...
                }
            ],
        }

    Vigtigt:
        Funktionen udfører kun SELECT og ændrer ingen WorkItems.
        Match på value er eksakt. Der anvendes ikke fritekstsøgning.
    """
    validated_queue_id = _validate_queue_id(queue_id)
    validated_box_path = _validate_box_path(box_path)
    validated_statuses = _validate_statuses(statuses)
    validated_start_datetime = _parse_utc_datetime(
        start_datetime,
        field_name="start_datetime",
    )
    validated_end_datetime = _parse_utc_datetime(
        end_datetime,
        field_name="end_datetime",
    )
    _validate_datetime_period(
        start_datetime=validated_start_datetime,
        end_datetime=validated_end_datetime,
    )

    if not isinstance(updated_at, bool):
        raise TypeError(
            "updated_at skal være True eller False."
        )

    validated_limit = _validate_limit(limit)
    datetime_field = (
        "updated_at"
        if updated_at
        else "created_at"
    )

    json_path = _build_json_path(
        validated_box_path
    )

    query = f"""
        SELECT
            id,
            data,
            reference,
            locked,
            status::text AS status,
            message,
            workqueue_id,
            created_at,
            updated_at,
            started_at,
            work_duration_seconds
        FROM public.workitem
        WHERE workqueue_id = %s
          AND status::text = ANY(%s)
          AND jsonb_path_exists(
                data -> 'box',
                %s::jsonpath,
                %s::jsonb
              )
          AND (
                %s::timestamp IS NULL
                OR {datetime_field} >= %s::timestamp
              )
          AND (
                %s::timestamp IS NULL
                OR {datetime_field} <= %s::timestamp
              )
        ORDER BY {datetime_field} DESC, id DESC
        LIMIT %s;
    """

    # JSONPath-variablen $search_value anvendes i stedet for at sætte
    # værdien direkte ind i SQL-teksten.
    json_path_variables = Json(
        {"search_value": value}
    )

    connection = None

    try:
        connection = get_connection()

        with connection.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                query,
                (
                    validated_queue_id,
                    validated_statuses,
                    json_path,
                    json_path_variables,
                    validated_start_datetime,
                    validated_start_datetime,
                    validated_end_datetime,
                    validated_end_datetime,
                    validated_limit,
                ),
            )

            rows = cursor.fetchall()

        items = [dict(row) for row in rows]

        return {
            "count": len(items),
            "exists": bool(items),
            "box_path": validated_box_path,
            "value": value,
            "datetime_field": datetime_field,
            "items": items,
        }

    finally:
        if connection is not None:
            connection.close()


def get_one_workitem_by_box_value(
    queue_id: int | str,
    box_path: str,
    value: Any,
    *,
    statuses: list[str] | tuple[str, ...] | None = None,
    start_datetime: datetime | str | None = None,
    end_datetime: datetime | str | None = None,
    updated_at: bool = False,
) -> dict[str, Any] | None:
    """Find højst ét WorkItem med en bestemt box-værdi.

    Output:
        En dictionary med databaserækken, hvis præcis ét item matcher.

        None, hvis intet item matcher.

    Fejl:
        RuntimeError, hvis flere items matcher. Funktionen vælger aldrig
        automatisk mellem flere WorkItems.
    """
    result = get_workitems_by_box_value(
        queue_id=queue_id,
        box_path=box_path,
        value=value,
        statuses=statuses,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        updated_at=updated_at,
        # To rækker er nok til at konstatere, at opslaget ikke er entydigt.
        limit=2,
    )

    if result["count"] == 0:
        return None

    if result["count"] > 1:
        matching_ids = [
            item["id"]
            for item in result["items"]
        ]

        raise RuntimeError(
            "Forventede højst ét WorkItem med "
            f"box_path={box_path!r} og value={value!r}, "
            f"men fandt flere. Item-id'er: {matching_ids}."
        )

    return result["items"][0]


def is_box_value_in_queue(
    queue_id: int | str,
    box_path: str,
    value: Any,
    *,
    statuses: list[str] | tuple[str, ...] | None = None,
) -> bool:
    """Kontrollér om mindst ét item har den ønskede box-værdi.

    Output:
        True, hvis mindst ét WorkItem matcher.
        False, hvis intet WorkItem matcher.
    """
    result = get_workitems_by_box_value(
        queue_id=queue_id,
        box_path=box_path,
        value=value,
        statuses=statuses,
        limit=1,
    )

    return result["exists"]


def _validate_box_path(box_path: str) -> str:
    """Kontrollér og returnér en sikker sti under data["box"]."""
    if not isinstance(box_path, str):
        raise TypeError(
            "box_path skal være tekst."
        )

    validated_box_path = box_path.strip()

    if not validated_box_path:
        raise ValueError(
            "box_path må ikke være tom."
        )

    if not _BOX_PATH_PATTERN.fullmatch(
        validated_box_path
    ):
        raise ValueError(
            "box_path har et ugyldigt format. Brug eksempelvis "
            "'memo_message_uuid', 'recipient.id' eller "
            "'submissions[].memo_message_uuid'."
        )

    return validated_box_path


def _build_json_path(box_path: str) -> str:
    """Lav box_path om til PostgreSQL JSONPath.

    Output:
        Eksempel:

        submissions[].memo_message_uuid

        bliver til:

        $.submissions[*].memo_message_uuid ? (@ == $search_value)
    """
    path_parts = []

    for part in box_path.split("."):
        if part.endswith("[]"):
            field_name = part[:-2]
            path_parts.append(
                f".{field_name}[*]"
            )
        else:
            path_parts.append(
                f".{part}"
            )

    return (
        "$"
        + "".join(path_parts)
        + " ? (@ == $search_value)"
    )


def _validate_statuses(
    statuses: list[str] | tuple[str, ...] | None,
) -> list[str]:
    """Kontrollér statusfilteret og returnér en liste."""
    if statuses is None:
        return list(ALL_WORKITEM_STATUSES)

    if not isinstance(statuses, (list, tuple)):
        raise TypeError(
            "statuses skal være en liste, tuple eller None."
        )

    if not statuses:
        raise ValueError(
            "statuses må ikke være en tom liste. Brug None for alle statusser."
        )

    validated_statuses = []

    for status in statuses:
        if not isinstance(status, str):
            raise TypeError(
                "Alle værdier i statuses skal være tekst."
            )

        validated_status = status.strip().upper()

        if validated_status not in ALL_WORKITEM_STATUSES:
            raise ValueError(
                f"Ukendt WorkItem-status: {status!r}. "
                f"Tilladte værdier: {list(ALL_WORKITEM_STATUSES)}."
            )

        if validated_status not in validated_statuses:
            validated_statuses.append(
                validated_status
            )

    return validated_statuses


def _validate_queue_id(queue_id: int | str) -> int:
    """Kontrollér queue_id og returnér et positivt helt tal."""
    if queue_id is None:
        raise ValueError(
            "queue_id skal angives og må ikke være None."
        )

    if isinstance(queue_id, bool):
        raise TypeError(
            "queue_id skal være et helt tal og må ikke være bool."
        )

    if isinstance(queue_id, str) and not queue_id.strip():
        raise ValueError(
            "queue_id må ikke være blank."
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


def _validate_limit(limit: int) -> int:
    """Kontrollér og returnér databasegrænsen."""
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError(
            "limit skal være et helt tal."
        )

    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(
            f"limit skal være mellem 1 og {MAX_LIMIT}."
        )

    return limit


def _parse_utc_datetime(
    value: datetime | str | None,
    *,
    field_name: str,
) -> datetime | None:
    """Omregn tidsværdi til UTC uden tidszonemarkering.

    Output:
        datetime i UTC uden tzinfo, fordi ATS-kolonnerne er
        timestamp without time zone.

        None, hvis input er None eller blank tekst.
    """
    if value is None:
        return None

    if isinstance(value, str):
        cleaned_value = value.strip()

        if not cleaned_value:
            return None

        if cleaned_value.endswith(("Z", "z")):
            cleaned_value = (
                cleaned_value[:-1]
                + "+00:00"
            )

        try:
            parsed_datetime = datetime.fromisoformat(
                cleaned_value
            )
        except ValueError as error:
            raise ValueError(
                f"{field_name} har et ugyldigt format. "
                "Brug eksempelvis '2026-07-01T00:00:00Z'."
            ) from error

    elif isinstance(value, datetime):
        parsed_datetime = value

    else:
        raise TypeError(
            f"{field_name} skal være datetime, tekst eller None."
        )

    if parsed_datetime.tzinfo is None:
        raise ValueError(
            f"{field_name} mangler tidszone. "
            "Angiv UTC som 'Z' eller '+00:00'."
        )

    return parsed_datetime.astimezone(
        timezone.utc
    ).replace(tzinfo=None)


def _validate_datetime_period(
    *,
    start_datetime: datetime | None,
    end_datetime: datetime | None,
) -> None:
    """Kontrollér at starttidspunktet ikke ligger efter sluttidspunktet."""
    if (
        start_datetime is not None
        and end_datetime is not None
        and start_datetime > end_datetime
    ):
        raise ValueError(
            "start_datetime må ikke ligge efter end_datetime."
        )
