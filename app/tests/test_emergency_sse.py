"""Provider HTTP boundary fault fixtures; not real model acceptance."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from fastapi.testclient import TestClient
from london_product.runtime import create_app


class ProviderFault(httpx.AsyncBaseTransport):
    def __init__(self, fault): self.fault=fault
    async def handle_async_request(self, request):
        if self.fault=='auth':
            return httpx.Response(401,json={'error':{'message':'Invalid audit credential','type':'authentication_error'}},request=request)
        if self.fault=='timeout':raise httpx.ReadTimeout('AUDIT timeout',request=request)
        if self.fault=='disconnect':raise httpx.ConnectError('AUDIT disconnected',request=request)
        if self.fault=='malformed':return httpx.Response(200,headers={'content-type':'text/event-stream'},content=b'data: {}\n\ndata: [DONE]\n\n',request=request)
        # The transport byte ceiling is separate from the 1,800-token model cap.
        text='A'*16_385 if self.fault=='oversize' else 'Insufficient evidence for this question.'
        payload=dict(id='AUDIT-CONTROLLED',object='chat.completion.chunk',created=1,model='controlled',
            choices=[dict(index=0,delta=dict(role='assistant',content=text),finish_reason='stop')],
            usage=dict(prompt_tokens=10,completion_tokens=10,total_tokens=20))
        return httpx.Response(200,headers={'content-type':'text/event-stream'},content=('data: '+json.dumps(payload)+'\n\ndata: [DONE]\n\n').encode(),request=request)


def events(response):
    return [json.loads(l[6:]) for l in response.text.splitlines() if l.startswith('data: ')]


@pytest.mark.parametrize('fault',['oversize','auth','timeout','disconnect','malformed'])
def test_provider_fault_always_terminates_stream_and_job(tmp_path,fault):
    app=create_app(tmp_path,seed=False,scheduler=False)
    factory=app.state.market.agent_factory
    def agent():
        result=factory();result.model.http_client=httpx.AsyncClient(transport=ProviderFault(fault));return result
    app.state.market.agent_factory=agent
    with TestClient(app) as client:
        response=client.post('/api/market/ask',json={'message':'Analyse the City office market.','mode':'agent'})
        terminal=events(response)[-1]
        assert terminal['type'] in ['done','error']
        job=app.state.market.store.get('jobs',terminal['submission_id'])
        assert job['status'] in ['succeeded','partial','failed','cancelled']
        assert job.get('finished_at')
        assert not any(j['status'] in ['running','queued'] for j in app.state.market.store.all('jobs'))
        assert 'KeyError' not in response.text and 'Traceback' not in response.text
        if fault=='oversize':assert terminal['code']=='MODEL_RESPONSE_TOO_LARGE'


def test_routing_exception_is_terminal_and_sanitized(tmp_path):
    app=create_app(tmp_path,seed=False,scheduler=False)
    async def broken(*args,**kwargs):raise RuntimeError('SECRET_NOT_FOR_PUBLIC')
    app.state.query_router.classify=broken
    with TestClient(app) as client:
        response=client.post('/api/market/ask',json={'message':'Analyse City office risk.','mode':'agent'})
        terminal=events(response)[-1]
        assert terminal['type']=='error' and terminal['submission_id']
        assert 'SECRET_NOT_FOR_PUBLIC' not in response.text
        assert app.state.market.store.get('jobs',terminal['submission_id'])['status']=='failed'


def test_five_concurrent_requests_have_independent_terminal_jobs(tmp_path):
    app=create_app(tmp_path,seed=False,scheduler=False)
    factory=app.state.market.agent_factory
    def agent():
        x=factory();x.model.http_client=httpx.AsyncClient(transport=ProviderFault('oversize'));return x
    app.state.market.agent_factory=agent
    with TestClient(app) as client:
        def one(n):return events(client.post('/api/market/ask',json={'message':f'Analyse City office market scenario {n}.','mode':'agent'}))[-1]
        with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(one,range(5)))
        assert len({r['submission_id'] for r in results})==5
        assert all(r['type']=='error' for r in results)
        assert all(j['status']=='failed' and j.get('finished_at') for j in app.state.market.store.all('jobs'))
