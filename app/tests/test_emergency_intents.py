import json
import re
from fastapi.testclient import TestClient
from london_product.runtime import create_app


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]


def test_audit_followup_does_not_create_replacement_report(tmp_path):
    app = create_app(tmp_path, seed=False, scheduler=False, offline=True)
    with TestClient(app) as client:
        first = events(client.post('/api/market/ask', json={'message':'Prepare a London office market briefing with rents vacancy supply', 'mode':'saved'}))
        rid = next(e['report_id'] for e in first if e['type']=='report')
        count = len(app.state.market.store.all('reports'))
        for question, operation in [('Perform a rigorous source and evidence audit of the report you just generated.', 'evidence_audit'), ('What is missing from the previous answer?', 'follow_up'), ('Why is this source still marked Pending review?', 'follow_up')]:
            output = events(client.post('/api/market/ask',json={'message':question,'parent_report_id':rid,'mode':'auto'}))
            assert not any(e['type']=='report' for e in output)
            done = next(e for e in output if e['type']=='done')
            assert done['operation']==operation
            assert done['report_id']==rid
            assert len(app.state.market.store.all('reports'))==count
            assert question not in ''.join(e.get('content','') for e in output)


def test_focused_lookup_and_monitoring_are_not_reports(tmp_path):
    app=create_app(tmp_path,seed=False,scheduler=False,offline=True)
    with TestClient(app) as client:
        for question, operation in [('What is the latest published West End vacancy rate, and which source supports it?', 'data_question'), ('Show the latest completed monitoring run.', 'monitoring_status'), ('Create a daily market-monitoring schedule.', 'schedule_request')]:
            output=events(client.post('/api/market/ask',json={'message':question,'mode':'auto'}))
            assert not any(e['type']=='report' for e in output)
            assert next(e for e in output if e['type']=='done')['operation']==operation
        assert not app.state.market.store.all('reports')


def test_withheld_draft_is_english_and_specific(tmp_path):
    from london_product.safe_answer import render_safe_answer
    answer=render_safe_answer(dict(verified_fact=[],publisher_reported_change=[],pending_review=[]),[],['UNSUPPORTED_NUMERIC_CLAIM'])
    assert not re.search('[\u4e00-\u9fff]',answer)
    assert 'UNSUPPORTED_NUMERIC_CLAIM' in answer
    assert 'draft' in answer.lower() and 'review' in answer.lower()


def test_native_operational_endpoint_requires_real_parent(tmp_path):
    app=create_app(tmp_path,seed=False,scheduler=False,offline=True)
    with TestClient(app) as client:
        r=client.post('/api/market/conversation',json={'message':'Audit the previous report','session_id':'unknown'})
        assert r.status_code==200
        assert r.json()['handled'] is True
        assert 'report' in r.json()['answer'].lower()
        assert not app.state.market.store.all('reports')


def test_new_report_runs_existing_workflow_and_preserves_partial_status(tmp_path):
    app=create_app(tmp_path,seed=False,scheduler=False,offline=True)
    with TestClient(app) as client:
        out=events(client.post('/api/market/ask',json={'message':'Prepare a concise London office market briefing with prime rents, vacancy, available space, leasing activity and supply pipeline.', 'session_id':'audit-session','mode':'saved'}))
        report=next(e['report'] for e in out if e['type']=='report')
        assert report['report_type']=='market_report'
        job=app.state.market.store.get('jobs',report['acquisition']['research_job_id'])
        assert job['native_status']=='COMPLETED' and job['status']=='partial'
        audit=client.post('/api/market/conversation',json={'message':'Audit the previous report','session_id':'audit-session'}).json()
        assert audit['report_id']==report['report_id'] and audit['operation']=='evidence_audit'
        assert len(app.state.market.store.all('reports'))==1


def test_multilingual_request_kept_internal_without_prompt_echo_in_exports(tmp_path):
    from london_product.chat_report import build_report,render_markdown,render_html
    app=create_app(tmp_path,seed=False,scheduler=False,offline=True)
    prompt='比较 City 和 Canary Wharf 的租金、空置和租赁活动，并分析风险。不要重复此说明。'
    report=build_report(app.state.market,prompt)
    assert report['query']==prompt
    for text in [render_markdown(report),render_html(report)]:
        assert not re.search('[\u3400-\u9fff]',text)
        assert 'Research scope' in text and prompt not in text


def test_evidence_audit_detects_tampering_without_approving_records(tmp_path):
    from test_finding_verification import observation
    from london_product.chat_report import build_report,respond_to_action
    app=create_app(tmp_path,seed=False,scheduler=False,offline=True)
    service=app.state.market
    fact=observation(service,'synthetic-audit-control',approved=False)
    report=build_report(service,'City vacancy Q2 2026')
    reviews=service.store.all('reviews')
    result=respond_to_action(service,'Audit previous report',report['report_id'])
    assert result['audit']['limited_or_failed_ids']==[fact['id']]
    assert 'literal value matched' in result['answer']
    doc=service.store.get('documents',fact['document_id'])
    from pathlib import Path
    Path(doc['path']).write_text('SYNTHETIC altered evidence',encoding='utf-8')
    result=respond_to_action(service,'Audit previous report',report['report_id'])
    assert 'failed' in result['answer']
    assert service.store.all('reviews')==reviews


def test_explicit_latest_query_has_its_own_action_with_parent():
    from london_product.routing import request_action
    assert request_action("What is the latest published West End vacancy rate, and which source supports it?",True)=="data_question"
    assert request_action("What about vacancy?",True)=="follow_up"
