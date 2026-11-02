"""Idempotent Fineract seed script for the Bank Agent competition project.

Creates everything the six demo scenarios need, and nothing else:

  * enables CNY currency
  * one shared savings product ("BANK_AGENT_SAVINGS")
  * four demo clients plus isolated card, flower and cake Demo merchants
  * one ACTIVE primary savings account per person, Alice's analysis account,
    five fixed zero-balance card accounts, and three isolated Demo merchant accounts
  * an opening balance plus up to 200 days of seed-reproducible categorized
    history: salary, housing bills, daily spending and monthly subscriptions

Design rules that matter:

  * **Idempotent.** Re-running never duplicates anything. Every resource is
    looked up by a stable key first (``externalId`` for clients, ``externalId``
    on the client->account mapping for savings accounts) and a local state
    file records the identifiers that Fineract does not let us query back.
  * **Reproducible.** Every run defaults to a fresh random seed; pass
    ``--history-seed`` and ``--as-of`` to reproduce the same planned history.
  * **No LLM, no policy.** This script is pure data plumbing - it writes facts
    to the bank of record. Nothing here decides anything.

Usage (from anywhere, uses the project .env by default)::

    python scripts/fineract/seed_fineract.py             # generate a new demo history
    python scripts/fineract/seed_fineract.py --dry-run   # preview, no core writes
    python scripts/fineract/seed_fineract.py --history-seed 7 --as-of 2026-10-23
    python scripts/fineract/seed_fineract.py --verbose   # per-request logging
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import secrets
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import httpx
from demo_history import (
    ANALYSIS_ACCOUNT_EXTERNAL_ID,
    CATEGORY_MERCHANTS,
    GENERATOR_VERSION,
    MONTHLY_SUBSCRIPTION_MERCHANTS,
    PlannedHistory,
    build_random_history,
    merchant_category_map,
    split_history_for_analysis_account,
)

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
STATE_FILE = SCRIPT_DIR / ".seed-state.json"

DATE_FORMAT = "yyyy-MM-dd"
LOCALE = "en"
CURRENCY = "CNY"

# The account must be opened before any transaction we want to post, otherwise
# Fineract rejects them as "before activation". New accounts open at the first
# day of the generated window (up to 200 days ending at the selected cutoff).
HISTORY_DAYS = 200
ACCOUNT_OPEN_OFFSET = HISTORY_DAYS - 1
MANIFEST_FILE = PROJECT_ROOT / ".runtime" / "demo-history-manifest.json"

PRODUCT_NAME = "BANK_AGENT_SAVINGS"
# Fineract caps this at 4 characters (validation.msg.savingsproduct.shortName...)
PRODUCT_SHORT_NAME = "AGTS"

# These are deliberately labelled Demo products.  The rates are stable
# competition fixtures, not market quotations or investment advice.
FIXED_DEPOSIT_PRODUCTS: tuple[dict[str, Any], ...] = (
    {
        "name": "BANK_AGENT_DEMO_FIXED_3M",
        "short_name": "AF3M",
        "description": "Bank Agent Demo 三个月人民币定存；利率仅用于比赛演示",
        "term_months": 3,
        "annual_interest_rate": "1.00",
        "risk_level": 1,
        "allows_premature": True,
    },
    {
        "name": "BANK_AGENT_DEMO_FIXED_6M",
        "short_name": "AF6M",
        "description": "Bank Agent Demo 六个月人民币定存；利率仅用于比赛演示",
        "term_months": 6,
        "annual_interest_rate": "1.20",
        "risk_level": 1,
        "allows_premature": True,
    },
)

log = logging.getLogger("seed")


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclasses.dataclass(frozen=True)
class FineractConfig:
    """Connection settings for the local Fineract instance."""

    base_url: str = _env(
        "FINERACT_BASE_URL", "https://localhost:8443/fineract-provider/api/v1"
    )
    user: str = _env("FINERACT_USER", "mifos")
    password: str = _env("FINERACT_PASSWORD", "password")
    tenant: str = _env("FINERACT_TENANT", "default")


# --------------------------------------------------------------------------- #
# Transport
# --------------------------------------------------------------------------- #


class FineractError(RuntimeError):
    """A non-2xx response from Fineract, carrying its error payload."""

    def __init__(self, status: int, body: Any, context: str = "") -> None:
        self.status = status
        self.body = body
        super().__init__(f"{context} failed: HTTP {status} {json.dumps(body, ensure_ascii=False)}")


class FineractClient:
    """Thin REST wrapper: auth + tenant header + hostile self-signed TLS.

    Deliberately dependency-free and synchronous. This is the same shape the
    real ``FineractAdapter`` in ``apps/backend`` will take, so the seed script
    doubles as a smoke test of the API surface we are going to depend on.
    """

    def __init__(self, config: FineractConfig, timeout: float = 30.0) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            auth=(config.user, config.password),
            headers={
                "Fineract-Platform-TenantId": config.tenant,
                "Content-Type": "application/json",
            },
            verify=False,  # Fineract ships a self-signed certificate locally
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, add_common: bool = False, **kwargs: Any) -> Any:
        log.debug("%s %s %s", method, path, kwargs.get("json") or kwargs.get("params") or "")
        # Client / account / transaction writes reject requests missing
        # dateFormat+locale with the cryptic
        # "validation.msg.input.field.invalid.Date". Product and currency
        # endpoints do the opposite and reject them as unsupported parameters,
        # hence the explicit opt-in instead of blanket injection.
        if add_common and method in ("POST", "PUT"):
            body = kwargs.get("json")
            if isinstance(body, dict):
                body.setdefault("dateFormat", DATE_FORMAT)
                body.setdefault("locale", LOCALE)
        response = self._client.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                payload: Any = response.json()
            except ValueError:
                payload = response.text
            raise FineractError(response.status_code, payload, f"{method} {path}")
        if not response.content:
            return None
        content_type = response.headers.get("content-type", "")
        return response.json() if "application/json" in content_type else response.text

    def get(self, path: str, **kwargs: Any) -> Any:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, add_common: bool = True, **kwargs: Any) -> Any:
        return self._request("POST", path, add_common=add_common, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        return self._request("PUT", path, **kwargs)


# --------------------------------------------------------------------------- #
# Dataset
# --------------------------------------------------------------------------- #


@dataclasses.dataclass
class ClientSpec:
    """Who we are creating. ``key`` becomes the Fineract ``externalId``."""

    key: str
    firstname: str
    lastname: str
    mobile: str
    opening_balance: float
    monthly_salary: float


CLIENTS: list[ClientSpec] = [
    ClientSpec("ALICE", "Alice", "Chen", "13800000001", 10_000.00, 12_000.00),
    ClientSpec("BOB", "Bob", "Wang", "13800000002", 8_000.00, 9_500.00),
    ClientSpec("CHARLIE", "Charlie", "Li", "13800000003", 5_000.00, 7_800.00),
    ClientSpec("MOM", "Mom", "Chen", "13800000004", 5_000.00, 6_000.00),
]

# Stable baseline card accounts.  The card rows and encrypted Demo PANs live
# in the middle tier; Fineract owns only these zero-balance settlement
# accounts.  Fixed external IDs let seed/reset reuse the same core resources
# instead of leaking a new account on every demo rehearsal.
DEMO_CARD_ACCOUNTS: dict[str, tuple[tuple[str, str], ...]] = {
    "ALICE": (
        ("AGENT-ALICE-CARD-1", "日常消费卡"),
        ("AGENT-ALICE-CARD-2", "备用卡"),
    ),
    "BOB": (("AGENT-BOB-CARD-1", "日常消费卡"),),
    "CHARLIE": (("AGENT-CHARLIE-CARD-1", "日常消费卡"),),
    "MOM": (("AGENT-MOM-CARD-1", "日常消费卡"),),
}

DEMO_MERCHANT = ClientSpec(
    "DEMO-MERCHANT",
    "Zhihui",
    "Demo Merchant",
    "13900000000",
    0.00,
    0.00,
)

DEMO_ORCHESTRATION_MERCHANTS: tuple[ClientSpec, ...] = (
    ClientSpec("DEMO-FLOWER", "Xinyi", "Demo Florist", "13900000001", 0.00, 0.00),
    ClientSpec("DEMO-CAKE", "Tianmi", "Demo Bakery", "13900000002", 0.00, 0.00),
)

def parse_fineract_date(value: Any) -> date | None:
    """Fineract serialises dates both as ``[2026, 4, 1]`` and ``"2026-04-01"``."""
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return date(int(value[0]), int(value[1]), int(value[2]))
    if isinstance(value, str) and len(value) >= 10:
        return date.fromisoformat(value[:10])
    return None


def external_id(key: str) -> str:
    """Stable external identifier, unique across teammates' machines."""
    return f"AGENT-{key}"


def parse_fineract_date(value: Any) -> date | None:
    """Fineract returns dates both as [2026, 4, 1] arrays and as ISO strings."""
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return date(int(value[0]), int(value[1]), int(value[2]))
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return None


def build_history(
    spec: ClientSpec, start: date, days: int, seed: int | None = None, *, include_salary: bool = True
) -> list[tuple[date, str, Decimal, int, str]]:
    """Build randomized history; pass a seed when a reproducible sample is needed."""
    return list(build_random_history(
        spec=spec, start=start, days=days, seed=secrets.randbits(63) if seed is None else seed,
        opening_balance=Decimal(str(spec.opening_balance)), include_salary=include_salary,
    ).rows)


def trim_to_balance(
    history: list[tuple[date, str, Decimal, int, str]], floor: Decimal = Decimal("500.00")
) -> list[tuple[date, str, Decimal, int, str]]:
    """Drop withdrawals that would push the running balance below ``floor``.

    Fineract enforces "no overdraft" for deposit products configured without a
    withdrawal limit, so we must not blindly replay withdrawals.
    """
    balance = Decimal("0")
    kept: list[tuple[date, str, Decimal, int, str]] = []
    for entry in history:
        _, kind, amount, _, _ = entry
        if kind == "deposit":
            balance += amount
            kept.append(entry)
        elif balance - amount >= Decimal(str(floor)):
            balance -= amount
            kept.append(entry)
    return kept


# --------------------------------------------------------------------------- #
# Seeding steps
# --------------------------------------------------------------------------- #


class State:
    """Tiny JSON-backed store for ids Fineract will not give back to us."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {
            "clients": {},
            "accounts": {},
            "product_id": None,
            "fixed_product_ids": {},
        }
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.data.update(loaded)

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8"
        )


class Seeder:
    def __init__(self, client: FineractClient, state: State, dry_run: bool = False) -> None:
        self.client = client
        self._state = state
        self.dry_run = dry_run
        self.as_of = datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1)
        self.opened = first_open_date(self.as_of)
        self.history_seed = secrets.randbits(63)
        self.history_results: dict[str, dict[str, Any]] = {}
        # Per-client opening date, refined once we know when the client really
        # entered Fineract: nothing may predate the client's own submitted date.
        self.open_dates: dict[str, date] = {}

    # -- helpers ----------------------------------------------------------- #

    @staticmethod
    def first_open_date() -> date:
        return first_open_date()

    def d(self, value: date) -> str:
        return value.strftime("%Y-%m-%d")

    def find_client(self, external: str) -> int | None:
        """Look a client up by its exact externalId.

        The ignored state file is a cache, not an authority.  Always verify the
        stable externalId with Fineract before returning an id so a stale cache
        can never make a seed/reset mutate an unrelated client.
        """
        page = self.client.get(
            "/clients", params={"externalId": external, "limit": 100}
        ) or {}
        rows = page.get("pageItems", []) if isinstance(page, dict) else page
        matches = [item for item in rows if item.get("externalId") == external]
        if len(matches) > 1:
            raise RuntimeError(f"Fineract 中存在重复客户 externalId={external}")
        if matches:
            self._state.data["clients"][external] = matches[0]["id"]
            return int(matches[0]["id"])
        return None

    def find_savings_account(self, client_id: int, external: str) -> int | None:
        """Find exactly the requested savings account externalId.

        Demo users will own multiple accounts once card support lands, so the
        first account in a client's list is never a safe fallback.
        """
        if client_id < 0:
            return None
        accounts = self.client.get(f"/clients/{client_id}/accounts")
        matches = [
            entry
            for entry in (accounts or {}).get("savingsAccounts", [])
            if entry.get("externalId") == external
        ]
        if len(matches) > 1:
            raise RuntimeError(f"Fineract 中存在重复储蓄账户 externalId={external}")
        if matches:
            self._state.data["accounts"][external] = matches[0]["id"]
            return int(matches[0]["id"])
        return None

    def active_transactions(self, account_id: int) -> list[dict[str, Any]]:
        """Return every currently effective transaction, across all pages."""
        rows: list[dict[str, Any]] = []
        page = 0
        page_size = 200
        while True:
            payload = self.client.get(
                f"/savingsaccounts/{account_id}/transactions/search",
                params={
                    "offset": page,
                    "limit": page_size,
                    "orderBy": "transactionDate,id",
                    "sortOrder": "DESC",
                },
            ) or {}
            content = payload.get("content")
            if not isinstance(content, list) or payload.get("total") is None:
                raise RuntimeError("Fineract 流水分页契约不兼容")
            rows.extend(
                row
                for row in content
                if not row.get("reversed") and not row.get("isReversal")
            )
            if (page + 1) * page_size >= int(payload["total"]):
                break
            page += 1
        return rows

    # -- steps -------------------------------------------------------------- #

    def seed_orchestration_merchants(self) -> dict[str, dict[str, Any]]:
        """Create only the two fixed birthday Demo merchants and zero-balance accounts."""
        self.step_currency()
        product_id = self.step_product()
        summary: dict[str, dict[str, Any]] = {}
        for spec in DEMO_ORCHESTRATION_MERCHANTS:
            client_id = self.ensure_client(spec)
            account_id = self.ensure_account(client_id, product_id, spec.key)
            balance = None
            if not self.dry_run and account_id > 0:
                details = self.client.get(f"/savingsaccounts/{account_id}")
                balance = (details or {}).get("summary", {}).get("availableBalance")
            summary[spec.key] = {
                "client_id": client_id,
                "account_id": account_id,
                "balance": balance,
                "existing": 0,
                "created": 0,
            }
        if not self.dry_run:
            self._state.save()
        return summary

    def seed_wealth_products(self) -> dict[str, int]:
        """Create only the two native CNY Demo fixed-deposit products."""
        self.step_currency()
        result = self.step_fixed_deposit_products()
        if not self.dry_run:
            self._state.save()
        return result

    def step_currency(self) -> None:
        configured = self.client.get("/currencies")
        codes = [row["code"] for row in configured.get("selectedCurrencyOptions", [])]
        if CURRENCY in codes:
            log.info("币种 %s 已启用", CURRENCY)
            return
        log.info("启用币种 %s", CURRENCY)
        if not self.dry_run:
            self.client.put("/currencies", json={"currencies": [*codes, CURRENCY]})

    def step_product(self) -> int:
        existing = self.client.get("/savingsproducts")
        for product in existing or []:
            if product.get("name") == PRODUCT_NAME:
                log.info("储蓄产品已存在 id=%s", product["id"])
                self._state.data["product_id"] = product["id"]
                return int(product["id"])

        payload = {
            "name": PRODUCT_NAME,
            "shortName": PRODUCT_SHORT_NAME,
            "description": "Bank Agent 演示用储蓄账户产品",
            "currencyCode": CURRENCY,
            "digitsAfterDecimal": 2,
            "interestCompoundingPeriodType": 1,  # daily
            "interestPostingPeriodType": 4,  # monthly
            "interestCalculationType": 1,  # daily balance
            "interestCalculationDaysInYearType": 365,
            "nominalAnnualInterestRate": 0.0,
            "minRequiredOpeningBalance": 0.0,
            "lockinPeriodFrequency": 0,
            "lockinPeriodFrequencyType": 0,
            "withdrawalFeeForTransfers": False,
            "accountingRule": 1,  # NONE - keeps us away from GL setup entirely
            # This endpoint wants locale but rejects dateFormat, hence no add_common.
            "locale": LOCALE,
        }
        log.info("创建储蓄产品 %s", PRODUCT_NAME)
        if self.dry_run:
            return -1
        created = self.client.post("/savingsproducts", add_common=False, json=payload)
        product_id = created["resourceId"]
        self._state.data["product_id"] = product_id
        return int(product_id)

    def step_fixed_deposit_products(self) -> dict[str, int]:
        existing = self.client.get("/fixeddepositproducts") or []
        result: dict[str, int] = {}
        for spec in FIXED_DEPOSIT_PRODUCTS:
            matches = [row for row in existing if row.get("name") == spec["name"]]
            if len(matches) > 1:
                raise RuntimeError(f"Fineract 中存在重复定存产品 name={spec['name']}")
            if matches:
                product_id = int(matches[0]["id"])
                log.info("定存产品已存在 %s id=%s", spec["name"], product_id)
            elif self.dry_run:
                product_id = -1
                log.info("将创建定存产品 %s", spec["name"])
            else:
                term = int(spec["term_months"])
                payload = {
                    "name": spec["name"],
                    "shortName": spec["short_name"],
                    "description": spec["description"],
                    "currencyCode": CURRENCY,
                    "digitsAfterDecimal": 2,
                    "interestCompoundingPeriodType": 1,
                    "interestPostingPeriodType": 4,
                    "interestCalculationType": 1,
                    "interestCalculationDaysInYearType": 365,
                    "accountingRule": 1,
                    "locale": LOCALE,
                    "lockinPeriodFrequency": 0,
                    "lockinPeriodFrequencyType": 0,
                    "preClosurePenalApplicable": False,
                    "minDepositTerm": term,
                    "minDepositTermTypeId": 2,
                    "maxDepositTerm": term,
                    "maxDepositTermTypeId": 2,
                    "depositAmount": "1000",
                    "minDepositAmount": "100",
                    "maxDepositAmount": "100000",
                    "withHoldTax": False,
                    "charts": [{
                        "fromDate": self.d(self.as_of),
                        "dateFormat": DATE_FORMAT,
                        "locale": LOCALE,
                        "isPrimaryGroupingByAmount": False,
                        "chartSlabs": [{
                            "description": f"Demo {term} month rate",
                            "periodType": 2,
                            # This Fineract version requires the first slab to
                            # start at 1 even when the product itself fixes the
                            # only allowed deposit term at 3 or 6 months.
                            "fromPeriod": 1,
                            "toPeriod": term,
                            "annualInterestRate": spec["annual_interest_rate"],
                            "locale": LOCALE,
                        }],
                    }],
                }
                created = self.client.post(
                    "/fixeddepositproducts", add_common=False, json=payload
                )
                product_id = int(created["resourceId"])
                existing.append({"id": product_id, "name": spec["name"]})
                log.info("已创建定存产品 %s id=%s", spec["name"], product_id)
            result[spec["name"]] = product_id
        self._state.data["fixed_product_ids"] = result
        return result

    def ensure_client_active(self, client_id: int) -> None:
        """Clients created while experimenting stay PENDING; accounts need ACTIVE."""
        details = self.client.get(f"/clients/{client_id}")
        if (details or {}).get("active"):
            return
        submitted = parse_fineract_date((details.get("timeline") or {}).get("submittedOnDate"))
        # Fineract refuses an activation date earlier than the submission date.
        activation = max([d for d in (submitted, self.opened) if d])
        log.info("激活客户 id=%s（激活日 %s）", client_id, activation)
        self.client.post(
            f"/clients/{client_id}",
            params={"command": "activate"},
            json={"activationDate": self.d(activation)},
        )

    def ensure_client(self, spec: ClientSpec) -> int:
        external = external_id(spec.key)
        existing = self.find_client(external)
        if existing:
            log.info("客户已存在 %s id=%s", spec.key, existing)
            if not self.dry_run:
                self.ensure_client_active(existing)
                details = self.client.get(f"/clients/{existing}") or {}
                # Never pretend the account is older than the client itself -
                # Fineract rejects that with "submitted date cannot be after the
                # activation date".
                submitted = parse_fineract_date(
                    (details.get("timeline") or {}).get("submittedOnDate")
                )
                if submitted and submitted > self.opened:
                    self.open_dates[spec.key] = submitted
                else:
                    self.open_dates[spec.key] = self.opened
            return existing

        target = self.opened
        payload = {
            "officeId": 1,
            "firstname": spec.firstname,
            "lastname": spec.lastname,
            "externalId": external,
            "mobileNo": spec.mobile,
            "active": True,
            "legalFormId": 1,  # Person
            "submittedOnDate": self.d(target),
            "activationDate": self.d(target),
        }
        log.info("创建客户 %s", spec.key)
        if self.dry_run:
            return -1
        created = self.client.post("/clients", json=payload)
        client_id = created["clientId"]
        self._state.data["clients"][external] = client_id
        return int(client_id)

    def ensure_account(
        self,
        client_id: int,
        product_id: int,
        key: str,
        *,
        account_external_id: str | None = None,
    ) -> int:
        account_no = account_external_id or external_id(f"{key}-SAV")
        existing = self.find_savings_account(client_id, account_no)
        if existing:
            if not self.dry_run:
                details = self.client.get(f"/savingsaccounts/{existing}") or {}
                if not (details.get("status") or {}).get("active"):
                    raise RuntimeError(
                        f"账户 {account_no} 已存在但不是 ACTIVE，拒绝复用"
                    )
            log.info("账户已存在 %s id=%s", account_no, existing)
            return existing

        # Opening an account is three calls in Fineract: create -> approve ->
        # activate. All three take their own date, which is how we get an
        # *activated* account whose history legally starts months ago.
        # Fineract rejects any date earlier than the client's own submitted
        # date, so each account opens on the client's effective start date.
        opened = self.open_dates.get(key, self.opened)
        payload = {
            "clientId": client_id,
            "productId": product_id,
            "externalId": account_no,
            "submittedOnDate": self.d(opened),
            "nominalAnnualInterestRate": 0.0,
        }
        log.info("开户并激活 %s", account_no)
        if self.dry_run:
            return -1
        created = self.client.post("/savingsaccounts", json=payload)
        account_id = created["savingsId"]

        for command, field in (("approve", "approvedOnDate"), ("activate", "activatedOnDate")):
            self.client.post(
                f"/savingsaccounts/{account_id}",
                add_common=False,
                params={"command": command},
                json={field: self.d(opened), "dateFormat": DATE_FORMAT, "locale": LOCALE},
            )

        self._state.data["accounts"][account_no] = account_id
        return int(account_id)

    def history_window(self, account_id: int, spec: ClientSpec) -> tuple[date, int]:
        oldest_allowed = self.as_of - timedelta(days=HISTORY_DAYS - 1)
        if account_id < 0:
            activated = self.open_dates.get(spec.key, self.opened)
        else:
            details = self.client.get(f"/savingsaccounts/{account_id}") or {}
            timeline = details.get("timeline") or {}
            activated = (
                parse_fineract_date(timeline.get("activatedOnDate"))
                or self.open_dates.get(spec.key)
                or self.opened
            )
        if activated > self.as_of:
            raise RuntimeError(f"账户 {spec.key} 激活日晚于历史截止日")
        start = max(activated, oldest_allowed)
        return start, max(1, min(HISTORY_DAYS, (self.as_of - start).days + 1))

    def step_history(
        self,
        account_id: int,
        spec: ClientSpec,
        *,
        seed: int,
        include_salary: bool = True,
        planned_history: PlannedHistory | None = None,
        skip_if_group_history_exists: bool = False,
    ) -> dict[str, int]:
        """Post the transaction history, skipping anything already present."""
        start, days = self.history_window(account_id, spec)
        if account_id < 0:
            if skip_if_group_history_exists:
                stats = {"existing": 0, "planned": 0, "created": 0, "skipped_insufficient_funds": 0}
                self.history_results[str(spec.key)] = stats
                return stats
            plan = planned_history or build_random_history(spec=spec, start=start, days=days, seed=seed,
                opening_balance=Decimal(str(spec.opening_balance)), include_salary=include_salary)
            planned = len(plan.rows)
            stats = {"existing": 0, "planned": planned, "created": planned,
                "skipped_insufficient_funds": plan.skipped_withdrawals}
            self.history_results[str(spec.key)] = stats
            return stats
        posted = len(self.active_transactions(account_id))
        if posted:
            log.info("账户 %s 已有 %s 条流水，跳过历史写入", spec.key, posted)
            stats = {"existing": posted, "planned": 0, "created": 0,
                "skipped_insufficient_funds": 0}
            self.history_results[str(spec.key)] = stats
            return stats
        if skip_if_group_history_exists:
            log.info("用户 %s 其他账户已有历史，本账户跳过以避免混合版本", spec.key)
            stats = {"existing": 0, "planned": 0, "created": 0, "skipped_insufficient_funds": 0}
            self.history_results[str(spec.key)] = stats
            return stats

        plan = planned_history or build_random_history(spec=spec, start=start, days=days, seed=seed,
            opening_balance=Decimal(str(spec.opening_balance)), include_salary=include_salary)
        history = list(plan.rows)
        log.info("写入历史流水 %s 条（起始 %s）→ %s", len(history), start, spec.key)

        if self.dry_run:
            stats = {"existing": 0, "planned": len(history), "created": len(history),
                "skipped_insufficient_funds": plan.skipped_withdrawals}
            self.history_results[str(spec.key)] = stats
            return stats

        created = 0
        failures: list[str] = []
        for day, kind, amount, payment_type, note in history:
            payload = {
                "transactionDate": self.d(day),
                "transactionAmount": f"{amount:.2f}",
                "paymentTypeId": payment_type,
                "note": note,
            }
            try:
                # Deposit/withdrawal is a *query* command in Fineract, not a body
                # field - posting transactionType in the payload yields
                # "query parameter command has an unsupported value of: null".
                self.client.post(
                    f"/savingsaccounts/{account_id}/transactions",
                    params={"command": kind},
                    json=payload,
                )
                created += 1
            except FineractError as exc:  # keep going: one bad row must not abort
                if not failures:
                    log.warning("首条失败：%s %s %s → %s", spec.key, day, amount, exc.body)
                failures.append(f"{day} {kind} {amount}")
        if failures:
            log.warning("%s 有 %s 条流水未写入", spec.key, len(failures))
        stats = {"existing": posted, "planned": len(history), "created": created,
            "skipped_insufficient_funds": plan.skipped_withdrawals}
        self.history_results[str(spec.key)] = stats
        return stats

    # -- orchestration ------------------------------------------------------ #

    def run(self) -> dict[str, Any]:
        self.step_currency()
        product_id = self.step_product()
        self.step_fixed_deposit_products()

        summary: dict[str, Any] = {}
        for spec in CLIENTS:
            client_id = self.ensure_client(spec)
            account_id = self.ensure_account(client_id, product_id, spec.key)
            analysis_account_id = None
            analysis_spec = None
            analysis_stats = None
            if spec.key == "ALICE":
                analysis_spec = dataclasses.replace(
                    spec, key="ALICE-ANALYSIS", opening_balance=5_000.00, monthly_salary=0.0
                )
                self.open_dates[analysis_spec.key] = self.open_dates.get(spec.key, self.opened)
                analysis_account_id = self.ensure_account(
                    client_id, product_id, spec.key,
                    account_external_id=ANALYSIS_ACCOUNT_EXTERNAL_ID,
                )
                group_has_history = any(
                    current_id > 0 and bool(self.active_transactions(current_id))
                    for current_id in (account_id, analysis_account_id)
                )
                primary_start, primary_days = self.history_window(account_id, spec)
                analysis_start, analysis_days = self.history_window(analysis_account_id, analysis_spec)
                common_start = max(primary_start, analysis_start)
                common_days = max(1, min(primary_days, analysis_days,
                    (self.as_of - common_start).days + 1, HISTORY_DAYS))
                unallocated = build_random_history(
                    spec=spec, start=common_start, days=common_days,
                    seed=self.history_seed,
                    opening_balance=Decimal(str(spec.opening_balance)),
                    include_salary=True,
                    apply_balance_guard=False,
                )
                primary_plan, analysis_plan = split_history_for_analysis_account(
                    unallocated, start=common_start, seed=self.history_seed,
                    analysis_opening_balance=Decimal(str(analysis_spec.opening_balance)),
                )
                stats = self.step_history(
                    account_id, spec, seed=self.history_seed,
                    planned_history=primary_plan,
                    skip_if_group_history_exists=group_has_history,
                )
                analysis_stats = self.step_history(
                    analysis_account_id, analysis_spec, seed=self.history_seed,
                    include_salary=False, planned_history=analysis_plan,
                    skip_if_group_history_exists=group_has_history,
                )
            else:
                stats = self.step_history(account_id, spec, seed=self.history_seed)
            balance = None
            if not self.dry_run and account_id > 0:
                details = self.client.get(f"/savingsaccounts/{account_id}")
                balance = (details or {}).get("summary", {}).get("availableBalance")
            summary[spec.key] = {
                "client_id": client_id,
                "account_id": account_id,
                "balance": balance,
                **stats,
            }
            if analysis_spec is not None:
                analysis_balance = None
                if not self.dry_run and analysis_account_id and analysis_account_id > 0:
                    analysis_details = self.client.get(f"/savingsaccounts/{analysis_account_id}")
                    analysis_balance = (analysis_details or {}).get("summary", {}).get("availableBalance")
                summary["ALICE-ANALYSIS"] = {
                    "client_id": client_id, "account_id": analysis_account_id,
                    "balance": analysis_balance, **analysis_stats,
                }
            for card_index, (card_external_id, _) in enumerate(
                DEMO_CARD_ACCOUNTS[spec.key], 1
            ):
                card_account_id = self.ensure_account(
                    client_id,
                    product_id,
                    spec.key,
                    account_external_id=card_external_id,
                )
                card_balance = None
                if not self.dry_run and card_account_id > 0:
                    card_details = self.client.get(
                        f"/savingsaccounts/{card_account_id}"
                    )
                    card_balance = (card_details or {}).get("summary", {}).get(
                        "availableBalance"
                    )
                summary[f"{spec.key}-CARD-{card_index}"] = {
                    "client_id": client_id,
                    "account_id": card_account_id,
                    "balance": card_balance,
                    "existing": 0,
                    "created": 0,
                }

        # The merchant is deliberately isolated from personal identities and
        # receives no synthetic history. Successful Demo card purchases are
        # the only source of money and transactions on this account.
        merchant_client_id = self.ensure_client(DEMO_MERCHANT)
        merchant_account_id = self.ensure_account(
            merchant_client_id, product_id, DEMO_MERCHANT.key
        )
        merchant_balance = None
        if not self.dry_run and merchant_account_id > 0:
            details = self.client.get(f"/savingsaccounts/{merchant_account_id}")
            merchant_balance = (details or {}).get("summary", {}).get(
                "availableBalance"
            )
        summary[DEMO_MERCHANT.key] = {
            "client_id": merchant_client_id,
            "account_id": merchant_account_id,
            "balance": merchant_balance,
            "existing": 0,
            "created": 0,
        }
        for merchant_spec in DEMO_ORCHESTRATION_MERCHANTS:
            client_id = self.ensure_client(merchant_spec)
            account_id = self.ensure_account(client_id, product_id, merchant_spec.key)
            balance = None
            if not self.dry_run and account_id > 0:
                details = self.client.get(f"/savingsaccounts/{account_id}")
                balance = (details or {}).get("summary", {}).get("availableBalance")
            summary[merchant_spec.key] = {
                "client_id": client_id,
                "account_id": account_id,
                "balance": balance,
                "existing": 0,
                "created": 0,
            }

        if not self.dry_run:
            self._state.save()
        write_manifest(self.history_seed, self.as_of, summary)
        return summary


def first_open_date(as_of: date | None = None) -> date:
    cutoff = as_of or (datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1))
    return cutoff - timedelta(days=ACCOUNT_OPEN_OFFSET)


def write_manifest(seed: int, as_of: date, summary: dict[str, Any]) -> None:
    """Write a local-only generation receipt; never contains credentials or PANs."""
    category_by_merchant = merchant_category_map()
    accounts = {}
    for key, row in summary.items():
        if key == DEMO_MERCHANT.key or key in {
            spec.key for spec in DEMO_ORCHESTRATION_MERCHANTS
        } or "CARD" in key:
            continue
        accounts[key] = {
            "account_id": row.get("account_id"),
            "role": "analysis" if key == "ALICE-ANALYSIS" else "primary",
            "transactions": {k: row.get(k, 0) for k in (
                "existing", "planned", "created", "skipped_insufficient_funds"
            )},
        }
    manifest = {
        "generator": GENERATOR_VERSION,
        "seed": seed,
        "as_of": as_of.isoformat(),
        "history_days": HISTORY_DAYS,
        "accounts": accounts,
        "categories": {
            category: list(merchants) for category, merchants in CATEGORY_MERCHANTS.items()
        },
        "merchant_category": category_by_merchant,
        "subscriptions": list(MONTHLY_SUBSCRIPTION_MERCHANTS),
    }
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = MANIFEST_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(MANIFEST_FILE)


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #


def load_env_file() -> None:
    """Populate os.environ from the project root .env if python-dotenv is absent."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
    for key in ("NO_PROXY", "no_proxy"):
        values = [item.strip() for item in os.environ.get(key, "").split(",") if item.strip()]
        for local in ("localhost", "127.0.0.1", "::1"):
            if local not in values:
                values.append(local)
        os.environ[key] = ",".join(values)


def main(argv: Iterable[str] | None = None) -> int:
    load_env_file()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只列出将执行的操作")
    parser.add_argument("--history-seed", type=int, help="指定历史随机种子以便复现")
    parser.add_argument("--as-of", type=date.fromisoformat, help="历史结束日上限 YYYY-MM-DD（默认上海时区昨天）")
    parser.add_argument("--verbose", action="store_true", help="打印每个 HTTP 请求")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--orchestration-merchants-only",
        action="store_true",
        help="仅幂等创建生日任务花店/蛋糕店及零余额账户，不生成个人流水",
    )
    scope.add_argument(
        "--wealth-products-only",
        action="store_true",
        help="仅幂等创建两个原生 CNY Demo 定存产品，不生成账户或流水",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(message)s",
    )

    client = FineractClient(FineractConfig())
    seeder = Seeder(client, State(STATE_FILE), dry_run=args.dry_run)
    seeder.history_seed = args.history_seed if args.history_seed is not None else secrets.randbits(63)
    seeder.as_of = args.as_of or (datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1))
    latest_allowed = datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1)
    if seeder.as_of > latest_allowed:
        parser.error("--as-of 不能晚于上海时区昨天")
    seeder.opened = first_open_date(seeder.as_of)

    print(f"Fineract: {FineractConfig().base_url}  tenant={FineractConfig().tenant}")
    print(f"历史种子: {seeder.history_seed}；截止日: {seeder.as_of}；生成器: {GENERATOR_VERSION}")
    print(f"开户日期: {seeder.d(seeder.opened)}（最长 {HISTORY_DAYS} 天历史）\n")

    try:
        if args.wealth_products_only:
            products = seeder.seed_wealth_products()
            print("\n=== Demo 定存产品 ===")
            for name, product_id in products.items():
                print(f"{name:<32} id={product_id}")
            print(f"\n状态文件：{STATE_FILE}")
            return 0
        summary = seeder.seed_orchestration_merchants() if args.orchestration_merchants_only else seeder.run()
    except httpx.ConnectError as exc:
        print(f"\n连不上 Fineract：{exc}", file=sys.stderr)
        print("请确认 Docker Desktop 已启动且基础设施已起来：", file=sys.stderr)
        print("  .\\infrastructure\\windows\\start.ps1", file=sys.stderr)
        return 1
    except FineractError as exc:
        print(f"\nFineract 返回错误：{exc}", file=sys.stderr)
        return 1
    finally:
        client.close()

    print("\n=== Seed 结果 ===")
    for key, row in summary.items():
        print(
            f"{key:<14} client={row['client_id']:<4} account={row['account_id']:<4} "
            f"balance={row['balance']}  计划={row.get('planned', 0)} "
            f"实际新建={row['created']} 跳过(余额不足)={row.get('skipped_insufficient_funds', 0)}"
        )
    print(f"\n状态文件：{STATE_FILE}")
    if not args.orchestration_merchants_only:
        print(f"历史生成清单：{MANIFEST_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
