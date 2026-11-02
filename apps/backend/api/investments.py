from decimal import Decimal
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from api.context import Actor, Db, Key, DecimalRoute, investment_service, action_service
from core.deps import get_admin
from core.errors import require
from models import Action, RiskAssessment, ProductMetadata, User
from schemas.banking import (
    RiskRequest,
    MetadataRequest,
    SubscriptionRequest,
    RedemptionRequest,
)
from services.common import owned, row_dict, lock_user, audit

router = APIRouter(prefix="/api", tags=["investments"], route_class=DecimalRoute)
Admin = Annotated[User, Depends(get_admin)]


@router.get("/risk-assessments/questionnaire")
def questionnaire(user: Actor):
    return {
        "version": "demo-v1",
        "answer_scores": [1, 2, 3, 4, 5],
        "valid_days": 0,
        "valid_minutes": 15,
        "questions": [
            {
                "id": 1,
                "text": "您的投资经验？",
                "choices": ["无", "不足一年", "一至三年", "三至五年", "超过五年"],
            },
            {
                "id": 2,
                "text": "您能接受的本金损失比例？",
                "choices": ["不能接受", "5%以内", "10%以内", "20%以内", "超过20%"],
            },
            {
                "id": 3,
                "text": "您的可投资资金占家庭资产比例？",
                "choices": ["低于5%", "5%至10%", "10%至20%", "20%至40%", "超过40%"],
            },
            {
                "id": 4,
                "text": "您的计划持有期限？",
                "choices": [
                    "一个月以内",
                    "一至三个月",
                    "三至六个月",
                    "六至十二个月",
                    "超过一年",
                ],
            },
            {
                "id": 5,
                "text": "面对短期波动时您的选择？",
                "choices": [
                    "立即退出",
                    "大幅减持",
                    "部分减持",
                    "继续持有",
                    "可以追加投入",
                ],
            },
        ],
        "level_ranges": [[5, 9], [10, 14], [15, 19], [20, 24], [25, 25]],
        "purpose": "Demo 适配规则，不构成投资建议",
    }


@router.post("/risk-assessments", status_code=201)
def assess(body: RiskRequest, user: Actor, db: Db):
    return investment_service(db).assess(user, body)


@router.get("/risk-assessments")
def assessments(user: Actor, db: Db):
    return [
        row_dict(r)
        for r in db.scalars(
            select(RiskAssessment)
            .where(RiskAssessment.user_id == user.id)
            .order_by(RiskAssessment.created_at.desc())
        )
    ]


@router.get("/risk-assessments/{id}")
def assessment(id: str, user: Actor, db: Db):
    return row_dict(owned(db, RiskAssessment, id, user))


@router.get("/investments/products")
def products(user: Actor, db: Db):
    return investment_service(db).products(user)


@router.get("/investments/products/compare")
def compare(
    user: Actor, db: Db, ids: Annotated[list[int], Query(min_length=2, max_length=10)]
):
    return [investment_service(db).product(user, id) for id in dict.fromkeys(ids)]


@router.get("/investments/products/{id}")
def product(id: int, user: Actor, db: Db):
    return investment_service(db).product(user, id)


@router.put("/investments/products/{id}/metadata")
def metadata(id: int, body: MetadataRequest, user: Admin, db: Db):
    lock_user(db, user)
    investment_service(db).product(user, id)
    row = db.get(ProductMetadata, id)
    require(not row or row.tenant == user.tenant, "NOT_FOUND", "产品不存在", 404)
    row = row or ProductMetadata(product_id=id, tenant=user.tenant)
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    db.add(row)
    audit(db, user, "PRODUCT_METADATA_CHANGED", product_id=id)
    db.commit()
    return row_dict(row)


@router.get("/investments/recommendations")
def recommendations(
    user: Actor,
    db: Db,
    amount: Annotated[Decimal, Query(gt=0, max_digits=18, decimal_places=2)],
    term_months: Annotated[int, Query(ge=1, le=120)],
    needs_liquidity: bool = False,
):
    return investment_service(db).recommendations(
        user, amount, term_months, needs_liquidity
    )


@router.post("/investments/subscriptions", status_code=201)
def subscribe(body: SubscriptionRequest, user: Actor, db: Db, key: Key):
    service = action_service(db)
    old = service.replay(user, "subscription", body.model_dump(mode="json"), key)
    if old:
        return service.view(old)
    investment = investment_service(db)
    payload = investment.prepare_subscription(user, body)
    payload["_request"] = body.model_dump(mode="json")
    action = service.create(
        user, "subscription", payload, key, body.amount, commit=False
    )
    investment.consume_assessment(user, payload["assessment_id"], action)
    db.commit()
    return service.view(action)


@router.get("/investments/subscriptions")
def subscriptions(user: Actor, db: Db):
    return orders(user, db, "subscription")


@router.get("/investments/subscriptions/{id}")
def subscription(id: str, user: Actor, db: Db):
    return order(user, db, id, "subscription")


@router.get("/investments/holdings")
def holdings(user: Actor, db: Db):
    return investment_service(db).holdings(user)


@router.get("/investments/holdings/{id}")
def holding(id: int, user: Actor, db: Db):
    return investment_service(db).holding(user, id)


@router.get("/investments/redemption-quotes")
def quote(
    user: Actor,
    db: Db,
    holding_id: Annotated[int, Query(gt=0)],
    to_account_id: Annotated[int, Query(gt=0)],
):
    return investment_service(db).quote(user, holding_id, to_account_id)


@router.post("/investments/redemptions", status_code=201)
def redeem(body: RedemptionRequest, user: Actor, db: Db, key: Key):
    service = action_service(db)
    old = service.replay(user, "redemption", body.model_dump(mode="json"), key)
    if old:
        return service.view(old)
    payload = investment_service(db).prepare_redemption(user, body)
    payload["_request"] = body.model_dump(mode="json")
    return service.view(
        service.create(user, "redemption", payload, key, Decimal(payload["principal"]))
    )


@router.get("/investments/redemptions")
def redemptions(user: Actor, db: Db):
    return orders(user, db, "redemption")


@router.get("/investments/redemptions/{id}")
def redemption(id: str, user: Actor, db: Db):
    return order(user, db, id, "redemption")


def orders(user, db, kind):
    return [
        action_service(db).view(a)
        for a in db.scalars(
            select(Action)
            .where(Action.user_id == user.id, Action.kind == kind)
            .order_by(Action.created_at.desc())
        )
    ]


def order(user, db, id, kind):
    a = owned(db, Action, id, user)
    require(a.kind == kind, "NOT_FOUND", "订单不存在", 404)
    return action_service(db).view(a)
