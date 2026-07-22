"""
Kontrollerer om en reference findes i en bestemt Automation Server-kø.

Funktionen læser kun fra databasen.
Funktionen ændrer ikke workitems.

Tidsfilteret bruger som standard created_at.
Hvis updated_at=True, bruges updated_at i stedet.
"""

from datetime import datetime, timezone

from psycopg2 import sql

from q_haderslev_vbo.automation_server.ats_database_connection import (
    get_connection,
)


# Statusværdier verificeret direkte i ATS-databasen.
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
    start_datetime: datetime | str | None = None,
    end_datetime: datetime | str | None = None,
    updated_at: bool = False,
) -> bool:
    """
    Kontrollerer om et workitem findes i en bestemt kø.

    Parametre:
        queue_id:
            Id på Automation Server-køen.

        item_reference:
            Den præcise reference, der skal søges efter.

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

        start_datetime:
            Valgfrit starttidspunkt.

            Tidspunktet er inkluderet i perioden.

            Eksempler:
            - "2026-07-01T00:00:00Z"
            - "2026-07-01T00:00:00+00:00"
            - datetime med tidszone

        end_datetime:
            Valgfrit sluttidspunkt.

            Tidspunktet er inkluderet i perioden.

        updated_at:
            False bruger created_at.
            True bruger updated_at.

    Hvis ingen status er valgt:
        Søges der i alle fem workitem-statusser.

    Hvis start_datetime og end_datetime mangler:
        Søges der uden tidsafgrænsning.

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

    # Standard er created_at.
    # Hvis updated_at=True, bruges updated_at.
    datetime_column = (
        "updated_at"
        if updated_at
        else "created_at"
    )

    query = sql.SQL(
        """
        SELECT EXISTS (
            SELECT 1
            FROM public.workitem
            WHERE workqueue_id = %s
              AND reference = %s
              AND status::text = ANY(%s)
              AND (
                  %s::timestamp IS NULL
                  OR {datetime_column} >= %s::timestamp
              )
              AND (
                  %s::timestamp IS NULL
                  OR {datetime_column} <= %s::timestamp
              )
        );
        """
    ).format(
        datetime_column=sql.Identifier(datetime_column)
    )

    connection = None

    try:
        connection = get_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    validated_queue_id,
                    validated_item_reference,
                    selected_statuses,
                    validated_start_datetime,
                    validated_start_datetime,
                    validated_end_datetime,
                    validated_end_datetime,
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
            "queue_id skal være et helt tal "
            "eller tekst med et helt tal."
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


def _parse_utc_datetime(
    value: datetime | str | None,
    *,
    field_name: str,
) -> datetime | None:
    """
    Omregner et tidspunkt til UTC uden tidszonemarkering.

    ATS forventes at gemme UTC i kolonner af typen
    timestamp without time zone.
    """

    if value is None:
        return None

    if isinstance(value, str):
        cleaned_value = value.strip()

        if not cleaned_value:
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
            f"{field_name} skal være datetime, tekst eller None."
        )

    if parsed_datetime.tzinfo is None:
        raise ValueError(
            f"{field_name} mangler tidszone. "
            "Angiv UTC som 'Z' eller '+00:00'."
        )

    utc_datetime = parsed_datetime.astimezone(
        timezone.utc
    )

    # ATS-kolonnen har ingen tidszonemarkering.
    # Værdien er først omregnet til UTC.
    return utc_datetime.replace(tzinfo=None)


def _validate_datetime_period(
    *,
    start_datetime: datetime | None,
    end_datetime: datetime | None,
) -> None:
    """
    Kontrollerer at start ikke ligger efter slut.
    """

    if (
        start_datetime is not None
        and end_datetime is not None
        and start_datetime > end_datetime
    ):
        raise ValueError(
            "start_datetime må ikke ligge efter end_datetime."
        )