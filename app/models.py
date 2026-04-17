from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Registration(Base, TimestampMixin):
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    registration_id: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    suffix: Mapped[str | None] = mapped_column(String(40))
    full_name: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str | None] = mapped_column(String(120))
    province: Mapped[str | None] = mapped_column(String(120))
    cellphone_number: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    birthday: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[str] = mapped_column(String(40), nullable=False)
    emergency_contact_name: Mapped[str] = mapped_column(String(240), nullable=False)
    emergency_contact_number: Mapped[str] = mapped_column(String(40), nullable=False)
    race_category: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    shirt_size: Mapped[str] = mapped_column(String(20), nullable=False)
    medical_conditions: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    waiver_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    privacy_consent_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    payment_status: Mapped[str] = mapped_column(String(40), index=True, nullable=False, default="PENDING_PAYMENT")
    payment_reference: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(120), index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bib_number: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    sms_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sms_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    payments: Mapped[list["Payment"]] = relationship(back_populates="registration")
    sms_logs: Mapped[list["SmsLog"]] = relationship(back_populates="registration")


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    registration_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("registrations.registration_id"),
        index=True,
        nullable=False,
    )
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False, default="mock")
    payment_method: Mapped[str | None] = mapped_column(String(80))
    payment_reference: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(120), index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="PHP")
    status: Mapped[str] = mapped_column(String(40), index=True, nullable=False, default="PENDING_PAYMENT")
    qr_code_url: Mapped[str | None] = mapped_column(String(1000))
    qr_code_payload: Mapped[str | None] = mapped_column(Text)
    payment_url: Mapped[str | None] = mapped_column(String(1000))
    raw_payload: Mapped[str | None] = mapped_column(Text)
    provider_response_raw: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    webhook_last_event: Mapped[str | None] = mapped_column(String(160))
    webhook_last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    registration: Mapped[Registration] = relationship(back_populates="payments")

    __table_args__ = (UniqueConstraint("provider_name", "payment_reference", name="uq_payment_provider_ref"),)


class SmsLog(Base):
    __tablename__ = "sms_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    registration_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("registrations.registration_id"),
        index=True,
        nullable=False,
    )
    phone_number: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="SENT")
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False, default="mock")
    message_type: Mapped[str] = mapped_column(String(40), nullable=False, default="CONFIRMATION")
    idempotency_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    registration: Mapped[Registration] = relationship(back_populates="sms_logs")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(80), index=True, nullable=False, default="unknown")
    external_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (UniqueConstraint("source", "external_event_id", name="uq_webhook_source_event"),)


class Sequence(Base):
    __tablename__ = "sequences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EventConfig(Base, TimestampMixin):
    __tablename__ = "event_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
