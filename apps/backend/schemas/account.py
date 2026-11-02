"""Response contracts for the account endpoints.

These are the *outward* shape of our API - deliberately nothing like Fineract's
own payloads. Callers (the Agent layer, the React frontend) should never have to
know that Fineract exists, which is what lets us swap or mock it later.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class AccountSummary(BaseModel):
    """Stable application-facing account contract; never expose raw Fineract JSON."""

    id: int
    account_no: str
    client_id: int
    client_name: str
    product_id: int
    product_name: str
    deposit_type: str
    currency: str
    status: str
    available_balance: Decimal


class AccountDetail(AccountSummary):
    external_id: str | None = None
    submitted_on: str | None = None
    approved_on: str | None = None
    activated_on: str | None = None
    nominal_annual_interest_rate: Decimal = Decimal("0")
    allow_overdraft: bool = False


class BalanceResponse(BaseModel):
    """What "我还有多少钱" resolves to.

    Note the invariants encoded here: the balance is a Decimal (never a float -
    money must not drift) and the currency is explicit, so the Agent can never
    silently compare a CNY amount against a USD one.
    """

    account_id: int = Field(description="Fineract 内部账户 id")
    account_no: str = Field(description="对外展示的账号")
    client_id: int = Field(description="所属客户 id")
    client_name: str = Field(description="客户姓名，如 Alice Chen")
    balance: Decimal = Field(description="可用余额")
    currency: str = Field(default="CNY", description="币种代码")


class AccountAggregateSummary(BaseModel):
    """Authoritative aggregate across all of the user's CNY savings accounts."""

    currency: str = "CNY"
    total: Decimal
    account_count: int = Field(ge=0)
    complete: bool
