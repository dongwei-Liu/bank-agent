from decimal import Decimal
from sqlalchemy import select
from core.errors import require
from models import AACollection, AAShare, Action, User
from services.common import owned, lock_user, row_dict, audit
from services.account_service import AccountService
from services.action_service import ActionService
from services.transfer_service import TransferService
from core.security import fingerprint


def split_cents(total, count):
    cents = int(Decimal(total) * 100)
    base, remainder = divmod(cents, count)
    require(base > 0, "INVALID_SPLIT", "每位参与人至少分摊一分钱")
    return [Decimal(base + (i < remainder)) / 100 for i in range(count)]


class AAService:
    def __init__(self, db, fineract, settings):
        self.db, self.fineract, self.settings = db, fineract, settings

    def view(self, user, collection_id):
        row = self.db.get(AACollection, collection_id)
        shares = self.db.scalars(
            select(AAShare).where(AAShare.collection_id == collection_id)
        ).all()
        require(
            row
            and (row.user_id == user.id or any(s.user_id == user.id for s in shares)),
            "NOT_FOUND",
            "收款单不存在",
            404,
        )
        return {**row_dict(row), "shares": [row_dict(s) for s in shares]}

    def list(self, user):
        ids = set(
            self.db.scalars(
                select(AACollection.id).where(AACollection.user_id == user.id)
            )
        )
        ids.update(
            self.db.scalars(
                select(AAShare.collection_id).where(AAShare.user_id == user.id)
            )
        )
        return [self.view(user, i) for i in sorted(ids)]

    def save(self, user, request, collection_id=None, *, idempotency_key=None):
        lock_user(self.db, user)
        request_hash = fingerprint(request.model_dump(mode="json"))
        if idempotency_key and collection_id is None:
            require(len(idempotency_key) <= 160, "IDEMPOTENCY_KEY_INVALID", "AA 请求幂等键过长")
            existing = self.db.scalar(select(AACollection).where(
                AACollection.user_id == user.id,
                AACollection.idempotency_key == idempotency_key,
            ))
            if existing:
                require(existing.request_hash == request_hash, "IDEMPOTENCY_CONFLICT",
                        "同一幂等键的 AA 请求参数不同", 409)
                return self.view(user, existing.id)
        AccountService(self.fineract).get_account(user, request.account_id)
        row = (
            owned(self.db, AACollection, collection_id, user)
            if collection_id
            else AACollection(user_id=user.id)
        )
        if collection_id:
            self.db.refresh(row, with_for_update=True)
            shares = self.db.scalars(
                select(AAShare).where(AAShare.collection_id == collection_id)
            ).all()
            require(
                row.status == "OPEN"
                and all(s.status in {"UNPAID", "SELF_PAID"} for s in shares),
                "COLLECTION_FROZEN",
                "已有付款或授权请求，不能修改分摊",
                409,
            )
            for s in shares:
                self.db.delete(s)
            self.db.flush()
        amounts = (
            split_cents(request.amount, len(request.participants))
            if request.mode == "equal"
            else [p.amount for p in request.participants]
        )
        row.account_id = request.account_id
        row.title = request.title
        row.amount = request.amount
        if idempotency_key and collection_id is None:
            row.idempotency_key = idempotency_key
            row.request_hash = request_hash
        self.db.add(row)
        self.db.flush()
        for participant, amount in zip(request.participants, amounts):
            target = self.db.get(User, participant.user_id)
            require(
                target
                and target.active
                and target.tenant == user.tenant
                and not target.is_admin,
                "INVALID_PARTICIPANT",
                "参与人无效",
            )
            self.db.add(
                AAShare(
                    collection_id=row.id,
                    user_id=target.id,
                    amount=amount,
                    status="SELF_PAID" if target.id == user.id else "UNPAID",
                )
            )
        self.db.flush()
        if all(p.user_id == user.id for p in request.participants):
            row.status = "COMPLETED"
        audit(self.db, user, "AA_SAVED")
        self.db.commit()
        return self.view(user, row.id)

    def agent_list(self, user):
        users = {row.id: row.username for row in self.db.scalars(select(User)).all()}
        result = []
        for collection in self.list(user):
            shares = []
            for share in collection["shares"]:
                action = self.db.get(Action, share["action_id"]) if share.get("action_id") else None
                shares.append({
                    "participant": users.get(share["user_id"], "成员"),
                    "amount": str(share["amount"]),
                    "status": share["status"],
                    "is_me": share["user_id"] == user.id,
                    "action_status": action.status if action else None,
                })
            result.append({
                "collection_ref": collection["id"],
                "title": collection["title"],
                "amount": str(collection["amount"]),
                "status": collection["status"],
                "shares": shares,
            })
        return result

    def cancel_share(self, user, collection_id, share_id):
        lock_user(self.db, user)
        collection = self.db.get(AACollection, collection_id)
        share = owned(self.db, AAShare, share_id, user)
        require(collection and share.collection_id == collection.id, "NOT_FOUND", "参与项不存在", 404)
        self.db.refresh(collection, with_for_update=True)
        require(collection.status == "OPEN", "COLLECTION_CLOSED", "收款单已结束", 409)
        if share.status == "CANCELLED":
            return row_dict(share)
        require(share.status not in {"PAID", "SELF_PAID"}, "SHARE_PAID", "本人份额已付款，不能取消", 409)
        if share.action_id:
            action = self.db.get(Action, share.action_id)
            require(action and action.status not in {"SUCCEEDED", "EXECUTING", "RECONCILING"},
                    "COLLECTION_BUSY", "付款已完成或正在核对，不能取消", 409)
            if action.status != "CANCELLED":
                ActionService(self.db, self.fineract, self.settings).cancel(user, action.id)
                self.db.refresh(share)
        share.status = "CANCELLED"
        audit(self.db, user, "AA_SHARE_CANCELLED", collection_id=collection.id)
        self.db.commit()
        return row_dict(share)

    def pay(self, user, collection_id, share_id, request, key):
        lock_user(self.db, user)
        row = self.db.scalar(
            select(AACollection)
            .where(AACollection.id == collection_id)
            .with_for_update()
        )
        share = owned(self.db, AAShare, share_id, user)
        require(row and share.collection_id == row.id, "NOT_FOUND", "参与项不存在", 404)
        if share.action_id:
            action = self.db.get(Action, share.action_id)
            require(
                action.payload["from_account_id"] == request.from_account_id
                and action.idempotency_key == key,
                "PAYMENT_EXISTS",
                "该份额已有付款请求",
                409,
            )
            return ActionService(self.db, self.fineract, self.settings).view(action)
        require(
            row.status == "OPEN" and share.status == "UNPAID",
            "COLLECTION_CLOSED",
            "收款单不可付款",
            409,
        )
        payload = TransferService(self.db, self.fineract).prepare_accounts(
            user, request.from_account_id, row.account_id, share.amount, row.title
        )
        payload["aa_share_id"] = share.id
        service = ActionService(self.db, self.fineract, self.settings)
        action = service.create(
            user, "transfer", payload, key, share.amount, commit=False
        )
        if action.status in {"CANCELLED", "FAILED"}:
            return service.view(action)
        share.action_id = action.id
        share.status = "PENDING"
        self.db.commit()
        return service.view(action)

    def cancel(self, user, collection_id):
        lock_user(self.db, user)
        row = owned(self.db, AACollection, collection_id, user)
        self.db.refresh(row, with_for_update=True)
        require(row.status == "OPEN", "COLLECTION_STATE", "收款单已结束", 409)
        shares = self.db.scalars(
            select(AAShare).where(AAShare.collection_id == row.id)
        ).all()
        for share in shares:
            if share.action_id:
                a = self.db.get(Action, share.action_id)
                require(
                    a.status not in {"EXECUTING", "RECONCILING"},
                    "COLLECTION_BUSY",
                    "存在执行中付款，先核对后再取消",
                    409,
                )
                if a.status not in {"SUCCEEDED", "CANCELLED"}:
                    a.status = "CANCELLED"
                    a.otp_hash = None
                    a.dev_otp = None
            if share.status not in {"PAID", "SELF_PAID"}:
                share.status = "CANCELLED"
        row.status = "CANCELLED"
        audit(self.db, user, "AA_CANCELLED")
        self.db.commit()
        return self.view(user, row.id)
