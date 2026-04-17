from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Registration, SmsLog


class SmsProvider:
    provider_name = "base"

    def send(self, phone_number: str, message: str) -> str:
        raise NotImplementedError


class MockSmsProvider(SmsProvider):
    provider_name = "mock"

    def send(self, phone_number: str, message: str) -> str:
        return "SENT"


def build_confirmation_message(registration: Registration) -> str:
    return (
        f"{settings.event_name}: payment confirmed for {registration.full_name}. "
        f"Bib number: {registration.bib_number}. Category: {registration.race_category}."
    )


def send_confirmation_sms(db: Session, registration_id: str) -> SmsLog | None:
    registration = (
        db.query(Registration).filter(Registration.registration_id == registration_id).one_or_none()
    )
    if registration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration not found")
    if registration.payment_status != "PAID" or not registration.bib_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation SMS can only be sent after successful payment",
        )
    if registration.sms_sent:
        return (
            db.query(SmsLog)
            .filter(SmsLog.idempotency_key == f"confirmation:{registration.registration_id}")
            .one_or_none()
        )

    provider = MockSmsProvider()
    message = build_confirmation_message(registration)
    now = datetime.now(UTC)
    log = SmsLog(
        registration_id=registration.registration_id,
        phone_number=registration.cellphone_number,
        message=message,
        status=provider.send(registration.cellphone_number, message),
        provider_name=provider.provider_name,
        message_type="CONFIRMATION",
        idempotency_key=f"confirmation:{registration.registration_id}",
        sent_at=now,
    )
    registration.sms_sent = True
    registration.sms_sent_at = now
    db.add(log)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return (
            db.query(SmsLog)
            .filter(SmsLog.idempotency_key == f"confirmation:{registration.registration_id}")
            .one_or_none()
        )

    db.refresh(log)
    return log


def resend_confirmation_sms(db: Session, registration_id: str) -> SmsLog:
    registration = (
        db.query(Registration).filter(Registration.registration_id == registration_id).one_or_none()
    )
    if registration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration not found")
    if registration.payment_status != "PAID" or not registration.bib_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manual resend is available only for paid registrations",
        )

    provider = MockSmsProvider()
    message = build_confirmation_message(registration)
    now = datetime.now(UTC)
    log = SmsLog(
        registration_id=registration.registration_id,
        phone_number=registration.cellphone_number,
        message=message,
        status=provider.send(registration.cellphone_number, message),
        provider_name=provider.provider_name,
        message_type="MANUAL_RESEND",
        sent_at=now,
    )
    registration.sms_sent = True
    registration.sms_sent_at = now
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

