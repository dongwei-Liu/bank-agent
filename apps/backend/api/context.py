from functools import wraps
from typing import Annotated
from fastapi import Depends, Header
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session
from core.database import get_db
from core.deps import get_user, get_fineract_client
from core.config import get_settings
from models import User
from services.common import safe_json

Db = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(get_user)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=160)]


class DecimalRoute(APIRoute):
    """Preserve monetary Decimal strings at the HTTP boundary on every business route."""

    def __init__(self, *args, **kwargs):
        endpoint = kwargs.get("endpoint")
        if endpoint and not getattr(endpoint, "_bank_decimal_wrapped", False):

            @wraps(endpoint)
            def encode(*a, **k):
                return safe_json(endpoint(*a, **k))

            encode._bank_decimal_wrapped = True
            kwargs["endpoint"] = encode
        super().__init__(*args, **kwargs)


def action_service(db):
    from services.action_service import ActionService

    return ActionService(db, get_fineract_client(), get_settings())


def transfer_service(db):
    from services.transfer_service import TransferService

    return TransferService(db, get_fineract_client())


def schedule_service(db):
    from services.schedule_service import ScheduleService

    return ScheduleService(db, get_fineract_client(), get_settings())


def aa_service(db):
    from services.aa_service import AAService

    return AAService(db, get_fineract_client(), get_settings())


def billing_service(db):
    from services.billing_service import BillingService

    return BillingService(db, get_fineract_client(), get_settings())


def bill_report_service(db):
    from services.bill_report_service import BillReportService

    return BillReportService(db, get_fineract_client(), get_settings())


def transaction_service(db):
    from services.transaction_service import TransactionService

    return TransactionService(db, get_fineract_client(), get_settings())


def analysis_service(db, accounts, investments=None):
    from services.analysis_result_service import AnalysisResultService
    return AnalysisResultService(db, accounts, get_settings(), investments)


def investment_service(db):
    from services.investment_service import InvestmentService

    return InvestmentService(db, get_fineract_client(), get_settings())


def subscription_service(db):
    from services.subscription_service import SubscriptionService

    return SubscriptionService(db, get_fineract_client(), get_settings())


def subscription_planning_service(db):
    from services.subscription_planning_service import SubscriptionPlanningService

    return SubscriptionPlanningService(db, get_fineract_client(), get_settings())


def card_service(db):
    from services.card_service import CardService

    return CardService(db, get_fineract_client(), get_settings())


def card_transaction_service(db):
    from services.card_transaction_service import CardTransactionService

    return CardTransactionService(db, get_fineract_client(), get_settings())


def orchestration_service(db):
    from services.orchestration_service import OrchestrationService

    return OrchestrationService(db, get_fineract_client(), get_settings())
