"""Synthetic-only training, time boundaries, persistence and fallback validation."""
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import copy
import numpy as np
import pytest
from sqlalchemy import select
from core.security import now, SHANGHAI
from models import User, AnomalyModel, Category
from services.billing_service import BillingService
from services.anomaly_detection_service import AnomalyDetectionService, feature_rows
from scripts.development.init_banking import initialize_billing_categories
from scripts.fineract.demo_history import build_random_history
from scripts.fineract.seed_fineract import CLIENTS


def raw(id_,day,amount='20',account=1):
    return {'id':id_,'accountId':account,'date':[day.year,day.month,day.day],'amount':amount,
            'currency':{'code':'CNY'},'entryType':'DEBIT','transactionType':{'withdrawal':True}}


def setup_history(bank,tmp_path):
    bank['settings'].anomaly_model_directory=str(tmp_path/'models')
    cutoff=date(2026,9,1)
    bank['core'].tx[1]=[raw(i+1,cutoff-timedelta(days=120-i//2),str(18+i%7)) for i in range(240)]
    return cutoff


def test_generated_categories_feed_temporary_model_and_six_detectors(bank,tmp_path):
    as_of=now().astimezone(SHANGHAI).date()-timedelta(days=1)
    start=as_of-timedelta(days=199)
    plan=build_random_history(spec=CLIENTS[0],start=start,days=200,seed=20261024,
        opening_balance=Decimal('30000.00'),include_salary=True)
    bank['settings'].anomaly_model_directory=str(tmp_path/'generated-history-models')
    bank['core'].tx[1]=[
        {'id':i+1,'accountId':1,'date':[day.year,day.month,day.day],
         'amount':str(amount),'currency':{'code':'CNY'},
         'entryType':'CREDIT' if kind=='deposit' else 'DEBIT',
         'transactionType':{kind:True,'code':kind},'note':note}
        for i,(day,kind,amount,_,note) in enumerate(plan.rows)
    ]
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0])
        initialize_billing_categories(db,user)
        db.commit()
        billing=BillingService(db,bank['core'],bank['settings'])
        _,rows=billing.scoped_transactions(user,1,start,as_of)
        expenses=[row for row in rows if row['kind']=='expense']
        categories={row['category'] for row in expenses}
        assert len(categories)>=5 and '未分类' not in categories
        vectors=feature_rows(rows)
        assert len(vectors)>=100
        assert all(len(vector)==13 for _,_,vector in vectors)
        assert any(vector[4] != vector[3] for _,_,vector in vectors)

        model=AnomalyDetectionService(billing).train(user,as_of)
        assert model.metadata_['profiles']['transaction']['status']=='ready'
        assert model.metadata_['profiles']['transaction']['feature_count']==13
        assert (tmp_path/'generated-history-models'/model.metadata_['filename']).is_file()

        report=billing.anomalies(user,1,as_of-timedelta(days=30),as_of,include_metadata=True)
        capabilities=report['detection']['capabilities']
        expected={'SPENDING_SURGE_V1','DAILY_CONCENTRATION_V1','MERCHANT_DEVIATION_V1',
                  'CATEGORY_MIX_SHIFT_V1','SUBSCRIPTION_DEVIATION_V1','ACCOUNT_HABIT_SHIFT_V1'}
        assert set(capabilities)==expected
        assert all(value['status'] in {'completed','partial','skipped'} for value in capabilities.values())
        assert all(isinstance(value['skip_reasons'],list) for value in capabilities.values())
        assert isinstance(report['items'],list)


def test_date_features_have_no_future_or_same_day_leak():
    def enriched(id_,day,amount):
        return {'transaction_id':id_,'account_id':1,'date':day,'amount':amount,'category':'餐饮','kind':'expense','reversed':False}
    rows=[enriched(1,'2026-08-01','10'),enriched(2,'2026-08-02','20'),enriched(3,'2026-08-02','30')]
    before=feature_rows(rows)
    after=feature_rows(rows+[enriched(4,'2026-09-01','999999')])
    assert [r[2] for r in before]==[r[2] for r in after[:3]]
    assert before[1][2][5:10]==before[2][2][5:10]
    assert before[1][2][11:]==before[2][2][11:]
    reverse=feature_rows([rows[0],rows[2],rows[1]])
    assert before==reverse


def test_training_loading_and_scoring_synthetic(bank,tmp_path):
    cutoff=setup_history(bank,tmp_path)
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]);billing=BillingService(db,bank['core'],bank['settings']);service=AnomalyDetectionService(billing)
        row=service.train(user,cutoff);db.commit()
        assert row.status=='ready' and row.metadata_['profiles']['transaction']['fit_count']>=80 and row.metadata_['profiles']['transaction']['calibration_count']>=20
        assert row.metadata_['profiles']['transaction']['calibration_start']>row.metadata_['training_start']
        forest,loaded,status=service.load(user,cutoff)
        assert status=='ready' and loaded.id==row.id
        # Append targets only after fitting: no target participates in model training.
        bank['core'].tx[1]+=[raw(900,cutoff+timedelta(days=1),'20'),raw(901,cutoff+timedelta(days=2),'990000')]
        _,history=billing.scoped_transactions(user,None,cutoff-timedelta(days=90),cutoff+timedelta(days=2))
        vectors=[r[2] for r in feature_rows(history) if r[1]['transaction_id'] in (900,901)]
        scores=-forest['transaction'].score_samples(vectors)
        assert scores[1]>scores[0]
        again,_,_=service.load(user,cutoff)
        np.testing.assert_allclose(again['transaction'].score_samples(vectors),forest['transaction'].score_samples(vectors))
        result=billing.anomalies(user,1,cutoff,cutoff+timedelta(days=3),include_metadata=True)
        assert result['detection']['status']=='ready' and result['detection']['score_is_fraud_probability'] is False
        hit=[r for r in result['items'] if 901 in r['transaction_ids']]
        assert hit and any('IFOREST_V1' in r['detectors'] for r in hit)
        # Same singleton detected by LARGE_V1 and IF is merged, not counted twice.
        assert len([r for r in hit if r['transaction_ids']==[901]])==1 and hit[0]['rule']=='LARGE_V1'
        assert hit[0]['ml_evidence']['severity'] in ('medium','high')
        assert service.load(user,cutoff-timedelta(days=1))[2]=='no_model'
        assert service.load(user,cutoff+timedelta(days=91))[2]=='stale_model'
        other=db.get(User,bank['ids'][1]);assert service.load(other,cutoff)[2]=='no_model'
        db.add(Category(user_id=user.id,name='Changed'));db.commit()
        assert service.load(user,cutoff)[2]=='configuration_changed'


@pytest.mark.parametrize('mutation,expected',[
    ('hash','invalid_model_artifact'),('filename','invalid_model_path'),
    ('version','incompatible_model'),('missing','model_load_failed'),('symlink','invalid_model_path'),
    ('threshold','invalid_model_artifact'),
])
def test_model_artifact_validation(bank,tmp_path,mutation,expected,monkeypatch):
    cutoff=setup_history(bank,tmp_path)
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]);service=AnomalyDetectionService(BillingService(db,bank['core'],bank['settings']))
        row=service.train(user,cutoff);db.commit();meta=copy.deepcopy(row.metadata_)
        target=service.directory()/meta['filename']
        if mutation=='hash':meta['sha256']='0'*64
        elif mutation=='filename':meta['filename']='../outside.skops'
        elif mutation=='version':meta['dependencies']['numpy']='invalid'
        elif mutation=='threshold':meta['profiles']['transaction']['threshold']=-1.0
        elif mutation=='missing':target.unlink()
        else:
            moved=tmp_path/'moved.skops';target.rename(moved)
            try:
                target.symlink_to(moved)
            except OSError as exc:
                if getattr(exc, "winerror", None) == 1314:
                    original_is_symlink = Path.is_symlink
                    monkeypatch.setattr(
                        Path,
                        "is_symlink",
                        lambda path: path == target or original_is_symlink(path),
                    )
                else:
                    raise
        row.metadata_=meta;db.commit()
        assert service.load(user,cutoff)[2]==expected
        result=service.analyze(user,1,cutoff,cutoff)
        assert result['detection']['mode']=='rules_only' and result['detection']['status']==expected


def test_cold_start_does_not_train_on_query(bank,tmp_path,monkeypatch):
    bank['settings'].anomaly_model_directory=str(tmp_path/'models')
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]);service=AnomalyDetectionService(BillingService(db,bank['core'],bank['settings']))
        row=service.train(user,date(2026,9,1));db.commit()
        assert row.status=='insufficient_history' and not (tmp_path/'models').exists()
        monkeypatch.setattr(AnomalyDetectionService,'train',lambda *a,**kw:pytest.fail('query must not train'))
        result=service.analyze(user,None,date(2026,9,1),date(2026,9,30))
        assert result['items']==[] and result['detection']['status']=='insufficient_history'


def test_inference_failure_keeps_rules_and_unknown_types_are_rejected(bank,tmp_path,monkeypatch):
    import skops.io as sio
    cutoff=setup_history(bank,tmp_path)
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]);service=AnomalyDetectionService(BillingService(db,bank['core'],bank['settings']))
        row=service.train(user,cutoff);db.commit()
        bank['core'].tx[1].append(raw(901,cutoff,'990000'))
        forest,_,_=service.load(user,cutoff)
        def fail(*args):raise ValueError('PRIVATE-FEATURES')
        for estimator in forest.values():
            if estimator is not None:monkeypatch.setattr(estimator,'score_samples',fail)
        monkeypatch.setattr(service,'load',lambda *args:(forest,row,'ready'))
        result=service.analyze(user,1,cutoff,cutoff)
        assert result['detection']['status']=='model_inference_failed'
        assert result['detection']['mode']=='rules_only'
        assert any(r['rule']=='LARGE_V1' for r in result['items'])
        assert 'PRIVATE-FEATURES' not in str(result)
        monkeypatch.setattr(sio,'get_untrusted_types',lambda **kw:['external.UnreviewedType'])
        other_service=AnomalyDetectionService(service.billing)
        assert other_service.load(user,cutoff)[2]=='invalid_model_artifact'

# Fixed synthetic cases for the six new capabilities. No core funds are created.
from datetime import datetime, timezone
from services.anomaly_detection_service import DailyIndex, DetectionRun, daily_vector, TYPES, quantile
from models import Merchant, Subscription


def expense(id_, day, amount='20', account=1, category='餐饮', merchant='Cafe'):
    return {'transaction_id': id_, 'account_id': account, 'date': day.isoformat(), 'amount': amount,
            'category': category, 'merchant': merchant, 'kind': 'expense', 'reversed': False}


def daily_history(target, days=120, count=2, **kwargs):
    return [expense(i * count + j + 1, target - timedelta(days=days-i), **kwargs)
            for i in range(days) for j in range(count)]


def detect(rows, day, today=None, accounts=1):
    result = {'capabilities': {}}
    run = DetectionRun('synthetic', [], result, today or day+timedelta(days=1), day, {}, accounts)
    index = DailyIndex(rows)
    run.aggregates(index, day, None)
    run.merchants(index, day)
    run.account_habit(index, index, day, 1)
    run.finish()
    return run


def findings(run, kind):
    return [f for i in run.items for f in i.get('findings', []) if f['type'] == kind]


def test_accumulated_and_concentration_with_nonlarge_distinct_transactions():
    day=date(2026,9,1)
    rows=daily_history(day)+[expense(1000+j,day,str(20+j)) for j in range(6)]
    run=detect(rows,day)
    assert findings(run,'SPENDING_SURGE_V1')
    assert findings(run,'DAILY_CONCENTRATION_V1')
    assert all(Decimal(r['amount'])<1000 for r in rows)
    normal=detect(daily_history(day)+[expense(1000,day)],day)
    assert not findings(normal,'SPENDING_SURGE_V1') and not findings(normal,'DAILY_CONCENTRATION_V1')
    boundary=detect(daily_history(day)+[expense(1000+j,day) for j in range(4)],day)
    assert not findings(boundary,'DAILY_CONCENTRATION_V1')
    assert quantile([Decimal('.10'),Decimal('.20')],.95)==Decimal('.195')
    assert all(b['start'] >= day-timedelta(days=90) and b['end'] < day for b in DailyIndex(rows).baseline(day,7))


@pytest.mark.parametrize('amount,merchant,expected', [('61','Cafe',True),('60','Cafe',False),('6','Cafe',True),('20','New',False),('61','New',True),('999',None,False)])
def test_merchant_rules_boundaries(amount,merchant,expected):
    day=date(2026,9,1)
    run=detect(daily_history(day)+[expense(1000,day,amount,merchant=merchant)],day)
    assert bool(findings(run,'MERCHANT_DEVIATION_V1')) is expected


def test_category_shift_coverage_and_today_deferral():
    day=date(2026,9,1)
    rows=daily_history(day)+[expense(1000+j,day,category='购物') for j in range(5)]
    assert findings(detect(rows,day),'CATEGORY_MIX_SHIFT_V1')
    missing=daily_history(day,category='未分类')+rows[-5:]
    assert not findings(detect(missing,day),'CATEGORY_MIX_SHIFT_V1')
    today=detect(rows,day,today=day)
    assert not findings(today,'CATEGORY_MIX_SHIFT_V1')
    assert not findings(today,'ACCOUNT_HABIT_SHIFT_V1')
    assert all(f['sources']==['rule'] and f['provisional'] for f in findings(today,'SPENDING_SURGE_V1'))
    assert today.metadata['capabilities']['CATEGORY_MIX_SHIFT_V1']['skip_reasons']==['incomplete_day']


def test_rolling_window_crosses_query_start_and_future_is_irrelevant():
    day=date(2026,9,1)
    rows=daily_history(day-timedelta(days=6))+[expense(1000+j,day-timedelta(days=6-j),'90') for j in range(7)]
    run=detect(rows,day)
    hits=findings(run,'SPENDING_SURGE_V1')
    assert any(f['window']['from_date']==day-timedelta(days=6) for f in hits)
    more=rows+[expense(9999,day+timedelta(days=1),'999999')]
    assert run.items==detect(more,day).items
    assert daily_vector(DailyIndex(rows),day)==daily_vector(DailyIndex(more),day)


def test_dormancy_and_single_account_share_skip():
    day=date(2026,9,1)
    rows=daily_history(day-timedelta(days=30))+[expense(1000+j,day) for j in range(3)]
    run=detect(rows,day)
    assert findings(run,'ACCOUNT_HABIT_SHIFT_V1')[0]['evidence']['reason_codes']==['DORMANT_ACCOUNT_RESUMED']
    assert 'share_not_applicable' in run.metadata['capabilities']['ACCOUNT_HABIT_SHIFT_V1']['skip_reasons']


def test_account_share_shift_and_exact_set_merge():
    day=date(2026,9,1)
    a=daily_history(day-timedelta(days=6),amount='10')
    b=daily_history(day-timedelta(days=6),amount='90',account=2)
    a += [expense(1000+j,day-timedelta(days=6-j),'300') for j in range(7)]
    run=DetectionRun('u',[],{'capabilities':{}},day+timedelta(days=1),day,{},2)
    run.account_habit(DailyIndex(a),DailyIndex(a+b),day,1)
    assert any('ACCOUNT_SHARE_SHIFT' in f['evidence']['reason_codes'] for f in findings(run,'ACCOUNT_HABIT_SHIFT_V1'))
    rows=a[-2:]
    for kind in ('SPENDING_SURGE_V1','CATEGORY_MIX_SHIFT_V1'):
        run.add(kind,rows,day-timedelta(days=6),day,['rule'],{'metric':2})
    assert len([i for i in run.items if len(i['transactions'])==2])==1
    run.add('SPENDING_SURGE_V1',rows[:1],day,day,['rule'],{'metric':3})
    assert len([i for i in run.items if len(i['transactions'])==1])==1


def subscription_fixture(db,user,day,cadence='MONTHLY'):
    merchant=Merchant(external_key='synthetic-subscription',name='Stream',category='娱乐')
    db.add(merchant);db.flush()
    sub=Subscription(user_id=user.id,merchant_id=merchant.id,status='VERIFIED',cadence=cadence,
        expected_amount=Decimal('999'),next_charge_at=day+timedelta(days=500),evidence={},
        verified_at=datetime(2020,1,1,tzinfo=timezone.utc))
    db.add(sub);db.flush()
    return sub


def subscription_run(service,sub,rows,start,end,ids=None,today=None):
    run=DetectionRun(sub.user_id,[],{'capabilities':{}},today or end+timedelta(days=1),end,{},2)
    service.subscription_findings(run,[sub],DailyIndex(rows),ids or [1],start,end)
    run.finish()
    return run


@pytest.mark.parametrize('gap,amount,reason',[(30,'110',None),(30,'110.01','PRICE_INCREASE'),(24,'100','EARLY_OR_DENSE_CHARGE'),(36,'100','LATE_CHARGE')])
def test_subscription_price_cycle_and_future_baseline(bank,gap,amount,reason):
    last=date(2026,8,1);target=last+timedelta(days=gap)
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]);service=AnomalyDetectionService(BillingService(db,bank['core'],bank['settings']))
        sub=subscription_fixture(db,user,target)
        rows=[expense(i+1,last-timedelta(days=60-i*30),'100',merchant='Stream') for i in range(3)]
        rows.append(expense(4,target,amount,merchant=' stream '))
        run=subscription_run(service,sub,rows,target,target)
        hit=findings(run,'SUBSCRIPTION_DEVIATION_V1')
        assert bool(hit) is bool(reason)
        if reason:assert reason in hit[0]['evidence']['reason_codes']
        future=rows+[expense(5,target+timedelta(days=30),'777',merchant='Stream')]
        assert run.items==subscription_run(service,sub,future,target,target).items


def test_subscription_missing_payment_other_account_ambiguity_and_status(bank):
    last=date(2026,8,1);cutoff=last+timedelta(days=36)
    rows=[expense(i+1,last-timedelta(days=60-i*30),'100',merchant='Stream') for i in range(3)]
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]);service=AnomalyDetectionService(BillingService(db,bank['core'],bank['settings']))
        sub=subscription_fixture(db,user,cutoff)
        run=subscription_run(service,sub,rows,cutoff,cutoff,today=cutoff)
        assert len(run.items)==1 and run.items[0]['transactions']==[]
        assert run.items[0]['observation_kind']=='expected_charge_not_observed'
        assert run.metadata['provisional']
        # A later cutoff does not create a new key for the same unpaid cycle.
        again=subscription_run(service,sub,rows,cutoff,cutoff+timedelta(days=2))
        assert again.items[0]['anomaly_key']==run.items[0]['anomaly_key']
        paid=rows+[expense(4,last+timedelta(days=30),'100',account=2,merchant='Stream')]
        assert not subscription_run(service,sub,paid,cutoff,cutoff).items
        unknown=rows+[expense(4,cutoff,'100',merchant=None)]
        uncertain=subscription_run(service,sub,unknown,cutoff,cutoff)
        assert not uncertain.items and 'payment_cannot_be_excluded' in uncertain.metadata['capabilities']['SUBSCRIPTION_DEVIATION_V1']['skip_reasons']
        sub.cancelled_at=datetime(2026,8,15,tzinfo=timezone.utc);sub.status='CANCELLED'
        assert not subscription_run(service,sub,rows,cutoff,cutoff).items
        sub.cancelled_at=None;sub.status='CANDIDATE'
        assert not subscription_run(service,sub,rows,cutoff,cutoff).items


def test_yearly_leap_dates_and_month_end(bank):
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]);service=AnomalyDetectionService(BillingService(db,bank['core'],bank['settings']))
        sub=subscription_fixture(db,user,date(2026,2,28),'YEARLY')
        rows=[expense(i+1,d,'100',merchant='Stream') for i,d in enumerate([date(2023,2,28),date(2024,2,29),date(2025,2,28),date(2026,2,28)])]
        assert not subscription_run(service,sub,rows,date(2026,2,28),date(2026,2,28)).items
        rows[-1]['amount']='110.01'
        yearly=subscription_run(service,sub,rows,date(2026,2,28),date(2026,2,28))
        assert 'PRICE_INCREASE' in findings(yearly,'SUBSCRIPTION_DEVIATION_V1')[0]['evidence']['reason_codes']
        overdue=subscription_run(service,sub,rows[:-1],date(2026,3,20),date(2026,3,20))
        assert overdue.items[0]['observation_kind']=='expected_charge_not_observed'
        assert not subscription_run(service,sub,rows,date(2026,3,20),date(2026,3,20)).items
        sub.cadence='MONTHLY'
        rows=[expense(i+1,d,'100',merchant='Stream') for i,d in enumerate([date(2024,1,31),date(2024,2,29),date(2024,3,31),date(2024,4,30)])]
        assert not subscription_run(service,sub,rows,date(2024,4,30),date(2024,4,30)).items


def test_one_authorized_read_dependency_revocation_and_no_training(bank,tmp_path,monkeypatch):
    from services.analysis_result_service import AnalysisResultService
    from services.account_service import AccountService
    from core.errors import DomainError
    bank['core'].owners[2]=1
    day=date(2026,9,1)
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]);billing=BillingService(db,bank['core'],bank['settings'])
        calls=[];original=billing.scoped_transactions
        def read(*args):calls.append(args[1:]);return original(*args)
        monkeypatch.setattr(billing,'scoped_transactions',read)
        monkeypatch.setattr(AnomalyDetectionService,'train',lambda *a:pytest.fail('query trained'))
        data=billing.anomalies(user,1,day,day,include_metadata=True)
        assert len(calls)==1 and data['dependency_account_ids']==[1,2] and data['account_ids']==[1]
        service=AnalysisResultService(db,AccountService(bank['core']),bank['settings'])
        summary=service.store(user,'anomalies',data,[1],day,day);db.commit()
        bank['core'].owners[2]=2
        with pytest.raises(DomainError):service.get(user,summary['analysis_id'])


def test_partial_bundle_and_daily_calibration_dates(bank,tmp_path):
    cutoff=setup_history(bank,tmp_path)
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]);service=AnomalyDetectionService(BillingService(db,bank['core'],bank['settings']))
        row=service.train(user,cutoff);db.commit()
        assert set(row.metadata_['profiles'])=={'transaction','user_day','account_day'}
        for profile in ('user_day','account_day'):
            info=row.metadata_['profiles'][profile]
            assert info['status']=='ready' and info['fit_count']>=80 and info['calibration_count']>=20
            assert info['calibration_start']<cutoff.isoformat()
        # Forty active dates support transaction fitting but cannot publish a daily estimator.
        bank['core'].tx[1]=[raw(i+1,cutoff-timedelta(days=40-i//4),str(20+i%3)) for i in range(160)]
        partial=service.train(user,cutoff);db.commit()
        bundle,loaded,status=service.load(user,cutoff)
        assert status=='ready' and loaded.id==partial.id
        assert bundle['transaction'] is not None and bundle['user_day'] is None and bundle['account_day'] is None


def test_provisional_never_uses_uncalibrated_daily_model_and_p99_gate():
    day=date(2026,9,1)
    rows=daily_history(day)
    # A strong score alone cannot trigger today's aggregate result.
    metadata={'capabilities':{}}
    run=DetectionRun('u',[],metadata,day,day,{('user_day',day,None,None):{'score':1.,'threshold':.1,'high_threshold':.2}},1)
    run.aggregates(DailyIndex(rows+[expense(9999,day,'20')]),day,None)
    assert not run.items
    run.aggregates(DailyIndex(rows+[expense(9999,day,'999')]),day,None)
    assert all(f['sources']==['rule'] and f['provisional'] for f in findings(run,'SPENDING_SURGE_V1'))


def test_legacy_review_and_window_deduplication(bank):
    from models import AnomalyReview
    day=date(2026,9,1)
    bank['core'].tx[1]=[raw(i+1,day-timedelta(days=40-i),'20') for i in range(40)]+[raw(500,day,'9999')]
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]);billing=BillingService(db,bank['core'],bank['settings'])
        legacy=billing.rule_anomalies(user,1,day,day)[0]
        db.add(AnomalyReview(user_id=user.id,anomaly_key=legacy['anomaly_key'],status='ignored'));db.commit()
        result=billing.anomalies(user,1,day,day,include_metadata=True)
        preserved=next(i for i in result['items'] if i['anomaly_key']==legacy['anomaly_key'])
        assert preserved['rule']=='LARGE_V1' and preserved['status']=='ignored'
        assert 'SPENDING_SURGE_V1' in preserved['anomaly_types']
    rows=[expense(1,day)]
    run=DetectionRun('u',[],{'capabilities':{}},day+timedelta(days=10),day,{},1)
    run.add('SPENDING_SURGE_V1',rows,day-timedelta(days=6),day,['rule'],{'metric':2})
    run.add('SPENDING_SURGE_V1',rows,day-timedelta(days=5),day+timedelta(days=1),['rule'],{'metric':3})
    assert len(run.items)==1 and len(run.items[0]['findings'])==1
    assert run.items[0]['findings'][0]['window']['to_date']==day+timedelta(days=1)


def test_shanghai_midnight_uses_local_incomplete_day(bank,monkeypatch):
    import services.anomaly_detection_service as module
    day=date(2026,9,1)
    bank['core'].tx[1]=[raw(i+1,day-timedelta(days=40-i),'20') for i in range(40)]
    bank['core'].tx[1]+=[raw(100+i,day,str(40+i)) for i in range(6)]
    monkeypatch.setattr(module,'now',lambda:datetime(2026,8,31,16,0,tzinfo=timezone.utc))
    with bank['db']() as db:
        user=db.get(User,bank['ids'][0]);service=AnomalyDetectionService(BillingService(db,bank['core'],bank['settings']))
        result=service.analyze(user,1,day,day)
        assert result['detection']['provisional']
        assert result['detection']['capabilities']['CATEGORY_MIX_SHIFT_V1']['skip_reasons']==['incomplete_day']
        assert all(f['sources']==['rule'] and f['provisional'] for i in result['items'] for f in i.get('findings',[]) if f['type']=='SPENDING_SURGE_V1')
