from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.payment import MockPaymentSuccessRequest
from app.schemas.registration import RegistrationRead
from app.services.payment_service import process_payment_success, record_and_process_webhook
from app.utils.responses import success_response

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/mock-success")
def mock_payment_success(payload: MockPaymentSuccessRequest, db: Session = Depends(get_db)) -> dict:
    registration = process_payment_success(
        db,
        registration_id=payload.registration_id,
        payment_reference=payload.payment_reference,
        provider_name="mock",
        provider_transaction_id=payload.provider_transaction_id,
        amount=payload.amount,
        currency=payload.currency,
        raw_payload=payload.model_dump(),
    )
    data = RegistrationRead.model_validate(registration)
    return success_response("Payment marked successful", data)


@router.post("/webhook")
def payment_webhook(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict:
    event, registration = record_and_process_webhook(db, payload)
    data = {
        "webhook_event_id": event.id,
        "event_type": event.event_type,
        "processed": event.processed,
        "processed_at": event.processed_at,
        "registration": RegistrationRead.model_validate(registration) if registration else None,
    }
    message = "Webhook processed" if event.processed else "Webhook received"
    return success_response(message, data)

