"""Private snapshots and a closed vocabulary for the model boundary.

This service never returns bank payloads to a Tool. User-authored input is outside
this result policy; no banking facts are copied from it into summaries.
"""
import calendar
import json
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from core.errors import require
from core.security import SHANGHAI, aware, fingerprint, now
from models import AnalysisResult, AnomalyReview
from services.common import lock_user, owned, safe_json

Kind = Literal[
    "balance",
    "transactions",
    "statistics",
    "anomalies",
    "wealth_products",
    "wealth_recommend",
    "wealth_holdings",
]
Code = Literal[
    "DETAILS_READY", "SUMMARY_LIMITED", "NO_ACCOUNTS", "NO_TRANSACTIONS",
    "NO_EXPENSES", "CATEGORY_OVERVIEW", "CANDIDATES_PRESENT", "NO_RULE_MATCH",
    "RULES_ONLY", "ML_AVAILABLE", "CANDIDATE_NOT_FRAUD", "PARTIAL_DETECTION", "PROVISIONAL_FINDINGS",
    "PRODUCTS_READY", "NO_PRODUCTS", "RECOMMENDATIONS_READY",
    "NO_RECOMMENDATIONS", "HOLDINGS_READY", "NO_HOLDINGS",
]
CategoryCode = Literal["DINING", "TRANSPORT", "SHOPPING", "HOUSING", "LEISURE", "HEALTH", "EDUCATION", "OTHER"]
CATEGORY_CODES = {"餐饮": "DINING", "交通": "TRANSPORT", "购物": "SHOPPING", "居住": "HOUSING", "娱乐": "LEISURE", "医疗": "HEALTH", "教育": "EDUCATION"}
TEXT = {
    "DETAILS_READY": "查询已完成，精确结果请查看下方结果卡。",
    "SUMMARY_LIMITED": "为保护隐私，本次仅提供精确结果卡，不生成细分文字摘要。",
    "NO_ACCOUNTS": "当前没有可查询的合格账户。",
    "NO_TRANSACTIONS": "查询期间没有可统计流水。",
    "NO_EXPENSES": "查询期间没有计入消费的交易。",
    "CATEGORY_OVERVIEW": "消费分类概况已生成，具体分类和金额请查看结果卡。",
    "CANDIDATES_PRESENT": "发现需要人工核实的异常消费候选，证据请查看结果卡。",
    "NO_RULE_MATCH": "本次未发现符合当前检测策略的候选，不代表全部交易安全。",
    "RULES_ONLY": "机器学习当前不可用，本次仅进行了规则检测，原因请查看结果卡。",
    "ML_AVAILABLE": "本次已结合个人历史行为模型和规则进行检测。",
    "PARTIAL_DETECTION": "部分检测条件不足或配置不可用，具体覆盖范围请查看结果卡。",
    "PROVISIONAL_FINDINGS": "结果包含当日临时提示，完整日结束后可重新查询。",
    "CANDIDATE_NOT_FRAUD": "消费行为异常候选不等于已确认欺诈。",
    "PRODUCTS_READY": "定存产品资料已读取，精确条款请查看结果卡。",
    "NO_PRODUCTS": "当前没有可展示的合格定存产品。",
    "RECOMMENDATIONS_READY": "适配筛选已完成，利率和估算收益请查看结果卡；结果不构成投资建议。",
    "NO_RECOMMENDATIONS": "当前没有同时满足风险、金额、期限和流动性条件的产品。",
    "HOLDINGS_READY": "本人定存持有已读取，本金、利率和到期信息请查看结果卡。",
    "NO_HOLDINGS": "当前没有定存持有。",
}


class ModelSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_id: str
    kind: Kind
    status: Literal["ready", "limited"]
    insight_codes: list[Code]
    main_category: CategoryCode | None = None


class AnalysisResultService:
    def __init__(self, db, accounts, settings, investments=None):
        self.db, self.accounts, self.settings = db, accounts, settings
        self.investments = investments
        # References only: never insert payloads into graph state/events.
        self.events = []
        self.summaries = []

    def store(
        self,
        user,
        kind,
        payload,
        account_ids,
        start=None,
        end=None,
        scope_details=None,
    ):
        payload = dict(payload)
        lock_user(self.db, user)  # serializes per-user privacy budgets across requests
        stamp = now()
        local = stamp.astimezone(SHANGHAI)
        day_start = datetime.combine(local.date(), time.min, SHANGHAI).astimezone(timezone.utc)
        scope_input = {
            "kind": kind,
            "accounts": sorted(account_ids),
            "start": start,
            "end": end,
        }
        if scope_details is not None:
            scope_input["details"] = scope_details
        scope = fingerprint(scope_input)
        previous = self.db.scalars(select(AnalysisResult).where(
            AnalysisResult.user_id == user.id, AnalysisResult.created_at >= day_start,
        )).all()
        scopes = {row.scope_hash for row in previous}
        cached = next((row.summary for row in reversed(previous) if row.scope_hash == scope), None)
        min_samples = self.settings.analysis_min_samples
        expense_count = payload.pop("_privacy_expense_count", 0)
        category_counts = payload.pop("_privacy_category_counts", {})
        codes = ["DETAILS_READY"]
        category = None
        wealth_kind = kind.startswith("wealth_")
        limited = (
            not wealth_kind
            and scope not in scopes
            and len(scopes) >= self.settings.analysis_daily_scope_limit
        )
        full_months = bool(start and end and start.day == 1 and end.day == calendar.monthrange(end.year, end.month)[1])
        limited = limited or (kind in {"statistics", "anomalies"} and not full_months)
        if kind == "wealth_products":
            codes.append("PRODUCTS_READY" if payload.get("items") else "NO_PRODUCTS")
        elif kind == "wealth_recommend":
            codes.append(
                "RECOMMENDATIONS_READY"
                if payload.get("items")
                else "NO_RECOMMENDATIONS"
            )
        elif kind == "wealth_holdings":
            codes.append("HOLDINGS_READY" if payload.get("items") else "NO_HOLDINGS")
        elif not account_ids:
            codes.append("NO_ACCOUNTS")
        elif kind == "transactions":
            if payload["transaction_count"] == 0:
                codes.append("NO_TRANSACTIONS")
        elif kind == "statistics":
            if payload["transaction_count"] == 0:
                codes.append("NO_TRANSACTIONS")
            elif expense_count == 0:
                codes.append("NO_EXPENSES")
            elif expense_count < min_samples:
                limited = True
            elif not limited:
                eligible = {k: v for k, v in payload["categories"].items() if category_counts.get(k, 0) >= min_samples}
                if eligible:
                    main = max(eligible, key=lambda k: Decimal(eligible[k]))
                    category = CATEGORY_CODES.get(main, "OTHER")
                    codes.append("CATEGORY_OVERVIEW")
                else:
                    limited = True
        elif kind == "anomalies":
            limited = limited or payload.get("expense_count", 0) < min_samples
            codes.extend(["ML_AVAILABLE" if payload["detection"]["status"] == "ready" else "RULES_ONLY", "CANDIDATE_NOT_FRAUD"])
            if payload["detection"].get("partial"):
                codes.append("PARTIAL_DETECTION")
            if payload["detection"].get("provisional"):
                codes.append("PROVISIONAL_FINDINGS")
            if not limited:
                codes.append("CANDIDATES_PRESENT" if payload["items"] else "NO_RULE_MATCH")
        if limited:
            # No small-window/group presence, category, score or numeric output.
            codes = ["DETAILS_READY", "SUMMARY_LIMITED"] + (["RULES_ONLY"] if kind == "anomalies" and payload["detection"]["status"] != "ready" else [])
            category = None
        # Once a scope was limited, repeat queries cannot promote it that day.
        if not wealth_kind and cached and cached["status"] == "limited":
            limited, category = True, None
            codes = ["DETAILS_READY", "SUMMARY_LIMITED"]
        row = AnalysisResult(user_id=user.id, kind=kind, scope_hash=scope,
            payload=safe_json({**payload, "account_ids": account_ids}), summary={},
            created_at=stamp, expires_at=stamp + timedelta(hours=self.settings.analysis_retention_hours))
        self.db.add(row)
        self.db.flush()
        summary = ModelSummary(analysis_id=row.id, kind=kind, status="limited" if limited else "ready", insight_codes=codes, main_category=category).model_dump()
        row.summary = summary
        self.events.append({"type": "ANALYSIS_READY", "data": {"analysis_id": row.id, "kind": kind}})
        self.summaries.append(summary)
        return summary

    def get(self, user, analysis_id):
        row = owned(self.db, AnalysisResult, analysis_id, user)
        require(aware(row.expires_at) > now(), "ANALYSIS_EXPIRED", "分析结果已过期，请重新查询", 410)
        for account_id in row.payload.get("dependency_account_ids", row.payload.get("account_ids", [])):
            self.accounts.get_account(user, account_id)
        product_ids = row.payload.get("dependency_product_ids", [])
        holding_ids = row.payload.get("dependency_holding_ids", [])
        if product_ids or holding_ids:
            require(
                self.investments is not None,
                "AGENT_CONTEXT_MISSING",
                "财富结果校验服务未配置",
                500,
            )
        for product_id in product_ids:
            self.investments.product(user, int(product_id))
        for holding_id in holding_ids:
            self.investments.holding(user, int(holding_id))
        payload = row.payload
        if row.kind == "anomalies":
            items = [dict(item) for item in row.payload.get("items", [])]
            keys = [item.get("anomaly_key") for item in items if item.get("anomaly_key")]
            reviews = {}
            if keys:
                reviews = dict(self.db.execute(
                    select(AnomalyReview.anomaly_key, AnomalyReview.status).where(
                        AnomalyReview.user_id == user.id,
                        AnomalyReview.anomaly_key.in_(keys),
                    )
                ).all())
            payload = {
                **row.payload,
                "items": [
                    {**item, "current_review_status": reviews.get(item.get("anomaly_key"), "unreviewed")}
                    for item in items
                ],
            }
        return {"analysis_id": row.id, "kind": row.kind, "created_at": row.created_at,
                "expires_at": row.expires_at, "data": payload}

    def render(self, model_text):
        """LLM chooses supported conclusions; server owns the factual vocabulary.

        A malformed or invented narration always falls back to trusted templates.
        No free-form model text can reintroduce financial figures or identifiers.
        """
        allowed = list(dict.fromkeys(c for s in self.summaries for c in s["insight_codes"]))
        try:
            proposal = json.loads(model_text)
            requested = proposal["insight_codes"]
            if not isinstance(requested, list) or not requested or any(c not in allowed for c in requested):
                raise ValueError("unsupported narration")
            chosen = list(dict.fromkeys(requested + allowed))
        except (ValueError, KeyError, TypeError):
            chosen = allowed
        execution_codes = {"RULES_ONLY", "ML_AVAILABLE", "PARTIAL_DETECTION"}
        return "\n".join(TEXT[code] for code in chosen if code not in execution_codes)
