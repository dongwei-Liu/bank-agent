from datetime import date
from typing import Annotated, Any
from langchain_core.tools import InjectedToolArg, tool
from langgraph.prebuilt import ToolRuntime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from agent.context import AgentContext
from agent.state import AgentState
from core.errors import require
from schemas.agent import (
    BillReportOpenedData,
    BillReportOpenedEvent,
    BillReportReadyData,
    BillReportReadyEvent,
)
from uuid import uuid4


class SpendingStatisticsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_ref: str | None = Field(..., pattern=r"^[a-f0-9]{32}$", description="上下文给出的不透明本人账户引用；明确查询全部账户时显式传 null，缺失范围不能当作全部")
    from_date: date = Field(description="开始日期，含当天，YYYY-MM-DD")
    to_date: date = Field(description="结束日期，含当天，YYYY-MM-DD")

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.from_date > self.to_date:
            raise ValueError("开始日期不能晚于结束日期")
        return self


class _SpendingToolInput(SpendingStatisticsInput):
    runtime: Annotated[Any, InjectedToolArg]


def query(runtime, kind, account_ref, start, end):
    context = runtime.context
    require(context.billing_service is not None and context.private_results is not None,
            "AGENT_CONTEXT_MISSING", "分析服务未配置", 500)
    account_id = context.resolve_account(account_ref)
    service = context.billing_service
    if kind == "statistics":
        data = service.statistics(context.user, account_id, start, end, include_private_counts=True)
    else:
        data = service.anomalies(context.user, account_id, start, end, include_metadata=True)
    return context.private_results.store(context.user, kind, data, data["account_ids"], start, end)


@tool(args_schema=_SpendingToolInput)
def get_spending_statistics(account_ref: str | None, from_date: date, to_date: date,
                            runtime: ToolRuntime[AgentContext, AgentState]) -> dict:
    """查询本人单账户或全账户的收支、分类和月度统计。

    使用请求上下文的不透明账户引用；明确全部账户时传 null。
    返回无金额的隐私摘要及分析引用，精确结果由授权前端单独读取。
    不修改分类、不保存业务报告，不自行计算占比或同比环比。
    """
    return query(runtime, "statistics", account_ref, from_date, to_date)


@tool(args_schema=_SpendingToolInput)
def get_spending_anomalies(account_ref: str | None, from_date: date, to_date: date,
                          runtime: ToolRuntime[AgentContext, AgentState]) -> dict:
    """查询本人单账户或全账户的行为异常候选。

    使用请求上下文账户引用；明确全部账户时传 null。
    中端结合可用的个人历史模型与确定性规则检测，缺少模型时明确仅规则检测。
    仅返回定性摘要，金额、商户、分数和交易引用只由授权前端读取。
    候选不等于欺诈，未命中不能保证安全；不修改核实状态。
    """
    return query(runtime, "anomalies", account_ref, from_date, to_date)


class BillReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_ref: str | None = Field(..., pattern=r"^[a-f0-9]{32}$",
        description="明确全部账户时传 null；单账户使用请求上下文不透明引用")
    period: str = Field(pattern=r"^\d{4}(-(?:0[1-9]|1[0-2]))?$")


class _BillReportToolInput(BillReportInput):
    runtime: Annotated[Any, InjectedToolArg]


@tool(args_schema=_BillReportToolInput)
def generate_bill_report(account_ref: str | None, period: str,
                         runtime: ToolRuntime[AgentContext, AgentState]) -> dict:
    """按用户明确选择的月度 YYYY-MM 或年度 YYYY 报告期间创建并排队生成。

    用户明确说“生成/保存账单报告、月报、年报”必须调用本 Tool；
    普通消费分类统计使用 get_spending_statistics，不能在这里保存。
    全部账户使用 account_ref=null；范围由可信请求上下文验证。
    """
    context = runtime.context
    require(context.bill_reports is not None, "AGENT_CONTEXT_MISSING", "报告服务未配置", 500)
    account_id = context.resolve_account(account_ref)
    result = context.bill_reports.enqueue(context.user, account_id, period, uuid4().hex)
    context.report_events.append(BillReportReadyEvent(data=BillReportReadyData(
        report_id=result["report_id"],
        status="queued",
        period=result["period"],
    )))
    return {"status": "queued", "report_reference": result["report_id"], "period": period}


@tool(args_schema=_BillReportToolInput)
def view_bill_report(account_ref: str | None, period: str,
                     runtime: ToolRuntime[AgentContext, AgentState]) -> dict:
    """Open the latest matching saved report, or generate it if absent.

    Use for explicit requests to view/read/open a monthly YYYY-MM or annual YYYY
    bill report. This is distinct from instant category statistics and from the
    explicit generate_bill_report operation. Only an opaque account reference
    supplied by request context may select one account; null means all accounts.
    """
    context = runtime.context
    require(context.bill_reports is not None, "AGENT_CONTEXT_MISSING", "报告服务未配置", 500)
    account_id = context.resolve_account(account_ref)
    result = context.bill_reports.view_or_generate(
        context.user, account_id, period, trace_id=context.trace_id,
    )
    event = BillReportOpenedEvent(data=BillReportOpenedData(
        report_id=result["report_id"],
        period=result["period"],
        status=result["status"],
        generated=result["generated"],
    ))
    context.report_events.append(event)
    return {
        "report_reference": result["report_id"],
        "period": result["period"],
        "status": result["status"],
        "generated": result["generated"],
    }
