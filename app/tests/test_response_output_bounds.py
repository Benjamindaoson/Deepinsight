"""Wire-level offline fixtures: no model calls and no real market approvals."""
import asyncio
from types import SimpleNamespace
import pytest
from openai.types.chat import ChatCompletionChunk
from london_data.extraction import BoundedOpenAIChat
from london_product.intelligence import query_model


def wire(model,text='',arguments=None):
 delta=dict(content=text)
 if arguments is not None:delta['tool_calls']=[dict(index=0,id='tool',type='function',function=dict(name='lookup',arguments=arguments))]
 return model._parse_provider_response_delta(ChatCompletionChunk(id='offline',model=model.id,created=1,
  object='chat.completion.chunk',choices=[dict(index=0,delta=delta,finish_reason=None)]))


@pytest.mark.parametrize('tool',[False,True])
def test_async_stream_aborts_early_closes_and_preserves_unknown_usage(monkeypatch,tool):
 model=query_model();model.budget.before(10,1800);closed=[];seen=[]
 async def fake(*args,**kwargs):
  try:
   for i in range(3):
    seen.append(i)
    yield wire(model,'x'*1000 if not tool else '', 'x'*1000 if tool else None)
  finally:closed.append(True)
 monkeypatch.setattr(BoundedOpenAIChat,'ainvoke_stream',fake)
 received=[]
 async def consume():
  async for response in model.ainvoke_stream(messages=[]):received.append(response)
 with pytest.raises(ValueError,match='MODEL_RESPONSE_TOO_LARGE'):asyncio.run(consume())
 assert len(received)==1 and seen==[0,1] and closed==[True]
 receipt=model.budget.record()
 assert receipt['input_tokens'] is None and receipt['output_tokens'] is None
 assert receipt['terminal_error']=='MODEL_RESPONSE_TOO_LARGE'
 assert receipt['calls'][-1]['response_bytes']>1800
 assert receipt['calls'][-1]['status']=='response_size_limit'
 with pytest.raises(ValueError,match='MODEL_RESPONSE_TOO_LARGE'):model.budget.before(10,1800)


def test_sync_stream_is_closed_on_size_abort(monkeypatch):
 model=query_model();model.budget.before(10,1800);closed=[]
 def fake(*args,**kwargs):
  try:
   yield wire(model,'x'*1000)
   yield wire(model,'x'*1000)
  finally:closed.append(True)
 monkeypatch.setattr(BoundedOpenAIChat,'invoke_stream',fake)
 with pytest.raises(ValueError,match='MODEL_RESPONSE_TOO_LARGE'):list(model.invoke_stream(messages=[]))
 assert closed==[True]


def test_guard_counts_utf8_bytes_instead_of_claiming_token_counts():
 model=query_model();model.budget.before(10,1800)
 with pytest.raises(ValueError,match='MODEL_RESPONSE_TOO_LARGE'):model._retain_wire(wire(model,'租'*601))
 assert model.budget.calls[-1]['response_bytes']==1803


def test_final_report_request_adds_compact_instruction_without_mutating_history():
 import json
 from agno.models.message import Message
 model=query_model()
 messages=[Message(role='user',content='Prepare report'),Message(role='tool',tool_name='search_market_evidence',
  content=json.dumps(dict(analysis_contract=dict(fields=['key_findings','risks','opportunities','outlook']))))]
 kwargs=dict(messages=messages,run_response=SimpleNamespace(run_id='offline-final'))
 model._reserve((),kwargs)
 assert len(messages)==2
 final=kwargs['messages'][-1]
 assert final.role=='system' and 'REPORT_INTERPRETATION_WIRE_V1' in final.content
 assert 'JSON' in final.content and '1,800 UTF-8 bytes' in final.content


def test_abort_closes_underlying_provider_before_event_loop_shutdown(monkeypatch):
 from agno.models.openai import OpenAIChat
 model=query_model();closed=[]
 async def provider(*args,**kwargs):
  try:
   yield wire(model,'x'*1000)
   yield wire(model,'x'*1000)
  finally:closed.append(True)
 monkeypatch.setattr(OpenAIChat,'ainvoke_stream',provider)
 async def consume():
  with pytest.raises(ValueError,match='MODEL_RESPONSE_TOO_LARGE'):
   async for _ in model.ainvoke_stream(messages=[]):pass
  assert closed==[True], 'Provider must close immediately, not at event-loop teardown'
 asyncio.run(consume())

@pytest.mark.parametrize('asynchronous',[False,True])
@pytest.mark.parametrize('abort',['size','consumer'])
def test_real_agno_sdk_response_is_closed_and_unfinished_usage_blocks(monkeypatch,asynchronous,abort):
 from agno.models.openai import OpenAIChat
 from agno.models.message import Message
 model=query_model();closed=[]
 chunks=[ChatCompletionChunk(id='offline-sdk',model=model.id,created=1,
  object='chat.completion.chunk',choices=[dict(index=0,delta=dict(content='x'*1000),finish_reason=None)]) for _ in range(3)]
 class SyncSDK:
  def __iter__(self):return iter(chunks)
  def close(self):closed.append(True)
 class AsyncSDK:
  def __aiter__(self):self.iterator=iter(chunks);return self
  async def __anext__(self):
   try:return next(self.iterator)
   except StopIteration:raise StopAsyncIteration
  async def close(self):closed.append(True)
 sdk=AsyncSDK() if asynchronous else SyncSDK()
 async def acreate(**kwargs):return sdk
 def create(**kwargs):return sdk
 client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=acreate if asynchronous else create)))
 client.with_options=lambda **kwargs:client
 monkeypatch.setattr(OpenAIChat,'get_async_client' if asynchronous else 'get_client',lambda self:client)
 if asynchronous:
  async def consume():
   stream=model.ainvoke_stream(messages=[],assistant_message=Message(role='assistant'))
   if abort=='consumer':await anext(stream);await stream.aclose()
   else:
    with pytest.raises(ValueError,match='MODEL_RESPONSE_TOO_LARGE'):
     async for _ in stream:pass
   assert closed==[True]
  asyncio.run(consume())
 else:
  stream=model.invoke_stream(messages=[],assistant_message=Message(role='assistant'))
  if abort=='consumer':next(stream);stream.close()
  else:
   with pytest.raises(ValueError,match='MODEL_RESPONSE_TOO_LARGE'):list(stream)
  assert closed==[True]
 budget=model.budget_for(None)
 assert budget.record()['output_tokens'] is None
 assert budget.calls[-1]['status']!='started'
 with pytest.raises(ValueError):budget.before(10,1800)
