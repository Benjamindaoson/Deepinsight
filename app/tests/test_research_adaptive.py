"""Bounded adaptive local investigation, synthetic stores, no provider requests."""
from test_finding_verification import svc,observation
from test_research_checkpoints import worker,settle


def test_every_requested_period_has_its_own_required_branch(svc,monkeypatch):
    observation(svc,'q1',period='2026Q1',value='9')
    observation(svc,'q2',period='2026Q2',value='8.5')
    observation(svc,'q3',period='2026Q3',value='8')
    calls=[];search=svc.store.search_evidence
    def record(query,**filters):
        calls.append(filters);return search(query,**filters)
    monkeypatch.setattr(svc.store,'search_evidence',record)
    result=settle(svc,worker(svc),'Compare City vacancy Q1 and Q3 2026')
    assert {x['period'] for x in calls if x['record_type']=='fact'}=={'2026Q1','2026Q3'}
    assert {x['period'] for x in result['plan']['coverage_requirements']}=={'2026Q1','2026Q3'}
    assert {x['record_id'] for x in result['result']['candidate_hits'] if x['record_type']=='fact'}=={'q1','q3'}


def test_missing_cells_add_and_execute_bounded_followups_without_approval(svc):
    result=settle(svc,worker(svc),'Research City West End Canary Wharf rent vacancy takeup Q2 2026')
    nodes=[n for n in result['plan']['nodes'] if n['kind']=='followup']
    assert len(nodes)==4
    assert result['plan']['adaptation']['missing_cells']==9
    assert result['plan']['adaptation']['deferred_cells']==5
    assert all(not n['required'] and n['depends_on'] and n['reason']=='missing_structured_observations' for n in nodes)
    assert all(result['checkpoints'][n['id']]['status']=='succeeded' for n in nodes)
    assert all(result['checkpoints'][n['id']]['input']['filters']['record_type']=='document' for n in nodes)
    assert result['status']=='partial' and result['model_requests']==0
    assert not svc.store.all('facts')


def test_retry_reuses_followups_then_removes_obsolete_failure(svc,monkeypatch):
    w=worker(svc);first=settle(svc,w,'Research City vacancy Q2 2026')
    nodes=[n for n in first['plan']['nodes'] if n['kind']=='followup']
    assert len(nodes)==1
    second=settle(svc,w,'Research City vacancy Q2 2026',retry_of=first['id'])
    assert second['checkpoints'][nodes[0]['id']]['reused']
    bad=second['checkpoints'];bad[nodes[0]['id']].update(status='failed',error='BRANCH_TIMEOUT')
    svc.store.update('jobs',second['id'],dict(checkpoints=bad))
    observation(svc,'city')
    third=settle(svc,w,'Research City vacancy Q2 2026',retry_of=second['id'])
    assert third['status']=='succeeded'
    assert not any(n['kind']=='followup' for n in third['plan']['nodes'])
    assert nodes[0]['id'] not in third['checkpoints']
    assert third['plan']['adaptation']['superseded_checkpoint_ids']==[nodes[0]['id']]


def test_raw_followup_lead_never_fills_structured_coverage(svc):
    source=dict(id='raw',name='Raw publisher',allow_llm=True)
    svc.store.put('sources','raw',source)
    text='City vacancy 2026Q2: a publisher document lead only.'
    svc.store.snapshot(source,'https://example.org/raw',text.encode(),'text/plain',
        [dict(text=text,page=1,locator='page 1')])
    result=settle(svc,worker(svc),'Research City vacancy Q2 2026')
    assert any(n['kind']=='followup' for n in result['plan']['nodes'])
    assert any(x['record_type']=='document' for x in result['result']['candidate_hits'])
    assert result['status']=='partial' and result['result']['generation_status']=='insufficient_evidence'
    assert not svc.store.all('facts')


def test_period_specific_evidence_change_reuses_other_period_only(svc):
    observation(svc,'q1',period='2026Q1',value='9')
    observation(svc,'q3',period='2026Q3',value='8')
    question='Compare City vacancy Q1 and Q3 2026'
    w=worker(svc);first=settle(svc,w,question)
    svc.store.update('jobs',first['id'],dict(status='interrupted'))
    svc.store.update('facts','q1',dict(human_review_status='pending_review',status='pending_review'))
    second=settle(svc,w,question,retry_of=first['id'])
    assert not second['checkpoints']['evidence:City:vacancy:2026Q1']['reused']
    assert second['checkpoints']['evidence:City:vacancy:2026Q3']['reused']
    assert second['status']=='partial'


def test_followup_timeout_is_optional_explicit_and_never_retried_implicitly(svc,monkeypatch):
    import time
    w=worker(svc);w.branch_timeout_seconds=.02
    search=svc.store.search_evidence;calls=[]
    def delayed(query,**filters):
        calls.append((query,filters))
        if filters['record_type']=='document' and query=='City vacancy 2026Q2':time.sleep(.12)
        return search(query,**filters)
    monkeypatch.setattr(svc.store,'search_evidence',delayed)
    result=settle(svc,w,'Research City vacancy Q2 2026')
    checkpoint=result['checkpoints']['followup:evidence:City:vacancy']
    assert checkpoint['status']=='failed' and checkpoint['error']=='BRANCH_TIMEOUT'
    assert not checkpoint['required'] and result['status']=='partial'
    time.sleep(.15)
    assert svc.store.get('jobs',result['id'])['checkpoints']['followup:evidence:City:vacancy']['status']=='failed'
    assert sum(query=='City vacancy 2026Q2' for query,_ in calls)==1


def test_legacy_single_period_failure_cannot_poison_new_multi_period_retry(svc):
    observation(svc,'q1',period='2026Q1',value='9')
    observation(svc,'q2',period='2026Q2',value='8')
    question='Compare City vacancy Q1 and Q2 2026'
    w=worker(svc);parent=settle(svc,w,question)
    assert parent['status']=='succeeded'
    legacy_id='evidence:City:vacancy'
    checkpoints=dict(parent['checkpoints'])
    checkpoints[legacy_id]=dict(status='failed',required=True,error='BRANCH_TIMEOUT',input_sha256='legacy')
    svc.store.update('jobs',parent['id'],dict(status='partial',checkpoints=checkpoints))
    resumed=settle(svc,w,question,retry_of=parent['id'])
    assert resumed['status']=='succeeded'
    assert legacy_id not in resumed['checkpoints']
    assert resumed['plan']['retired_checkpoint_ids']==[legacy_id]
