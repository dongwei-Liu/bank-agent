import calendar
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select
from core.errors import DomainError, require
from core.security import aware, fingerprint, now, SHANGHAI
from models import ProductMetadata, RiskAssessment
from services.account_service import AccountService
from services.common import lock_user, row_dict, safe_json, audit
from services.transaction_service import iso_date


def enum_id(value):
    return value.get("id") if isinstance(value, dict) else value


def term_value(months, unit, today):
    if unit == 2:
        return Decimal(months)
    if unit == 3:
        return Decimal(months) / 12
    year = today.year + (today.month - 1 + months) // 12
    month = (today.month - 1 + months) % 12 + 1
    end = today.replace(
        year=year, month=month, day=min(today.day, calendar.monthrange(year, month)[1])
    )
    days = Decimal((end - today).days)
    if unit == 0:
        return days
    if unit == 1:
        return days / 7
    raise DomainError("PRODUCT_CONTRACT", "产品期限单位不兼容", 502)


class InvestmentService:
    def __init__(self, db, fineract, settings):
        self.db, self.fineract, self.settings = db, fineract, settings
        self.accounts = AccountService(fineract)

    def product(self, user, product_id):
        raw = self.fineract.fixed_product(product_id)
        metadata = self.db.get(ProductMetadata, product_id)
        return {
            **safe_json(raw),
            "suitability": row_dict(metadata)
            if metadata and metadata.tenant == user.tenant
            else None,
        }

    def products(self, user):
        return [self.product(user, p["id"]) for p in self.fineract.fixed_products()]

    def risk(self, user, assessment_id=None, *, require_unused=False):
        query = select(RiskAssessment).where(RiskAssessment.user_id == user.id)
        if assessment_id:
            query = query.where(RiskAssessment.id == assessment_id)
        else:
            query = query.order_by(
                RiskAssessment.created_at.desc(), RiskAssessment.id.desc()
            )
        if require_unused and not assessment_id:
            query = query.where(
                RiskAssessment.used_at.is_(None), RiskAssessment.action_id.is_(None)
            )
        row = self.db.scalar(query)
        require(
            row and row.purpose == "subscription",
            "RISK_ASSESSMENT_REQUIRED",
            "请为本次申购重新完成风险评估",
            409,
        )
        if require_unused and assessment_id:
            require(
                row.used_at is None and row.action_id is None,
                "ASSESSMENT_ALREADY_USED",
                "这份风险评估已用于其他申购，请重新完成本次评估",
                409,
            )
        require(
            aware(row.created_at) + timedelta(minutes=15) > now()
            and aware(row.expires_at) > now(),
            "RISK_ASSESSMENT_REQUIRED",
            "请为本次申购重新完成风险评估",
            409,
        )
        return row

    def assess(self, user, request):
        lock_user(self.db, user)
        score = sum(request.answers)
        level = min(5, 1 + (score - 5) // 5)
        row = RiskAssessment(
            user_id=user.id,
            answers=request.answers,
            score=score,
            level=level,
            purpose="subscription",
            expires_at=now() + timedelta(minutes=15),
        )
        self.db.add(row)
        audit(self.db, user, "RISK_ASSESSED")
        self.db.commit()
        return row_dict(row)

    def applicable(
        self,
        user,
        product,
        amount,
        months,
        needs_liquidity=False,
        assessment=None,
    ):
        meta = product.get("suitability")
        require(meta and meta["enabled"], "PRODUCT_NOT_ENABLED", "产品未配置适配规则")
        assessment = assessment or self.risk(user)
        require(
            meta["risk_level"] <= assessment.level,
            "RISK_MISMATCH",
            "产品风险超过客户承受等级",
        )
        require(
            (product.get("currency") or {}).get("code") == "CNY",
            "UNSUPPORTED_CURRENCY",
            "产品不是 CNY",
        )
        require(
            not needs_liquidity or meta["allows_premature"],
            "LIQUIDITY_MISMATCH",
            "产品不满足流动性需求",
        )
        today = now().astimezone(SHANGHAI).date()
        for field, lower in [("minDepositAmount", True), ("maxDepositAmount", False)]:
            if product.get(field) is not None:
                limit = Decimal(str(product[field]))
                require(
                    amount >= limit if lower else amount <= limit,
                    "PRODUCT_AMOUNT",
                    "金额不满足产品条件",
                )
        for field, typefield, lower in [
            ("minDepositTerm", "minDepositTermType", True),
            ("maxDepositTerm", "maxDepositTermType", False),
        ]:
            if product.get(field) is not None:
                value = term_value(
                    months,
                    enum_id(product.get(typefield, product.get(typefield + "Id"))),
                    today,
                )
                require(
                    value >= Decimal(str(product[field]))
                    if lower
                    else value <= Decimal(str(product[field])),
                    "PRODUCT_TERM",
                    "期限不满足产品条件",
                )
        multiple = product.get("inMultiplesOfDepositTerm")
        if multiple:
            unit = enum_id(
                product.get(
                    "inMultiplesOfDepositTermType",
                    product.get("inMultiplesOfDepositTermTypeId"),
                )
            )
            require(
                term_value(months, unit, today) % Decimal(str(multiple)) == 0,
                "PRODUCT_TERM",
                "期限不满足产品倍数规则",
            )
        rates = []
        charts = product.get("interestRateCharts", [])
        if product.get("activeChart"):
            charts = [product["activeChart"]]
        else:
            eligible = [
                c
                for c in charts
                if (
                    not c.get("fromDate")
                    or date.fromisoformat(iso_date(c["fromDate"])) <= today
                )
                and (
                    not c.get("endDate")
                    or date.fromisoformat(iso_date(c["endDate"])) >= today
                )
            ]
            latest = max(
                (
                    iso_date(c["fromDate"]) if c.get("fromDate") else "0001-01-01"
                    for c in eligible
                ),
                default=None,
            )
            charts = [
                c
                for c in eligible
                if (iso_date(c["fromDate"]) if c.get("fromDate") else "0001-01-01")
                == latest
            ]
        for chart in charts:
            if (
                chart.get("fromDate")
                and date.fromisoformat(iso_date(chart["fromDate"])) > today
            ):
                continue
            if (
                chart.get("endDate")
                and date.fromisoformat(iso_date(chart["endDate"])) < today
            ):
                continue
            for slab in chart.get("chartSlabs", []):
                value = term_value(months, enum_id(slab.get("periodType")), today)
                if value < Decimal(str(slab.get("fromPeriod", 0))):
                    continue
                if slab.get("toPeriod") is not None and value > Decimal(
                    str(slab["toPeriod"])
                ):
                    continue
                if slab.get("amountRangeFrom") is not None and amount < Decimal(
                    str(slab["amountRangeFrom"])
                ):
                    continue
                if slab.get("amountRangeTo") is not None and amount > Decimal(
                    str(slab["amountRangeTo"])
                ):
                    continue
                # Incentive formulas require an upstream calculation; don't guess a rate.
                require(
                    not slab.get("incentives"),
                    "PRODUCT_CONTRACT",
                    "首版不支持附加激励利率",
                    422,
                )
                rates.append(Decimal(str(slab["annualInterestRate"])))
        require(
            len(rates) == 1,
            "PRODUCT_RATE_UNAVAILABLE",
            "无法唯一确定当前金额和期限适用利率",
            422,
        )
        return rates[0]

    def recommendations(self, user, amount, months, needs_liquidity=False):
        assessment = self.risk(user)
        result = []
        for product in self.products(user):
            try:
                rate = self.applicable(
                    user,
                    product,
                    amount,
                    months,
                    needs_liquidity,
                    assessment,
                )
            except DomainError as exc:
                if exc.status >= 500:
                    raise
                continue
            result.append(
                {
                    "product": product,
                    "term_months": months,
                    "annual_interest_rate": str(rate),
                    "estimated_interest": str(
                        (amount * rate / 100 * Decimal(months) / 12).quantize(
                            Decimal(".01")
                        )
                    ),
                    "estimate_only": True,
                    "reason": "金额、期限、风险等级及流动性条件匹配",
                }
            )
        return sorted(
            result,
            key=lambda r: (-Decimal(r["annual_interest_rate"]), r["product"]["id"]),
        )

    def prepare_subscription(self, user, request):
        product = self.product(user, request.product_id)
        meta = product.get("suitability")
        require(meta and meta["enabled"], "PRODUCT_NOT_ENABLED", "产品未配置适配规则")
        assessment = self.risk(
            user, request.assessment_id, require_unused=True
        )
        rate = self.applicable(
            user,
            product,
            request.amount,
            request.term_months,
            assessment=assessment,
        )
        account = self.accounts.get_account(user, request.from_account_id)
        self.accounts.require_active(account)
        require(
            self.accounts.get_balance(user, request.from_account_id).balance
            >= request.amount,
            "INSUFFICIENT_FUNDS",
            "余额不足",
        )
        self.fineract.fixed_template(user.client_id, request.product_id)
        return {
            **request.model_dump(mode="json"),
            "assessment_id": assessment.id,
            "annual_interest_rate": str(rate),
            "product_contract_hash": fingerprint(product),
        }

    def consume_assessment(self, user, assessment_id, action):
        assessment = self.db.scalar(
            select(RiskAssessment)
            .where(
                RiskAssessment.id == assessment_id,
                RiskAssessment.user_id == user.id,
            )
            .with_for_update()
        )
        require(
            assessment and assessment.purpose == "subscription",
            "RISK_ASSESSMENT_REQUIRED",
            "请为本次申购重新完成风险评估",
            409,
        )
        require(
            assessment.used_at is None and assessment.action_id is None,
            "ASSESSMENT_ALREADY_USED",
            "这份风险评估已用于其他申购，请重新完成本次评估",
            409,
        )
        require(
            aware(assessment.created_at) + timedelta(minutes=15) > now()
            and aware(assessment.expires_at) > now(),
            "RISK_ASSESSMENT_REQUIRED",
            "请为本次申购重新完成风险评估",
            409,
        )
        assessment.used_at = now()
        assessment.action_id = action.id
        audit(
            self.db,
            user,
            "RISK_ASSESSMENT_CONSUMED",
            action,
            assessment_id=assessment.id,
        )

    def bound_assessment(self, user, action):
        assessment = self.db.scalar(
            select(RiskAssessment).where(
                RiskAssessment.id == action.payload.get("assessment_id"),
                RiskAssessment.user_id == user.id,
            )
        )
        require(
            assessment
            and assessment.action_id == action.id
            and assessment.used_at is not None,
            "RISK_ASSESSMENT_REQUIRED",
            "本次申购没有绑定有效风险评估",
            409,
        )
        return assessment

    def holding(self, user, holding_id):
        raw = self.fineract.fixed_account(holding_id)
        require(
            raw.get("clientId") == user.client_id, "NOT_FOUND", "持有账户不存在", 404
        )
        require(
            (raw.get("currency") or {}).get("code") == "CNY",
            "UNSUPPORTED_CURRENCY",
            "仅支持 CNY",
        )
        return raw

    def holdings(self, user):
        data = self.fineract.list_client_accounts(user.client_id)
        return [
            safe_json(self.holding(user, r["id"]))
            for r in data.get("savingsAccounts", [])
            if enum_id(r.get("depositType")) == 200
        ]

    def quote(self, user, holding_id, to_account_id):
        account = self.holding(user, holding_id)
        self.accounts.require_active(self.accounts.get_account(user, to_account_id))
        status = account.get("status") or {}
        require(
            status.get("active") or status.get("matured"),
            "HOLDING_STATE",
            "账户不可赎回",
            409,
        )
        today = now().astimezone(SHANGHAI).date()
        maturity = date.fromisoformat(iso_date(account["maturityDate"]))
        command = "close" if today >= maturity else "prematureClose"
        if command == "close":
            require(
                status.get("matured"),
                "MATURITY_PROCESSING_REQUIRED",
                "核心系统尚未完成到期处理，请稍后重新报价",
                409,
            )
        if command == "prematureClose":
            meta = self.db.get(ProductMetadata, account["depositProductId"])
            require(
                meta and meta.tenant == user.tenant and meta.allows_premature,
                "PREMATURE_NOT_ALLOWED",
                "产品不允许提前支取",
            )
            estimate = self.fineract.fixed_command(
                holding_id,
                "calculatePrematureAmount",
                {
                    "closedOnDate": today.isoformat(),
                    "locale": "en",
                    "dateFormat": "yyyy-MM-dd",
                },
                f"quote:{holding_id}:{today}",
            )
        else:
            estimate = self.fineract.fixed_closure_template(holding_id)
        # Bind to stable financial facts, not full DTO templates with changing optional lists.
        quote = {
            "holding_id": holding_id,
            "to_account_id": to_account_id,
            "command": command,
            "date": today.isoformat(),
            "principal": str(account["depositAmount"]),
            "maturity_date": maturity.isoformat(),
            "estimated_amount": str(
                estimate.get(
                    "maturityAmount",
                    estimate.get(
                        "accountBalance",
                        (estimate.get("summary") or {}).get("accountBalance", ""),
                    ),
                )
            ),
            "annual_interest_rate": str(
                estimate.get(
                    "nominalAnnualInterestRate",
                    account.get("nominalAnnualInterestRate", ""),
                )
            ),
        }
        require(
            quote["estimated_amount"] != "", "UPSTREAM_DATA", "赎回报价缺少金额", 502
        )
        quote["quote_hash"] = fingerprint(quote)
        return quote

    def prepare_redemption(self, user, request):
        quote = self.quote(user, request.holding_id, request.to_account_id)
        require(
            quote["quote_hash"] == request.quote_hash,
            "QUOTE_CHANGED",
            "报价已变化，请重新确认",
            409,
        )
        return quote

    def preflight(self, user, action):
        p = action.payload
        if action.kind == "subscription":
            product = self.product(user, p["product_id"])
            self.applicable(
                user,
                product,
                Decimal(p["amount"]),
                p["term_months"],
                assessment=self.bound_assessment(user, action),
            )
            require(
                fingerprint(product) == p["product_contract_hash"],
                "PRODUCT_CHANGED",
                "产品条件变化，请取消并重新创建请求",
                409,
            )
        else:
            quote = self.quote(user, p["holding_id"], p["to_account_id"])
            require(
                quote["quote_hash"] == p["quote_hash"],
                "QUOTE_CHANGED",
                "赎回条件变化，请取消并重新创建请求",
                409,
            )

    def execute(self, user, action):
        if action.kind == "subscription":
            return self.subscribe(user, action)
        require(action.kind == "redemption", "UNKNOWN_ACTION", "未知业务操作", 400)
        p = action.payload
        quote = self.quote(user, p["holding_id"], p["to_account_id"])
        require(
            quote["quote_hash"] == p["quote_hash"],
            "QUOTE_CHANGED",
            "赎回条件已变化，请重新创建请求",
            409,
        )
        payload = {
            "closedOnDate": p["date"],
            "onAccountClosureId": 200,
            "toSavingsAccountId": p["to_account_id"],
            "transferDescription": "Bank Agent fixed deposit redemption",
            "locale": "en",
            "dateFormat": "yyyy-MM-dd",
        }
        response = self.fineract.fixed_command(
            p["holding_id"], p["command"], payload, f"bank:{action.id}:redeem"
        )
        require(
            response.get("resourceId"), "EXECUTION_UNCONFIRMED", "赎回命令尚未执行", 502
        )
        action.steps = {**action.steps, "closed": True}
        self.db.commit()
        return self.reconcile(user, action)

    def step_key(self, action, command):
        attempt = action.steps.get("retry_" + command, 0)
        return (
            f"b:{action.id}:{command[0]}:{attempt}"
            if attempt
            else f"bank:{action.id}:{command}"
        )

    def subscribe(self, user, action):
        p = action.payload
        product = self.product(user, p["product_id"])
        rate = self.applicable(
            user,
            product,
            Decimal(p["amount"]),
            p["term_months"],
            assessment=self.bound_assessment(user, action),
        )
        require(
            fingerprint(product) == p["product_contract_hash"]
            and str(rate) == p["annual_interest_rate"],
            "PRODUCT_CHANGED",
            "产品条件变化，请重新创建请求",
            409,
        )
        self.accounts.require_active(
            self.accounts.get_account(user, p["from_account_id"])
        )
        today = now().astimezone(SHANGHAI).date().isoformat()
        common = {"locale": "en", "dateFormat": "yyyy-MM-dd"}
        holding_id = action.steps.get("holding_id")
        if not holding_id:
            response = self.fineract.create_fixed(
                {
                    **common,
                    "clientId": user.client_id,
                    "productId": p["product_id"],
                    "externalId": f"BANK-{action.id}",
                    "submittedOnDate": today,
                    "depositAmount": p["amount"],
                    "depositPeriod": p["term_months"],
                    "depositPeriodFrequencyId": 2,
                    "linkAccountId": p["from_account_id"],
                    "maturityInstructionId": 100,
                    "transferInterestToSavings": False,
                },
                f"bank:{action.id}:create",
            )
            require(
                response.get("resourceId"),
                "EXECUTION_UNCONFIRMED",
                "开户命令尚未执行",
                502,
            )
            holding_id = int(response["resourceId"])
            action.steps = {**action.steps, "holding_id": holding_id}
            self.db.commit()
        account = self.holding(user, holding_id)
        status = account.get("status") or {}
        if status.get("submittedAndPendingApproval"):
            action.steps = {**action.steps, "pending_step": "approve"}
            self.db.commit()
            self.fineract.fixed_command(
                holding_id,
                "approve",
                {**common, "approvedOnDate": today},
                self.step_key(action, "approve"),
            )
            action.steps = {**action.steps, "pending_step": None}
            self.db.commit()
            account = self.holding(user, holding_id)
            status = account.get("status") or {}
        if status.get("approved"):
            require(
                self.accounts.get_balance(user, p["from_account_id"]).balance
                >= Decimal(p["amount"]),
                "INSUFFICIENT_FUNDS",
                "激活前余额不足",
            )
            action.steps = {**action.steps, "pending_step": "activate"}
            self.db.commit()
            self.fineract.fixed_command(
                holding_id,
                "activate",
                {**common, "activatedOnDate": today},
                self.step_key(action, "activate"),
            )
            action.steps = {**action.steps, "pending_step": None}
            self.db.commit()
        return self.reconcile(user, action)

    def reconcile(self, user, action):
        p = action.payload
        if action.kind == "subscription":
            holding_id = action.steps.get("holding_id")
            if not holding_id:
                matches = [
                    a["id"]
                    for a in self.fineract.list_client_accounts(user.client_id).get(
                        "savingsAccounts", []
                    )
                    if a.get("externalId") == f"BANK-{action.id}"
                    and enum_id(a.get("depositType")) == 200
                ]
                require(
                    len(matches) == 1,
                    "MANUAL_RECONCILIATION_REQUIRED",
                    "未找到唯一核心定存申请，禁止重复开户",
                    409,
                )
                holding_id = matches[0]
                action.steps = {**action.steps, "holding_id": holding_id}
                self.db.commit()
            require(
                holding_id,
                "MANUAL_RECONCILIATION_REQUIRED",
                "开户结果未知，请核对 externalId 后处理",
                409,
            )
            account = self.holding(user, holding_id)
            require(
                (account.get("status") or {}).get("active")
                and Decimal(str(account.get("depositAmount", -1)))
                == Decimal(p["amount"]),
                "EXECUTION_UNCONFIRMED",
                "定存账户尚未完成激活，需续办",
                409,
            )
            return safe_json(account)
        account = self.holding(user, p["holding_id"])
        status = account.get("status") or {}
        require(
            status.get("closed") or status.get("prematureClosed"),
            "EXECUTION_UNCONFIRMED",
            "账户尚未完成赎回",
            409,
        )
        return safe_json(account)
