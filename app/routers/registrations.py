from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.registration import RegistrationCreate, RegistrationRead
from app.services.registration_service import (
    create_registration,
    get_registration_or_404,
    get_registration_status,
)
from app.utils.responses import success_response

router = APIRouter(prefix="/registrations", tags=["registrations"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_registration_endpoint(
    payload: RegistrationCreate,
    db: Session = Depends(get_db),
) -> dict:
    registration = create_registration(db, payload)
    data = RegistrationRead.model_validate(registration)
    return success_response("Registration created successfully", data)


@router.get("/{registration_id}")
def get_registration_endpoint(registration_id: str, db: Session = Depends(get_db)) -> dict:
    registration = get_registration_or_404(db, registration_id)
    data = RegistrationRead.model_validate(registration)
    return success_response("Registration retrieved successfully", data)


@router.get("/{registration_id}/status")
def get_registration_status_endpoint(registration_id: str, db: Session = Depends(get_db)) -> dict:
    data = get_registration_status(db, registration_id)
    return success_response("Registration status retrieved successfully", data)

