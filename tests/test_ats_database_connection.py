"""
Undersøger Automation Server-databasens workitem-tabeller og statusser.

Testen laver kun SELECT-kald og ændrer derfor ikke data.

Kør fra q-haderslev-vbo-projektets rodmappe:

    uv run python tests/test_ats_database_connection.py
"""

from psycopg2 import sql

from q_haderslev_vbo.automation_server.ats_database_connection import (
    get_connection,
)


def test_ats_database_connection() -> None:
    """
    Tester databaseforbindelsen og undersøger workitem-tabeller.
    """

    connection = None

    try:
        print("")
        print("=" * 70)
        print("1. TESTER FORBINDELSEN TIL AUTOMATION SERVER-DATABASEN")
        print("=" * 70)

        connection = get_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    current_database(),
                    current_user,
                    NOW();
                """
            )

            connection_result = cursor.fetchone()

            if connection_result is None:
                raise RuntimeError(
                    "Databasen returnerede ikke forbindelsesoplysninger."
                )

            database_name, database_user, database_time = connection_result

            print(f"Database: {database_name}")
            print(f"Databasebruger: {database_user}")
            print(f"Databasetid: {database_time}")
            print("")
            print("✅ Forbindelsen til databasen virker.")

            # ---------------------------------------------------------
            # Find relevante tabeller
            # ---------------------------------------------------------

            print("")
            print("=" * 70)
            print("2. FINDER RELEVANTE TABELLER")
            print("=" * 70)

            cursor.execute(
                """
                SELECT
                    table_schema,
                    table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema NOT IN (
                      'pg_catalog',
                      'information_schema'
                  )
                  AND (
                      LOWER(table_name) LIKE '%workitem%'
                      OR LOWER(table_name) LIKE '%work_item%'
                      OR LOWER(table_name) LIKE '%workqueue%'
                      OR LOWER(table_name) LIKE '%work_queue%'
                      OR LOWER(table_name) LIKE '%queue%'
                  )
                ORDER BY
                    table_schema,
                    table_name;
                """
            )

            relevant_tables = cursor.fetchall()

            if not relevant_tables:
                print("⚠️ Ingen relevante workitem- eller queue-tabeller fundet.")
                print("")
                print("Alle almindelige tabeller i databasen:")

                cursor.execute(
                    """
                    SELECT
                        table_schema,
                        table_name
                    FROM information_schema.tables
                    WHERE table_type = 'BASE TABLE'
                      AND table_schema NOT IN (
                          'pg_catalog',
                          'information_schema'
                      )
                    ORDER BY
                        table_schema,
                        table_name;
                    """
                )

                all_tables = cursor.fetchall()

                for table_schema, table_name in all_tables:
                    print(f"  - {table_schema}.{table_name}")

                return

            print("Relevante tabeller:")

            for table_schema, table_name in relevant_tables:
                print(f"  - {table_schema}.{table_name}")

            # ---------------------------------------------------------
            # Vis kolonner i relevante tabeller
            # ---------------------------------------------------------

            print("")
            print("=" * 70)
            print("3. VISER KOLONNER I DE RELEVANTE TABELLER")
            print("=" * 70)

            tables_with_status = []

            for table_schema, table_name in relevant_tables:
                print("")
                print(f"Tabel: {table_schema}.{table_name}")

                cursor.execute(
                    """
                    SELECT
                        column_name,
                        data_type,
                        udt_name,
                        is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = %s
                    ORDER BY ordinal_position;
                    """,
                    (
                        table_schema,
                        table_name,
                    ),
                )

                columns = cursor.fetchall()

                if not columns:
                    print("  Ingen kolonner fundet.")
                    continue

                column_names = []

                for (
                    column_name,
                    data_type,
                    udt_name,
                    is_nullable,
                ) in columns:
                    column_names.append(column_name)

                    print(
                        f"  - {column_name}"
                        f" | type: {data_type}"
                        f" | intern type: {udt_name}"
                        f" | nullable: {is_nullable}"
                    )

                if "status" in column_names:
                    tables_with_status.append(
                        (
                            table_schema,
                            table_name,
                        )
                    )

            # ---------------------------------------------------------
            # Vis anvendte statusværdier
            # ---------------------------------------------------------

            print("")
            print("=" * 70)
            print("4. VISER STATUSVÆRDIER")
            print("=" * 70)

            if not tables_with_status:
                print(
                    "⚠️ Ingen af de relevante tabeller "
                    "har en kolonne med navnet 'status'."
                )
            else:
                for table_schema, table_name in tables_with_status:
                    print("")
                    print(f"Tabel: {table_schema}.{table_name}")

                    status_query = sql.SQL(
                        """
                        SELECT
                            status::text AS status,
                            COUNT(*) AS antal
                        FROM {}.{}
                        GROUP BY status::text
                        ORDER BY status::text;
                        """
                    ).format(
                        sql.Identifier(table_schema),
                        sql.Identifier(table_name),
                    )

                    cursor.execute(status_query)
                    status_rows = cursor.fetchall()

                    if not status_rows:
                        print("  Tabellen indeholder ingen rækker.")
                        continue

                    for status, antal in status_rows:
                        print(f"  - {status}: {antal} item(s)")

            # ---------------------------------------------------------
            # Undersøg om status er en PostgreSQL-enum
            # ---------------------------------------------------------

            print("")
            print("=" * 70)
            print("5. VISER ALLE TILLADTE ENUM-STATUSSER")
            print("=" * 70)

            cursor.execute(
                """
                SELECT DISTINCT
                    columns.table_schema,
                    columns.table_name,
                    columns.column_name,
                    enum_type.typname AS enum_type,
                    enum_value.enumlabel AS enum_value,
                    enum_value.enumsortorder
                FROM information_schema.columns AS columns
                JOIN pg_namespace AS namespace
                    ON namespace.nspname = columns.udt_schema
                JOIN pg_type AS enum_type
                    ON enum_type.typname = columns.udt_name
                    AND enum_type.typnamespace = namespace.oid
                JOIN pg_enum AS enum_value
                    ON enum_value.enumtypid = enum_type.oid
                WHERE columns.column_name = 'status'
                ORDER BY
                    columns.table_schema,
                    columns.table_name,
                    enum_value.enumsortorder;
                """
            )

            enum_rows = cursor.fetchall()

            if not enum_rows:
                print(
                    "Statuskolonnen er ikke en PostgreSQL-enum, "
                    "eller databasebrugeren kan ikke se enum-oplysningerne."
                )
            else:
                current_table = None

                for (
                    table_schema,
                    table_name,
                    column_name,
                    enum_type,
                    enum_value,
                    _sort_order,
                ) in enum_rows:
                    table_identifier = (
                        table_schema,
                        table_name,
                        column_name,
                        enum_type,
                    )

                    if table_identifier != current_table:
                        print("")
                        print(
                            f"{table_schema}.{table_name}.{column_name}"
                            f" | enum-type: {enum_type}"
                        )
                        current_table = table_identifier

                    print(f"  - {enum_value}")

        print("")
        print("=" * 70)
        print("✅ DATABASEUNDERSØGELSEN ER FÆRDIG")
        print("=" * 70)

    except Exception as error:
        print("")
        print("=" * 70)
        print("❌ DATABASEUNDERSØGELSEN FEJLEDE")
        print("=" * 70)
        print(f"Fejltype: {type(error).__name__}")
        print(f"Fejl: {error}")

        raise

    finally:
        if connection is not None:
            connection.close()
            print("")
            print("Databaseforbindelsen er lukket.")


if __name__ == "__main__":
    test_ats_database_connection()