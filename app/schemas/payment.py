from typing import Any

from pydantic import BaseModel, Field, model_validator


class PaymentSessionRead(BaseModel):
    registration_id: str
    participant_name: str
    race_category: str
    shirt_size: str
    payment_reference: str
    provider: str
    payment_method: str
    payment_status: str
    amount: float
    currency: str
    qr_code_url: str | None = None
    qr_code_payload: str | None = None
    payment_url: str | None = None
    expires_at: str | None = None
    paid_at: str | None = None
    raw_response: dict[str, Any] | None = None
    sms_status: str
    webhook_last_event: str | None = None
    webhook_last_event_at: str | None = None
    bib_number: str | None = None
    is_confirmed: bool


class PaymentProviderSession(BaseModel):
    provider: str
    payment_reference: str
    payment_status: str
    qr_code_url: str | None = None
    qr_code_payload: str | None = None
    payment_url: str | None = None
    expires_at: str | None = None
    raw_response: dict[str, Any] = Field(default_factory=dict)


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
