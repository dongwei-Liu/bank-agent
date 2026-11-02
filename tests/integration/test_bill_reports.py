import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

from sqlalchemy import select

from models import Audit, BillReport, BillReportJob, User
from services.bill_report_service import BillReportService


def transaction(id_, day, amount, kind, *, merchant=None, reversed=False):
    type_key = {"expense": "withdrawal", "income": "deposit", "fee": "feeDeduction"}[kind]
    row = {"id": id_, "accountId": 1, "date": [int(v) for v in day.split("-")],
           "amount": amount, "currency": {"code": "CNY"},
           "entryType": "CREDIT" if kind == "income" else "DEBIT",
           "transactionType": {type_key: True}, "reversed": reversed}
    if merchant:
        row["note"] = f"[Merchant] {merchant}"
    return row


class SafeNarrativeModel:
    def invoke(self, messages):
        prompt = json.loads(messages[-1].content)
        return SimpleNamespace(content=json.dumps({"codes": prompt["allowed_conclusion_codes"]}))


def test_report_generation_is_idempotent_private_and_snapshotted(bank, monkeypatch):
    bank["core"].tx[1] = [
        transaction(1, "2025-09-03", "200.00", "income"),
        transaction(2, "2025-09-04", "40.00", "expense", merchant="Market"),
        transaction(3, "2025-09-05", "10.00", "fee"),
        transaction(4, "2025-09-06", "500.00", "expense", merchant="Reversed", reversed=True),
    ]
    monkeypatch.setattr("services.bill_report_service.ChatOpenAI", lambda **_: SafeNarrativeModel())
    headers = {**bank["headers"]["alice"], "Idempotency-Key": "report-request-0001"}
    request = {"account_id": None, "period": "2025-09"}
    created = bank["http"].post("/api/bill-report-generations", headers=headers, json=request)
    assert created.status_code == 202, created.text
    first = created.json()
    replay = bank["http"].post("/api/bill-report-generations", headers=headers, json=request)
    assert replay.status_code == 202 and replay.json()["report_id"] == first["report_id"]
    conflict = bank["http"].post("/api/bill-report-generations", headers=headers,
        json={"account_id": None, "period": "2025-10"})
    assert conflict.status_code == 409

    with bank["db"]() as db:
        assert BillReportService(db, bank["core"], bank["settings"]).run_one()
    detail = bank["http"].get(f"/api/bill-reports/{first['report_id']}", headers=bank["headers"]["alice"])
    assert detail.status_code == 200 and detail.headers["cache-control"] == "no-store"
    payload = detail.json()
    assert payload["status"] == "partial"  # absent baselines are visible, never interpreted as zero
    assert payload["account_scope"] == "all_accounts" and payload["scope_account_id"] is None
    assert payload["summary"]["totals"]["income"] == "200.00"
    assert payload["summary"]["totals"]["expense"] == "40.00"
    assert payload["summary"]["totals"]["fees"] == "10.00"
    assert payload["summary"]["totals"]["net_cash_flow"] == "150.00"
    assert payload["summary"]["transaction_count"] == 3
    assert payload["summary"]["categories"][0]["share"] == "1"
    assert "transactions" not in payload  # transaction snapshot is paginated separately

    page = bank["http"].get(f"/api/bill-reports/{first['report_id']}/transactions?page=1&page_size=2",
        headers=bank["headers"]["alice"])
    assert page.status_code == 200 and page.headers["cache-control"] == "no-store"
    assert page.json()["total"] == 4  # reversed record remains traceable in the source snapshot
    assert len(page.json()["items"]) == 2
    assert bank["http"].get(f"/api/bill-reports/{first['report_id']}", headers=bank["headers"]["bob"]).status_code == 404
    summaries = bank["http"].get("/api/bill-report-summaries", headers=bank["headers"]["alice"])
    assert summaries.status_code == 200 and summaries.headers["cache-control"] == "no-store"
    assert summaries.json()["total"] == 1
    assert summaries.json()["items"][0]["account_scope"] == "all_accounts"
    filtered_summaries = bank["http"].get(
        "/api/bill-report-summaries?period_from=2025-09&period_to=2025-09&status=partial&account_id=1",
        headers=bank["headers"]["alice"],
    )
    assert filtered_summaries.status_code == 200 and filtered_summaries.json()["total"] == 1
    filtered_transactions = bank["http"].get(
        f"/api/bill-reports/{first['report_id']}/transactions?direction=debit&category=%E6%9C%AA%E5%88%86%E7%B1%BB&from_date=2025-09-04&to_date=2025-09-05",
        headers=bank["headers"]["alice"],
    )
    assert filtered_transactions.status_code == 200 and filtered_transactions.json()["total"] == 2
    bank["core"].owners[1] = 999
    assert bank["http"].get(f"/api/bill-reports/{first['report_id']}", headers=bank["headers"]["alice"]).status_code == 404
    assert bank["http"].get(f"/api/bill-report-generations/{first['report_id']}/status", headers=bank["headers"]["alice"]).status_code == 404


def test_single_account_scope_is_preserved_in_report_summary(bank):
    response = bank["http"].post("/api/bill-report-generations", headers={**bank["headers"]["alice"], "Idempotency-Key": "single-scope-report-0001"},
        json={"account_id": 1, "period": "2025-09"})
    assert response.status_code == 202
    report_id = response.json()["report_id"]
    summaries = bank["http"].get("/api/bill-report-summaries", headers=bank["headers"]["alice"])
    item = next(item for item in summaries.json()["items"] if item["id"] == report_id)
    assert item["account_scope"] == "single_account" and item["scope_account_id"] == 1


def _queue_report(bank, account_id, period, key):
    response = bank["http"].post(
        "/api/bill-report-generations",
        headers={**bank["headers"]["alice"], "Idempotency-Key": key},
        json={"account_id": account_id, "period": period},
    )
    assert response.status_code == 202, response.text
    return response.json()["report_id"]


def test_view_or_generate_reuses_exact_scope_and_audits(bank):
    # Single-account and all-account reports remain distinct even when both
    # happen to cover the user's only currently eligible account.
    single_id = _queue_report(bank, 1, "2025-09", "view-single-report-0001")
    with bank["db"]() as db:
        user = db.get(User, bank["ids"][0])
        service = BillReportService(db, bank["core"], bank["settings"])
        opened = service.view_or_generate(user, None, "2025-09", trace_id="trace-view-all")
        assert opened["report_id"] != single_id
        assert opened == {
            "report_id": opened["report_id"], "period": "2025-09",
            "status": "queued", "generated": True, "error": None,
        }
        reused = service.view_or_generate(user, None, "2025-09", trace_id="trace-view-all-again")
        assert reused["report_id"] == opened["report_id"]
        assert reused["generated"] is False
        audit_row = db.scalar(select(Audit).where(
            Audit.event == "BILL_REPORT_OPENED", Audit.trace_id == "trace-view-all-again",
        ))
        assert audit_row is not None
        assert audit_row.resource_id == opened["report_id"]
        assert audit_row.data["generated"] is False


def test_view_or_generate_reuses_failed_report_without_queue_loop(bank):
    report_id = _queue_report(bank, None, "2025-09", "view-failed-report-0001")
    with bank["db"]() as db:
        report = db.get(BillReport, report_id)
        report.payload = {**report.payload, "status": "failed", "error": "受控失败原因"}
        job = db.scalar(select(BillReportJob).where(BillReportJob.report_id == report_id))
        job.status = "failed"
        job.error_code = "CONTROLLED_FAILURE"
        db.commit()

        user = db.get(User, bank["ids"][0])
        service = BillReportService(db, bank["core"], bank["settings"])
        opened = service.view_or_generate(user, None, "2025-09", trace_id="trace-view-failed")
        assert opened == {
            "report_id": report_id, "period": "2025-09", "status": "failed",
            "generated": False, "error": "受控失败原因",
        }
        assert len(db.scalars(select(BillReport).where(BillReport.user_id == user.id)).all()) == 1


def test_view_or_generate_prefers_latest_ready_report_over_newer_pending(bank):
    ready_id = _queue_report(bank, None, "2025-09", "view-ready-report-0001")
    pending_id = _queue_report(bank, None, "2025-09", "view-pending-report-0002")
    with bank["db"]() as db:
        ready = db.get(BillReport, ready_id)
        ready.payload = {**ready.payload, "status": "partial"}
        ready_job = db.scalar(select(BillReportJob).where(BillReportJob.report_id == ready_id))
        ready_job.status = "partial"
        db.commit()

        user = db.get(User, bank["ids"][0])
        opened = BillReportService(db, bank["core"], bank["settings"]).view_or_generate(
            user, None, "2025-09", trace_id="trace-view-ready",
        )
        assert opened["report_id"] == ready_id
        assert opened["report_id"] != pending_id
        assert opened["status"] == "partial" and opened["generated"] is False


def test_parallel_report_views_create_only_one_job(bank):
    barrier = Barrier(2)

    def open_report():
        with bank["db"]() as db:
            user = db.get(User, bank["ids"][0])
            barrier.wait(timeout=5)
            return BillReportService(db, bank["core"], bank["settings"]).view_or_generate(
                user, None, "2025-09",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = [future.result(timeout=10) for future in [
            pool.submit(open_report), pool.submit(open_report),
        ]]

    assert first["report_id"] == second["report_id"]
    assert sorted([first["generated"], second["generated"]]) == [False, True]
    with bank["db"]() as db:
        user_reports = db.scalars(select(BillReport).where(
            BillReport.user_id == bank["ids"][0],
        )).all()
        assert len(user_reports) == 1


def test_report_calendar_progress_and_comparison_ranges():
    from datetime import date
    from decimal import Decimal
    from services.bill_report_service import _compare, _facts, _progress_end
    assert _progress_end("2024-03", date(2024, 3, 31), years=-1) == date(2023, 3, 31)
    assert _progress_end("2024-03", date(2024, 3, 31), months=-1) == date(2024, 2, 29)
    assert _progress_end("2025", date(2025, 10, 26), years=-1) == date(2024, 10, 26)
    empty = _facts([])
    assert empty["totals"]["income"] is None and empty["totals"]["expense"] is None
    current = _facts([{"date": "2026-01-03", "kind": "expense", "amount": "2.00",
        "category": "餐饮", "components": {"expense": Decimal("2.00")}, "reversed": False}])
    non_spending_baseline = _facts([{"date": "2025-01-03", "kind": "internal_transfer", "amount": "5.00",
        "category": "未分类", "components": {"internal_transfer": Decimal("5.00")}, "reversed": False}])
    comparison = _compare(current, non_spending_baseline)["expense"]
    assert comparison["delta"] == Decimal("2.00")
    assert comparison["change_ratio"] is None and comparison["unavailable_reason"] == "baseline_zero"
    assert _compare(empty, current)["expense"]["unavailable_reason"] == "no_current_transactions"
    mutual_transfer = _facts([
        {"date": "2026-01-05", "kind": "internal_transfer", "amount": "25.00", "category": "未分类",
         "components": {"internal_transfer": Decimal("25.00")}, "transfer_reference": 71, "reversed": False},
        {"date": "2026-01-05", "kind": "internal_transfer", "amount": "25.00", "category": "未分类",
         "components": {"internal_transfer": Decimal("25.00")}, "transfer_reference": 71, "reversed": False},
    ])
    assert mutual_transfer["totals"]["internal_transfer"] == Decimal("25.00")
    assert mutual_transfer["totals"]["income"] == Decimal("0.00")
    assert mutual_transfer["totals"]["expense"] == Decimal("0.00")
