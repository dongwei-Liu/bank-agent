import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

password_hasher = PasswordHasher()
SHANGHAI = ZoneInfo("Asia/Shanghai")


def now():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def fingerprint(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str))


def token():
    return secrets.token_urlsafe(48)


def otp_digest(secret, action_id, nonce, code):
    return hmac.new(
        secret.encode(), f"{action_id}:{nonce}:{code}".encode(), hashlib.sha256
    ).hexdigest()


def verify_password(hashed, password):
    try:
        return password_hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def money(value):
    amount = Decimal(str(value))
    if (
        not amount.is_finite()
        or amount < 0
        or amount != amount.quantize(Decimal(".01"))
    ):
        from core.errors import DomainError

        raise DomainError("INVALID_AMOUNT", "金额必须非负且最多两位小数")
    return amount
