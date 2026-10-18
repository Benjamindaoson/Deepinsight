"""OFFLINE only: deterministic fixtures and replay of saved real provider output."""
import hashlib
import json
from pathlib import Path
import pytest
from london_product.store import Store
from london_product.analysis_guard import review_analysis


def fixture(tmp_path, status='pending_review', kind='fact'):
    store = Store(tmp_path)
    quote = 'Quarterly office take-up was 2.6 million sq.ft., up 4% quarter-on-quarter.'
    raw = tmp_path / 'original.txt'; raw.write_text(quote, encoding='utf-8')
    store.put('sources', 's', dict(id='s', allow_llm=True))
    doc = store.put('documents', 'd', dict(id='d', source_id='s', title='Fixture report',
        url='https://example.org/report', path=str(raw), sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
        published_at='2026-08-01', segments=[dict(text=quote, page=1, locator='page:1')]))
    item = dict(id='f', source_id='s', document_id='d', metric='takeup', period='2026Q2',
        geography='Central London', definition='Quarterly office take-up', value='2.6', unit='million sqft',
        status=status, human_review_status='approved' if status=='approved' else 'pending_review',
        evidence=dict(quote=quote, page=1, locator='page:1'))
    if kind=='publisher':
        item.update(classification='publisher_reported_change', evidence_validation='exact_quote_in_hash_verified_original',
                    document_sha256=doc['sha256'], calculation_performed=False)
    store.put('events' if kind=='publisher' else 'facts', 'f', item)
    return store, dict(facts=[item] if kind=='fact' else [], publisher_reported_changes=[item] if kind=='publisher' else [])


@pytest.mark.parametrize('draft', [
    'City rents rose from £92.50 to £95, proving strong demand.',
    'GPE pre-let 4,300 sq ft.',
    'BNP supply 22.8m and JLL supply 21.6m: supply declined.',
    '政府批准City Plan 2040，规划已经获批。',
    'Quarterly take-up was 2.6 million sqft. City rents increased.',
])
def test_unsafe_draft_replaced_not_edited(tmp_path, draft):
    store, pack = fixture(tmp_path)
    before = store.all('facts')
    result = review_analysis(draft, store, evidence_packs=[pack])
    assert result['publication_review']['status']=='withheld'
    assert result['answer_origin']=='deterministic_evidence_fallback'
    assert result['raw_answer']==draft and draft not in result['answer']
    assert 'pending_review' in result['answer'] and 'https://example.org/report' in result['answer']
    assert '2.6' in result['answer'] and '证据不足' in result['answer']
    assert not result['safe_evidence']['verified_fact']
    assert store.all('facts')==before


def test_approved_fact_and_attributed_publisher_change(tmp_path):
    store, pack = fixture(tmp_path, status='approved')
    result = review_analysis('Supply declined.', store, evidence_packs=[pack])
    assert len(result['safe_evidence']['verified_fact'])==1
    assert 'Quarterly office take-up' in result['answer']
    other, publisher = fixture(tmp_path/'publisher', kind='publisher')
    result = review_analysis('Supply declined.', other, evidence_packs=[publisher])
    assert len(result['safe_evidence']['publisher_reported_change'])==1
    assert 'up 4% quarter-on-quarter' in result['answer']
    assert not result['safe_evidence']['verified_fact']
    assert '不是系统计算' in result['answer']


def test_empty_or_tampered_evidence_is_not_published(tmp_path):
    store, pack = fixture(tmp_path)
    for packs in [[], [dict(facts=[dict(pack['facts'][0], value='999')])]]:
        result=review_analysis('City rents increased.',store,evidence_packs=packs)
        assert '证据不足' in result['answer']
        assert not result['safe_evidence']['pending_review']
        assert '999' not in result['answer']
    Path(store.get('documents','d')['path']).write_text('changed',encoding='utf-8')
    result=review_analysis('Supply declined.',store,evidence_packs=[pack])
    assert not result['safe_evidence']['pending_review']


def test_replay_saved_real_draft_is_offline_and_non_mutating(tmp_path):
    from test_qa_context_budget import saved_service
    service=saved_service(tmp_path)
    root=Path(__file__).parents[1]/'data/product/evidence/qa-context-repair-20261018'
    run=json.loads((root/'live-native-run.json').read_text(encoding='utf-8'))
    before={t:service.store.all(t) for t in ['facts','events','documents','sources']}
    packs=[json.loads(t['result']) for t in run['tools'] if t['tool_name']=='search_market_evidence']
    result=review_analysis(run['content'],service.store,evidence_packs=packs)
    assert result['publication_review']['status']=='withheld'
    assert result['safe_evidence']['pending_review']
    assert not result['safe_evidence']['verified_fact']
    assert '£92.50→£95' not in result['answer']
    assert '政府批准City Plan' not in result['answer']
    assert result['raw_answer']==run['content']
    assert before=={t:service.store.all(t) for t in before}


def test_native_publication_read_preserves_run_and_never_calls_model(tmp_path):
    from agno.db.sqlite import SqliteDb
    from agno.db.base import SessionType
    from agno.session.agent import AgentSession
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    store, pack=fixture(tmp_path)
    app=create_app(tmp_path,seed=False,scheduler=False)
    app.state.market.agent_factory=lambda: pytest.fail('Offline GET attempted model creation')
    db=SqliteDb(id='london-product',db_file=str(tmp_path/'agno.sqlite3'))
    run=dict(run_id='r',session_id='s',agent_id='london-market-agent',status='COMPLETED',content='City rents rose.',
             tools=[dict(tool_name='search_market_evidence',result=json.dumps(pack))])
    db.upsert_session(AgentSession.from_dict(dict(session_id='s',agent_id='london-market-agent',runs=[run],created_at=1,updated_at=1)))
    before=db.get_session('s',session_type=SessionType.AGENT,deserialize=False)
    with TestClient(app) as client:
        a=client.get('/api/market/sessions/s/runs/r/publication')
        b=client.get('/api/market/sessions/s/runs/r/publication')
        assert a.status_code==200 and a.json()==b.json()
        assert a.json()['answer_origin']=='deterministic_evidence_fallback'
        assert 'raw_answer' not in a.json()
        assert client.get('/api/market/sessions/wrong/runs/r/publication').status_code==404
    assert db.get_session('s',session_type=SessionType.AGENT,deserialize=False)==before


@pytest.mark.parametrize('status',['ERROR','CANCELLED','RUNNING'])
def test_failed_or_unfinished_run_does_not_become_success(tmp_path,status):
    from london_product.safe_answer import project_run
    with pytest.raises(ValueError,match='FINAL_ANSWER_MISSING'):
        project_run(dict(agent_id='london-market-agent',status=status,content='partial draft'),Store(tmp_path))


def test_pending_plain_claims_cannot_escape_by_avoiding_trend_words(tmp_path):
    store,pack=fixture(tmp_path)
    result=review_analysis('The market is healthy and offers investment opportunities.',store,evidence_packs=[pack])
    assert result['publication_review']['status']=='withheld'
    assert 'NO_VERIFIED_FACTS' in result['publication_review']['codes']
    assert 'investment opportunities' not in result['answer']


def test_rejected_and_source_revoked_records_are_omitted(tmp_path):
    store,pack=fixture(tmp_path)
    store.update('facts','f',{'human_review_status':'rejected'})
    result=review_analysis('Supply declined.',store,evidence_packs=[pack])
    assert not any(result['safe_evidence'].values())
    store.update('facts','f',{'human_review_status':'pending_review'})
    store.update('sources','s',{'allow_llm':False})
    result=review_analysis('Supply declined.',store,evidence_packs=[pack])
    assert not any(result['safe_evidence'].values())


def test_real_saved_publisher_change_is_attributed_without_calculation(tmp_path):
    from test_qa_context_budget import saved_service
    from london_product.publisher_changes import saved_reported_changes
    service=saved_service(tmp_path)
    changes=saved_reported_changes(service.store)
    assert changes, 'Expected existing JLL case; no discovery or writes allowed'
    result=review_analysis('Supply declined.',service.store,evidence_packs=[{'publisher_reported_changes':changes}])
    assert result['safe_evidence']['publisher_reported_change']
    assert not result['safe_evidence']['verified_fact']
    for change in changes:
        assert change['reported_change'] in result['answer']
    assert '不是系统计算' in result['answer']


def test_combined_transaction_quote_keeps_both_statuses(tmp_path):
    store,_=fixture(tmp_path)
    quote='GPE has pre let one floor, with a further floor under offer. The transactions total 4,300 sq ft.'
    doc=store.get('documents','d');Path(doc['path']).write_text(quote,encoding='utf-8')
    store.update('documents','d',{'sha256':hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest(),
        'segments':[dict(text=quote,locator='page:1',page=1)]})
    event=store.put('events','e',dict(id='e',source_id='s',document_id='d',status='pending_review',
        evidence={'quote':'The transactions total 4,300 sq ft.','locator':'page:1','page':1}))
    result=review_analysis('GPE pre-let 4,300 sq ft.',store,evidence_packs=[{'events':[event]}])
    assert 'a further floor under offer' in result['answer']
    assert 'GPE pre-let 4,300' not in result['answer']
    assert not result['safe_evidence']['verified_fact']
