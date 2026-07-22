"""
Tester get_completed_items_in_period mod den rigtige ATS-database.

Testen læser kun data.
Testen ændrer ikke workitems.

Kør fra projektets rodmappe:

    uv run python tests/test_get_completed_items_in_period.py
"""

from datetime import datetime

from q_haderslev_vbo.automation_server.ats_queue_status import (
    get_completed_items_in_period,
)


# Ret værdien til id på den kø, der skal testes.
TEST_QUEUE_ID = 4

# Perioden angives i UTC.
TEST_START_DATETIME = "2026-01-01T00:00:00Z"
TEST_END_DATETIME = "2026-12-31T23:59:59.999999Z"

# False betyder, at perioden anvendes på created_at.
# True betyder, at perioden anvendes på updated_at.
TEST_UPDATED_AT = False


def test_get_completed_items_in_period() -> None:
    """
    Henter completed items fra den valgte kø og periode.

    Alle input vises i kaldet:
    - queue_id
    - start_datetime
    - end_datetime
    - updated_at
    """

    print("")
    print("=" * 70)
    print("TESTER COMPLETED ITEMS I EN PERIODE")
    print("=" * 70)

    print(f"Queue id: {TEST_QUEUE_ID}")
    print(f"Start: {TEST_START_DATETIME}")
    print(f"Slut: {TEST_END_DATETIME}")
    print(f"Updated at: {TEST_UPDATED_AT}")

    result = get_completed_items_in_period(
        queue_id=TEST_QUEUE_ID,
        start_datetime=TEST_START_DATETIME,
        end_datetime=TEST_END_DATETIME,
        updated_at=TEST_UPDATED_AT,
    )

    print("")
    print("Resultat:")
    print(f"Anvendt tidsfelt: {result['datetime_field']}")
    print(f"Antal completed items: {result['count']}")
    print(f"Findes completed items: {result['exists']}")

    # Kontroller resultatets struktur.
    assert isinstance(result, dict), (
        "Resultatet skal være en dictionary."
    )

    expected_fields = {
        "count",
        "exists",
        "datetime_field",
        "items",
    }

    missing_fields = expected_fields.difference(result)

    assert not missing_fields, (
        f"Resultatet mangler felter: {sorted(missing_fields)}"
    )

    # Kontroller typerne.
    assert isinstance(result["count"], int), (
        "'count' skal være et helt tal."
    )

    assert isinstance(result["exists"], bool), (
        "'exists' skal være True eller False."
    )

    assert isinstance(result["datetime_field"], str), (
        "'datetime_field' skal være tekst."
    )

    assert isinstance(result["items"], list), (
        "'items' skal være en liste."
    )

    # Kontroller sammenhængen mellem værdierne.
    assert result["count"] == len(result["items"]), (
        "'count' skal være lig med antal items i listen."
    )

    assert result["exists"] == (result["count"] > 0), (
        "'exists' passer ikke med værdien i 'count'."
    )

    expected_datetime_field = (
        "updated_at"
        if TEST_UPDATED_AT
        else "created_at"
    )

    assert result["datetime_field"] == expected_datetime_field, (
        "Funktionen brugte ikke det forventede tidsfelt."
    )

    # Omregn testperioden til datetime-objekter.
    start_datetime = _parse_test_datetime(
        TEST_START_DATETIME
    )

    end_datetime = _parse_test_datetime(
        TEST_END_DATETIME
    )

    print("")
    print("Fundne items:")

    if not result["items"]:
        print("  Ingen completed items i perioden.")

    for item in result["items"]:
        _validate_completed_item(
            item=item,
            queue_id=TEST_QUEUE_ID,
            datetime_field=expected_datetime_field,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
        )

        print(
            f"  - Id: {item['id']} | "
            f"Reference: {item['reference']} | "
            f"Status: {item['status']} | "
            f"{expected_datetime_field}: "
            f"{item[expected_datetime_field]}"
        )

    print("")
    print("✅ Testen af completed items er OK.")


def _validate_completed_item(
    *,
    item: dict,
    queue_id: int,
    datetime_field: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> None:
    """
    Kontrollerer ét returneret item.
    """

    assert isinstance(item, dict), (
        "Hvert item skal være en dictionary."
    )

    expected_item_fields = {
        "id",
        "data",
        "reference",
        "locked",
        "status",
        "message",
        "workqueue_id",
        "created_at",
        "updated_at",
        "started_at",
        "work_duration_seconds",
    }

    missing_fields = expected_item_fields.difference(item)

    assert not missing_fields, (
        f"Et item mangler felter: {sorted(missing_fields)}"
    )

    # Funktionen må kun returnere completed items.
    assert item["status"] == "COMPLETED", (
        f"Item {item['id']} har status "
        f"{item['status']} i stedet for COMPLETED."
    )

    # Itemet skal høre til den valgte kø.
    assert item["workqueue_id"] == int(queue_id), (
        f"Item {item['id']} tilhører queue "
        f"{item['workqueue_id']} i stedet for {queue_id}."
    )

    item_datetime = item[datetime_field]

    assert isinstance(item_datetime, datetime), (
        f"Itemets {datetime_field} skal være et datetime-objekt."
    )

    # ATS-tiderne returneres uden tidszone og repræsenterer UTC.
    assert start_datetime <= item_datetime <= end_datetime, (
        f"Item {item['id']} ligger uden for testperioden. "
        f"{datetime_field}: {item_datetime}"
    )


def _parse_test_datetime(value: str) -> datetime:
    """
    Laver UTC-tekst om til datetime uden tidszone.

    Databasekolonnerne er timestamp without time zone.
    """

    cleaned_value = value.strip()

    if cleaned_value.endswith(("Z", "z")):
        cleaned_value = cleaned_value[:-1] + "+00:00"

    parsed_datetime = datetime.fromisoformat(
        cleaned_value
    )

    # Omregning er ikke nødvendig for Z eller +00:00,
    # men tidszonemarkeringen fjernes før sammenligningen.
    return parsed_datetime.replace(tzinfo=None)


if __name__ == "__main__":
    test_get_completed_items_in_period()