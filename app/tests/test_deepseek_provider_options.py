"""Actual Agno formatting, isolated configuration fixtures; no network calls."""
from types import SimpleNamespace
import pytest
from agno.models.message import Message
from london_product import intelligence


@pytest.mark.parametrize('endpoint,model_id,official',[
    ('https://api.deepseek.com/v1','deepseek-flash',True),
    ('https://api.deepseek.com','deepseek-v4-pro',True),
    ('https://api.jingziai.club/v1','deepseek-flash',False),
    ('https://api.deepseek.com.evil.example/v1','deepseek-flash',False),
    ('https://api.deepseek.com/v1','claude-sonnet-4-6',False),
])
def test_official_deepseek_uses_supported_system_role_without_changing_other_providers(monkeypatch,endpoint,model_id,official):
    config=SimpleNamespace(id=model_id,api_key='OFFLINE',base_url=endpoint,extra_body={'fixture':'preserved'})
    monkeypatch.setattr(intelligence,'configured_model',lambda *a,**k:config)
    model=intelligence.query_model()
    body=model._format_all_messages([Message(role='system',content='Evidence rules'),Message(role='user',content='Question')])
    assert body[0]['role']==('system' if official else 'developer')
    assert body[1]['role']=='user'
    if official:
        assert model.extra_body['thinking']=={'type':'disabled'}
    else:assert 'thinking' not in model.extra_body
    assert model.extra_body['fixture']=='preserved'
    assert config.extra_body=={'fixture':'preserved'}
