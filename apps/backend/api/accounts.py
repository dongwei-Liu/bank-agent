from datetime import date
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Query
from api.context import Actor, Db, DecimalRoute
from core.deps import get_account_service, get_fineract_client
from core.config import get_settings
from schemas.account import (
    AccountAggregateSummary,
    AccountDetail,
    AccountSummary,
    BalanceResponse,
)
from services.transaction_service import TransactionService

router = APIRouter(prefix="/api/accounts", tags=["accounts"], route_class=DecimalRoute)


@router.get("", response_model=list[AccountSummary])
def accounts(user: Actor):
    return get_account_service().list_accounts(user)


@router.get("/summary", response_model=AccountAggregateSummary)
def summary(user: Actor):
    return get_account_service().summary(user)


@router.get("/{account_id}/balance", response_model=BalanceResponse)
def balance(account_id: int, user: Actor):
    return get_account_service().get_balance(user, account_id)


@router.get("/{account_id}", response_model=AccountDetail)
def detail(account_id: int, user: Actor):
    return get_account_service().account_detail(user, account_id)


@router.get("/{account_id}/transactions")
def transactions(
    account_id: int,
    user: Actor,
    db: Db,
    page: int = Query(0, ge=0),
    page_size: int = Query(20, ge=1, le=100),
    from_date: date | None = None,
    to_date: date | None = None,
    direction: Literal["credit", "debit"] | None = None,
    min_amount: Decimal | None = Query(None, ge=0),
    max_amount: Decimal | None = Query(None, ge=0),
):
    return TransactionService(db, get_fineract_client(), get_settings()).list(
        user,
        account_id,
        page,
        page_size,
        from_date,
        to_date,
        direction,
        min_amount,
        max_amount,
    )


@router.get("/{account_id}/transactions/{transaction_id}")
def transaction(account_id: int, transaction_id: int, user: Actor, db: Db):
    return TransactionService(db, get_fineract_client(), get_settings()).detail(
        user, account_id, transaction_id
    )
