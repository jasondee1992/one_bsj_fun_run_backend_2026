from typing import Protocol

from app.models import Registration
from app.schemas.payment import PaymentProviderSession


class PaymentProvider(Protocol):
    provider_name: str

    def create_payment_session(self, registration: Registration) -> PaymentProviderSession:
        raise NotImplementedError
