import re
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class PaymentStatus(StrEnum):
    pending = "PENDING"
    pending_payment = "PENDING_PAYMENT"
    awaiting_payment = "AWAITING_PAYMENT"
    paid = "PAID"
    failed = "FAILED"
    payment_failed = "PAYMENT_FAILED"
    expired = "EXPIRED"
    cancelled = "CANCELLED"


class RaceCategory(StrEnum):
    three_k = "3K"
    five_k = "5K"
    ten_k = "10K"


class ShirtSize(StrEnum):
    xs = "XS"
    s = "S"
    m = "M"
    l = "L"
    xl = "XL"
    two_xl = "2XL"
    three_xl = "3XL"


PHONE_PATTERN = re.compile(r"^[0-9+() .-]{7,30}$")


def validate_phone(value: str) -> str:
    cleaned = value.strip()
    if not PHONE_PATTERN.fullmatch(cleaned):
        raise ValueError("Phone number must contain 7 to 30 valid phone characters")
    return cleaned


class RegistrationCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    suffix: str | None = Field(default=None, max_length=40)
    address: str = Field(min_length=1, max_length=500)
    city: str | None = Field(default=None, max_length=120)
    province: str | None = Field(default=None, max_length=120)
    cellphone_number: str
    email: EmailStr
    birthday: date
    sex: str = Field(min_length=1, max_length=40)
    emergency_contact_name: str = Field(min_length=1, max_length=240)
    emergency_contact_number: str
    race_category: RaceCategory
    shirt_size: ShirtSize
    medical_conditions: str | None = None
    notes: str | None = None
    waiver_accepted: bool
    privacy_consent_accepted: bool

    @field_validator(
        "first_name",
        "middle_name",
        "last_name",
        "suffix",
        "address",
        "city",
        "province",
        "sex",
        "emergency_contact_name",
        mode="before",
    )
    @classmethod
    def trim_short_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("medical_conditions", "notes", mode="before")
    @classmethod
    def trim_optional_long_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("cellphone_number", "emergency_contact_number")
    @classmethod
    def phone_number_is_valid(cls, value: str) -> str:
        return validate_phone(value)

    @model_validator(mode="after")
    def consents_must_be_accepted(self) -> "RegistrationCreate":
        if not self.waiver_accepted:
            raise ValueError("Waiver must be accepted")
        if not self.privacy_consent_accepted:
            raise ValueError("Privacy consent must be accepted")
        return self


class RegistrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    registration_id: str
    created_at: datetime
    updated_at: datetime
    first_name: str
    middle_name: str
    last_name: str
    suffix: str | None
    full_name: str
    address: str
    city: str | None
    province: str | None
    cellphone_number: str
    email: EmailStr
    birthday: date
    sex: str
    emergency_contact_name: str
    emergency_contact_number: str
    race_category: str
    shirt_size: str
    medical_conditions: str | None
    notes: str | None
    waiver_accepted: bool
    privacy_consent_accepted: bool
    payment_status: str
    payment_reference: str
    provider_transaction_id: str | None
    paid_at: datetime | None
    bib_number: str | None
    sms_sent: bool
    sms_sent_at: datetime | None


class RegistrationStatusRead(BaseModel):
    registration_id: str
    full_name: str
    payment_status: str
    payment_reference: str
    bib_number: str | None
    race_category: str
    sms_sent: bool
    sms_sent_at: datetime | None
    paid_at: datetime | None
