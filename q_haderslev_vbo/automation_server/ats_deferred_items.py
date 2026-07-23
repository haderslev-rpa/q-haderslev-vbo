"""
Databaseopslag til Automation Server defer-monitor.

Placering i q-haderslev-vbo:
q_haderslev_vbo/automation_server/ats_deferred_items.py

Funktionerne læser kun fra PostgreSQL.
Statusændringer foretages aldrig direkte i databasen.
"""

from typing import Any

from psycopg2.extras import RealDictCursor

from q_haderslev_vbo.automation_server.ats_database_connection import (
    get_connection,
)


def get_expired_pending_user_items(
    *,
    limit: int = 100,
    only_item_id: int | str | None = None,
) -> dict[str, Any]:
    """
    Henter PENDING_USER_ACTION-items med et udløbet defer-tidspunkt.

    Der søges automatisk på tværs af alle workqueues.
    Den kaldende proces skal derfor ikke angive et workqueue-id.

    only_item_id bruges kun til integrationstest og fejlfinding.
    """
    validated_limit = _validate_limit(limit)
    validated_item_id = (
        _validate_item_id(only_item_id)
        if only_item_id is not None
        else None
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
          AND (%s::bigint IS NULL OR id = %s::bigint)
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
                (
                    validated_item_id,
                    validated_item_id,
                    validated_limit,
                ),
            )
            rows = cursor.fetchall()

        items = [dict(row) for row in rows]

        return {
            "count": len(items),
            "exists": bool(items),
            "items": items,
        }

    finally:
        if connection is not None:
            connection.close()


def get_workitem_database_row_by_id(
    item_id: int | str,
) -> dict[str, Any]:
    """Henter præcis én workitem-række via det tekniske item-id."""
    validated_item_id = _validate_item_id(item_id)

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
        WHERE id = %s;
    """

    connection = None

    try:
        connection = get_connection()

        with connection.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(query, (validated_item_id,))
            row = cursor.fetchone()

        if row is None:
            raise RuntimeError(
                f"Workitem-id {validated_item_id} blev ikke fundet i databasen."
            )

        return dict(row)

    finally:
        if connection is not None:
            connection.close()


def _validate_item_id(item_id: int | str) -> int:
    if item_id is None:
        raise ValueError("item_id skal angives.")

    if isinstance(item_id, bool):
        raise TypeError("item_id må ikke være bool.")

    try:
        validated_item_id = int(item_id)
    except (TypeError, ValueError) as error:
        raise ValueError("item_id skal være et helt tal.") from error

    if validated_item_id <= 0:
        raise ValueError("item_id skal være større end 0.")

    return validated_item_id


def _validate_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError("limit skal være et helt tal.")

    if not 1 <= limit <= 1000:
        raise ValueError("limit skal være mellem 1 og 1000.")

    return limit
