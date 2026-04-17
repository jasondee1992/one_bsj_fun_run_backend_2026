from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Payment, Registration
from app.schemas.registration import PaymentStatus, RegistrationCreate, RegistrationStatusRead


def _make_registration_id() -> str:
    return f"REG-{uuid4().hex[:12].upper()}"


def _make_payment_reference(registration_id: str) -> str:
    return f"PAY-{registration_id.removeprefix('REG-')}"


def build_full_name(registration: RegistrationCreate) -> str:
    parts = [
        registration.first_name,
        registration.middle_name,
        registration.last_name,
        registration.suffix,
    ]
    return " ".join(part for part in parts if part)


def create_registration(db: Session, payload: RegistrationCreate) -> Registration:
    registration_id = _make_registration_id()
    payment_reference = _make_payment_reference(registration_id)
    registration = Registration(
        registration_id=registration_id,
        first_name=payload.first_name,
        middle_name=payload.middle_name,
        last_name=payload.last_name,
        suffix=payload.suffix,
        full_name=build_full_name(payload),
        address=payload.address,
        city=payload.city,
        province=payload.province,
        cellphone_number=payload.cellphone_number,
        email=str(payload.email),
        birthday=payload.birthday,
        sex=payload.sex,
        emergency_contact_name=payload.emergency_contact_name,
        emergency_contact_number=payload.emergency_contact_number,
        race_category=payload.race_category.value,
        shirt_size=payload.shirt_size.value,
        medical_conditions=payload.medical_conditions,
        notes=payload.notes,
        waiver_accepted=payload.waiver_accepted,
        privacy_consent_accepted=payload.privacy_consent_accepted,
        payment_status=PaymentStatus.pending_payment.value,
        payment_reference=payment_reference,
    )
    payment = Payment(
        registration_id=registration_id,
        provider_name="mock",
        payment_reference=payment_reference,
        amount=settings.default_registration_amount,
        currency=settings.default_currency,
        status=PaymentStatus.pending_payment.value,
    )
    db.add(registration)
    db.add(payment)
    db.commit()
    db.refresh(registration)
    return registration


def get_registration_or_404(db: Session, registration_id: str) -> Registration:
    registration = (
        db.query(Registration).filter(Registration.registration_id == registration_id).one_or_none()
    )
    if registration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration not found")
    return registration


def get_registration_status(db: Session, registration_id: str) -> RegistrationStatusRead:
    registration = get_registration_or_404(db, registration_id)
    return RegistrationStatusRead(
        registration_id=registration.registration_id,
        full_name=registration.full_name,
        payment_status=registration.payment_status,
        payment_reference=registration.payment_reference,
        bib_number=registration.bib_number,
        race_category=registration.race_category,
        sms_sent=registration.sms_sent,
        sms_sent_at=registration.sms_sent_at,
        paid_at=registration.paid_at,
    )


def list_registrations(
    db: Session,
    status_filter: str | None = None,
    category: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Registration], int]:
    query = db.query(Registration)
    if status_filter:
        query = query.filter(Registration.payment_status == status_filter.upper())
    if category:
        query = query.filter(Registration.race_category == category.upper())
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Registration.full_name.ilike(pattern),
                Registration.bib_number.ilike(pattern),
                Registration.cellphone_number.ilike(pattern),
                Registration.email.ilike(pattern),
            )
        )
    total = query.count()
    items = (
        query.order_by(Registration.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total

