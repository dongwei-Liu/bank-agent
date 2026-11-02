"""Live contract probe using isolated clients and official Fineract APIs only."""

import json, sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/backend"))
from core.config import get_settings
from core.security import now, SHANGHAI, password_hasher, token
from clients.fineract import FineractClient, FineractError
from core.database import session_factory
from models import User
from sqlalchemy import select
from fastapi.testclient import TestClient
from main import app

COMMON = {"locale": "en", "dateFormat": "yyyy-MM-dd"}
SETTINGS = get_settings()
STATE_PATH = ROOT / ".runtime/banking-probe-state.json"


def run():
    client = FineractClient(SETTINGS)
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}

    def remember(key, value):
        state[key] = value
        STATE_PATH.parent.mkdir(exist_ok=True)
        STATE_PATH.write_text(json.dumps(state))
        return value

    today = now().astimezone(SHANGHAI).date()
    opened = today - timedelta(days=90)
    savings_product = client.request("GET", "savingsproducts")[0]["id"]
    actors = []
    payment = client.request("GET", "paymenttypes")[0]["id"]
    for index in range(2):
        prefix = f"probe{index}"
        cid = state.get(prefix + "_client")
        if not cid:
            cid = remember(
                prefix + "_client",
                client.request(
                    "POST",
                    "clients",
                    payload={
                        **COMMON,
                        "officeId": 1,
                        "firstname": "Contract",
                        "lastname": f"Probe{index}",
                        "externalId": f"BANK-PROBE-{token()[:12]}",
                        "active": True,
                        "legalFormId": 1,
                        "submittedOnDate": str(opened),
                        "activationDate": str(opened),
                    },
                )["clientId"],
            )
        aid = state.get(prefix + "_account")
        if not aid:
            aid = remember(
                prefix + "_account",
                client.request(
                    "POST",
                    "savingsaccounts",
                    payload={
                        **COMMON,
                        "clientId": cid,
                        "productId": savings_product,
                        "submittedOnDate": str(opened),
                    },
                )["resourceId"],
            )
        raw = client.get_savings_account(aid)
        if raw["status"].get("submittedAndPendingApproval"):
            client.request(
                "POST",
                f"savingsaccounts/{aid}",
                params={"command": "approve"},
                payload={**COMMON, "approvedOnDate": str(opened)},
            )
        raw = client.get_savings_account(aid)
        if raw["status"].get("approved"):
            client.request(
                "POST",
                f"savingsaccounts/{aid}",
                params={"command": "activate"},
                payload={**COMMON, "activatedOnDate": str(opened)},
            )
        if not state.get(prefix + "_funded"):
            client.request(
                "POST",
                f"savingsaccounts/{aid}/transactions",
                params={"command": "deposit"},
                payload={
                    **COMMON,
                    "transactionDate": str(opened),
                    "transactionAmount": "10000",
                    "paymentTypeId": payment,
                },
                key=f"probe:fund:{aid}:payment-v2",
            )
            remember(prefix + "_funded", True)
        with session_factory()() as db:
            user = db.scalar(select(User).where(User.client_id == cid))
            if not user:
                user = User(
                    username=f"contract_probe_{cid}",
                    password_hash=password_hasher.hash(SETTINGS.demo_password),
                    client_id=cid,
                    tenant=SETTINGS.fineract_tenant,
                )
                db.add(user)
                db.commit()
            actors.append((user.username, aid))
    pid = state.get("product_id")
    if not pid:
        pid = remember(
            "product_id",
            client.request(
                "POST",
                "fixeddepositproducts",
                payload={
                    "name": f"Bank Contract Probe {token()[:6]}",
                    "shortName": "BCP1",
                    "description": "Isolated contract test product",
                    "currencyCode": "CNY",
                    "digitsAfterDecimal": 2,
                    "interestCompoundingPeriodType": 1,
                    "interestPostingPeriodType": 4,
                    "interestCalculationType": 1,
                    "interestCalculationDaysInYearType": 365,
                    "accountingRule": 1,
                    "locale": "en",
                    "lockinPeriodFrequency": 0,
                    "lockinPeriodFrequencyType": 0,
                    "preClosurePenalApplicable": False,
                    "minDepositTerm": 1,
                    "minDepositTermTypeId": 0,
                    "maxDepositTerm": 36,
                    "maxDepositTermTypeId": 2,
                    "depositAmount": "100",
                    "minDepositAmount": "1",
                    "maxDepositAmount": "100000",
                    "withHoldTax": False,
                    "charts": [
                        {
                            "fromDate": str(opened),
                            "dateFormat": "yyyy-MM-dd",
                            "locale": "en",
                            "isPrimaryGroupingByAmount": False,
                            "chartSlabs": [
                                {
                                    "description": "Contract slab",
                                    "periodType": 0,
                                    "fromPeriod": 1,
                                    "toPeriod": 2000,
                                    "annualInterestRate": "2",
                                    "locale": "en",
                                }
                            ],
                        }
                    ],
                },
                key="probe:product:" + token()[:20],
            )["resourceId"],
        )
    evidence = {"at": now().isoformat(), "isolated": True, "checks": {}}
    with TestClient(app) as http:

        def call(method, path, body=None, headers=None):
            r = http.request(method, path, json=body, headers=headers)
            if r.status_code >= 400:
                raise RuntimeError(f"{method} {path}: {r.status_code} {r.text}")
            return r.json()

        login = call(
            "POST",
            "/api/auth/login",
            {"username": actors[0][0], "password": SETTINGS.demo_password},
        )
        headers = {"Authorization": "Bearer " + login["access_token"]}

        def invoke(method, path, body=None, key=None):
            return call(
                method,
                path,
                body,
                {**headers, **({"Idempotency-Key": key} if key else {})},
            )

        def approve(a):
            a = invoke(
                "POST",
                f"/api/actions/{a['id']}/confirm",
                {"request_hash": a["request_hash"]},
            )
            if a["status"] == "WAITING_VERIFICATION":
                invoke("POST", f"/api/actions/{a['id']}/otp")
                code = invoke("GET", f"/api/dev/otp-inbox/{a['id']}")["code"]
                a = invoke("POST", f"/api/actions/{a['id']}/verify", {"code": code})
            assert a["status"] == "SUCCEEDED", a
            return a

        def balances():
            return [
                Decimal(str(client.get_savings_account(a)["summary"]["accountBalance"]))
                for _, a in actors
            ]

        recipient = invoke(
            "POST",
            "/api/recipients",
            {"name": "Isolated Receiver", "account_id": actors[1][1]},
        )
        before = balances()
        a = invoke(
            "POST",
            "/api/transfers",
            {
                "from_account_id": actors[0][1],
                "recipient_id": recipient["id"],
                "amount": "1.23",
            },
            "probe:" + token()[:20],
        )
        a = approve(a)
        after = balances()
        assert before[0] - after[0] == Decimal("1.23") and after[1] - before[
            1
        ] == Decimal("1.23")
        evidence["checks"]["transfer"] = {
            "status": "passed",
            "debit": "1.23",
            "credit": "1.23",
            "response_fields": sorted(a["result"]),
        }
        raw = {
            **COMMON,
            "fromOfficeId": 1,
            "fromClientId": client.get_savings_account(actors[0][1])["clientId"],
            "fromAccountType": 2,
            "fromAccountId": actors[0][1],
            "toOfficeId": 1,
            "toClientId": client.get_savings_account(actors[1][1])["clientId"],
            "toAccountType": 2,
            "toAccountId": actors[1][1],
            "transferDate": str(today),
            "transferAmount": "0.01",
            "transferDescription": "isolated idempotency probe",
        }
        key = "probe:idem:" + token()[:20]
        first = client.create_transfer(raw, key)
        try:
            second = client.create_transfer(raw, key)
        except FineractError as exc:
            second = {"status": exc.status}
        assert after[0] - balances()[0] == Decimal(".01"), (first, second)
        evidence["checks"]["native_idempotency"] = {
            "status": "passed",
            "repeat_response": second,
        }
        for i in range(3):
            client.request(
                "POST",
                f"savingsaccounts/{actors[1][1]}/transactions",
                params={"command": "deposit"},
                payload={
                    **COMMON,
                    "transactionDate": str(today),
                    "transactionAmount": "0.01",
                    "paymentTypeId": payment,
                },
                key="probe:page:" + token()[:20],
            )
        p0 = client.search_transactions(actors[1][1], 0, 2)
        p1 = client.search_transactions(actors[1][1], 1, 2)
        assert not {r["id"] for r in p0["items"]} & {r["id"] for r in p1["items"]}
        evidence["checks"]["transaction_page"] = {
            "status": "passed",
            "offset_semantics": "page",
            "response_fields": ["total", "content", "pageable"],
        }
        admin = call(
            "POST",
            "/api/auth/login",
            {"username": "admin", "password": SETTINGS.admin_password},
        )
        call(
            "PUT",
            f"/api/investments/products/{pid}/metadata",
            {"risk_level": 1, "enabled": True, "allows_premature": True},
            {"Authorization": "Bearer " + admin["access_token"]},
        )
        invoke("POST", "/api/risk-assessments", {"answers": [5] * 5})
        inv_before = balances()[0]
        a = invoke(
            "POST",
            "/api/investments/subscriptions",
            {
                "product_id": pid,
                "from_account_id": actors[0][1],
                "amount": "100",
                "term_months": 1,
            },
            "probe:sub:" + token()[:20],
        )
        a = approve(a)
        hid = a["steps"]["holding_id"]
        inv_after = balances()[0]
        assert inv_before - inv_after == 100
        evidence["checks"]["fixed_activation"] = {
            "status": "passed",
            "savings_debit": "100",
            "principal": str(client.fixed_account(hid)["depositAmount"]),
        }
        # Repeating the exact activation command cannot deduct a second principal.
        try:
            client.fixed_command(
                hid,
                "activate",
                {**COMMON, "activatedOnDate": str(today)},
                f"bank:{a['id']}:activate",
            )
        except FineractError:
            pass
        assert balances()[0] == inv_after
        evidence["checks"]["activation_idempotency"] = {"status": "passed"}
        q = invoke(
            "GET",
            f"/api/investments/redemption-quotes?holding_id={hid}&to_account_id={actors[0][1]}",
        )
        r = invoke(
            "POST",
            "/api/investments/redemptions",
            {
                "holding_id": hid,
                "to_account_id": actors[0][1],
                "quote_hash": q["quote_hash"],
            },
            "probe:redeem:" + token()[:20],
        )
        r = approve(r)
        credit = balances()[0] - inv_after
        assert credit >= 100
        evidence["checks"]["premature_close"] = {
            "status": "passed",
            "savings_credit": str(credit),
            "holding_status": r["result"]["status"],
        }
    # The native maturity job is tenant-wide. Refuse to run if any deposit belongs
    # to clients outside this isolated probe (no business-account side effects).
    deposits = client.request(
        "GET", "fixeddepositaccounts", params={"limit": 1000, "offset": 0}
    )
    rows = deposits.get("pageItems", []) if isinstance(deposits, dict) else deposits
    assert all(
        r.get("clientId") in {state["probe0_client"], state["probe1_client"]}
        for r in rows
    ), "Non-probe fixed deposits exist; maturity job refused"
    assert not isinstance(deposits, dict) or deposits.get(
        "totalFilteredRecords", len(rows)
    ) <= len(rows)
    recurring = client.request(
        "GET", "recurringdepositaccounts", params={"limit": 1000, "offset": 0}
    )
    recurring_rows = (
        recurring.get("pageItems", []) if isinstance(recurring, dict) else recurring
    )
    assert all(
        r.get("clientId") in {state["probe0_client"], state["probe1_client"]}
        for r in recurring_rows
    ), "Non-probe recurring deposits exist; maturity job refused"
    assert not isinstance(recurring, dict) or recurring.get(
        "totalFilteredRecords", len(recurring_rows)
    ) <= len(recurring_rows)
    history = (today - timedelta(days=2)).isoformat()
    fd = client.create_fixed(
        {
            **COMMON,
            "clientId": state["probe0_client"],
            "productId": pid,
            "submittedOnDate": history,
            "depositAmount": "1000",
            "depositPeriod": 1,
            "depositPeriodFrequencyId": 0,
            "linkAccountId": actors[0][1],
            "maturityInstructionId": 100,
            "transferInterestToSavings": False,
        },
        "probe:historical:" + token()[:20],
    )["resourceId"]
    client.fixed_command(
        fd,
        "approve",
        {**COMMON, "approvedOnDate": history},
        "probe:hist-approve:" + token()[:20],
    )
    client.fixed_command(
        fd,
        "activate",
        {**COMMON, "activatedOnDate": history},
        "probe:hist-activate:" + token()[:20],
    )
    jobs = client.request("GET", "jobs")
    job = next(
        j
        for j in jobs
        if "update" in j["displayName"].lower()
        and "maturity" in j["displayName"].lower()
    )
    # Job submission returns 202 with an empty body in this image.
    response = client._client.post(
        f"jobs/{job['jobId']}", params={"command": "executeJob"}
    )
    assert response.is_success, response.text
    import time

    for attempt in range(50):
        if client.fixed_account(fd)["status"].get("matured"):
            break
        time.sleep(0.2)
    assert client.fixed_account(fd)["status"].get("matured"), (
        "Native maturity job did not complete"
    )
    # Verify mature close through the same public quote/Action/OTP chain.
    with TestClient(app) as http:
        login = http.post(
            "/api/auth/login",
            json={"username": actors[0][0], "password": SETTINGS.demo_password},
        ).json()
        headers = {"Authorization": "Bearer " + login["access_token"]}

        def api(method, path, body=None, key=None):
            r = http.request(
                method,
                path,
                json=body,
                headers={**headers, **({"Idempotency-Key": key} if key else {})},
            )
            assert r.status_code < 400, r.text
            return r.json()

        q = api(
            "GET",
            f"/api/investments/redemption-quotes?holding_id={fd}&to_account_id={actors[0][1]}",
        )
        assert q["command"] == "close"
        before = Decimal(
            str(client.get_savings_account(actors[0][1])["summary"]["accountBalance"])
        )
        a = api(
            "POST",
            "/api/investments/redemptions",
            {
                "holding_id": fd,
                "to_account_id": actors[0][1],
                "quote_hash": q["quote_hash"],
            },
            "probe:mature:" + token()[:20],
        )
        a = api(
            "POST",
            f"/api/actions/{a['id']}/confirm",
            {"request_hash": a["request_hash"]},
        )
        api("POST", f"/api/actions/{a['id']}/otp")
        code = api("GET", f"/api/dev/otp-inbox/{a['id']}")["code"]
        a = api("POST", f"/api/actions/{a['id']}/verify", {"code": code})
        assert a["status"] == "SUCCEEDED", a
        credit = (
            Decimal(
                str(
                    client.get_savings_account(actors[0][1])["summary"][
                        "accountBalance"
                    ]
                )
            )
            - before
        )
        assert credit > 1000, credit
        evidence["checks"]["mature_close"] = {
            "status": "passed",
            "savings_credit": str(credit),
            "principal": "1000",
            "interest": str(credit - 1000),
        }
        stats = api(
            "GET",
            f"/api/billing/statistics?account_id={actors[0][1]}&from_date={opened}&to_date={today}",
        )
        assert (
            "expense" not in stats["totals"]
            and Decimal(stats["totals"]["interest"]) > 0
        )
        evidence["bill_readback"] = {
            "totals": stats["totals"],
            "transaction_count": stats["transaction_count"],
            "snapshot_atomic": stats["snapshot_atomic"],
        }
    client.close()
    output = ROOT / "docs/testing/banking-live-contracts.json"
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + "\n"
    )
    print(json.dumps(evidence, ensure_ascii=False, default=str))


if __name__ == "__main__":
    try:
        run()
    except FineractError as exc:
        print(
            json.dumps(
                {"upstream_status": exc.status, "body": exc.body},
                ensure_ascii=False,
                default=str,
            )
        )
        raise
