import hmac

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.core.security import create_access_token
from app.schemas.auth import AdminLoginRequest, AdminLoginResponse
from app.utils.responses import success_response

router = APIRouter(tags=["auth"])


@router.post("/admin/login")
def admin_login(payload: AdminLoginRequest) -> dict:
    username_ok = hmac.compare_digest(payload.username, settings.admin_username)
    password_ok = hmac.compare_digest(payload.password, settings.admin_password)
    if not username_ok or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin username or password",
        )

    token = create_access_token(subject=payload.username)
    data = AdminLoginResponse(
        access_token=token,
        expires_in_minutes=settings.access_token_expire_minutes,
    )
    return success_response("Admin login successful", data)

