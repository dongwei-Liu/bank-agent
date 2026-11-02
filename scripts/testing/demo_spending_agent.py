"""Authenticated read-only model probe. Prints only privacy-safe summaries."""
import argparse
import calendar
from datetime import date
from getpass import getpass
import json
from pathlib import Path
import re
import sys
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/backend'))
from langchain_core.messages import AIMessage, ToolMessage
from langsmith import tracing_context
from openai import APITimeoutError
from agent.context import AgentContext, prepare_account_refs
from agent.graph import build_agent_graph
from clients.fineract import FineractClient
from core.config import get_settings
from core.database import session_factory
from core.errors import DomainError, require
from schemas.agent import AgentQueryContext
from services.account_service import AccountService
from services.analysis_result_service import AnalysisResultService, ModelSummary
from services.auth_service import AuthService
from services.billing_service import BillingService


def month(value):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', value):
        raise argparse.ArgumentTypeError('月份必须为 YYYY-MM')
    year, number = map(int, value.split('-'))
    if not 1900 <= year <= 9998:
        raise argparse.ArgumentTypeError('年份超出范围')
    return date(year, number, 1), date(year, number, calendar.monthrange(year, number)[1])


def timeout_seconds(value):
    seconds = int(value)
    if not 1 <= seconds <= 300:
        raise argparse.ArgumentTypeError('模型超时必须在 1 到 300 秒之间')
    return seconds


def inspect_result(result, expected, query='statistics'):
    messages = result.get('messages', [])
    calls = [call for m in messages if isinstance(m, AIMessage) for call in m.tool_calls]
    require(len(calls) == 1, 'DEMO_TOOL_CALL', f'必须实际调用目标工具且仅调用一次；实际为 {len(calls)} 次')
    call = calls[0]
    require(call['name'] == 'get_spending_' + query and call['args'] == expected,
            'DEMO_TOOL_ARGS', '工具或账户、日期参数不符合预期')
    outputs = [m for m in messages if isinstance(m, ToolMessage) and m.tool_call_id == call['id']]
    require(len(outputs) == 1 and outputs[0].status == 'success', 'DEMO_TOOL_RESULT', '没有成功的工具结果')
    try:
        summary = ModelSummary.model_validate_json(outputs[0].content)
        require(summary.kind == query, 'DEMO_RESULT_SHAPE', '摘要类型不符')
    except (ValueError, TypeError) as exc:
        raise DomainError('DEMO_RESULT_SHAPE', '工具摘要不符合隐私契约') from exc
    require(isinstance(messages[-1], AIMessage) and not messages[-1].tool_calls and bool(messages[-1].content),
            'DEMO_NO_ANSWER', '没有最终回答')
    return call, summary.model_dump(), messages[-1].content, sum(isinstance(m, AIMessage) for m in messages)


def print_model_diagnostics(result):
    for message in result.get('messages', []):
        if isinstance(message, AIMessage):
            print(json.dumps({'finish_reason': message.response_metadata.get('finish_reason'),
                              'tool_count': len(message.tool_calls)}, ensure_ascii=False), file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--username', required=True)
    parser.add_argument('--account-id', type=int)
    parser.add_argument('--period', type=month, required=True)
    parser.add_argument('--query', choices=['statistics', 'anomalies'], default='statistics')
    parser.add_argument('--model-timeout', type=timeout_seconds, default=60)
    args = parser.parse_args()
    settings = get_settings()
    require(settings.siliconflow_api_key and settings.siliconflow_model, 'MODEL_CONFIG', '请配置模型')
    client = FineractClient(settings)
    try:
        with session_factory()() as db:
            auth = AuthService(db)
            tokens = auth.login(args.username, getpass('登录密码：'))
            user, session = auth.authenticate(tokens['access_token'])
            try:
                require(user.tenant == settings.fineract_tenant, 'TENANT_MISMATCH', '身份租户不匹配', 403)
                accounts = AccountService(client)
                choices = accounts.list_accounts(user)
                require(choices, 'NO_ACCOUNTS', '本人没有合格账户')
                # Only local account selection; no banking data is printed into model diagnostics.
                account_id = args.account_id or choices[0].id
                start, end = args.period
                selection = AgentQueryContext(account_id=account_id, period=start.strftime('%Y-%m'))
                refs, selected, _ = prepare_account_refs(user, accounts, selection, '')
                private = AnalysisResultService(db, accounts, settings)
                context = AgentContext(user=user, account_service=accounts, billing_service=BillingService(db, client, settings),
                                       query_context=selection, private_results=private, account_refs=refs, selected_ref=selected)
                prompt = f'查询所选账户从 {start} 到 {end} 的' + ('消费分类统计' if args.query == 'statistics' else '异常消费候选')
                started = perf_counter()
                try:
                    with tracing_context(enabled=False):
                        result = build_agent_graph(('insights',), model_timeout_seconds=args.model_timeout).invoke(
                            {'messages': [('user', prompt)], 'events': []}, context=context,
                            config={'recursion_limit': 4, 'max_concurrency': 1})
                except APITimeoutError as exc:
                    raise DomainError('DEMO_MODEL_TIMEOUT', f'模型请求超时（设置 {args.model_timeout} 秒）', 503) from exc
                call, summary, answer, count = inspect_result(result, {'account_ref': selected, 'from_date': str(start), 'to_date': str(end)}, args.query)
                db.commit()
                print('调用链检查通过：', call['name'], json.dumps(summary, ensure_ascii=False))
                print(private.render(answer))
                print(f'模型返回 {count} 次，耗时 {perf_counter() - started:.2f} 秒；精确结果仅通过授权前端读取。')
            finally:
                db.rollback()
                auth.logout(user, session)
    finally:
        client.close()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'测试失败：{type(exc).__name__}', file=sys.stderr)
        raise SystemExit(1)
