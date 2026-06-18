# test_sp_files.py

from q_haderslev_vbo.automation_server.sharepoint.sp_api import get_client


def run_test():
    print("🚀 Starter test...")

    client = get_client()  # objekt (konkret instans af klasse)

    site_name = "Automatisering"
    base_path = "Test"

    # 1. Hent site
    site_id = client.get_site_id(site_name)
    print("✅ Site ID:", site_id)

    # 2. Hent drive
    drive_id = client.get_drive_id(site_id)
    print("✅ Drive ID:", drive_id)

    # 3. Opret mappe
    folder = client.create_folder(
        drive_id,
        base_path,
        "NyMappeFraNytRepo"
    )

    folder_id = folder["id"]
    print("✅ Mappe oprettet:", folder_id)

    # 4. Upload fil
    content = b"Hej igen"

    uploaded = client.upload_file(
        drive_id,
        "Test/NyMappeFraNytRepo",
        "test.txt",
        content
    )

    print("✅ Fil uploadet:", uploaded["id"])

    # 5. Slet mappe
    client.delete_item(drive_id, folder_id)

    print("🗑️ Mappe slettet")
    print("✅ TEST OK")


if __name__ == "__main__":
    run_test()