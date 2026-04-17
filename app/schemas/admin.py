from datetime import datetime

from pydantic import BaseModel

from app.schemas.registration import RegistrationRead


class DashboardSummary(BaseModel):
    total_registrations: int
    paid: int
    pending: int
    failed: int
    cancelled: int


class RegistrationListItem(BaseModel):
    registration_id: str
    created_at: datetime
    full_name: str
    cellphone_number: str
    email: str
    race_category: str
    shirt_size: str
    payment_status: str
    payment_reference: str
    bib_number: str | None
    sms_sent: bool
    paid_at: datetime | None


class RegistrationListResponse(BaseModel):
    items: list[RegistrationListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class AdminRegistrationDetail(RegistrationRead):
    payments: list[dict]
    sms_logs: list[dict]

