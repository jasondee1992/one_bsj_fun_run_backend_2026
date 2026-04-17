import csv
from io import StringIO
from math import ceil

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.session import get_db
from app.models import Payment, Registration, SmsLog
from app.schemas.admin import (
    AdminRegistrationDetail,
    DashboardSummary,
    RegistrationListItem,
    RegistrationListResponse,
)
from app.schemas.registration import PaymentStatus, RaceCategory
from app.services.registration_service import get_registration_or_404, list_registrations
from app.services.sms_service import resend_confirmation_sms
from app.utils.responses import success_response

router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/me")
def admin_me(admin: dict = Depends(require_admin)) -> dict:
    return success_response("Admin token is valid", {"username": admin["sub"]})


@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)) -> dict:
    total = db.query(func.count(Registration.id)).scalar() or 0
    paid = (
        db.query(func.count(Registration.id))
        .filter(Registration.payment_status == PaymentStatus.paid.value)
        .scalar()
        or 0
    )
    pending = (
        db.query(func.count(Registration.id))
        .filter(Registration.payment_status == PaymentStatus.pending_payment.value)
        .scalar()
        or 0
    )
    failed = (
        db.query(func.count(Registration.id))
        .filter(Registration.payment_status == PaymentStatus.payment_failed.value)
        .scalar()
        or 0
    )
    cancelled = (
        db.query(func.count(Registration.id))
        .filter(Registration.payment_status == PaymentStatus.cancelled.value)
        .scalar()
        or 0
    )
    data = DashboardSummary(
        total_registrations=total,
        paid=paid,
        pending=pending,
        failed=failed,
        cancelled=cancelled,
    )
    return success_response("Dashboard summary retrieved successfully", data)


@router.get("/registrations")
def admin_list_registrations(
    status: PaymentStatus | None = None,
    category: RaceCategory | None = None,
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    items, total = list_registrations(
        db,
        status_filter=status.value if status else None,
        category=category.value if category else None,
        search=search,
        page=page,
        page_size=page_size,
    )
    data = RegistrationListResponse(
        items=[
            RegistrationListItem(
                registration_id=item.registration_id,
                created_at=item.created_at,
                full_name=item.full_name,
                cellphone_number=item.cellphone_number,
                email=item.email,
                race_category=item.race_category,
                shirt_size=item.shirt_size,
                payment_status=item.payment_status,
                payment_reference=item.payment_reference,
                bib_number=item.bib_number,
                sms_sent=item.sms_sent,
                paid_at=item.paid_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )
    return success_response("Registrations retrieved successfully", data)


def _payment_dict(payment: Payment) -> dict:
    return {
        "id": payment.id,
        "provider_name": payment.provider_name,
        "payment_method": payment.payment_method,
        "payment_reference": payment.payment_reference,
        "provider_transaction_id": payment.provider_transaction_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "status": payment.status,
        "qr_code_url": payment.qr_code_url,
        "qr_code_payload": payment.qr_code_payload,
        "payment_url": payment.payment_url,
        "raw_payload": payment.raw_payload,
        "provider_response_raw": payment.provider_response_raw,
        "paid_at": payment.paid_at,
        "expires_at": payment.expires_at,
        "webhook_last_event": payment.webhook_last_event,
        "webhook_last_event_at": payment.webhook_last_event_at,
        "created_at": payment.created_at,
        "updated_at": payment.updated_at,
    }


def _sms_log_dict(log: SmsLog) -> dict:
    return {
        "id": log.id,
        "phone_number": log.phone_number,
        "message": log.message,
        "status": log.status,
        "provider_name": log.provider_name,
        "message_type": log.message_type,
        "created_at": log.created_at,
        "sent_at": log.sent_at,
    }


@router.get("/registrations/{registration_id}")
def admin_get_registration_detail(registration_id: str, db: Session = Depends(get_db)) -> dict:
    registration = get_registration_or_404(db, registration_id)
    data = AdminRegistrationDetail(
        **RegistrationListItem.model_validate(
            RegistrationListItem(
                registration_id=registration.registration_id,
                created_at=registration.created_at,
                full_name=registration.full_name,
                cellphone_number=registration.cellphone_number,
                email=registration.email,
                race_category=registration.race_category,
                shirt_size=registration.shirt_size,
                payment_status=registration.payment_status,
                payment_reference=registration.payment_reference,
                bib_number=registration.bib_number,
                sms_sent=registration.sms_sent,
                paid_at=registration.paid_at,
            )
        ).model_dump(),
        updated_at=registration.updated_at,
        first_name=registration.first_name,
        middle_name=registration.middle_name,
        last_name=registration.last_name,
        suffix=registration.suffix,
        address=registration.address,
        city=registration.city,
        province=registration.province,
        birthday=registration.birthday,
        sex=registration.sex,
        emergency_contact_name=registration.emergency_contact_name,
        emergency_contact_number=registration.emergency_contact_number,
        medical_conditions=registration.medical_conditions,
        notes=registration.notes,
        waiver_accepted=registration.waiver_accepted,
        privacy_consent_accepted=registration.privacy_consent_accepted,
        provider_transaction_id=registration.provider_transaction_id,
        sms_sent_at=registration.sms_sent_at,
        payments=[_payment_dict(payment) for payment in registration.payments],
        sms_logs=[_sms_log_dict(log) for log in registration.sms_logs],
    )
    return success_response("Registration detail retrieved successfully", data)


@router.post("/registrations/{registration_id}/resend-sms")
def admin_resend_sms(registration_id: str, db: Session = Depends(get_db)) -> dict:
    log = resend_confirmation_sms(db, registration_id)
    return success_response("SMS resent successfully", _sms_log_dict(log))


@router.get("/export/csv")
def admin_export_csv(db: Session = Depends(get_db)) -> StreamingResponse:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "registration_id",
            "created_at",
            "full_name",
            "cellphone_number",
            "email",
            "birthday",
            "sex",
            "race_category",
            "shirt_size",
            "payment_status",
            "payment_reference",
            "provider_transaction_id",
            "paid_at",
            "bib_number",
            "sms_sent",
            "sms_sent_at",
            "city",
            "province",
        ]
    )
    registrations = db.query(Registration).order_by(Registration.created_at.asc()).all()
    for registration in registrations:
        writer.writerow(
            [
                registration.registration_id,
                registration.created_at,
                registration.full_name,
                registration.cellphone_number,
                registration.email,
                registration.birthday,
                registration.sex,
                registration.race_category,
                registration.shirt_size,
                registration.payment_status,
                registration.payment_reference,
                registration.provider_transaction_id,
                registration.paid_at,
                registration.bib_number,
                registration.sms_sent,
                registration.sms_sent_at,
                registration.city,
                registration.province,
            ]
        )

    output.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="onebsj-registrations.csv"'}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
