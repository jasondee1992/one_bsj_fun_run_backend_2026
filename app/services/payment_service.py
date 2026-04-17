import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Payment, Registration, WebhookEvent
from app.providers import get_payment_provider
from app.schemas.payment import PaymentSessionRead
from app.schemas.registration import PaymentStatus
from app.services.sequence_service import next_bib_number
from app.services.sms_service import send_confirmation_sms


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, default=str, sort_keys=True, separators=(",", ":"))


def _json_loads(payload: str | None) -> dict[str, Any] | None:
    if not payload:
        return None
    try:
        value = json.loads(payload)
    except json.JSONDecodeError:
        return {"raw": payload}
    return value if isinstance(value, dict) else {"raw": value}


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_payment_status(status_value: str | None) -> str:
    value = (status_value or "").upper()
    if value in {"PAID", "SUCCESS", "SUCCEEDED", "PAYMENT_SUCCEEDED"}:
        return "paid"
    if value in {"AWAITING_PAYMENT", "PENDING_PAYMENT", "PENDING"}:
        return "pending"
    if value in {"PAYMENT_FAILED", "FAILED"}:
        return "failed"
    if value == "EXPIRED":
        return "expired"
    if value in {"CANCELLED", "CANCELED"}:
        return "cancelled"
    return "pending"


def _internal_status(status_value: str) -> str:
    value = _normalize_payment_status(status_value)
    if value == "paid":
        return PaymentStatus.paid.value
    if value == "failed":
        return PaymentStatus.payment_failed.value
    if value == "cancelled":
        return PaymentStatus.cancelled.value
    if value == "expired":
        return "EXPIRED"
    if value == "pending":
        return PaymentStatus.pending_payment.value
    return PaymentStatus.pending_payment.value


def _sms_status(registration: Registration) -> str:
    return "sent" if registration.sms_sent else "not_sent"


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _latest_payment(db: Session, registration: Registration) -> Payment | None:
    return (
        db.query(Payment)
        .filter(Payment.registration_id == registration.registration_id)
        .order_by(Payment.updated_at.desc(), Payment.id.desc())
        .first()
    )


def _serialize_payment_session(registration: Registration, payment: Payment) -> PaymentSessionRead:
    if (
        payment.expires_at
        and payment.status != PaymentStatus.paid.value
        and _as_aware(payment.expires_at) < _now()
    ):
        payment.status = "EXPIRED"
        registration.payment_status = "EXPIRED"

    return PaymentSessionRead(
        registration_id=registration.registration_id,
        participant_name=registration.full_name,
        race_category=registration.race_category,
        shirt_size=registration.shirt_size,
        payment_reference=payment.payment_reference,
        provider=payment.provider_name,
        payment_method=payment.payment_method or "qr",
        payment_status=_normalize_payment_status(payment.status),
        amount=payment.amount,
        currency=payment.currency,
        qr_code_url=payment.qr_code_url,
        qr_code_payload=payment.qr_code_payload,
        payment_url=payment.payment_url,
        expires_at=payment.expires_at.isoformat() if payment.expires_at else None,
        paid_at=(payment.paid_at or registration.paid_at).isoformat()
        if payment.paid_at or registration.paid_at
        else None,
        raw_response=_json_loads(payment.provider_response_raw or payment.raw_payload),
        sms_status=_sms_status(registration),
        webhook_last_event=payment.webhook_last_event,
        webhook_last_event_at=payment.webhook_last_event_at.isoformat()
        if payment.webhook_last_event_at
        else None,
        bib_number=registration.bib_number,
        is_confirmed=registration.payment_status == PaymentStatus.paid.value,
    )


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


def get_payment_session(db: Session, registration_id: str) -> PaymentSessionRead:
    registration = _find_registration(db, registration_id=registration_id)
    payment = _latest_payment(db, registration)
    if payment is None:
        return create_payment_session(db, registration_id)
    session = _serialize_payment_session(registration, payment)
    db.commit()
    return session


def create_payment_session(db: Session, registration_id: str) -> PaymentSessionRead:
    registration = _find_registration(db, registration_id=registration_id)
    payment = _latest_payment(db, registration)
    if registration.payment_status == PaymentStatus.paid.value and payment is not None:
        return _serialize_payment_session(registration, payment)

    provider = get_payment_provider()
    provider_session = provider.create_payment_session(registration)

    if payment is None:
        payment = Payment(
            registration_id=registration.registration_id,
            provider_name=provider_session.provider,
            payment_reference=provider_session.payment_reference,
        )
        db.add(payment)

    payment.provider_name = provider_session.provider
    payment.payment_method = payment.payment_method or "qr"
    payment.payment_reference = provider_session.payment_reference
    payment.amount = payment.amount or settings.default_registration_amount
    payment.currency = payment.currency or settings.default_currency
    payment.status = _internal_status(provider_session.payment_status)
    payment.qr_code_url = provider_session.qr_code_url
    payment.qr_code_payload = provider_session.qr_code_payload
    payment.payment_url = provider_session.payment_url
    payment.provider_response_raw = _json_dumps(provider_session.raw_response)
    if provider_session.expires_at:
        payment.expires_at = datetime.fromisoformat(provider_session.expires_at)

    if registration.payment_status != PaymentStatus.paid.value:
        registration.payment_status = payment.status

    db.commit()
    db.refresh(payment)
    db.refresh(registration)
    return _serialize_payment_session(registration, payment)


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
    payment.payment_method = payment.payment_method or "qr"
    payment.amount = amount if amount is not None else payment.amount or settings.default_registration_amount
    payment.currency = currency or payment.currency or settings.default_currency
    payment.status = PaymentStatus.paid.value
    payment.paid_at = payment.paid_at or datetime.now(UTC)
    payment.raw_payload = _json_dumps(raw_payload) if raw_payload is not None else payment.raw_payload
    payment.provider_response_raw = (
        _json_dumps(raw_payload) if raw_payload is not None else payment.provider_response_raw
    )
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
    registration_for_event = None
    data = payload.get("data") or payload
    registration_id = data.get("registration_id")
    payment_reference = data.get("payment_reference")
    if registration_id or payment_reference:
        try:
            registration_for_event = _find_registration(db, registration_id, payment_reference)
        except HTTPException:
            registration_for_event = None

    if registration_for_event is not None:
        payment = _latest_payment(db, registration_for_event)
        if payment is not None:
            payment.webhook_last_event = event_type
            payment.webhook_last_event_at = datetime.now(UTC)
            payment.raw_payload = _json_dumps(payload)
            db.commit()

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
    elif registration_for_event is not None:
        mapped_status = _internal_status(normalized_status)
        if mapped_status in {
            PaymentStatus.payment_failed.value,
            PaymentStatus.cancelled.value,
            "EXPIRED",
        }:
            registration_for_event.payment_status = mapped_status
            payment = _latest_payment(db, registration_for_event)
            if payment is not None:
                payment.status = mapped_status
                payment.webhook_last_event = event_type
                payment.webhook_last_event_at = datetime.now(UTC)
            event.processed = True
            event.processed_at = datetime.now(UTC)
            db.commit()
            db.refresh(event)

    return event, processed_registration


def simulate_payment_success(db: Session, registration_id: str) -> PaymentSessionRead:
    registration = process_payment_success(
        db,
        registration_id=registration_id,
        provider_name=settings.payment_provider or "mock",
        provider_transaction_id=f"SIM-{registration_id}",
        amount=settings.default_registration_amount,
        currency=settings.default_currency,
        raw_payload={
            "source": "local-dev",
            "event_type": "SIMULATED_PAYMENT_SUCCESS",
            "registration_id": registration_id,
        },
    )
    payment = _latest_payment(db, registration)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    payment.webhook_last_event = "SIMULATED_PAYMENT_SUCCESS"
    payment.webhook_last_event_at = datetime.now(UTC)
    db.commit()
    db.refresh(payment)
    db.refresh(registration)
    return _serialize_payment_session(registration, payment)
