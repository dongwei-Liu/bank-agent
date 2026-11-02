from decimal import Decimal
from datetime import datetime
from sqlalchemy import select
from core.errors import require
from core.security import aware
from models import Audit, User


_AUDIT_REDACTED = "[REDACTED]"
_AUDIT_SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "access_token",
    "refresh_token",
    "id_token",
    "authorization",
    "cookie",
    "set_cookie",
    "api_key",
    "client_secret",
    "secret",
    "otp",
    "otp_code",
    "dev_otp",
    "one_time_password",
    "card_number",
    "full_card_number",
    "pan",
    "pan_ciphertext",
    "cvv",
    "cvc",
}


def redact_audit_data(value):
    """Recursively redact credentials and payment secrets before persistence."""

    if isinstance(value, dict):
        return {
            key: (
                _AUDIT_REDACTED
                if str(key).lower().replace("-", "_") in _AUDIT_SENSITIVE_KEYS
                else redact_audit_data(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_audit_data(item) for item in value]
    return value


def owned(db, model, resource_id, user):
    row = db.get(model, resource_id)
    require(row is not None and row.user_id == user.id, "NOT_FOUND", "资源不存在", 404)
    return row


def lock_user(db, user):
    # All mutations/quotas for one customer serialize in PostgreSQL. SQLite is test-only.
    return db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def audit(
    db,
    user,
    event,
    action=None,
    *,
    trace_id=None,
    resource_type=None,
    resource_id=None,
    **data,
):
    if resource_type is None or resource_id is None:
        for field, type_ in (
            ("card_id", "card"),
            ("subscription_id", "subscription"),
            ("schedule_id", "transfer_schedule"),
            ("recipient_id", "recipient"),
            ("product_id", "investment_product"),
        ):
            if data.get(field) is not None:
                resource_type = resource_type or type_
                resource_id = resource_id or str(data[field])
                break
    trace_id = trace_id or (action.id if action else None)
    resource_type = resource_type or (action.kind if action else None)
    resource_id = resource_id or (action.id if action else None)
    stored_data = redact_audit_data(data)
    if trace_id:
        stored_data.setdefault("trace_id", trace_id)
    db.add(
        Audit(
            user_id=user.id,
            action_id=action.id if action else None,
            trace_id=trace_id,
            resource_type=resource_type,
            resource_id=resource_id,
            event=event,
            data=stored_data,
        )
    )


def row_dict(row, exclude=()):
    return {
        c.name: getattr(row, c.name)
        for c in row.__table__.columns
        if c.name not in exclude
    }


def safe_json(value):
    import json
    from fastapi.encoders import jsonable_encoder

    return json.loads(
        json.dumps(
            jsonable_encoder(
                value,
                custom_encoder={
                    Decimal: str,
                    datetime: lambda item: aware(item).isoformat(),
                },
            )
        )
    )
