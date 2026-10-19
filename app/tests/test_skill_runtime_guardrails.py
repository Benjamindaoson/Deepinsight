"""Engineering regressions only; provider wire fixtures are not live acceptance."""
import json
from types import SimpleNamespace

from agno.models.message import Message
from openai.types.chat import ChatCompletionChunk

from london_product.intelligence import query_model


def test_utf8_response_budget_is_independent_of_output_token_count():
    model=query_model();model.budget.before(100,1800)
    wire=ChatCompletionChunk(id='offline-regression',model=model.id,created=1,object='chat.completion.chunk',
        choices=[dict(index=0,delta=dict(content='租'*601),finish_reason=None)])
    model._retain_wire(model._parse_provider_response_delta(wire))
    call=model.budget.calls[-1]
    assert call['response_bytes']==1803
    assert call['response_byte_limit']>1800
    assert call['max_output']==1800


def test_model_selects_skills_before_retrieval_within_three_requests():
    model=query_model()
    tools=[dict(type='function',function=dict(name=n,parameters={'type':'object'}))
           for n in ['load_market_skills','search_market_evidence','compare_market_facts']]
    messages=[Message(role='user',content='Explain saved West End vacancy changes.')]
    args=dict(messages=messages,tools=tools,run_response=SimpleNamespace(run_id='offline-skill-order'))
    model._reserve((),args)
    assert args['tool_choice']['function']['name']=='load_market_skills'
    model.budget.after(100,10)
    messages.append(Message(role='tool',tool_name='load_market_skills',content=json.dumps({'status':'loaded'})))
    model._reserve((),args)
    assert args['tool_choice']['function']['name']=='search_market_evidence'
    model.budget.after(100,10)
    messages.append(Message(role='tool',tool_name='search_market_evidence',content='{}'))
    model._reserve((),args)
    assert args['tool_choice']=='none'
    assert model.budget.requests==3


def test_live_health_describes_available_model_path_without_claiming_success(tmp_path):
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    app=create_app(tmp_path,seed=False,scheduler=False,offline=False)
    with TestClient(app) as client:
        result=client.get('/health').json()
    assert result['mode']=='live'
    assert result['model_execution_available'] is True
    assert result['model_call_verified'] is False


def test_explicit_json_download_has_attachment_headers(tmp_path):
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    app=create_app(tmp_path,seed=False,scheduler=False,offline=True)
    service=app.state.market
    report=service.generate_report('weekly')
    with TestClient(app) as client:
        response=client.get(f"/api/market/reports/{report['id']}?format=json&download=true")
    assert response.status_code==200
    assert 'attachment' in response.headers.get('content-disposition','')
    assert '.json' in response.headers['content-disposition']


def test_explicit_agent_does_not_short_circuit_macro_question_as_saved_clarification(tmp_path):
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    app=create_app(tmp_path,seed=False,scheduler=False,offline=False)
    attempted=[]
    def factory():
        attempted.append(True)
        raise RuntimeError('OFFLINE_TEST_SENTINEL_NO_PROVIDER')
    app.state.market.agent_factory=factory
    with TestClient(app) as client:
        response=client.post('/api/market/ask',json=dict(mode='agent',message=
            '现有资料能够证明英国利率、就业变化或混合办公趋势已经导致伦敦办公租金变化吗？请区分直接观测到的事实、可能的解释和目前无法证明的因果关系，并逐条列出证据。'))
    assert response.status_code==200
    assert attempted==[True], 'Explicit model analysis must reach the real Agent boundary, not a zero-model saved clarification.'


def test_artifact_exports_support_actual_markdown_and_html_downloads(tmp_path):
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    from london_product.chat_report import build_report
    app=create_app(tmp_path,seed=False,scheduler=False,offline=True)
    report=build_report(app.state.market,'City vacancy Q2 2026')
    with TestClient(app) as client:
        for format,suffix in [('markdown','.md'),('html','.html')]:
            response=client.get(f"/api/market/reports/{report['report_id']}?format={format}&download=true")
            assert response.status_code==200
            assert 'attachment' in response.headers.get('content-disposition','')
            assert suffix in response.headers['content-disposition']


def test_ask_returns_and_persists_real_conversation_identity_without_provider(tmp_path):
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    from uuid import UUID
    app=create_app(tmp_path,seed=False,scheduler=False,offline=True)
    with TestClient(app) as client:
        first=client.post('/api/market/ask',json=dict(mode='saved',message='Analyse City vacancy Q2 2026'))
        events=[json.loads(line[6:]) for line in first.text.splitlines() if line.startswith('data: ')]
        session=events[0]['session_id']
        assert UUID(session)
        second=client.post('/api/market/ask',json=dict(mode='saved',message='What about West End?',session_id=session))
        next_events=[json.loads(line[6:]) for line in second.text.splitlines() if line.startswith('data: ')]
        assert next_events[0]['session_id']==session
    jobs=app.state.market.store.all('jobs')
    assert len(jobs)==2 and all(j.get('session_id')==session for j in jobs)
