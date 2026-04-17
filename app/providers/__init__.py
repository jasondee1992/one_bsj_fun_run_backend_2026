from app.core.config import settings
from app.providers.base import PaymentProvider
from app.providers.generic_gateway_provider import GenericGatewayProvider
from app.providers.mock_provider import MockPaymentProvider


def get_payment_provider() -> PaymentProvider:
    provider = settings.payment_provider.lower()
    if provider in {"generic", "gateway", "paymongo"} and settings.payment_secret_key:
        return GenericGatewayProvider()
    return MockPaymentProvider()
