from datetime import date
from fastapi import APIRouter, Query, Response

from api.context import (
    Actor, Db, Key, DecimalRoute, subscription_planning_service,
    subscription_service,
)
from core.config import get_settings
from core.errors import require
from schemas.banking import (
    SubscriptionBudgetRuleRequest, SubscriptionReminderRuleRequest,
    SubscriptionRenewalsResponse, SubscriptionScanResponse,
)

router = APIRouter(prefix="/api", tags=["subscriptions"], route_class=DecimalRoute)


@router.post("/subscriptions/scan", response_model=SubscriptionScanResponse)
def scan_subscriptions(user: Actor, db: Db):
    return subscription_service(db).scan(user)


@router.get("/subscriptions/renewals", response_model=SubscriptionRenewalsResponse)
def get_upcoming_renewals(
    user: Actor,
    db: Db,
    days: int = Query(default=3, ge=1, le=90),
):
    return subscription_service(db).renewals(user, days)


@router.get("/subscriptions/forecast")
def get_subscription_forecast(
    user: Actor,
    db: Db,
    response: Response,
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    from_date: date | None = None,
    to_date: date | None = None,
):
    response.headers["Cache-Control"] = "no-store"
    return subscription_planning_service(db).forecast(
        user, month=month, from_date=from_date, to_date=to_date
    )


@router.get("/subscriptions/reminder-rules")
def list_reminder_rules(user: Actor, db: Db, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return subscription_planning_service(db).list_reminder_rules(user)


@router.get("/subscriptions/reminder-rules/{rule_id}")
def get_reminder_rule(rule_id: str, user: Actor, db: Db, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return subscription_planning_service(db).get_reminder_rule(user, rule_id)


@router.post("/subscriptions/reminder-rules", status_code=201)
def create_reminder_rule(user: Actor, db: Db, body: SubscriptionReminderRuleRequest, key: Key):
    row, reused = subscription_planning_service(db).create_reminder_rule(
        user, **body.model_dump(), key=key
    )
    return {**row, "reused": reused}


@router.put("/subscriptions/reminder-rules/{rule_id}")
def update_reminder_rule(rule_id: str, user: Actor, db: Db,
                         body: SubscriptionReminderRuleRequest, key: Key):
    row, replayed = subscription_planning_service(db).edit_reminder_rule(
        user, rule_id, **body.model_dump(), key=key
    )
    return {**row, "replayed": replayed}


@router.post("/subscriptions/reminder-rules/{rule_id}/{command}")
def command_reminder_rule(rule_id: str, command: str, user: Actor, db: Db, key: Key):
    return subscription_planning_service(db).command_reminder_rule(user, rule_id, command, key)


@router.get("/subscriptions/budget-rules")
def list_budget_rules(user: Actor, db: Db, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return subscription_planning_service(db).list_budget_rules(user)


@router.get("/subscriptions/budget-rules/{rule_id}")
def get_budget_rule(rule_id: str, user: Actor, db: Db, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return subscription_planning_service(db).get_budget_rule(user, rule_id)


@router.post("/subscriptions/budget-rules", status_code=201)
def upsert_budget_rule(user: Actor, db: Db, body: SubscriptionBudgetRuleRequest, key: Key):
    rule, reused, evaluation = subscription_planning_service(db).upsert_budget_rule(
        user, month=body.month, amount=body.amount, key=key
    )
    return {"rule": {"id": rule.id, "month": rule.month,
            "amount": str(rule.amount), "status": rule.status},
            "reused": reused, "evaluation": evaluation}


@router.put("/subscriptions/budget-rules/{rule_id}")
def update_budget_rule(rule_id: str, user: Actor, db: Db,
                       body: SubscriptionBudgetRuleRequest, key: Key):
    rule, replayed, evaluation = subscription_planning_service(db).edit_budget_rule(
        user, rule_id, month=body.month, amount=body.amount, key=key
    )
    return {"rule": rule, "replayed": replayed, "evaluation": evaluation}


@router.post("/subscriptions/budget-rules/{rule_id}/{command}")
def command_budget_rule(rule_id: str, command: str, user: Actor, db: Db, key: Key):
    return subscription_planning_service(db).command_budget_rule(user, rule_id, command, key)


@router.get("/notifications/unread-count")
def get_notification_unread_count(user: Actor, db: Db, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"count": subscription_planning_service(db).unread_count(user)}


@router.get("/notifications")
def list_notifications(user: Actor, db: Db, response: Response, unread_only: bool = False):
    response.headers["Cache-Control"] = "no-store"
    return subscription_planning_service(db).list_notifications(user, unread_only=unread_only)


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str, user: Actor, db: Db):
    return subscription_planning_service(db).mark_notification_read(user, notification_id)


@router.get("/subscriptions")
def list_subscriptions(user: Actor, db: Db):
    return subscription_service(db).list(user)


@router.get("/subscriptions/{subscription_id}")
def get_subscription(subscription_id: str, user: Actor, db: Db):
    return subscription_service(db).detail(user, subscription_id)


@router.post("/subscriptions/{subscription_id}/verify")
def verify_subscription(subscription_id: str, user: Actor, db: Db, key: Key):
    return subscription_service(db).set_status(user, subscription_id, "VERIFIED")


@router.post("/subscriptions/{subscription_id}/ignore")
def ignore_subscription(subscription_id: str, user: Actor, db: Db, key: Key):
    return subscription_service(db).set_status(user, subscription_id, "IGNORED")


@router.post("/subscriptions/{subscription_id}/cancel", status_code=201)
def cancel_subscription(subscription_id: str, user: Actor, db: Db, key: Key):
    return subscription_service(db).request_cancel(user, subscription_id, key)


@router.post("/demo/subscriptions/{subscription_id}/charge")
def demo_subscription_charge(subscription_id: str, user: Actor, db: Db, key: Key):
    require(
        get_settings().environment == "development",
        "NOT_FOUND",
        "资源不存在",
        404,
    )
    return subscription_service(db).demo_charge(user, subscription_id)
