"""
Små hjælpefunktioner til opslag i Automation Server-køer.

Filen indeholder:

1. check_pending_items_in_queue()
   Tæller aktive items i en bestemt kø.

2. get_completed_items_in_period()
   Henter completed items fra en bestemt periode.

Funktionerne læser kun fra databasen.
Funktionerne ændrer ikke workitems.
"""

from datetime import datetime, timezone
from typing import Any

from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from q_haderslev_vbo.automation_server.ats_database_connection import (
    get_connection,
)


def check_pending_items_in_queue(
    queue_id: int | str,
    *,
    new: bool = True,
    in_progress: bool = True,
    pending_user_action: bool = True,
) -> dict[str, int | bool]:
    """
    Kontrollerer om køen indeholder aktive items.

    Som standard tælles disse statusser:

    - NEW
    - IN_PROGRESS
    - PENDING_USER_ACTION

    Parametre:
        queue_id:
            Id på den kø, der skal undersøges.

        new:
            True medtager status NEW.
            Standard er True.

        in_progress:
            True medtager status IN_PROGRESS.
            Standard er True.

        pending_user_action:
            True medtager status PENDING_USER_ACTION.
            Standard er True.

    Returnerer:
        En dictionary med:

        - count: Antal fundne items.
        - exists: True, hvis mindst ét item findes.

    Eksempel på resultat:

        {
            "count": 3,
            "exists": True,
        }
    """

    validated_queue_id = _validate_queue_id(queue_id)

    selected_statuses = _build_pending_status_filter(
        new=new,
        in_progress=in_progress,
        pending_user_action=pending_user_action,
    )

    # Hvis alle statusser er slået fra, kan intet matche.
    if not selected_statuses:
        return {
            "count": 0,
            "exists": False,
        }

    connection = None

    try:
        connection = get_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM public.workitem
                WHERE workqueue_id = %s
                  AND status::text = ANY(%s);
                """,
                (
                    validated_queue_id,
                    selected_statuses,
                ),
            )

            result = cursor.fetchone()

        if result is None:
            raise RuntimeError(
                "Databasen returnerede ikke et resultat."
            )

        item_count = int(result[0])

        return {
            "count": item_count,
            "exists": item_count > 0,
        }

    finally:
        if connection is not None:
            connection.close()


def get_completed_items_in_period(
    queue_id: int | str,
    start_datetime: datetime | str,
    end_datetime: datetime | str,
    *,
    updated_at: bool = False,
) -> dict[str, Any]:
    """
    Henter completed items fra en bestemt kø og periode.

    Parametre:
        queue_id:
            Id på den kø, der skal undersøges.

        start_datetime:
            Periodens starttidspunkt.

            Starttidspunktet er inkluderet.

            Accepterer:
            - datetime med tidszone
            - ISO-tekst med tidszone
            - ISO-tekst med Z for UTC

        end_datetime:
            Periodens sluttidspunkt.

            Sluttidspunktet er inkluderet.

        updated_at:
            False søger i created_at.
            True søger i updated_at.

            Standard er False.

    Returnerer:
        En dictionary med:

        - count: Antal fundne items.
        - exists: True, hvis mindst ét item findes.
        - items: Liste med de fundne items.
        - datetime_field: Det anvendte tidsfelt.

    Eksempel på resultat:

        {
            "count": 2,
            "exists": True,
            "datetime_field": "created_at",
            "items": [
                {
                    "id": 123,
                    "reference": "ABC-123",
                    "status": "COMPLETED",
                    ...
                }
            ],
        }
    """

    validated_queue_id = _validate_queue_id(queue_id)

    validated_start_datetime = _parse_utc_datetime(
        start_datetime,
        field_name="start_datetime",
        required=True,
    )

    validated_end_datetime = _parse_utc_datetime(
        end_datetime,
        field_name="end_datetime",
        required=True,
    )

    if validated_start_datetime > validated_end_datetime:
        raise ValueError(
            "start_datetime må ikke ligge efter end_datetime."
        )

    if not isinstance(updated_at, bool):
        raise TypeError(
            "updated_at skal være True eller False."
        )

    datetime_field = (
        "updated_at"
        if updated_at
        else "created_at"
    )

    # Kolonnen kan ikke sendes som en almindelig SQL-værdi.
    # sql.Identifier indsætter kolonnen sikkert.
    query = sql.SQL(
        """
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
          AND status::text = 'COMPLETED'
          AND {datetime_field} >= %s::timestamp
          AND {datetime_field} <= %s::timestamp
        ORDER BY {datetime_field} ASC;
        """
    ).format(
        datetime_field=sql.Identifier(datetime_field)
    )

    connection = None

    try:
        connection = get_connection()

        # RealDictCursor gør hver række til en dictionary.
        with connection.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                query,
                (
                    validated_queue_id,
                    validated_start_datetime,
                    validated_end_datetime,
                ),
            )

            rows = cursor.fetchall()

        items = [
            dict(row)
            for row in rows
        ]

        item_count = len(items)

        return {
            "count": item_count,
            "exists": item_count > 0,
            "datetime_field": datetime_field,
            "items": items,
        }

    finally:
        if connection is not None:
            connection.close()


def _build_pending_status_filter(
    *,
    new: bool,
    in_progress: bool,
    pending_user_action: bool,
) -> list:
    """
    Bygger listen over aktive statusser.
    """

    status_choices = {
        "NEW": new,
        "IN_PROGRESS": in_progress,
        "PENDING_USER_ACTION": pending_user_action,
    }

    for input_name, input_value in status_choices.items():
        if not isinstance(input_value, bool):
            raise TypeError(
                f"{input_name.lower()} skal være True eller False."
            )

    return [
        status
        for status, is_selected in status_choices.items()
        if is_selected
    ]


def _validate_queue_id(queue_id: int | str) -> int:
    """
    Kontrollerer queue_id og returnerer et helt tal.
    """

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
            "queue_id skal angives og må ikke være blank."
        )

    try:
        validated_queue_id = int(queue_id)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "queue_id skal være et helt tal "
            "eller tekst med et helt tal."
        ) from error

    if validated_queue_id <= 0:
        raise ValueError(
            "queue_id skal være større end 0."
        )

    return validated_queue_id


def _parse_utc_datetime(
    value: datetime | str | None,
    *,
    field_name: str,
    required: bool,
) -> datetime | None:
    """
    Omregner et tidspunkt til UTC uden tidszonemarkering.

    ATS forventes at gemme UTC i kolonner af typen
    timestamp without time zone.
    """

    if value is None:
        if required:
            raise ValueError(
                f"{field_name} skal angives."
            )

        return None

    if isinstance(value, str):
        cleaned_value = value.strip()

        if not cleaned_value:
            if required:
                raise ValueError(
                    f"{field_name} skal angives."
                )

            return None

        # Z betyder UTC.
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
                "Brug eksempelvis "
                "'2026-07-01T00:00:00Z'."
            ) from error

    elif isinstance(value, datetime):
        parsed_datetime = value

    else:
        raise TypeError(
            f"{field_name} skal være datetime eller tekst."
        )

    if parsed_datetime.tzinfo is None:
        raise ValueError(
            f"{field_name} mangler tidszone. "
            "Angiv eksempelvis 'Z' eller '+00:00'."
        )

    utc_datetime = parsed_datetime.astimezone(
        timezone.utc
    )

    # Værdien er UTC.
    # Tidszonemarkeringen fjernes, fordi ATS-kolonnerne
    # er timestamp without time zone.
    return utc_datetime.replace(tzinfo=None)


def get_expired_pending_user_items(
    *,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Henter PENDING_USER_ACTION-items, hvor defer-tidspunktet
    er nået eller overskredet.

    Funktionen læser kun fra databasen.
    Funktionen ændrer ikke workitems eller item-data.

    Parametre:
        limit:
            Det maksimale antal items, der returneres.
            Skal være mellem 1 og 1000.

    Returnerer:
        En dictionary med:

        - count: Antal fundne items.
        - exists: True, hvis mindst ét item findes.
        - items: Liste med databaserækker.

    Bemærk:
        data["defer"] forventes at indeholde et ISO 8601-tidspunkt
        med tidszone, eksempelvis:

        2026-07-21T13:05:00Z
    """

    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError(
            "limit skal være et helt tal og må ikke være bool."
        )

    if not 1 <= limit <= 1000:
        raise ValueError(
            "limit skal være mellem 1 og 1000."
        )

    query = """
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
        WHERE status::text = 'PENDING_USER_ACTION'
          AND data ? 'defer'
          AND NULLIF(data ->> 'defer', '') IS NOT NULL
          AND (data ->> 'defer')::timestamptz <= NOW()
        ORDER BY
            (data ->> 'defer')::timestamptz ASC,
            id ASC
        LIMIT %s;
    """

    connection = None

    try:
        connection = get_connection()

        with connection.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                query,
                (limit,),
            )

            rows = cursor.fetchall()

        items = [
            dict(row)
            for row in rows
        ]

        item_count = len(items)

        return {
            "count": item_count,
            "exists": item_count > 0,
            "items": items,
        }

    finally:
        if connection is not None:
            connection.close()