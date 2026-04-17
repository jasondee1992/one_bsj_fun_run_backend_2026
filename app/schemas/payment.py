from typing import Any

from pydantic import BaseModel, Field, model_validator


class MockPaymentSuccessRequest(BaseModel):
    registration_id: str | None = Field(default=None, max_length=40)
    payment_reference: str | None = Field(default=None, max_length=80)
    provider_transaction_id: str | None = Field(default=None, max_length=120)
    amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=10)

    @model_validator(mode="after")
    def has_registration_or_reference(self) -> "MockPaymentSuccessRequest":
        if not self.registration_id and not self.payment_reference:
            raise ValueError("registration_id or payment_reference is required")
        return self


class WebhookRequest(BaseModel):
    source: str | None = Field(default="generic", max_length=80)
    event_type: str | None = Field(default=None, max_length=120)
    external_event_id: str | None = Field(default=None, max_length=160)
    data: dict[str, Any] | None = None

    model_config = {"extra": "allow"}

