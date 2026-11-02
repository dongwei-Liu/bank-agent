from fastapi import APIRouter

from api.context import (
    Actor,
    Db,
    Key,
    DecimalRoute,
    card_transaction_service,
)
from core.config import get_settings
from core.errors import require
from schemas.banking import CardTransactionRequest

router = APIRouter(prefix="/api", tags=["demo-card-transactions"], route_class=DecimalRoute)


def require_demo_environment() -> None:
    require(
        get_settings().environment == "development",
        "NOT_FOUND",
        "资源不存在",
        404,
    )


@router.get("/demo/merchants")
def list_demo_merchants(user: Actor, db: Db):
    require_demo_environment()
    return card_transaction_service(db).list_merchants()


@router.post("/demo/card-transactions", status_code=201)
def create_demo_card_transaction(
    body: CardTransactionRequest, user: Actor, db: Db, key: Key
):
    require_demo_environment()
    return card_transaction_service(db).request(user, body, key)


@router.get("/cards/{card_id}/transactions")
def list_card_transactions(card_id: str, user: Actor, db: Db):
    require_demo_environment()
    return card_transaction_service(db).list_transactions(user, card_id)
