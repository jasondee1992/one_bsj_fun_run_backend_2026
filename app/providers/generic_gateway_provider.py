from app.core.config import settings
from app.models import Registration
from app.providers.mock_provider import MockPaymentProvider
from app.schemas.payment import PaymentProviderSession


class GenericGatewayProvider:
    provider_name = "generic_gateway"

    def create_payment_session(self, registration: Registration) -> PaymentProviderSession:
        # Provider SDK wiring belongs here. Until credentials and SDK details are
        # configured, keep local development usable through the normalized mock flow.
        fallback = MockPaymentProvider().create_payment_session(registration)
        fallback.provider = self.provider_name
        fallback.raw_response = {
            **fallback.raw_response,
            "mode": settings.payment_mode,
            "provider_ready": bool(settings.payment_secret_key),
            "note": "Generic gateway adapter is ready for provider SDK wiring.",
        }
        return fallback
