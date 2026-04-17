import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Payment, Registration, WebhookEvent
from app.schemas.registration import PaymentStatus
from app.services.sequence_service import next_bib_number
from app.services.sms_service import send_confirmation_sms


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, default=str, sort_keys=True, separators=(",", ":"))


def _find_registration(
    db: Session,
    registration_id: str | None = None,
    payment_reference: str | None = None,
) -> Registration:
    query = db.query(Registration)
    if registration_id:
        registration = query.filter(Registration.registration_id == registration_id).one_or_none()
    elif payment_reference:
        registration = query.filter(Registration.payment_reference == payment_reference).one_or_none()
    else:
        registration = None

    if registration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration not found")
    return registration


def _upsert_payment(
    db: Session,
    registration: Registration,
    provider_name: str,
    provider_transaction_id: str | None,
    amount: float | None,
    currency: str | None,
    raw_payload: Any,
) -> Payment:
    payment = (
        db.query(Payment)
        .filter(
            Payment.provider_name == provider_name,
            Payment.payment_reference == registration.payment_reference,
        )
        .one_or_none()
    )
    if payment is None:
        payment = Payment(
            registration_id=registration.registration_id,
            provider_name=provider_name,
            payment_reference=registration.payment_reference,
        )
        db.add(payment)

    payment.provider_transaction_id = provider_transaction_id or payment.provider_transaction_id
    payment.amount = amount if amount is not None else payment.amount or settings.default_registration_amount
    payment.currency = currency or payment.currency or settings.default_currency
    payment.status = PaymentStatus.paid.value
    payment.raw_payload = _json_dumps(raw_payload) if raw_payload is not None else payment.raw_payload
    return payment


def process_payment_success(
    db: Session,
    registration_id: str | None = None,
    payment_reference: str | None = None,
    provider_name: str = "mock",
    provider_transaction_id: str | None = None,
    amount: float | None = None,
    currency: str | None = None,
    raw_payload: Any = None,
) -> Registration:
    registration = _find_registration(db, registration_id, payment_reference)

    if registration.payment_status == PaymentStatus.paid.value:
        _upsert_payment(
            db,
            registration,
            provider_name,
            provider_transaction_id,
            amount,
            currency,
            raw_payload,
        )
        db.commit()
        send_confirmation_sms(db, registration.registration_id)
        db.refresh(registration)
        return registration

    if registration.payment_status == PaymentStatus.cancelled.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cancelled registration cannot be marked as paid",
        )

    now = datetime.now(UTC)
    registration.payment_status = PaymentStatus.paid.value
    registration.paid_at = now
    registration.provider_transaction_id = provider_transaction_id
    registration.bib_number = next_bib_number(db)
    _upsert_payment(
        db,
        registration,
        provider_name,
        provider_transaction_id,
        amount,
        currency,
        raw_payload,
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not assign a unique bib number. Retry the payment success call.",
        ) from exc

    db.refresh(registration)
    send_confirmation_sms(db, registration.registration_id)
    db.refresh(registration)
    return registration


def record_and_process_webhook(db: Session, payload: dict[str, Any]) -> tuple[WebhookEvent, Registration | None]:
    source = str(payload.get("source") or "generic")
    event_type = str(payload.get("event_type") or payload.get("type") or "unknown")
    external_event_id = payload.get("external_event_id") or payload.get("id")
    if not external_event_id:
        external_event_id = hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()

    existing_event = (
        db.query(WebhookEvent)
        .filter(
            WebhookEvent.source == source,
            WebhookEvent.external_event_id == str(external_event_id),
        )
        .one_or_none()
    )
    if existing_event is not None:
        if existing_event.processed:
            return existing_event, None
        event = existing_event
    else:
        event = WebhookEvent(
            source=source,
            event_type=event_type,
            external_event_id=str(external_event_id),
            payload=_json_dumps(payload),
            processed=False,
        )
        db.add(event)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            event = (
                db.query(WebhookEvent)
                .filter(
                    WebhookEvent.source == source,
                    WebhookEvent.external_event_id == str(external_event_id),
                )
                .one()
            )
            if event.processed:
                return event, None
        else:
            db.refresh(event)

    data = payload.get("data") or payload
    normalized_status = str(data.get("status") or payload.get("status") or event_type).upper()
    is_success = normalized_status in {"PAID", "SUCCESS", "SUCCEEDED", "PAYMENT_SUCCEEDED"}
    is_success = is_success or event_type.upper() in {"PAYMENT_SUCCEEDED", "PAYMENT_SUCCESS", "PAID"}

    processed_registration = None
    if is_success:
        # Future PayMongo/Xendit adapters should normalize their payload into these fields.
        processed_registration = process_payment_success(
            db,
            registration_id=data.get("registration_id"),
            payment_reference=data.get("payment_reference"),
            provider_name=source,
            provider_transaction_id=data.get("provider_transaction_id")
            or data.get("transaction_id")
            or data.get("id"),
            amount=data.get("amount"),
            currency=data.get("currency"),
            raw_payload=payload,
        )
        event = db.query(WebhookEvent).filter(WebhookEvent.id == event.id).one()
        event.processed = True
        event.processed_at = datetime.now(UTC)
        db.commit()
        db.refresh(event)

    return event, processed_registration

