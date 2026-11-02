from functools import lru_cache
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from clients.fineract import FineractClient
from core.config import get_settings
from core.database import get_db
from core.errors import require
from services.account_service import AccountService
from services.auth_service import AuthService

bearer = HTTPBearer(auto_error=False)


@lru_cache
def get_fineract_client():
    return FineractClient(get_settings())


def get_account_service():
    return AccountService(get_fineract_client())


def get_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    require(
        credentials is not None and credentials.scheme.lower() == "bearer",
        "UNAUTHENTICATED",
        "请登录",
        401,
    )
    user, session = AuthService(db).authenticate(credentials.credentials)
    require(
        user.tenant == get_settings().fineract_tenant,
        "TENANT_MISMATCH",
        "身份租户不匹配",
        403,
    )
    return user, session


def get_user(identity=Depends(get_identity)):
    return identity[0]


def get_admin(user=Depends(get_user)):
    require(user.is_admin, "FORBIDDEN", "需要管理员权限", 403)
    return user
