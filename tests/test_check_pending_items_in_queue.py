"""
Tester check_pending_items_in_queue mod den rigtige ATS-database.

Testen læser kun data.
Testen ændrer ikke workitems.

Kør fra projektets rodmappe:

    uv run python tests/test_check_pending_items_in_queue.py
"""

from q_haderslev_vbo.automation_server.ats_queue_status import (
    check_pending_items_in_queue,
)


# Ret værdien til id på den kø, der skal testes.
TEST_QUEUE_ID = 2


def test_check_pending_items_in_queue() -> None:
    """
    Tæller aktive items i den valgte kø.

    Alle input vises i kaldet:
    - queue_id
    - new
    - in_progress
    - pending_user_action
    """

    print("")
    print("=" * 70)
    print("TESTER AKTIVE ITEMS I KØEN")
    print("=" * 70)

    print(f"Queue id: {TEST_QUEUE_ID}")
    print("Medtager NEW: True")
    print("Medtager IN_PROGRESS: True")
    print("Medtager PENDING_USER_ACTION: True")

    result = check_pending_items_in_queue(
        queue_id=TEST_QUEUE_ID,
        new=True,
        in_progress=True,
        pending_user_action=True,
    )

    print("")
    print("Resultat:")
    print(f"Antal aktive items: {result['count']}")
    print(f"Findes aktive items: {result['exists']}")

    # Kontroller resultatets struktur.
    assert isinstance(result, dict), (
        "Resultatet skal være en dictionary."
    )

    assert "count" in result, (
        "Resultatet mangler feltet 'count'."
    )

    assert "exists" in result, (
        "Resultatet mangler feltet 'exists'."
    )

    # Kontroller typerne.
    assert isinstance(result["count"], int), (
        "'count' skal være et helt tal."
    )

    assert isinstance(result["exists"], bool), (
        "'exists' skal være True eller False."
    )

    # Antallet må aldrig være negativt.
    assert result["count"] >= 0, (
        "'count' må ikke være negativ."
    )

    # Kontroller sammenhængen mellem count og exists.
    assert result["exists"] == (result["count"] > 0), (
        "'exists' passer ikke med værdien i 'count'."
    )

    print("")

    if result["exists"]:
        print(
            f"ℹ️ Køen indeholder "
            f"{result['count']} aktiv(e) item(s)."
        )
    else:
        print("ℹ️ Køen indeholder ingen aktive items.")

    print("")
    print("✅ Testen af aktive items er OK.")


def test_all_statuses_disabled() -> None:
    """
    Kontrollerer resultatet, når alle statusser er slået fra.

    Funktionen skal returnere:
    - count = 0
    - exists = False
    """

    print("")
    print("=" * 70)
    print("TESTER ALLE STATUSSER SLÅET FRA")
    print("=" * 70)

    result = check_pending_items_in_queue(
        queue_id=TEST_QUEUE_ID,
        new=False,
        in_progress=False,
        pending_user_action=False,
    )

    print(f"Antal aktive items: {result['count']}")
    print(f"Findes aktive items: {result['exists']}")

    assert result["count"] == 0, (
        "Antallet skal være 0, når alle statusser er False."
    )

    assert result["exists"] is False, (
        "'exists' skal være False, "
        "når alle statusser er False."
    )

    print("")
    print("✅ Testen med alle statusser slået fra er OK.")


def run_all_tests() -> None:
    """
    Kører begge tests.
    """

    test_check_pending_items_in_queue()
    test_all_statuses_disabled()

    print("")
    print("=" * 70)
    print("✅ ALLE PENDING-TESTS ER FÆRDIGE")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()