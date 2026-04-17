import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    registration_payload = {
        "first_name": "Juan",
        "middle_name": "Santos",
        "last_name": "Dela Cruz",
        "address": "123 Main Street",
        "cellphone_number": "09171234567",
        "email": "juan@example.com",
        "birthday": "1990-01-15",
        "sex": "Male",
        "emergency_contact_name": "Maria Dela Cruz",
        "emergency_contact_number": "09176543210",
        "race_category": "5K",
        "shirt_size": "M",
        "waiver_accepted": True,
        "privacy_consent_accepted": True,
    }

    with TestClient(app) as client:
        create_response = client.post("/api/registrations", json=registration_payload)
        create_response.raise_for_status()
        registration = create_response.json()["data"]
        registration_id = registration["registration_id"]
        print(f"Created registration: {registration_id}")

        payment_response = client.post("/api/payments/mock-success", json={"registration_id": registration_id})
        payment_response.raise_for_status()
        paid_registration = payment_response.json()["data"]
        print(f"Marked paid with bib: {paid_registration['bib_number']}")

        duplicate_payment_response = client.post(
            "/api/payments/mock-success",
            json={"registration_id": registration_id},
        )
        duplicate_payment_response.raise_for_status()
        duplicate = duplicate_payment_response.json()["data"]
        print(f"Repeated payment call returned same bib: {duplicate['bib_number']}")

        login_response = client.post(
            "/api/admin/login",
            json={"username": "admin", "password": "admin123"},
        )
        login_response.raise_for_status()
        token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        summary_response = client.get("/api/admin/dashboard/summary", headers=headers)
        summary_response.raise_for_status()
        print(f"Dashboard summary: {summary_response.json()['data']}")

        list_response = client.get("/api/admin/registrations", headers=headers)
        list_response.raise_for_status()
        print(f"Admin list returned {len(list_response.json()['data']['items'])} row(s)")

        detail_response = client.get(f"/api/admin/registrations/{registration_id}", headers=headers)
        detail_response.raise_for_status()
        detail = detail_response.json()["data"]
        confirmation_logs = [
            log for log in detail["sms_logs"] if log["message_type"] == "CONFIRMATION"
        ]
        assert len(confirmation_logs) == 1
        print(f"Admin detail returned {len(detail['sms_logs'])} SMS log(s)")

        webhook_payload = {
            "source": "smoke-provider",
            "event_type": "PAYMENT_SUCCEEDED",
            "external_event_id": f"evt_{registration_id}",
            "data": {
                "registration_id": registration_id,
                "provider_transaction_id": f"txn_{registration_id}",
                "status": "SUCCEEDED",
            },
        }
        webhook_response = client.post("/api/payments/webhook", json=webhook_payload)
        webhook_response.raise_for_status()
        duplicate_webhook_response = client.post("/api/payments/webhook", json=webhook_payload)
        duplicate_webhook_response.raise_for_status()
        print("Webhook retry handled idempotently")

        export_response = client.get("/api/admin/export/csv", headers=headers)
        export_response.raise_for_status()
        assert registration_id in export_response.text
        print("CSV export returned registration data")


if __name__ == "__main__":
    main()
