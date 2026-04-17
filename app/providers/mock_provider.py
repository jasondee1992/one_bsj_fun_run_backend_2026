from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.models import Registration
from app.schemas.payment import PaymentProviderSession


class MockPaymentProvider:
    provider_name = "mock"

    def create_payment_session(self, registration: Registration) -> PaymentProviderSession:
        expires_at = datetime.now(UTC) + timedelta(minutes=settings.payment_session_ttl_minutes)
        amount = settings.default_registration_amount
        payload = (
            "onebsj://sandbox-payment?"
            f"registration_id={registration.registration_id}"
            f"&reference={registration.payment_reference}"
            f"&amount={amount:.2f}"
            f"&currency={settings.default_currency}"
        )

        return PaymentProviderSession(
            provider=self.provider_name,
            payment_reference=registration.payment_reference,
            payment_status="pending",
            qr_code_payload=payload,
            payment_url=None,
            expires_at=expires_at.isoformat(),
            raw_response={
                "mode": "sandbox",
                "provider": self.provider_name,
                "registration_id": registration.registration_id,
                "payment_reference": registration.payment_reference,
                "qr_code_payload": payload,
                "expires_at": expires_at.isoformat(),
            },
        )
