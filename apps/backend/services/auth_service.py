from datetime import timedelta
from sqlalchemy import select
from core.errors import DomainError, require
from core.security import aware, digest, now, password_hasher, token, verify_password
from models import LoginSession, User
from services.common import audit

# Equal-cost password check for absent usernames.
_DUMMY_HASH = password_hasher.hash(token())


class AuthService:
    def __init__(self, db):
        self.db = db

    def _tokens(self, session):
        access, refresh = token(), token()
        session.access_hash, session.refresh_hash = digest(access), digest(refresh)
        session.access_expires = now() + timedelta(minutes=15)
        session.refresh_expires = now() + timedelta(days=7)
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "expires_in": 900,
        }

    def login(self, username, password):
        user = self.db.scalar(
            select(User).where(User.username == username).with_for_update()
        )
        valid = verify_password(user.password_hash if user else _DUMMY_HASH, password)
        require(
            user is not None and user.active,
            "INVALID_CREDENTIALS",
            "账号或密码错误",
            401,
        )
        require(
            not user.login_locked_until or aware(user.login_locked_until) <= now(),
            "LOGIN_LOCKED",
            "登录暂时锁定",
            429,
        )
        if not valid:
            user.login_failures += 1
            if user.login_failures >= 5:
                user.login_locked_until = now() + timedelta(minutes=15)
                user.login_failures = 0
            audit(self.db, user, "LOGIN_FAILED")
            self.db.commit()
            raise DomainError("INVALID_CREDENTIALS", "账号或密码错误", 401)
        user.login_failures = 0
        session = LoginSession(user_id=user.id)
        result = self._tokens(session)
        self.db.add(session)
        audit(self.db, user, "LOGIN")
        self.db.commit()
        return result

    def authenticate(self, bearer):
        session = self.db.scalar(
            select(LoginSession).where(LoginSession.access_hash == digest(bearer))
        )
        require(
            session and not session.revoked and aware(session.access_expires) > now(),
            "UNAUTHENTICATED",
            "请重新登录",
            401,
        )
        user = self.db.get(User, session.user_id)
        require(user and user.active, "UNAUTHENTICATED", "请重新登录", 401)
        return user, session

    def refresh(self, refresh):
        session = self.db.scalar(
            select(LoginSession)
            .where(LoginSession.refresh_hash == digest(refresh))
            .with_for_update()
        )
        require(
            session and not session.revoked and aware(session.refresh_expires) > now(),
            "UNAUTHENTICATED",
            "刷新令牌无效",
            401,
        )
        require(
            self.db.get(User, session.user_id).active,
            "UNAUTHENTICATED",
            "账号不可用",
            401,
        )
        result = self._tokens(session)
        self.db.commit()
        return result

    def logout(self, user, session):
        session.revoked = True
        audit(self.db, user, "LOGOUT")
        self.db.commit()
        return {"status": "logged_out"}
