"""Offline provider wire fixtures, never live model evidence."""
import asyncio
from types import SimpleNamespace
import pytest
from openai.types.chat import ChatCompletionChunk
from agno.models.openai import OpenAIChat
from london_product.intelligence import query_model
from london_product.qa_context import classify_error


def test_stream_records_finish_and_reasoning_usage_then_rejects_length(monkeypatch):
    model=query_model()
    wire=ChatCompletionChunk(id='SYNTHETIC',model='SYNTHETIC',created=1,object='chat.completion.chunk',
        choices=[dict(index=0,delta=dict(content='partial'),finish_reason='length')],
        usage=dict(prompt_tokens=10,completion_tokens=8,total_tokens=18,completion_tokens_details=dict(reasoning_tokens=6)))
    async def fake(*args,**kwargs):
        # Exercise the actual wire parser, not a fabricated verifier result.
        parsed=model._parse_provider_response_delta(wire)
        yield parsed
    monkeypatch.setattr(OpenAIChat,'ainvoke_stream',fake)
    async def consume():
        async for _ in model.ainvoke_stream(messages=[]):pass
    with pytest.raises(ValueError,match='MODEL_OUTPUT_TRUNCATED'):asyncio.run(consume())
    budget=model.budget_for(None)
    call=budget.calls[-1]
    assert call['finish_reason']=='length'
    assert call['raw_provider_usage'][0]['completion_tokens_details']['reasoning_tokens']==6
    assert budget.record()['input_tokens']==10
    assert classify_error('MODEL_OUTPUT_TRUNCATED')=='MODEL_OUTPUT_TRUNCATED'


def test_nonstream_length_response_is_not_a_final_answer():
    from openai.types.chat import ChatCompletion
    model=query_model();model.budget.before(100,1800)
    wire=ChatCompletion(id='SYNTHETIC',model='SYNTHETIC',created=1,object='chat.completion',
        choices=[dict(index=0,message=dict(role='assistant',content='partial'),finish_reason='length')],
        usage=dict(prompt_tokens=10,completion_tokens=8,total_tokens=18))
    parsed=model._parse_provider_response(wire)
    with pytest.raises(ValueError,match='MODEL_OUTPUT_TRUNCATED'):model._record(parsed)
    assert model.budget.calls[-1]['finish_reason']=='length'
    assert model.budget.record()['output_tokens']==8
