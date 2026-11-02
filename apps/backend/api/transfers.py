from fastapi import APIRouter
from sqlalchemy import select
from api.context import (
    Actor,
    Db,
    Key,
    DecimalRoute,
    action_service,
    transfer_service,
    schedule_service,
    aa_service,
)
from core.deps import get_fineract_client
from core.errors import require
from models import Action, Schedule, ScheduleRun, Audit
from schemas.banking import (
    RecipientRequest,
    TransferRequest,
    InternalTransferRequest,
    ConfirmRequest,
    VerifyRequest,
    ScheduleRequest,
    AARequest,
    AAPayRequest,
)
from services.common import owned, row_dict
from services.recipient_service import RecipientService

router = APIRouter(prefix="/api", tags=["transfers"], route_class=DecimalRoute)

AUDIT_SUMMARIES = {
    "ACTION_CREATED": "请求已创建",
    "CONFIRMED_OTP_REQUIRED": "已确认，需要安全验证",
    "OTP_ISSUED": "演示验证码已发送",
    "OTP_FAILED": "安全验证码校验失败",
    "OTP_VERIFIED": "安全验证已通过",
    "EXECUTION_STARTED": "正在处理",
    "EXECUTION_SUCCEEDED": "处理成功",
    "EXECUTION_FAILED": "处理失败",
    "ACTION_CANCELLED": "操作已取消",
    "RECONCILED": "已核对处理结果",
    "RESUME_REQUIRES_AUTHORIZATION": "已恢复处理，请重新确认",
    "SUBSCRIPTION_CANCELLED": "Demo 订阅已取消",
    "CARD_ACTIVATED": "借记卡已激活",
    "CARD_CONTROLS_CHANGED": "卡片设置已更新",
    "CARD_NUMBER_REVEALED": "已安全查看 Demo 卡号",
    "CARD_REVEAL_GRANTED": "已授权临时查看 Demo 卡号",
}


def recipients(db):
    return RecipientService(db, get_fineract_client())


@router.get("/recipients")
def list_recipients(
    user: Actor, db: Db, field: str | None = None, query: str | None = None
):
    return recipients(db).list(user, field, query)


@router.post("/recipients", status_code=201)
def create_recipient(body: RecipientRequest, user: Actor, db: Db):
    return recipients(db).save(user, body)


@router.get("/recipients/{recipient_id}")
def get_recipient(recipient_id: str, user: Actor, db: Db):
    return recipients(db).details(user, recipient_id)


@router.put("/recipients/{recipient_id}")
def update_recipient(recipient_id: str, body: RecipientRequest, user: Actor, db: Db):
    return recipients(db).save(user, body, recipient_id)


@router.delete("/recipients/{recipient_id}")
def delete_recipient(recipient_id: str, user: Actor, db: Db):
    return recipients(db).delete(user, recipient_id)


@router.post("/transfers", status_code=201)
def request_transfer(body: TransferRequest, user: Actor, db: Db, key: Key):
    # Request fingerprint binds business inputs too, even if two aliases refer to the same account.
    service = action_service(db)
    old = service.replay(user, "transfer", body.model_dump(mode="json"), key)
    if old:
        return service.view(old)
    payload = transfer_service(db).prepare(user, body)
    payload["recipient_id"] = body.recipient_id
    payload["_request"] = body.model_dump(mode="json")
    return service.view(service.create(user, "transfer", payload, key, body.amount))


@router.post("/internal-transfers", status_code=201)
def request_internal_transfer(
    body: InternalTransferRequest, user: Actor, db: Db, key: Key
):
    service = action_service(db)
    request = body.model_dump(mode="json")
    old = service.replay(user, "internal_transfer", request, key)
    if old:
        return service.view(old)
    payload = transfer_service(db).prepare_internal(user, body)
    payload["_request"] = request
    return service.view(
        service.create(user, "internal_transfer", payload, key, body.amount)
    )


@router.get("/transfers")
def list_transfers(user: Actor, db: Db):
    return [
        action_service(db).view(a)
        for a in db.scalars(
            select(Action)
            .where(
                Action.user_id == user.id,
                Action.kind.in_(("transfer", "internal_transfer")),
            )
            .order_by(Action.created_at.desc())
        )
    ]


@router.get("/transfers/{transfer_id}")
def get_transfer(transfer_id: str, user: Actor, db: Db):
    action = owned(db, Action, transfer_id, user)
    require(
        action.kind in {"transfer", "internal_transfer"},
        "NOT_FOUND",
        "转账不存在",
        404,
    )
    return action_service(db).view(action)


@router.get("/actions/{action_id}")
def get_action(action_id: str, user: Actor, db: Db):
    return action_service(db).view(owned(db, Action, action_id, user))


@router.post("/actions/{action_id}/confirm")
def confirm_action(action_id: str, body: ConfirmRequest, user: Actor, db: Db):
    return action_service(db).confirm(user, action_id, body.request_hash)


@router.post("/actions/{action_id}/otp")
def challenge_action(action_id: str, user: Actor, db: Db):
    return action_service(db).challenge(user, action_id)


@router.post("/actions/{action_id}/verify")
def verify_action(action_id: str, body: VerifyRequest, user: Actor, db: Db):
    return action_service(db).verify(user, action_id, body.code)


@router.post("/actions/{action_id}/cancel")
def cancel_action(action_id: str, user: Actor, db: Db):
    return action_service(db).cancel(user, action_id)


@router.post("/actions/{action_id}/reconcile")
def reconcile_action(action_id: str, user: Actor, db: Db):
    return action_service(db).reconcile(user, action_id)


@router.post("/actions/{action_id}/resume")
def resume_action(action_id: str, user: Actor, db: Db):
    return action_service(db).resume(user, action_id)


@router.get("/actions/{action_id}/audit")
def action_audit(action_id: str, user: Actor, db: Db):
    action = owned(db, Action, action_id, user)
    return [
        {
            "id": a.id,
            "event": a.event,
            "summary": AUDIT_SUMMARIES.get(a.event, "操作状态已更新"),
            "status": action.status,
            "failure_reason": action.error_code if action.status == "FAILED" else None,
            "trace_id": a.trace_id or action.id,
            "resource_type": a.resource_type or action.kind,
            "resource_id": a.resource_id or action.id,
            "data": {},
            "created_at": a.created_at,
        }
        for a in db.scalars(
            select(Audit)
            .where(Audit.user_id == user.id, Audit.action_id == action_id)
            .order_by(Audit.created_at)
        )
    ]


@router.get("/transfer-schedules")
def list_schedules(user: Actor, db: Db):
    return [
        row_dict(r)
        for r in db.scalars(select(Schedule).where(Schedule.user_id == user.id))
    ]


@router.post("/transfer-schedules", status_code=201)
def create_schedule(body: ScheduleRequest, user: Actor, db: Db):
    return schedule_service(db).save(user, body)


@router.get("/transfer-schedules/{schedule_id}")
def get_schedule(schedule_id: str, user: Actor, db: Db):
    return row_dict(owned(db, Schedule, schedule_id, user))


@router.put("/transfer-schedules/{schedule_id}")
def update_schedule(schedule_id: str, body: ScheduleRequest, user: Actor, db: Db):
    return schedule_service(db).save(user, body, schedule_id)


@router.delete("/transfer-schedules/{schedule_id}")
def delete_schedule(schedule_id: str, user: Actor, db: Db):
    return schedule_service(db).state(user, schedule_id, "cancel")


@router.post("/transfer-schedules/{schedule_id}/authorize")
def authorize_schedule(schedule_id: str, user: Actor, db: Db, key: Key):
    return schedule_service(db).authorize(user, schedule_id, key)


@router.post("/transfer-schedules/{schedule_id}/pause")
def pause_schedule(schedule_id: str, user: Actor, db: Db):
    return schedule_service(db).state(user, schedule_id, "pause")


@router.post("/transfer-schedules/{schedule_id}/resume")
def resume_schedule(schedule_id: str, user: Actor, db: Db):
    return schedule_service(db).state(user, schedule_id, "resume")


@router.get("/transfer-schedules/{schedule_id}/runs")
def schedule_runs(schedule_id: str, user: Actor, db: Db):
    owned(db, Schedule, schedule_id, user)
    rows = db.scalars(
        select(ScheduleRun)
        .where(ScheduleRun.schedule_id == schedule_id)
        .order_by(ScheduleRun.scheduled_at.desc())
    ).all()
    return [
        {
            **row_dict(r),
            "status": db.get(Action, r.action_id).status
            if r.action_id and r.status != "MISSED"
            else r.status,
        }
        for r in rows
    ]


@router.get("/aa-collections")
def list_aa(user: Actor, db: Db):
    return aa_service(db).list(user)


@router.post("/aa-collections", status_code=201)
def create_aa(body: AARequest, user: Actor, db: Db):
    return aa_service(db).save(user, body)


@router.get("/aa-collections/{collection_id}")
def get_aa(collection_id: str, user: Actor, db: Db):
    return aa_service(db).view(user, collection_id)


@router.put("/aa-collections/{collection_id}")
def update_aa(collection_id: str, body: AARequest, user: Actor, db: Db):
    return aa_service(db).save(user, body, collection_id)


@router.delete("/aa-collections/{collection_id}")
def cancel_aa(collection_id: str, user: Actor, db: Db):
    return aa_service(db).cancel(user, collection_id)


@router.post("/aa-collections/{collection_id}/shares/{share_id}/pay")
def pay_aa(
    collection_id: str, share_id: str, body: AAPayRequest, user: Actor, db: Db, key: Key
):
    return aa_service(db).pay(user, collection_id, share_id, body, key)


@router.get("/actions")
def list_actions(user: Actor, db: Db):
    return [
        action_service(db).view(a)
        for a in db.scalars(
            select(Action)
            .where(Action.user_id == user.id)
            .order_by(Action.created_at.desc())
        )
    ]
