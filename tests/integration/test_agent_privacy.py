"""Privacy contracts, authorization, lifecycle and frontend channel semantics."""
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from sqlalchemy import select

import agent.graph as graph_module
from langsmith import get_tracing_context
from agent.context import prepare_account_refs, AgentContext, query_context_prompt, routing_message
from api.agent import get_agent_graph_factory, get_agent_router
from core.errors import DomainError
from core.security import now
from models import AnalysisResult, AnomalyReview, Audit, BillReport, BillReportJob, User
from schemas.agent import AgentQueryContext
from services.account_service import AccountService
from services.analysis_result_service import AnalysisResultService
from services.billing_service import BillingService


class PrivateModel:
    def __init__(self, tools): self.tools, self.calls, self.summary_ids = tools, [], []
    def bind_tools(self, tools): return self
    def invoke(self, messages):
        assert get_tracing_context()["enabled"] is False
        self.calls.append(messages)
        if len(self.calls)==1:
            data=json.loads(messages[0].content.rsplit('\n',1)[1])
            ref=data['selection']['account_ref'] if data.get('selection') else next(iter(data['available_account_refs']),None)
            return AIMessage(content='',tool_calls=[{'name':name,'id':f'q-{i}', 'args':{} if name=='get_my_balance' else {'account_ref':None if all_ else ref,'from_date':'2026-09-01','to_date':'2026-09-30'}} for i,(name,all_) in enumerate(self.tools)])
        outputs=[m for m in messages if isinstance(m,ToolMessage)]
        self.summary_ids=[json.loads(m.content)['analysis_id'] for m in outputs]
        # Model invents unsafe data: API must not relay it.
        return AIMessage(content='余额是999999.99元，商户PRIVATE-MERCHANT已确认欺诈')


def install(bank,monkeypatch,tools):
    model=PrivateModel(tools)
    monkeypatch.setattr(graph_module,'ChatOpenAI',lambda **kw:model)
    app=bank['http'].app
    app.dependency_overrides[get_agent_router]=lambda:lambda *a,**kw:tuple(['accounts'] if all(t[0]=='get_my_balance' for t in tools) else ['accounts','insights'])
    app.dependency_overrides[get_agent_graph_factory]=lambda:graph_module.build_agent_graph
    return model


@pytest.mark.parametrize('tools',[
    [('get_my_balance',True)], [('get_spending_statistics',False)], [('get_spending_statistics',True)],
    [('get_spending_anomalies',False)], [('get_spending_anomalies',True)],
    [('get_my_balance',True),('get_spending_statistics',True),('get_spending_anomalies',True)],
])
def test_private_http_model_boundary_and_exact_results(bank,monkeypatch,tools,caplog,capsys):
    core=bank['core']; core.balances[1]=Decimal('728391.67')
    core.tx[1]=[{'id':i,'accountId':1,'date':[2026,9,10],'amount':'4321.98','currency':{'code':'CNY'},'entryType':'DEBIT','transactionType':{'withdrawal':True},'note':'[Merchant] PRIVATE-MERCHANT'} for i in range(1,7)]
    model=install(bank,monkeypatch,tools)
    try:
        response=bank['http'].post('/api/agent/messages',headers=bank['headers']['alice'],json={'message':'查询所选账户','query_context':{'account_id':1,'period':'2026-09'}})
        assert response.status_code==200,response.text
        body=response.json()
        assert len(body['events'])==len(tools)
        assert '999999' not in body['message'] and 'PRIVATE-MERCHANT' not in body['message']
        model_visible=str(model.calls)
        for sentinel in ('728391.67','4321.98','PRIVATE-MERCHANT','25931.88'):
            assert sentinel not in model_visible
        assert '"account_id"' not in model_visible
        for event in body['events']:
            assert set(event)=={'type','data'} and event['type']=='ANALYSIS_READY'
            assert set(event['data'])=={'analysis_id','kind'}
            id_=event['data']['analysis_id']
            private=bank['http'].get('/api/agent/analyses/'+id_,headers=bank['headers']['alice'])
            assert private.status_code==200 and private.headers['cache-control']=='no-store'
            data=private.json()['data']
            if event['data']['kind']=='balance': assert Decimal(data['total'])==Decimal('728391.67')
            if event['data']['kind']=='statistics': assert Decimal(data['totals']['expense'])==Decimal('25931.88')
            if event['data']['kind']=='anomalies': assert data['items'][0]['evidence']['merchant']=='PRIVATE-MERCHANT'
            assert bank['http'].get('/api/agent/analyses/'+id_,headers=bank['headers']['bob']).status_code==404
        with bank['db']() as db:
            record=db.scalar(select(Audit).where(Audit.trace_id==body['trace_id']))
            assert record and all(s not in str(record.data) for s in ('4321.98','PRIVATE-MERCHANT','728391.67'))
            assert 'account_id' not in str(record.data['tool_calls'])
        console=capsys.readouterr()
        for sentinel in ('728391.67','4321.98','PRIVATE-MERCHANT','25931.88'):
            assert sentinel not in caplog.text+console.out+console.err
    finally: bank['http'].app.dependency_overrides.clear()


def test_result_expiration_revocation_and_not_found(bank):
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]); service=AnalysisResultService(db,AccountService(bank['core']),bank['settings'])
        summary=service.store(user,'balance',{'total':'12','currency':'CNY','account_count':1,'complete':True},[1]);db.commit()
        id_=summary['analysis_id']
        bank['core'].owners[1]=2
        with pytest.raises(DomainError) as revoked: service.get(user,id_)
        assert revoked.value.code=='ACCOUNT_NOT_FOUND'
        bank['core'].owners[1]=1
        row=db.get(AnalysisResult,id_);row.expires_at=now()-timedelta(seconds=1);db.commit()
        with pytest.raises(DomainError) as expired:service.get(user,id_)
        assert expired.value.status==410
    assert bank['http'].get('/api/agent/analyses/'+id_,headers=bank['headers']['bob']).status_code==404
    assert bank['http'].get('/api/agent/analyses/nonexistent',headers=bank['headers']['alice']).status_code==404
    assert bank['http'].get('/api/agent/analyses/'+id_).status_code==401
    expired_http = bank['http'].get('/api/agent/analyses/'+id_,headers=bank['headers']['alice'])
    assert expired_http.status_code==410 and expired_http.headers['cache-control']=='no-store'
    assert bank['http'].get('/api/agent/analyses/'+id_).headers['cache-control']=='no-store'


def statistical_payload(count,category='餐饮'):
    return {'transaction_count':count,'categories':{category:'93847.52'},'totals':{'expense':'93847.52'},
            '_privacy_expense_count':count,'_privacy_category_counts':{category:count}}


@pytest.mark.parametrize('count,category,limited,code',[(1,'餐饮',True,None),(5,'餐饮',False,'DINING'),(5,'SECRET-merchant',False,'OTHER')])
def test_summary_sample_and_category_policy(bank,count,category,limited,code):
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]);s=AnalysisResultService(db,AccountService(bank['core']),bank['settings'])
        result=s.store(user,'statistics',statistical_payload(count,category),[1],date(2026,9,1),date(2026,9,30))
        assert (result['status']=='limited')==limited and result['main_category']==code
        assert '93847.52' not in str(result) and 'SECRET-merchant' not in str(result)


def test_privacy_quota_repeat_queries_and_small_windows(bank):
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]);s=AnalysisResultService(db,AccountService(bank['core']),bank['settings'])
        for year in range(2000,2010):
            assert s.store(user,'statistics',statistical_payload(5),[1],date(year,9,1),date(year,9,30))['status']=='ready'
        assert s.store(user,'statistics',statistical_payload(5),[1],date(2010,9,1),date(2010,9,30))['status']=='limited'
        assert s.store(user,'statistics',statistical_payload(5),[1],date(2000,9,1),date(2000,9,30))['status']=='ready'
        assert s.store(user,'statistics',statistical_payload(5),[1],date(2026,9,10),date(2026,9,11))['status']=='limited'
        assert len(db.scalars(select(AnalysisResult)).all())==13


def test_context_and_explicit_account_aliases(bank):
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]); accounts=AccountService(bank['core'])
        refs,selected,text=prepare_account_refs(user,accounts,AgentQueryContext(account_id=1,period='2026-09'),'账户id1在9月份的消费情况')
        context=AgentContext(user=user,account_service=accounts,query_context=AgentQueryContext(account_id=1,period='2026-09'),account_refs=refs,selected_ref=selected,current_date=date(2026,10,26))
        prompt=query_context_prompt(context)
        assert '账户id1' not in text and selected in text and selected in prompt
        assert '"account_id"' not in prompt
        assert '"last_30_days": {"from_date": "2026-10-02", "to_date": "2026-10-31"}' in prompt
        assert '"bill_report_periods": {"this_month": "2026-10", "last_month": "2026-09", "this_year": "2026", "last_year": "2025"}' in prompt
        with pytest.raises(DomainError):prepare_account_refs(user,accounts,None,'账户2消费')
        period_request='生成我所有账户 2025 年 9 月账单报告'
        no_refs, no_selection, unchanged=prepare_account_refs(user,accounts,None,period_request)
        assert no_refs == {} and no_selection is None and unchanged == period_request
        assert routing_message('查询账户 583921 的消费')=='查询所选账户 的消费'
        assert routing_message('用户输入金额123.45及备注')=='用户输入金额123.45及备注'


def test_failed_graph_rolls_back_private_results(bank,monkeypatch):
    class FailingModel(PrivateModel):
        def invoke(self,messages):
            if self.calls:raise TimeoutError('UNTRUSTED-SENSITIVE-DETAIL')
            return super().invoke(messages)
    model=FailingModel([('get_my_balance',True)])
    monkeypatch.setattr(graph_module,'ChatOpenAI',lambda **kw:model)
    app=bank['http'].app
    app.dependency_overrides[get_agent_router]=lambda:lambda *a,**kw:('accounts',)
    app.dependency_overrides[get_agent_graph_factory]=lambda:graph_module.build_agent_graph
    try:
        response=bank['http'].post('/api/agent/messages',headers=bank['headers']['alice'],json={'message':'余额'})
        assert response.status_code==503 and 'SENSITIVE' not in response.text
        with bank['db']() as db:assert db.scalars(select(AnalysisResult)).all()==[]
    finally:app.dependency_overrides.clear()


@pytest.mark.parametrize('domains',[(),('insights',)])
def test_no_tool_cannot_claim_facts(bank,domains):
    class NoTool:
        def invoke(self,*a,**kw):return {'messages':[AIMessage(content='余额123456.78')],'events':[]}
    app=bank['http'].app
    app.dependency_overrides[get_agent_router]=lambda:lambda *a,**kw:domains
    app.dependency_overrides[get_agent_graph_factory]=lambda:lambda *a:NoTool()
    try:
        result=bank['http'].post('/api/agent/messages',headers=bank['headers']['alice'],json={'message':'查余额'})
        assert result.status_code==200 and '123456.78' not in result.text
        assert result.json()['events']==[]
    finally:app.dependency_overrides.clear()


@pytest.mark.parametrize('field',['user_id','enabled_domains','system_prompt'])
def test_client_cannot_choose_identity_or_authority(bank,field):
    result=bank['http'].post('/api/agent/messages',headers=bank['headers']['alice'],json={'message':'查询',field:'forged'})
    assert result.status_code==422


@pytest.mark.parametrize('failure',['cross_user','upstream','routing'])
def test_http_failures_have_safe_audit_and_no_private_result(bank,monkeypatch,failure):
    from clients.fineract import FineractUnavailableError
    model=install(bank,monkeypatch,[('get_spending_anomalies',False)])
    app=bank['http'].app
    if failure=='upstream':
        def unavailable(*a,**kw):raise FineractUnavailableError(503,'核心银行连接不可用')
        monkeypatch.setattr(bank['core'],'search_transactions',unavailable)
    if failure=='routing':
        def fail(*a,**kw):raise DomainError('AGENT_ROUTING_FAILED','路由暂不可用',503)
        app.dependency_overrides[get_agent_router]=lambda:fail
    try:
        result=bank['http'].post('/api/agent/messages',headers=bank['headers']['alice'],json={'message':'查询异常','query_context':{'account_id':2 if failure=='cross_user' else 1,'period':'2026-09'}})
        assert result.status_code==(404 if failure=='cross_user' else 503)
        assert len(model.calls)<=1 and 'events' not in result.json()
        with bank['db']() as db:
            assert not db.scalars(select(AnalysisResult)).all()
            assert db.scalar(select(Audit).where(Audit.event=='AGENT_MESSAGE_FAILED'))
    finally:app.dependency_overrides.clear()


def test_same_owner_can_refresh_and_read_from_a_different_session(bank):
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]);s=AnalysisResultService(db,AccountService(bank['core']),bank['settings'])
        summary=s.store(user,'balance',{'total':'12','currency':'CNY','account_count':1,'complete':True},[1]);db.commit()
    client=bank['http']
    login=client.post('/api/auth/login',json={'username':'alice','password':'test-password-123'}).json()
    refreshed=client.post('/api/auth/refresh',json={'refresh_token':login['refresh_token']}).json()
    headers={'Authorization':'Bearer '+refreshed['access_token']}
    assert client.get('/api/agent/analyses/'+summary['analysis_id'],headers=headers).status_code==200
    assert client.post('/api/auth/logout',headers=headers).status_code==200
    assert client.get('/api/agent/analyses/'+summary['analysis_id'],headers=headers).status_code==401


def test_frontend_shortcut_account_id_never_reaches_router_or_execution_model(bank,monkeypatch):
    core=bank['core'];core.owners[583921]=1;core.balances[583921]=Decimal('0');core.tx[583921]=[]
    model=install(bank,monkeypatch,[('get_spending_statistics',False)])
    seen=[]
    def route(message,**kw):seen.append(message);return ('insights',)
    app=bank['http'].app;app.dependency_overrides[get_agent_router]=lambda:route
    try:
        response=bank['http'].post('/api/agent/messages',headers=bank['headers']['alice'],json={'message':'查询账户 583921 在2026年9月的消费统计','query_context':{'account_id':583921,'period':'2026-09'}})
        assert response.status_code==200,response.text
        assert seen and '583921' not in str(seen) and '583921' not in str(model.calls)
        event=response.json()['events'][0]['data']
        private=bank['http'].get('/api/agent/analyses/'+event['analysis_id'],headers=bank['headers']['alice'])
        assert private.json()['data']['account_ids']==[583921]
    finally:app.dependency_overrides.clear()


def test_subscription_observation_never_enters_model_or_trace(bank,monkeypatch,caplog):
    from datetime import datetime, timezone
    from models import Subscription, Merchant
    with bank['db']() as db:
        merchant=Merchant(external_key='private-observation',name='PRIVATE-OBSERVATION-MERCHANT')
        db.add(merchant);db.flush()
        db.add(Subscription(user_id=bank['ids'][0],merchant_id=merchant.id,status='VERIFIED',cadence='MONTHLY',
            expected_amount=Decimal('789.43'),evidence={},verified_at=datetime(2026,1,1,tzinfo=timezone.utc)))
        db.commit()
    bank['core'].tx[1]=[{'id':i,'accountId':1,'date':[2026,m,1],'amount':'789.43','currency':{'code':'CNY'},'entryType':'DEBIT',
        'transactionType':{'withdrawal':True},'note':'[Merchant] PRIVATE-OBSERVATION-MERCHANT'} for i,m in enumerate([6,7,8],1)]
    model=install(bank,monkeypatch,[('get_spending_anomalies',False)])
    try:
        response=bank['http'].post('/api/agent/messages',headers=bank['headers']['alice'],json={'message':'查询所选账户异常','query_context':{'account_id':1,'period':'2026-09'}})
        assert response.status_code==200
        id_=response.json()['events'][0]['data']['analysis_id']
        data=bank['http'].get('/api/agent/analyses/'+id_,headers=bank['headers']['alice']).json()['data']
        assert any(i.get('observation_kind')=='expected_charge_not_observed' and not i['transactions'] for i in data['items'])
        assert 'PRIVATE-OBSERVATION-MERCHANT' not in str(model.calls)+caplog.text
        assert '789.43' not in str(model.calls)+caplog.text
        assert 'SUMMARY_LIMITED' in str(model.calls)
    finally:bank['http'].app.dependency_overrides.clear()


@pytest.mark.parametrize('status,code', [('ready', 'ML_AVAILABLE'), ('no_model', 'RULES_ONLY')])
def test_execution_metadata_retained_but_not_narrated(bank, status, code):
    with bank['db']() as db:
        user = db.get(User, bank['ids'][0])
        service = AnalysisResultService(db, AccountService(bank['core']), bank['settings'])
        detection = {'status': status, 'partial': True, 'provisional': True,
                     'capabilities': {'SPENDING_SURGE_V1': {'status': 'partial', 'sources': ['rule']}}}
        items = [{'rule': 'IFOREST_V1', 'evidence': {'score': 0.73}, 'sources': ['ml']}]
        summary = service.store(user, 'anomalies', {'expense_count': 100, 'items': items, 'detection': detection},
                                [1], date(2026, 9, 1), date(2026, 9, 30))
        assert code in summary['insight_codes']
        assert 'PARTIAL_DETECTION' in summary['insight_codes']
        data = service.get(user, summary['analysis_id'])['data']
        assert data['detection'] == detection
        assert [{key: value for key, value in item.items() if key != 'current_review_status'}
                for item in data['items']] == items
        assert all(item['current_review_status'] == 'unreviewed' for item in data['items'])
        for proposal in ('invalid free text', json.dumps({'insight_codes': [code]})):
            message = service.render(proposal)
            assert all(word not in message for word in ('机器学习', '规则检测', '部分检测', '模型可用'))
            assert '候选' in message and '结果' in message


def test_private_anomaly_result_keeps_snapshot_and_overlays_current_review_per_user(bank):
    with bank['db']() as db:
        alice = db.get(User, bank['ids'][0])
        bob = db.get(User, bank['ids'][1])
        service = AnalysisResultService(db, AccountService(bank['core']), bank['settings'])
        item = {'anomaly_key': 'shared-shaped-key', 'status': 'unreviewed',
                'rule': 'LARGE_V1', 'evidence': {'amount': '18.22'}}
        alice_summary = service.store(alice, 'anomalies', {
            'expense_count': 20, 'items': [item], 'detection': {'status': 'no_model'},
        }, [1], date(2026, 9, 1), date(2026, 9, 30))
        bob_summary = service.store(bob, 'anomalies', {
            'expense_count': 20, 'items': [item], 'detection': {'status': 'no_model'},
        }, [2], date(2026, 9, 1), date(2026, 9, 30))
        db.add(AnomalyReview(user_id=alice.id, anomaly_key='shared-shaped-key', status='verified'))
        db.commit()

        alice_data = service.get(alice, alice_summary['analysis_id'])['data']['items'][0]
        bob_data = service.get(bob, bob_summary['analysis_id'])['data']['items'][0]
        assert alice_data['status'] == 'unreviewed'  # immutable detection snapshot
        assert alice_data['current_review_status'] == 'verified'
        assert bob_data['status'] == 'unreviewed'
        assert bob_data['current_review_status'] == 'unreviewed'
        with pytest.raises(DomainError) as error:
            service.get(bob, alice_summary['analysis_id'])
        assert error.value.status == 404


def test_agent_report_request_returns_only_opaque_background_reference(bank, monkeypatch):
    class ReportModel:
        def __init__(self): self.calls = 0
        def bind_tools(self, tools): return self
        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(content='', tool_calls=[{'name': 'generate_bill_report', 'id': 'report-1',
                    'args': {'account_ref': None, 'period': '2025-09'}}])
            return AIMessage(content='模型杜撰了精确数据，不应展示。')

    model = ReportModel()
    monkeypatch.setattr(graph_module, 'ChatOpenAI', lambda **kw: model)
    bank['http'].app.dependency_overrides[get_agent_router] = lambda: lambda *a, **kw: ['insights']
    bank['http'].app.dependency_overrides[get_agent_graph_factory] = lambda: graph_module.build_agent_graph
    try:
        response = bank['http'].post('/api/agent/messages', headers=bank['headers']['alice'],
            json={'message': '生成我所有账户 2025 年 9 月账单报告'})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['message'] == '账单报告已提交后台生成，完成后可在报告页查看。'
        assert len(body['events']) == 1 and body['events'][0]['type'] == 'BILL_REPORT_READY'
        assert body['events'][0]['data']['period'] == '2025-09'
        assert '精确数据' not in body['message']
        assert model.calls == 1  # deterministic report acknowledgement avoids a second model call
        with bank['db']() as db:
            report = db.get(BillReport, body['events'][0]['data']['report_id'])
            assert report and report.payload['account_scope'] == 'all_accounts'
            assert db.scalar(select(BillReportJob).where(BillReportJob.report_id == report.id)) is not None
    finally:
        bank['http'].app.dependency_overrides.clear()


def test_agent_natural_language_opens_or_queues_exact_bill_report(bank, monkeypatch):
    class ViewModel:
        def __init__(self):
            self.bound_tools = []
            self.invocations = 0

        def bind_tools(self, tools):
            self.bound_tools = [tool.name for tool in tools]
            return self

        def invoke(self, messages):
            self.invocations += 1
            raise AssertionError('report view uses deterministic parsing and must not call the model')

    model = ViewModel()
    monkeypatch.setattr(graph_module, 'ChatOpenAI', lambda **kw: model)
    app = bank['http'].app
    app.dependency_overrides[get_agent_router] = lambda: lambda *a, **kw: ('insights',)
    app.dependency_overrides[get_agent_graph_factory] = lambda: graph_module.build_agent_graph
    try:
        headers = bank['headers']['alice']
        first = bank['http'].post('/api/agent/messages', headers=headers, json={
            'message': '查看我的年度账单报告',
            'query_context': {'account_id': 1, 'period': '2026-08'},
        })
        assert first.status_code == 200, first.text
        first_body = first.json()
        assert first_body['message'] == '未找到对应报告，已开始生成；你可以在结果卡查看进度。'
        assert first_body['events'][0]['type'] == 'BILL_REPORT_OPENED'
        first_event = first_body['events'][0]['data']
        assert first_event['period'] == '2026'
        assert first_event['status'] == 'queued' and first_event['generated'] is True

        second = bank['http'].post('/api/agent/messages', headers=headers, json={
            'message': '看看2026年的年度账单报告',
            'query_context': {'account_id': 1, 'period': '2026-09'},
        })
        assert second.status_code == 200, second.text
        second_body = second.json()
        assert second_body['message'] == '已找到对应报告任务，正在生成；结果卡会显示进度。'
        assert second_body['events'][0]['type'] == 'BILL_REPORT_OPENED'
        second_event = second_body['events'][0]['data']
        assert second_event['report_id'] == first_event['report_id']
        assert second_event['period'] == '2026'
        assert second_event['generated'] is False
        assert model.bound_tools == [
            'get_spending_statistics', 'get_spending_anomalies',
            'generate_bill_report', 'view_bill_report',
        ]
        assert model.invocations == 0

        with bank['db']() as db:
            report = db.get(BillReport, first_event['report_id'])
            assert report.payload['account_scope'] == 'single_account'
            assert report.payload['scope_account_id'] == 1
            opened_audits = db.scalars(select(Audit).where(
                Audit.event == 'BILL_REPORT_OPENED',
                Audit.trace_id.in_([first_body['trace_id'], second_body['trace_id']]),
            )).all()
            assert len(opened_audits) == 2
            assert {row.data['generated'] for row in opened_audits} == {False, True}
    finally:
        app.dependency_overrides.clear()
