"""Real ToolNode/Service integration with private assertions, never raw ToolMessage facts."""
import json
import runpy
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.prebuilt.tool_node import ToolInvocationError
from pydantic import ValidationError
from sqlalchemy import select

import agent.graph as graph_module
from agent.context import AgentContext
from agent.registry import resolve_agent
from agent.tools.insights import SpendingStatisticsInput, get_spending_statistics, get_spending_anomalies
from clients.fineract import FineractUnavailableError
from core.errors import DomainError
from models import AnalysisResult, Annotation, Category, LoginSession, User
from services.account_service import AccountService
from services.analysis_result_service import AnalysisResultService, ModelSummary
from services.billing_service import BillingService

REF = 'a' * 32
OTHER = 'b' * 32
ARGS = {'account_ref': REF, 'from_date': '2026-09-01', 'to_date': '2026-09-30'}


class ScriptedModel:
    tool_name = 'get_spending_statistics'
    def __init__(self, args):
        self.args, self.calls = args, []
    def bind_tools(self, tools):
        assert [t.name for t in tools] == ['get_spending_statistics', 'get_spending_anomalies', 'generate_bill_report', 'view_bill_report']
        return self
    def invoke(self, messages):
        self.calls.append(messages)
        if len(self.calls) == 1:
            return AIMessage(content='', tool_calls=[{'name': self.tool_name, 'args': self.args, 'id': 'query'}])
        assert isinstance(messages[-1], ToolMessage)
        summary = ModelSummary.model_validate_json(messages[-1].content)
        return AIMessage(content=json.dumps({'insight_codes': summary.insight_codes}))


class AnomalyModel(ScriptedModel):
    tool_name = 'get_spending_anomalies'


def transaction(id_, amount='10', **extra):
    return {'id': id_, 'accountId': 1, 'date': [2026, 9, 10], 'amount': amount,
            'currency': {'code': 'CNY'}, 'entryType': 'DEBIT', 'transactionType': {'withdrawal': True}, **extra}


def invoke(bank, monkeypatch, args=None, billing=True, message='分析所选账户在2026年9月的消费', model_type=ScriptedModel):
    model = model_type(ARGS if args is None else args)
    monkeypatch.setattr(graph_module, 'ChatOpenAI', lambda **kw: model)
    with bank['db']() as db:
        private = AnalysisResultService(db, AccountService(bank['core']), bank['settings'])
        context = AgentContext(user=db.get(User, bank['ids'][0]), account_service=AccountService(bank['core']),
            billing_service=BillingService(db, bank['core'], bank['settings']) if billing else None,
            private_results=private, account_refs={REF: 1, OTHER: 2}, selected_ref=REF)
        try:
            result = graph_module.build_agent_graph(('insights',)).invoke(
                {'messages': [HumanMessage(content=message)], 'events': []}, context=context,
                config={'recursion_limit': 4, 'max_concurrency': 1})
        except Exception:
            assert len(model.calls) == 1
            raise
        assert len(model.calls) == 2
        summary = ModelSummary.model_validate_json(next(m.content for m in result['messages'] if isinstance(m, ToolMessage)))
        data = db.get(AnalysisResult, summary.analysis_id).payload
        assert set(summary.model_dump()) == {'analysis_id','kind','status','insight_codes','main_category'}
        assert result['events'] == []
        return data, result


@pytest.mark.parametrize('tool', [get_spending_statistics, get_spending_anomalies])
def test_agent_insights_schema_and_domain_isolation(tool):
    schema = tool.tool_call_schema.model_json_schema()
    assert set(schema['properties']) == set(ARGS)
    assert 'account_ref' in schema['required']
    assert SpendingStatisticsInput.model_validate({**ARGS, 'account_ref': None}).account_ref is None
    assert [t.name for t in resolve_agent(('accounts',)).tools] == ['get_my_balance', 'get_my_transactions']


@pytest.mark.parametrize('changes', [
    {'account_ref': 1}, {'account_ref': True}, {'account_ref': 'bank-123'},
    {'from_date':'2026-02-30'}, {'from_date':'2026-10-01'},
    {'user_id':'victim'}, {'account_ids':[1,2]}, {'account_id':1},
])
def test_agent_insights_rejects_invalid_input(changes):
    with pytest.raises(ValidationError):
        SpendingStatisticsInput.model_validate({**ARGS, **changes})


def test_agent_insights_rejects_missing_scope():
    with pytest.raises(ValidationError):
        SpendingStatisticsInput.model_validate({k:v for k,v in ARGS.items() if k != 'account_ref'})


def test_agent_insights_graph_classification_and_totals(bank, monkeypatch):
    bank['core'].transfers[1] = {'fromAccount':{'id':1},'toAccount':{'id':2}}
    bank['core'].tx[1] = [transaction(i) for i in range(1,206)] + [
        transaction(206, '999', reversed=True), transaction(207,'500',transfer={'id':1})]
    with bank['db']() as db:
        category = Category(user_id=bank['ids'][0],name='SENSITIVE-CATEGORY-merchant-583921')
        db.add(category); db.flush()
        db.add(Annotation(user_id=bank['ids'][0],account_id=1,transaction_id=1,category_id=category.id,note='PRIVATE-NOTE-4821'))
        db.commit()
    data,result=invoke(bank,monkeypatch)
    assert data['totals']=={'expense':'2050','transfer':'500'}
    assert data['categories']=={'SENSITIVE-CATEGORY-merchant-583921':'10','未分类':'2040'}
    assert data['transaction_count']==206 and data['snapshot_atomic'] is False
    visible=str(result)
    for sentinel in ('2050','2040','583921','4821','SENSITIVE-CATEGORY'):
        assert sentinel not in visible


@pytest.mark.parametrize('tool_type', [ScriptedModel,AnomalyModel])
def test_agent_insights_empty_period(bank,monkeypatch,tool_type):
    data,_=invoke(bank,monkeypatch,model_type=tool_type)
    assert data.get('items',[])==[]
    if tool_type is ScriptedModel:
        assert data['transaction_count']==0 and data['totals']=={}
    else:
        assert data['detection']['status']=='no_model'


@pytest.mark.parametrize('reference,code', [(OTHER,'ACCOUNT_NOT_FOUND'), ('c'*32,'INVALID_ACCOUNT_REFERENCE')])
def test_agent_insights_cross_user_rejected(bank,monkeypatch,reference,code):
    with pytest.raises(DomainError) as error:
        invoke(bank,monkeypatch,{**ARGS,'account_ref':reference})
    assert error.value.code==code


@pytest.mark.parametrize('kind', [ScriptedModel,AnomalyModel])
@pytest.mark.parametrize('mode', ['unavailable','incomplete'])
def test_agent_insights_upstream_failure(bank,monkeypatch,kind,mode):
    def fail(*a,**kw):
        if mode=='unavailable': raise FineractUnavailableError(503,'核心银行连接不可用')
        return {'items':[transaction(1)],'total':2,'page':0,'page_size':100}
    monkeypatch.setattr(bank['core'],'search_transactions',fail)
    with pytest.raises(FineractUnavailableError if mode=='unavailable' else DomainError):
        invoke(bank,monkeypatch,model_type=kind)


def test_agent_insights_missing_context(bank,monkeypatch):
    with pytest.raises(DomainError) as error: invoke(bank,monkeypatch,billing=False)
    assert error.value.code=='AGENT_CONTEXT_MISSING'


@pytest.mark.parametrize('tool_type',[ScriptedModel,AnomalyModel])
def test_agent_insights_graph_rejects_forged_identity(bank,monkeypatch,tool_type):
    with pytest.raises(ToolInvocationError):
        invoke(bank,monkeypatch,{**ARGS,'user_id':bank['ids'][1]},model_type=tool_type)


@pytest.mark.parametrize('second_amount,second_merchant,count',[('88','Cafe',1),('89','Cafe',0),('88',None,0)])
def test_agent_insights_duplicate_anomalies(bank,monkeypatch,second_amount,second_merchant,count):
    bank['core'].tx[1]=[transaction(1,'88'),transaction(2,second_amount)]
    with bank['db']() as db:
        for id_,merchant in [(1,'Cafe'),(2,second_merchant)]:
            db.add(Annotation(user_id=bank['ids'][0],account_id=1,transaction_id=id_,merchant=merchant))
        db.commit()
    data,result=invoke(bank,monkeypatch,model_type=AnomalyModel)
    assert len(data['items'])==count
    if count:
        item=data['items'][0]
        assert item['rule']=='DUPLICATE_V1' and item['transaction_ids']==[1,2]
        assert item['evidence']['merchant']=='Cafe' and item['candidate_only'] is True
        assert item['status']=='unreviewed'
    assert 'Cafe' not in str(result)


@pytest.mark.parametrize('model_type',[ScriptedModel,AnomalyModel])
def test_agent_all_account_ownership_and_collision(bank,monkeypatch,model_type):
    core=bank['core']; core.owners[4]=1; core.balances[4]=Decimal('0')
    core.tx[1]=[transaction(1,'88',note='[Merchant] Cafe'), transaction(2,'7',reversed=True)]
    core.tx[4]=[transaction(1,'88',accountId=4,note='[Merchant] Cafe')]
    core.tx[2]=[transaction(1,'9999',accountId=2,note='[Merchant] Cafe')]
    core.transfers[88]={'fromAccount':{'id':1},'toAccount':{'id':4}}
    core.tx[1].append(transaction(3,'40',transfer={'id':88}))
    core.tx[4].append(transaction(3,'40',accountId=4,entryType='CREDIT',transfer={'id':88}))
    data,result=invoke(bank,monkeypatch,{**ARGS,'account_ref':None},model_type=model_type)
    assert set(data['account_ids'])=={1,4}
    if model_type is ScriptedModel:
        assert data['totals']['expense']=='176' and data['transaction_count']==4
    else:
        assert len(data['items'])==1
        assert data['items'][0]['transactions']==[{'account_id':1,'transaction_id':1},{'account_id':4,'transaction_id':1}]
    assert '9999' not in str(data) and 'Cafe' not in str(result)


@pytest.mark.parametrize('model_type',[ScriptedModel,AnomalyModel])
def test_agent_all_account_no_accounts(bank,monkeypatch,model_type):
    bank['core'].owners[1]=2
    data,result=invoke(bank,monkeypatch,{**ARGS,'account_ref':None},model_type=model_type)
    assert data['account_ids']==[]
    assert 'NO_ACCOUNTS' in str(result)


@pytest.mark.parametrize('model_type',[ScriptedModel,AnomalyModel])
def test_agent_all_account_partial_failure(bank,monkeypatch,model_type):
    bank['core'].owners[4]=1; bank['core'].balances[4]=Decimal('0'); bank['core'].tx[4]=[]
    original=bank['core'].search_transactions
    def search(id_,*a,**kw):
        if id_==4: raise FineractUnavailableError(503,'第二账户不可用')
        return original(id_,*a,**kw)
    monkeypatch.setattr(bank['core'],'search_transactions',search)
    with pytest.raises(FineractUnavailableError):
        invoke(bank,monkeypatch,{**ARGS,'account_ref':None},model_type=model_type)


def test_agent_insights_model_timeout_configuration(monkeypatch):
    options=[]
    def factory(**kw): options.append(kw); return ScriptedModel(ARGS)
    monkeypatch.setattr(graph_module,'ChatOpenAI',factory)
    graph_module.build_agent_graph(('insights',)); graph_module.build_agent_graph(('insights',),model_timeout_seconds=120)
    assert [o['timeout'] for o in options]==[20,120]
    assert all(o['max_retries']==0 for o in options)
    for invalid in (0,-1,301,float('nan')):
        with pytest.raises(ValueError): graph_module.build_agent_graph(('insights',),model_timeout_seconds=invalid)


@pytest.mark.parametrize('query',['statistics','anomalies'])
def test_agent_demo_validates_private_summary(query):
    demo=runpy.run_path(str(Path(__file__).resolve().parents[2]/'scripts/testing/demo_spending_agent.py'))
    summary={'analysis_id':'opaque','kind':query,'status':'ready','insight_codes':['DETAILS_READY'],'main_category':None}
    call={'name':'get_spending_'+query,'args':ARGS,'id':'demo'}
    messages=[AIMessage(content='',tool_calls=[call]),ToolMessage(content=json.dumps(summary),tool_call_id='demo'),AIMessage(content='完成')]
    assert demo['inspect_result']({'messages':messages},ARGS,query)[1]==summary
    messages[1]=ToolMessage(content=json.dumps({'totals':{'expense':'123456.78'}}),tool_call_id='demo')
    with pytest.raises(DomainError): demo['inspect_result']({'messages':messages},ARGS,query)
    assert demo['month']('2024-02')==(date(2024,2,1),date(2024,2,29))


@pytest.mark.parametrize('query',['balance','statistics','anomalies'])
@pytest.mark.parametrize('failure',[None,'core','timeout'])
def test_private_cli_authentication_cleanup_and_no_sensitive_output(bank,monkeypatch,capsys,query,failure):
    import httpx
    from openai import APITimeoutError
    script='scripts/development/probe_agent_balance.py' if query=='balance' else 'scripts/testing/demo_spending_agent.py'
    main=runpy.run_path(str(Path(__file__).resolve().parents[2]/script))['main']
    scope=main.__globals__
    settings=bank['settings'].model_copy(update={'siliconflow_api_key':'PRIVATE-API-KEY','siliconflow_model':'test-model'})
    monkeypatch.setitem(scope,'get_settings',lambda:settings)
    monkeypatch.setitem(scope,'session_factory',lambda:bank['db'])
    monkeypatch.setitem(scope,'FineractClient',lambda settings:bank['core'])
    monkeypatch.setitem(scope,'getpass',lambda prompt:'test-password-123')
    monkeypatch.setattr(bank['core'],'close',lambda:None,raising=False)
    argv=[script,'--username','alice']
    if query!='balance':argv+=['--account-id','1','--period','2026-09','--query',query]
    monkeypatch.setattr('sys.argv',argv)
    class CliModel:
        calls=0
        def bind_tools(self,tools):return self
        def invoke(self,messages):
            self.calls+=1
            if failure=='timeout':raise APITimeoutError(request=httpx.Request('POST','https://example.invalid'))
            if self.calls==1:
                prompt=json.loads(messages[0].content.rsplit('\n',1)[1])
                args={} if query=='balance' else {**ARGS,'account_ref':prompt['selection']['account_ref']}
                return AIMessage(content='',tool_calls=[{'name':'get_my_balance' if query=='balance' else 'get_spending_'+query,'args':args,'id':'cli'}])
            return AIMessage(content='PRIVATE-MERCHANT invented 728391.67')
    model=CliModel()
    monkeypatch.setattr(graph_module,'ChatOpenAI',lambda **kw:model)
    bank['core'].balances[1]=Decimal('728391.67')
    bank['core'].tx[1]=[transaction(1,'4321.98',note='[Merchant] PRIVATE-MERCHANT'),transaction(2,'4321.98',note='[Merchant] PRIVATE-MERCHANT')]
    if failure=='core':
        def fail(*a,**kw):raise FineractUnavailableError(503,'不可用')
        monkeypatch.setattr(bank['core'],'get_savings_account' if query=='balance' else 'search_transactions',fail)
    if failure:
        with pytest.raises((DomainError,FineractUnavailableError,APITimeoutError)):main()
    else:main()
    output=capsys.readouterr()
    for sentinel in ('728391.67','4321.98','PRIVATE-MERCHANT','PRIVATE-API-KEY','test-password-123'):
        assert sentinel not in output.out+output.err
    with bank['db']() as db:
        sessions=db.scalars(select(LoginSession).where(LoginSession.user_id==bank['ids'][0])).all()
        assert len(sessions)==2 and sum(s.revoked for s in sessions)==1
        snapshots=db.scalars(select(AnalysisResult)).all()
        assert bool(snapshots)==(failure is None)
