from datetime import date
from fastapi import APIRouter, Header, Query, Response
from api.context import Actor, Db, DecimalRoute, billing_service, bill_report_service
from core.errors import require
from models import Category, ClassificationRule, Annotation, BillReport
from schemas.banking import (
    CategoryRequest,
    RuleRequest,
    AnnotationRequest,
    ReportRequest,
    BillReportGenerationRequest,
    ReviewRequest,
)
from services.common import owned, row_dict

router = APIRouter(prefix="/api", tags=["billing"], route_class=DecimalRoute)


@router.get("/categories")
def categories(user: Actor, db: Db):
    return billing_service(db).list_resources(user, Category)


@router.post("/categories", status_code=201)
def category_create(body: CategoryRequest, user: Actor, db: Db):
    return billing_service(db).save_category(user, body)


@router.put("/categories/{id}")
def category_update(id: str, body: CategoryRequest, user: Actor, db: Db):
    return billing_service(db).save_category(user, body, id)


@router.delete("/categories/{id}")
def category_delete(id: str, user: Actor, db: Db):
    return billing_service(db).delete(user, Category, id)


@router.get("/classification-rules")
def rules(user: Actor, db: Db):
    return billing_service(db).list_resources(user, ClassificationRule)


@router.post("/classification-rules", status_code=201)
def rule_create(body: RuleRequest, user: Actor, db: Db):
    return billing_service(db).save_rule(user, body)


@router.put("/classification-rules/{id}")
def rule_update(id: str, body: RuleRequest, user: Actor, db: Db):
    return billing_service(db).save_rule(user, body, id)


@router.delete("/classification-rules/{id}")
def rule_delete(id: str, user: Actor, db: Db):
    return billing_service(db).delete(user, ClassificationRule, id)


@router.get("/transaction-annotations")
def annotations(
    user: Actor,
    db: Db,
    account_id: int | None = Query(default=None, gt=0),
    transaction_id: int | None = Query(default=None, gt=0),
):
    require(
        (account_id is None) == (transaction_id is None),
        "INVALID_FILTER",
        "账户和流水编号必须同时提供",
        422,
    )
    service = billing_service(db)
    if account_id is not None:
        service.transactions.detail(user, account_id, transaction_id)
    rows = service.list_resources(user, Annotation)
    if account_id is None:
        return rows
    return [
        row
        for row in rows
        if row["account_id"] == account_id
        and row["transaction_id"] == transaction_id
    ]


@router.post("/transaction-annotations", status_code=201)
def annotation_create(body: AnnotationRequest, user: Actor, db: Db):
    return billing_service(db).annotate(user, body)


@router.put("/transaction-annotations/{id}")
def annotation_update(id: str, body: AnnotationRequest, user: Actor, db: Db):
    return billing_service(db).annotate(user, body, id)


@router.delete("/transaction-annotations/{id}")
def annotation_delete(id: str, user: Actor, db: Db):
    return billing_service(db).delete(user, Annotation, id)


@router.get("/billing/statistics")
def statistics(
    user: Actor,
    db: Db,
    from_date: date,
    to_date: date,
    account_id: int | None = None,
):
    require(from_date <= to_date, "INVALID_DATE", "开始日期晚于结束日期")
    return billing_service(db).statistics(user, account_id, from_date, to_date)


@router.get("/billing/anomalies")
def anomalies(
    user: Actor,
    db: Db,
    from_date: date,
    to_date: date,
    account_id: int | None = None,
    include_metadata: bool = False,
):
    """异常候选，兼容单账户列表/全账户对象。include_metadata=true 返回统一包装，
    detection.capabilities 说明六类检测的执行来源/跳过原因；findings 给出各窗口证据，
    expected_charge_not_observed 为无交易订阅观测。精确数据仅供授权客户端。
    """
    require(from_date <= to_date, "INVALID_DATE", "开始日期晚于结束日期")
    return billing_service(db).anomalies(user, account_id, from_date, to_date, include_metadata)


@router.post("/billing/anomaly-reviews")
def review(body: ReviewRequest, user: Actor, db: Db):
    return billing_service(db).review(user, body)


@router.post("/bill-reports", status_code=201)
def report_create(body: ReportRequest, user: Actor, db: Db):
    return billing_service(db).report(user, body)


@router.get("/bill-reports")
def reports(user: Actor, db: Db):
    # Kept for clients of the original persisted report snapshot contract.
    return bill_report_service(db).legacy_list(user)


@router.post("/bill-report-generations", status_code=202)
def report_generate(body: BillReportGenerationRequest, user: Actor, db: Db,
                    idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=160)):
    result = bill_report_service(db).enqueue(user, body.account_id, body.period, idempotency_key)
    db.commit()
    return result


@router.get("/bill-report-generations/{id}/status")
def report_status(id: str, user: Actor, db: Db, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return bill_report_service(db).status(user, id)


@router.get("/bill-report-summaries")
def report_summaries(user: Actor, db: Db, response: Response,
                     period: str | None = Query(default=None, pattern=r"^\d{4}(-(?:0[1-9]|1[0-2]))?$"),
                     period_from: str | None = Query(default=None, pattern=r"^\d{4}(-(?:0[1-9]|1[0-2]))?$"),
                     period_to: str | None = Query(default=None, pattern=r"^\d{4}(-(?:0[1-9]|1[0-2]))?$"),
                     status: str | None = None, account_id: int | None = None, page: int = Query(default=1, ge=1),
                     page_size: int = Query(default=20, ge=1, le=100)):
    if account_id is not None:
        from core.deps import get_account_service
        get_account_service().get_account(user, account_id)
    response.headers["Cache-Control"] = "no-store"
    return bill_report_service(db).list(user, period=period, period_from=period_from,
        period_to=period_to, status=status, account_id=account_id, page=page, page_size=page_size)


@router.get("/bill-reports/{id}/transactions")
def report_transactions(id: str, user: Actor, db: Db, response: Response, page: int = Query(default=1, ge=1),
                        page_size: int = Query(default=50, ge=1, le=100), direction: str | None = None,
                        category: str | None = None, from_date: date | None = None,
                        to_date: date | None = None):
    response.headers["Cache-Control"] = "no-store"
    return bill_report_service(db).transactions(user, id, page=page, page_size=page_size,
        direction=direction, category=category, from_date=from_date, to_date=to_date)


@router.get("/bill-reports/{id}")
def report_detail(id: str, user: Actor, db: Db, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return bill_report_service(db).detail(user, id)


@router.delete("/bill-reports/{id}")
def report_delete(id: str, user: Actor, db: Db):
    return bill_report_service(db).delete(user, id)


@router.get("/categories/{id}")
def category_detail(id: str, user: Actor, db: Db):
    return row_dict(owned(db, Category, id, user))


@router.get("/classification-rules/{id}")
def rule_detail(id: str, user: Actor, db: Db):
    return row_dict(owned(db, ClassificationRule, id, user))


@router.get("/transaction-annotations/{id}")
def annotation_detail(id: str, user: Actor, db: Db):
    return row_dict(owned(db, Annotation, id, user))
