from copy import deepcopy
from datetime import date

from sqlalchemy import select

from core.security import now, SHANGHAI
from models import Audit, ClassificationRule


def raw_transaction(transaction_id, *, note, transaction_type=None):
    today = now().astimezone(SHANGHAI).date()
    return {
        "id": transaction_id,
        "accountId": 1,
        "date": [today.year, today.month, today.day],
        "amount": "23.40",
        "currency": {"code": "CNY"},
        "entryType": "DEBIT",
        "transactionType": transaction_type or {"withdrawal": True, "code": "withdrawal"},
        "note": note,
    }


def request(bank, method, path, body=None, *, user="alice", expected=200):
    response = bank["http"].request(
        method,
        f"/api{path}",
        headers=bank["headers"][user],
        **({"json": body} if body is not None else {}),
    )
    assert response.status_code == expected, response.text
    return response.json() if response.content else None


def test_personal_annotation_filters_precedence_restore_and_audit(bank):
    original = raw_transaction(701, note="[Merchant] Cafe")
    bank["core"].tx[1] = [deepcopy(original)]
    category = request(bank, "POST", "/categories", {"name": "餐饮"}, expected=201)
    manual_category = request(bank, "POST", "/categories", {"name": "个人修正"}, expected=201)
    rule = request(bank, "POST", "/classification-rules", {
        "category_id": category["id"], "field": "merchant", "contains": "Cafe", "priority": 100,
    }, expected=201)
    assert request(bank, "GET", "/accounts/1/transactions/701")["category"] == "餐饮"
    assert request(bank, "GET", "/transaction-annotations") == []
    assert request(bank, "GET", "/transaction-annotations?account_id=1", expected=422)["error"]["code"] == "INVALID_FILTER"

    annotation = request(bank, "POST", "/transaction-annotations", {
        "account_id": 1, "transaction_id": 701, "category_id": manual_category["id"],
        "merchant": "Cafe", "note": "本人备注",
    }, expected=201)
    assert request(bank, "GET", "/transaction-annotations?account_id=1&transaction_id=701") == [annotation]
    assert request(bank, "GET", "/accounts/1/transactions/701")["category"] == "个人修正"
    day = date(*original["date"])
    stats = request(bank, "GET", f"/billing/statistics?from_date={day}&to_date={day}")
    assert stats["categories"] == {"个人修正": "23.40"}
    assert request(bank, "GET", f"/transaction-annotations?account_id=1&transaction_id=701", user="bob", expected=404)["error"]["code"] == "ACCOUNT_NOT_FOUND"
    assert request(bank, "PUT", f"/transaction-annotations/{annotation['id']}", {
        "account_id": 1, "transaction_id": 701, "category_id": None,
        "merchant": "forged", "note": "forged",
    }, user="bob", expected=404)["error"]["code"] == "ACCOUNT_NOT_FOUND"
    assert request(bank, "PUT", f"/categories/{manual_category['id']}", {
        "name": "越权类别",
    }, user="bob", expected=404)["error"]["code"] == "NOT_FOUND"
    assert request(bank, "DELETE", f"/categories/{manual_category['id']}", expected=409)["error"]["code"] == "CATEGORY_IN_USE"
    assert bank["core"].tx[1] == [original]

    request(bank, "DELETE", f"/transaction-annotations/{annotation['id']}")
    assert request(bank, "GET", "/accounts/1/transactions/701")["category"] == "餐饮"
    assert bank["core"].tx[1] == [original]
    with bank["db"]() as db:
        rows = db.scalars(
            select(Audit)
            .where(Audit.resource_type == "transaction_annotation")
            .order_by(Audit.created_at, Audit.id)
        ).all()
        events = [row.event for row in rows]
    assert events == ["TRANSACTION_ANNOTATION_CREATED", "TRANSACTION_ANNOTATION_DELETED"]


def test_classification_rules_support_all_fields_priority_and_stable_updates(bank):
    bank["core"].tx[1] = [
        raw_transaction(711, note="[Merchant] Cafe"),
        raw_transaction(712, note="lunch receipt"),
        raw_transaction(713, note="[Merchant] Cafe", transaction_type={"withdrawal": True, "code": "cashWithdrawal"}),
    ]
    categories = {
        name: request(bank, "POST", "/categories", {"name": name}, expected=201)
        for name in ["按商户", "按备注", "按类型", "高优先级"]
    }
    rules = [
        request(bank, "POST", "/classification-rules", {"category_id": categories["按商户"]["id"], "field": "merchant", "contains": "Cafe", "priority": 10}, expected=201),
        request(bank, "POST", "/classification-rules", {"category_id": categories["按备注"]["id"], "field": "note", "contains": "lunch", "priority": 20}, expected=201),
        request(bank, "POST", "/classification-rules", {"category_id": categories["按类型"]["id"], "field": "type", "contains": "cashWithdrawal", "priority": 300}, expected=201),
        request(bank, "POST", "/classification-rules", {"category_id": categories["高优先级"]["id"], "field": "merchant", "contains": "Cafe", "priority": 200}, expected=201),
    ]
    assert request(bank, "GET", "/accounts/1/transactions/711")["category"] == "高优先级"
    assert request(bank, "GET", "/accounts/1/transactions/712")["category"] == "按备注"
    assert request(bank, "GET", "/accounts/1/transactions/713")["category"] == "按类型"

    changed = request(bank, "PUT", f"/classification-rules/{rules[0]['id']}", {
        "category_id": categories["按商户"]["id"], "field": "merchant", "contains": "Cafe", "priority": 250,
    })
    assert changed["priority"] == 250
    assert request(bank, "GET", "/accounts/1/transactions/711")["category"] == "按商户"
    request(bank, "DELETE", f"/classification-rules/{rules[0]['id']}")
    assert request(bank, "GET", "/accounts/1/transactions/711")["category"] == "高优先级"
    assert bank["core"].tx[1][0]["note"] == "[Merchant] Cafe"


def test_equal_priority_rules_use_a_stable_id_order(bank):
    bank["core"].tx[1] = [raw_transaction(721, note="[Merchant] Tie")]
    first = request(bank, "POST", "/categories", {"name": "同级一"}, expected=201)
    second = request(bank, "POST", "/categories", {"name": "同级二"}, expected=201)
    request(bank, "POST", "/classification-rules", {
        "category_id": second["id"], "field": "merchant", "contains": "Tie", "priority": 80,
    }, expected=201)
    request(bank, "POST", "/classification-rules", {
        "category_id": first["id"], "field": "merchant", "contains": "Tie", "priority": 80,
    }, expected=201)
    with bank["db"]() as db:
        winner = db.scalar(
            select(ClassificationRule)
            .where(ClassificationRule.contains == "Tie")
            .order_by(ClassificationRule.priority.desc(), ClassificationRule.id)
        )
    expected = first if winner.category_id == first["id"] else second
    assert request(bank, "GET", "/accounts/1/transactions/721")["category"] == expected["name"]


def test_category_rule_and_annotation_audits_record_resource_changes(bank):
    bank["core"].tx[1] = [raw_transaction(731, note="[Merchant] Cafe")]
    category = request(bank, "POST", "/categories", {"name": "餐饮"}, expected=201)
    request(bank, "PUT", f"/categories/{category['id']}", {"name": "餐饮新版"})
    rule = request(bank, "POST", "/classification-rules", {
        "category_id": category["id"], "field": "merchant", "contains": "Cafe", "priority": 100,
    }, expected=201)
    request(bank, "PUT", f"/classification-rules/{rule['id']}", {
        "category_id": category["id"], "field": "note", "contains": "lunch", "priority": 250,
    })
    annotation = request(bank, "POST", "/transaction-annotations", {
        "account_id": 1, "transaction_id": 731, "category_id": category["id"],
        "merchant": "Cafe", "note": "原备注",
    }, expected=201)
    request(bank, "PUT", f"/transaction-annotations/{annotation['id']}", {
        "account_id": 1, "transaction_id": 731, "category_id": category["id"],
        "merchant": "Cafe Plus", "note": "更新备注",
    })
    request(bank, "DELETE", f"/transaction-annotations/{annotation['id']}")
    request(bank, "DELETE", f"/classification-rules/{rule['id']}")
    request(bank, "DELETE", f"/categories/{category['id']}")

    with bank["db"]() as db:
        rows = db.scalars(
            select(Audit)
            .where(Audit.resource_id.in_([category["id"], rule["id"], annotation["id"]]))
            .order_by(Audit.created_at, Audit.id)
        ).all()
    by_resource = {}
    for row in rows:
        by_resource.setdefault(row.resource_type, []).append(row)
    assert [row.event for row in by_resource["category"]] == [
        "CATEGORY_CREATED", "CATEGORY_UPDATED", "CATEGORY_DELETED",
    ]
    assert by_resource["category"][1].data["changed_fields"] == ["name"]
    assert [row.event for row in by_resource["classification_rule"]] == [
        "CLASSIFICATION_RULE_CREATED", "CLASSIFICATION_RULE_UPDATED", "CLASSIFICATION_RULE_DELETED",
    ]
    assert set(by_resource["classification_rule"][1].data["changed_fields"]) == {
        "field", "contains", "priority",
    }
    assert [row.event for row in by_resource["transaction_annotation"]] == [
        "TRANSACTION_ANNOTATION_CREATED", "TRANSACTION_ANNOTATION_UPDATED", "TRANSACTION_ANNOTATION_DELETED",
    ]
    assert by_resource["transaction_annotation"][1].data["changed_fields"] == ["merchant", "note"]


def test_anomaly_review_audits_only_actual_state_changes(bank):
    key = "a" * 64
    request(bank, "POST", "/billing/anomaly-reviews", {"anomaly_key": key, "status": "verified"})
    request(bank, "POST", "/billing/anomaly-reviews", {"anomaly_key": key, "status": "verified"})
    request(bank, "POST", "/billing/anomaly-reviews", {"anomaly_key": key, "status": "ignored"})
    with bank["db"]() as db:
        rows = db.scalars(select(Audit).where(Audit.resource_type == "anomaly_review")).all()
    assert [row.event for row in rows] == ["ANOMALY_REVIEWED", "ANOMALY_REVIEW_CHANGED"]
    assert rows[0].data == {"previous_status": "unreviewed", "status": "verified"}
    assert rows[1].data == {"previous_status": "verified", "status": "ignored"}
