"""
Tester is_item_in_queue mod den rigtige ATS-database.

Ret TEST_QUEUE_ID og TEST_REFERENCE inden testen køres.
"""
import os

from q_haderslev_vbo.automation_server.ats_is_item_in_queue import (
    is_item_in_queue,
)


TEST_QUEUE_ID = 2
TEST_REFERENCE = os.getenv("test_cpr2")


def run_test() -> None:
    """
    Søger efter testreferencen i alle statusser.
    """

    print("")
    print("=" * 70)
    print("TESTER IS_ITEM_IN_QUEUE")
    print("=" * 70)

    print(f"Queue id: {TEST_QUEUE_ID}")
    print(f"Reference: {TEST_REFERENCE}")

    item_exists = is_item_in_queue(
        queue_id=TEST_QUEUE_ID,
        item_reference=TEST_REFERENCE,
        completed=False,
        failed=False,
        in_progress=True,
        new=False,
        pending_user_action=False,
    )

    print("")
    print(f"Findes item: {item_exists}")

    if item_exists:
        print("✅ Item blev fundet i køen.")
    else:
        print("ℹ️ Item blev ikke fundet i køen.")

    print("")
    print("=" * 70)
    print("✅ TESTEN ER FÆRDIG")
    print("=" * 70)


if __name__ == "__main__":
    run_test()