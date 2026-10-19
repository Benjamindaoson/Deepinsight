"""Actual saved-evidence branches; synthetic records and no model/network calls."""
import threading,time
import pytest
from agno.db.sqlite import SqliteDb
from london_product.research import ResearchInput,ResearchWorker
from london_product.chat_report import build_report
from test_finding_verification import svc,observation


def worker(svc):
    return ResearchWorker(svc,SqliteDb(db_file=str(svc.store.root/'agno.sqlite3')))


def settle(svc,w,question='Research City and West End vacancy in 2026 Q2',retry_of=None):
    future=[]
    original=svc.pool.submit
    def submit(fn,*args,**kwargs):
        task=original(fn,*args,**kwargs);future.append(task);return task
    svc.pool.submit=submit
    try:job=w.submit(ResearchInput(question=question),retry_of=retry_of)
    finally:svc.pool.submit=original
    for task in future:task.result(timeout=25)
    return svc.store.get('jobs',job['id'])


def test_missing_required_coverage_never_claims_success(svc):
    result=settle(svc,worker(svc))
    assert result['status']=='partial'
    plan=result['plan']
    assert plan['scope']['geographies']==['City','West End']
    assert plan['scope']['metrics']==['vacancy']
    assert plan['scope']['observation_period']=='2026Q2'
    assert plan['decision']=='partial_delivery' and plan['next_checks']
    assert all(n['depends_on'] for n in plan['nodes'] if n['kind']=='report')


def test_branches_overlap_and_retries_reuse_valid_checkpoints(svc,monkeypatch):
    observation(svc,'city');observation(svc,'west',geography='West End')
    w=worker(svc);calls=[];lock=threading.Lock();both_started=threading.Barrier(2)
    original=svc.store.search_evidence
    def search(query,**filters):
        with lock:calls.append((query,filters))
        if filters.get("record_type")=="fact":both_started.wait(timeout=3)
        time.sleep(.05)
        return original(query,**filters)
    monkeypatch.setattr(svc.store,'search_evidence',search)
    first=settle(svc,w)
    assert first['status']=='succeeded',first
    nodes=[v for k,v in first['checkpoints'].items() if k.startswith('evidence:')]
    assert len(nodes)==2
    assert max(n['started_monotonic'] for n in nodes)<min(n['finished_monotonic'] for n in nodes)
    before=len(calls)
    # Explicit retry of an interrupted Job whose branch checkpoints were persisted.
    svc.store.update('jobs',first['id'],dict(status='interrupted'))
    resumed=settle(svc,w,retry_of=first['id'])
    assert resumed['status']=='succeeded' and len(calls)==before
    assert all(c['reused'] for c in resumed['checkpoints'].values())
    assert resumed['result']['report_id']==first['result']['report_id']


def test_evidence_changes_invalidate_affected_branch_and_report(svc,monkeypatch):
    observation(svc,'city');observation(svc,'west',geography='West End')
    w=worker(svc);first=settle(svc,w)
    svc.store.update('facts','city',dict(status='rejected',human_review_status='rejected'))
    svc.store.update('jobs',first['id'],dict(status='partial'))
    second=settle(svc,w,retry_of=first['id'])
    assert second['status']=='partial'
    assert not second['checkpoints']['evidence:City:vacancy']['reused']
    assert second['checkpoints']['evidence:West End:vacancy']['reused']
    assert not second['checkpoints']['report']['reused']
    assert second['result']['report_id']!=first['result']['report_id']


def test_required_timeout_is_bounded_and_late_output_not_committed(svc,monkeypatch):
    observation(svc,'city')
    w=worker(svc);w.branch_timeout_seconds=.02
    original=svc.store.search_evidence
    def search(query,**filters):
        if filters.get('geography')=='West End':time.sleep(.15)
        return original(query,**filters)
    monkeypatch.setattr(svc.store,'search_evidence',search)
    result=settle(svc,w)
    checkpoint=result['checkpoints']['evidence:West End:vacancy']
    assert checkpoint['status']=='failed' and checkpoint['error']=='BRANCH_TIMEOUT'
    assert result['status']=='partial' and result['result']['model_requests']==0
    time.sleep(.18)
    assert svc.store.get('jobs',result['id'])['checkpoints']['evidence:West End:vacancy']['status']=='failed'


def test_report_failure_resumes_evidence_nodes_instead_of_starting_over(svc,monkeypatch):
    import london_product.chat_report as reports
    observation(svc,'city')
    w=worker(svc);original=reports.build_report
    def fail(*args,**kwargs):raise RuntimeError('SYNTHETIC_REPORT_FAILURE')
    monkeypatch.setattr(reports,'build_report',fail)
    first=settle(svc,w,'Research City vacancy in 2026 Q2')
    assert first['status']=='failed'
    assert first['run_id'] and first['native_status']=='ERROR'
    assert first['checkpoints']['evidence:City:vacancy']['status']=='succeeded'
    monkeypatch.setattr(reports,'build_report',original)
    second=settle(svc,w,'Research City vacancy in 2026 Q2',retry_of=first['id'])
    assert second['status']=='succeeded'
    assert second['checkpoints']['evidence:City:vacancy']['reused']
    assert not second['checkpoints']['report']['reused']


def test_optional_context_timeout_keeps_required_evidence_but_discloses_partial(svc,monkeypatch):
    observation(svc,'city')
    w=worker(svc);w.branch_timeout_seconds=.02
    original=svc.store.search_evidence
    def search(query,**filters):
        if filters['record_type']=='document':time.sleep(.15)
        return original(query,**filters)
    monkeypatch.setattr(svc.store,'search_evidence',search)
    result=settle(svc,w,'Research City vacancy in 2026 Q2')
    assert result['status']=='partial'
    assert result['checkpoints']['evidence:City:vacancy']['status']=='succeeded'
    assert result['checkpoints']['context:documents']['error']=='BRANCH_TIMEOUT'
    assert result['result']['generation_status']=='success'
    assert result['plan']['branch_failures']


def test_failed_collection_retains_partial_report_and_is_not_cached_as_success(svc,monkeypatch):
    observation(svc,'city')
    svc.store.put('sources','free-source',dict(id='free-source',enabled=True,allow_llm=True))
    calls=[]
    async def refresh(_):
        calls.append(1)
        return dict(successes=0 if len(calls)==1 else 1,failures=1 if len(calls)==1 else 0)
    monkeypatch.setattr(svc,'refresh',refresh)
    w=worker(svc)
    def run(retry_of=None):
        job=w.submit(ResearchInput(question='Research City vacancy Q2 2026',refresh_sources=True,source_id='free-source'),retry_of=retry_of)
        for _ in range(200):
            row=svc.store.get('jobs',job['id'])
            if row['status'] not in ['queued','running']:return row
            time.sleep(.02)
        pytest.fail('Collection job timeout')
    first=run()
    assert first['status']=='partial' and first['result']['report_id']
    assert first['result']['generation_status']=='partial'
    assert first['checkpoints']['collect']['status']=='failed'
    second=run(first['id'])
    assert second['status']=='succeeded' and len(calls)==2
    assert second['result']['generation_status']=='success'
    assert second['result']['report_id']!=first['result']['report_id']
    assert not second['checkpoints']['collect']['reused']
    third_parent=svc.store.update('jobs',second['id'],dict(status='interrupted'))
    third=run(third_parent['id'])
    assert third['status']=='succeeded' and len(calls)==2
    assert third['checkpoints']['collect']['reused']


def test_concurrent_research_preserves_every_native_workflow_run(svc,monkeypatch):
    from agno.db.base import SessionType
    import london_product.chat_report as reports
    observation(svc,'city');observation(svc,'west',geography='West End')
    db=SqliteDb(db_file=str(svc.store.root/'agno.sqlite3'));w=ResearchWorker(svc,db)
    warm=settle(svc,w,'Research City vacancy Q2 2026')
    barrier=threading.Barrier(2);original=reports.build_report
    def simultaneous(*args,**kwargs):barrier.wait(timeout=10);return original(*args,**kwargs)
    monkeypatch.setattr(reports,'build_report',simultaneous)
    jobs=[w.submit(ResearchInput(question='Research '+geo+' vacancy Q2 2026')) for geo in ['City','West End']]
    completed=[]
    for job in jobs:
        for _ in range(400):
            row=svc.store.get('jobs',job['id'])
            if row['status'] not in ['queued','running']:break
            time.sleep(.02)
        assert row['status']=='succeeded',row
        completed.append(row)
    for row in [warm]+completed:
        session=db.get_session(row['workflow_session_id'],session_type=SessionType.WORKFLOW,deserialize=False)
        assert row['run_id'] in {r['run_id'] for r in session['runs']}
    assert len({row['workflow_session_id'] for row in [warm]+completed})==3


def test_completed_but_late_branch_is_discarded_even_after_coordinator_delay(svc,monkeypatch):
    observation(svc,'city')
    w=worker(svc);w.branch_timeout_seconds=.02
    search=svc.store.search_evidence;persist=w._save_checkpoint
    def delayed_search(query,**filters):
        if filters['record_type']=='fact':time.sleep(.04)
        return search(query,**filters)
    def busy_coordinator(job_id,node_id,value):
        if node_id=='context:documents' and value['status']=='running':time.sleep(.09)
        return persist(job_id,node_id,value)
    monkeypatch.setattr(svc.store,'search_evidence',delayed_search)
    monkeypatch.setattr(w,'_save_checkpoint',busy_coordinator)
    result=settle(svc,w,'Research City vacancy Q2 2026')
    assert result['checkpoints']['evidence:City:vacancy']['status']=='failed'
    assert result['checkpoints']['evidence:City:vacancy']['error']=='BRANCH_TIMEOUT'
    assert not any(hit['record_id']=='city' for hit in result['result']['candidate_hits'])
    assert result['status']=='partial' and result['result']['generation_status']=='partial'


def test_whitespace_only_questions_fail_before_any_execution():
    from pydantic import ValidationError
    from london_product.contracts import AskInput,ClassifyInput
    for cls,field in [(ResearchInput,'question'),(AskInput,'message'),(ClassifyInput,'message')]:
        with pytest.raises(ValidationError):cls(**{field:'   '})
