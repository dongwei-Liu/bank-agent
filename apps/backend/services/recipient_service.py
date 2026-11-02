from sqlalchemy import select
from core.errors import require
from models import Recipient, User
from services.common import owned, lock_user, row_dict, audit


class RecipientService:
    def __init__(self, db, fineract):
        self.db, self.fineract = db, fineract

    def validate(self, account_id):
        account = self.fineract.get_savings_account(account_id)
        require(
            (account.get("depositType") or {}).get("id") == 100,
            "ACCOUNT_TYPE",
            "联系人收款账户必须为普通储蓄账户",
        )
        require(
            (account.get("currency") or {}).get("code") == "CNY",
            "UNSUPPORTED_CURRENCY",
            "收款账户必须为 CNY",
        )
        require(
            (account.get("status") or {}).get("active"),
            "ACCOUNT_INACTIVE",
            "收款账户未激活",
        )

    def list(self, user, field=None, query=None):
        stmt = select(Recipient).where(
            Recipient.user_id == user.id, Recipient.deleted.is_(False)
        )
        if query:
            value = query.strip().casefold()
            require(
                field in {"name", "phone", "alias", None},
                "INVALID_FIELD",
                "检索字段无效",
            )
            # Python casefold supports non-ASCII aliases without SQL wildcard interpretation.
            rows = self.db.scalars(stmt).all()
            return [
                row_dict(r, ("user_id", "deleted"))
                for r in rows
                if any(
                    value in getattr(r, f).casefold()
                    for f in ([field] if field else ["name", "phone", "alias"])
                )
            ]
        return [
            row_dict(r, ("user_id", "deleted"))
            for r in self.db.scalars(stmt.order_by(Recipient.name))
        ]

    def get(self, user, resource_id):
        row = owned(self.db, Recipient, resource_id, user)
        require(not row.deleted, "NOT_FOUND", "联系人不存在", 404)
        return row

    def details(self, user, resource_id):
        row = self.get(user, resource_id)
        account = self.fineract.get_savings_account(row.account_id)
        participant = self.db.scalar(
            select(User).where(
                User.client_id == account["clientId"],
                User.tenant == user.tenant,
                User.active.is_(True),
                User.is_admin.is_(False),
            )
        )
        return {
            **row_dict(row, ("user_id", "deleted")),
            "participant_user_id": participant.id if participant else None,
        }

    def save(self, user, data, resource_id=None):
        lock_user(self.db, user)
        self.validate(data.account_id)
        row = self.get(user, resource_id) if resource_id else Recipient(user_id=user.id)
        for k, v in data.model_dump().items():
            setattr(row, k, v)
        self.db.add(row)
        audit(self.db, user, "RECIPIENT_SAVED")
        self.db.commit()
        return row_dict(row, ("user_id", "deleted"))

    def delete(self, user, resource_id):
        lock_user(self.db, user)
        self.get(user, resource_id).deleted = True
        self.db.commit()
        return {"deleted": True}
