"""Balance probe through the private result channel; never prints bank facts."""
import argparse
from getpass import getpass
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/backend'))
from langsmith import tracing_context
from agent.context import AgentContext
from agent.graph import build_agent_graph
from clients.fineract import FineractClient
from core.config import get_settings
from core.database import session_factory
from core.errors import require
from services.account_service import AccountService
from services.analysis_result_service import AnalysisResultService
from services.auth_service import AuthService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--username', default='alice')
    parser.add_argument('--allow-external-balance', action='store_true', help='Deprecated: exact balance is never sent')
    args = parser.parse_args()
    settings = get_settings()
    client = FineractClient(settings)
    try:
        with session_factory()() as db:
            auth = AuthService(db)
            tokens = auth.login(args.username, getpass('登录密码：'))
            user, session = auth.authenticate(tokens['access_token'])
            try:
                require(user.tenant == settings.fineract_tenant, 'TENANT_MISMATCH', '身份租户不匹配', 403)
                accounts = AccountService(client)
                private = AnalysisResultService(db, accounts, settings)
                context = AgentContext(user=user, account_service=accounts, private_results=private)
                with tracing_context(enabled=False):
                    result = build_agent_graph(('accounts',), model_timeout_seconds=60).invoke(
                        {'messages': [('user', '我还有多少钱？')], 'events': []}, context=context,
                        config={'recursion_limit': 4, 'max_concurrency': 1})
                if not private.events:
                    raise RuntimeError('No verified balance result')
                db.commit()
                print(private.render(result['messages'][-1].content))
                print('余额私有通道探针通过，未打印或向模型发送精确余额。')
            finally:
                db.rollback()
                auth.logout(user, session)
    finally:
        client.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Probe failed: {type(exc).__name__}', file=sys.stderr)
        raise SystemExit(1)
