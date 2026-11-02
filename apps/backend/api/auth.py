from fastapi import APIRouter, Depends
from core.deps import get_identity
from core.config import get_settings
from core.errors import require
from models import Action
from schemas.banking import LoginRequest, RefreshRequest
from services.auth_service import AuthService
from services.common import owned
from api.context import Db, Actor, DecimalRoute

router = APIRouter(prefix="/api", tags=["identity"], route_class=DecimalRoute)


@router.post("/auth/login")
def login(body: LoginRequest, db: Db):
    return AuthService(db).login(body.username, body.password)


@router.post("/auth/refresh")
def refresh(body: RefreshRequest, db: Db):
    return AuthService(db).refresh(body.refresh_token)


@router.post("/auth/logout")
def logout(db: Db, identity=Depends(get_identity)):
    return AuthService(db).logout(*identity)


@router.get("/me")
def me(user: Actor):
    return {
        "id": user.id,
        "username": user.username,
        "client_id": user.client_id,
        "is_admin": user.is_admin,
    }


@router.get("/dev/otp-inbox/{action_id}", include_in_schema=False)
def inbox(action_id: str, user: Actor, db: Db):
    settings = get_settings()
    require(
        settings.environment == "development" and settings.dev_otp_inbox,
        "NOT_FOUND",
        "资源不存在",
        404,
    )
    action = owned(db, Action, action_id, user)
    from core.security import aware, now

    require(
        action.dev_otp and action.otp_expires and aware(action.otp_expires) > now(),
        "NOT_FOUND",
        "没有有效验证码",
        404,
    )
    return {
        "action_id": action.id,
        "code": action.dev_otp,
        "expires_at": action.otp_expires,
    }
