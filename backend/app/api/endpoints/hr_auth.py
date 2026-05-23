"""HR Admin / ATS authentication endpoints (mounted under /hr/auth)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_request_context,
    require_hr_admin,
)
from app.core.database import get_db
from app.models.auth import SCOPE_HR, User
from app.schemas.auth import LoginRequest, LoginResponse, UserRead
from app.services.audit_log import ACTION_LOGOUT, record_audit
from app.services.auth import AuthError, RequestMeta, authenticate, user_to_read


router = APIRouter(prefix="/hr/auth", tags=["Auth - HR Admin"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Log in to the HR ATS portal",
)
def hr_login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    ctx = get_request_context(request)
    try:
        return authenticate(
            db,
            email=str(payload.email),
            password=payload.password,
            required_scope=SCOPE_HR,
            meta=RequestMeta(
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
            ),
        )
    except AuthError as exc:
        status_code = (
            status.HTTP_401_UNAUTHORIZED
            if exc.code in ("invalid_credentials", "inactive")
            else status.HTTP_403_FORBIDDEN
        )
        raise HTTPException(status_code=status_code, detail=exc.message)


@router.post("/logout")
def hr_logout(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> Response:
    ctx = get_request_context(request)
    record_audit(
        db,
        action=ACTION_LOGOUT,
        actor_id=user.id,
        actor_email=user.email,
        scope=SCOPE_HR,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserRead, summary="Current HR user")
def hr_me(user: User = Depends(require_hr_admin)) -> UserRead:
    return user_to_read(user)
