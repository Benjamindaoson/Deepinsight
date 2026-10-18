"""Offline synthetic provider usage; no paid requests."""
import json
from types import SimpleNamespace
import pytest
from agno.models.message import Message
from london_product.intelligence import query_model


def reserved(tmp_path, run_id='offline-receipt'):
    model=query_model()
    model.ledger_root=tmp_path
    model._reserve((),dict(messages=[Message(role='user',content='test evidence')],
        run_response=SimpleNamespace(run_id=run_id)))
    return model


def receipt(tmp_path):
    files=list(tmp_path.glob('*.json'))
    assert len(files)==1, 'A durable per-run ledger must exist before/after every request'
    return json.loads(files[0].read_text(encoding='utf-8'))


def test_reservation_is_durable_before_provider_returns(tmp_path):
    model=reserved(tmp_path)
    saved=receipt(tmp_path)
    assert saved['run_id']=='offline-receipt'
    assert saved['calls'][0]['status']=='started'
    assert saved['calls'][0]['request_payload']['max_tokens']==1800
    assert saved['calls'][0]['estimated_input']>0
    assert saved['input_tokens']==0
    assert 'api_key' not in json.dumps(saved)


def test_overrun_exact_usage_is_saved_before_raise_and_is_terminal(tmp_path):
    model=reserved(tmp_path)
    with pytest.raises(ValueError,match='PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED'):
        model.budget.after(4132,1801)
    saved=receipt(tmp_path)
    assert saved['input_tokens']==4132 and saved['output_tokens']==1801
    assert saved['calls'][0]['limit_violations']==['single_request_output']
    assert saved['calls'][0]['status']=='usage_limit_exceeded'
    with pytest.raises(ValueError,match='PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED'):
        model.budget.before(100,1800)
    assert model.budget.requests==1


def test_cumulative_input_error_is_distinguishable(tmp_path):
    model=reserved(tmp_path)
    with pytest.raises(ValueError,match='PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED'):
        model.budget.after(60001,2)
    assert receipt(tmp_path)['calls'][0]['limit_violations']==['cumulative_input']


def test_missing_usage_remains_unknown_and_timeout_is_saved(tmp_path):
    model=reserved(tmp_path)
    model.budget.failed(TimeoutError())
    saved=receipt(tmp_path)
    assert saved['input_tokens'] is None and saved['output_tokens'] is None
    assert saved['calls'][0]['estimated_input']>0
    assert saved['calls'][0]['error_type']=='TimeoutError'


def test_provider_raw_usage_and_body_survive_parse(tmp_path):
    from openai.types.chat import ChatCompletionChunk
    model=reserved(tmp_path)
    chunk=ChatCompletionChunk(id='offline',created=1,model=model.id,object='chat.completion.chunk',
        choices=[dict(index=0,delta={'content':'Unapproved source observation'},finish_reason=None)],
        usage={'prompt_tokens':120,'completion_tokens':1801,'total_tokens':1921})
    model._parse_provider_response_delta(chunk)
    saved=receipt(tmp_path)
    assert saved['calls'][0]['raw_provider_usage'][-1]['completion_tokens']==1801
    assert saved['calls'][0]['raw_response_text']=='Unapproved source observation'


@pytest.mark.parametrize('completion_tokens',[12,1801])
def test_actual_sdk_wire_limits_and_usage_with_offline_transport(tmp_path,completion_tokens):
    """Exercise the installed SDK serialization; MockTransport cannot access network."""
    import asyncio
    import httpx
    from openai import AsyncOpenAI
    model=query_model();model.ledger_root=tmp_path
    bodies=[]
    def handler(request):
        bodies.append(json.loads(request.content))
        chunk=dict(id='offline-wire',created=1,model=model.id,object='chat.completion.chunk',
            choices=[dict(index=0,delta={'content':'Offline candidate, pending review.'},finish_reason='stop')])
        usage=dict(chunk,choices=[],usage=dict(prompt_tokens=234,completion_tokens=completion_tokens,
            total_tokens=234+completion_tokens))
        data=''.join('data: '+json.dumps(x)+'\n\n' for x in [chunk,usage])+'data: [DONE]\n\n'
        return httpx.Response(200,headers={'content-type':'text/event-stream'},text=data)
    async def execute():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            model.async_client=AsyncOpenAI(api_key='offline-not-a-key',base_url='https://offline.invalid/v1',
                max_retries=0,http_client=http)
            assert model.get_async_client().max_retries==0
            async for _ in model.ainvoke_stream(messages=[Message(role='user',content='Offline test')],
                assistant_message=Message(role='assistant'),response_format=None,tools=None,tool_choice=None,
                run_response=SimpleNamespace(run_id='offline-wire')):pass
    if completion_tokens>1800:
        with pytest.raises(ValueError,match='PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED'):asyncio.run(execute())
    else:asyncio.run(execute())
    assert len(bodies)==1
    assert bodies[0]['max_tokens']==1800
    assert bodies[0]['stream_options']=={'include_usage':True}
    saved=receipt(tmp_path)
    assert saved['input_tokens']==234 and saved['output_tokens']==completion_tokens
    assert saved['calls'][0]['request_payload']==bodies[0]
    assert saved['calls'][0]['raw_provider_usage'][0]['completion_tokens']==completion_tokens


def test_windows_reader_sharing_violation_retries_only_local_replace(tmp_path,monkeypatch):
    from pathlib import Path
    model=reserved(tmp_path)
    replace=Path.replace;attempts=[]
    def sharing_once(path,target):
        attempts.append(str(path))
        if len(attempts)==1:raise PermissionError('offline Windows sharing violation')
        return replace(path,target)
    monkeypatch.setattr(Path,'replace',sharing_once)
    monkeypatch.setattr('london_product.intelligence.time.sleep',lambda _:None)
    model.budget.after(23,7)
    assert len(attempts)==2
    assert receipt(tmp_path)['requests']==1
    assert receipt(tmp_path)['output_tokens']==7


def test_permanent_ledger_failure_is_bounded_and_readable(tmp_path,monkeypatch):
    from pathlib import Path
    model=reserved(tmp_path);attempts=[]
    def blocked(path,target):
        attempts.append(str(path));raise PermissionError('offline persistent block')
    monkeypatch.setattr(Path,'replace',blocked)
    monkeypatch.setattr('london_product.intelligence.time.sleep',lambda _:None)
    with pytest.raises(RuntimeError,match='AUDIT_STORAGE_ERROR'):model.budget.after(23,7)
    assert len(attempts)==5 and model.budget.requests==1


def test_real_windows_open_reader_does_not_abort_usage_receipt(tmp_path):
    import ctypes,os,threading,time
    from ctypes import wintypes
    if os.name!='nt':pytest.skip('Windows sharing semantics')
    model=reserved(tmp_path)
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    api.CreateFileW.restype=wintypes.HANDLE
    api.CloseHandle.argtypes=[wintypes.HANDLE]
    # Like a Windows reader that shares reads/writes but not deletion/rename.
    handle=api.CreateFileW(str(model.budget.receipt_path),0x80000000,3,None,3,0,None)
    assert handle!=wintypes.HANDLE(-1).value
    release=threading.Thread(target=lambda:(time.sleep(.05),api.CloseHandle(handle)))
    release.start()
    try:model.budget.after(23,7)
    finally:release.join()
    assert receipt(tmp_path)['output_tokens']==7
