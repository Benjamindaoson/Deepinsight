import json
import pytest
from london_product.store import Store
from london_product.model_connections import Connections, model_options, ACTIVE_CONNECTION
from london_product.attachments import save_attachment, attachment_context


def test_encrypted_credentials_are_owner_scoped(tmp_path):
    store = Store(tmp_path)
    connections = Connections(store)
    row = connections.save('browser-a', 'Personal', 'https://api.deepseek.com', 'secret-test-key')
    assert 'secret-test-key' not in json.dumps(store.all('settings'))
    assert 'api_key' not in row
    assert connections.resolve('browser-a', row['id'])['api_key'] == 'secret-test-key'
    with pytest.raises(KeyError): connections.resolve('browser-b', row['id'])
    assert connections.list('browser-b') == []
    connections.delete('browser-a', row['id'])
    with pytest.raises(KeyError): connections.resolve('browser-a', row['id'])


def test_supported_thinking_and_context_isolation():
    params = model_options('https://api.deepseek.com', 'deepseek-flash', 'deep')
    assert params['extra_body']['thinking']['type'] == 'enabled'
    assert params['reasoning_effort'] == 'high'
    assert params['role_map']['user'] == 'user'
    assert model_options('https://api.deepseek.com', 'deepseek-flash', 'standard')['extra_body']['thinking']['type'] == 'disabled'
    with pytest.raises(ValueError): model_options('https://toapis.cn/v1', 'claude-sonnet-4-6', 'deep')
    assert ACTIVE_CONNECTION.get() is None


def test_real_upload_parser_does_not_create_approved_facts(tmp_path):
    store = Store(tmp_path)
    row = save_attachment(store, 'browser-a', 'source.csv', b'area,value\nCity,100\n', 'text/csv')
    assert row['sha256'] and row['segment_count'] == 1
    context = attachment_context(store, 'browser-a', [row['id']])
    assert 'City' in json.dumps(context) and context[0]['review_status'] == 'unreviewed_user_upload'
    assert store.all('facts') == []
    with pytest.raises(KeyError): attachment_context(store, 'browser-b', [row['id']])
    with pytest.raises(ValueError): save_attachment(store, 'browser-a', 'x.exe', b'abc', 'application/octet-stream')
    with pytest.raises(ValueError): save_attachment(store, 'browser-a', 'empty.txt', b'', 'text/plain')


def test_api_ownership_cors_and_sensitive_validation(tmp_path):
    from fastapi.testclient import TestClient
    from london_product.runtime import create_app
    app = create_app(tmp_path, seed=False, scheduler=False, offline=True, frontend_port=3107)
    with TestClient(app) as a, TestClient(app) as b:
        headers = {'Origin': 'http://127.0.0.1:3107'}
        listed = a.get('/api/market/model-connections', headers=headers)
        assert listed.status_code == 200
        assert listed.headers['access-control-allow-credentials'] == 'true'
        assert 'HttpOnly' in listed.headers['set-cookie']
        saved = a.post('/api/market/model-connections', json=dict(name='Test', base_url='https://api.deepseek.com', api_key='never-display-test-key'))
        assert saved.status_code == 200 and 'never-display-test-key' not in saved.text
        identity = saved.json()['id']
        b.get('/api/market/model-connections')
        assert b.delete('/api/market/model-connections/' + identity).status_code == 404
        assert b.get('/api/market/model-connections').json()['items'] == []
        invalid = a.post('/api/market/model-connections', json=dict(name='', base_url='invalid', api_key='never-display-test-key'))
        assert invalid.status_code == 422 and 'never-display-test-key' not in invalid.text
        uploaded = a.post('/api/market/attachments', files={'file': ('reference.txt', b'Unreviewed source reference.', 'text/plain')})
        assert uploaded.status_code == 200
        attachment_id = uploaded.json()['id']
        assert b.get('/api/market/attachments/' + attachment_id).status_code == 404
        assert a.get('/api/market/attachments/' + attachment_id).content == b'Unreviewed source reference.'
        assert a.post('/api/market/model-connections', headers={'Origin':'https://evil.example'}, json=dict(name='x',base_url='https://api.deepseek.com',api_key='test')).status_code == 403


def test_reject_private_destinations_and_unknown_model(tmp_path):
    from london_product.model_connections import validate_endpoint
    for url in ['http://api.deepseek.com', 'https://localhost', 'https://127.0.0.1/v1', 'https://169.254.169.254', 'https://user:secret@toapis.cn/v1']:
        with pytest.raises(ValueError): validate_endpoint(url)
    vault = Connections(Store(tmp_path))
    row = vault.save('a', 'Test', 'https://api.deepseek.com', 'test')
    with pytest.raises(ValueError): vault.select('a', row['id'], 'invented-model', 'standard')


def test_personal_claude_contract_survives_single_system_message_relays():
    from agno.models.message import Message
    from london_product.intelligence import query_model
    from types import SimpleNamespace
    token = ACTIVE_CONNECTION.set(dict(personal=True, model='claude-haiku-4-5', api_key='offline-test-key', base_url='https://toapis.cn/v1', **model_options('https://toapis.cn/v1','claude-haiku-4-5')))
    try:
        model = query_model()
        original = Message(role='system', content='Base safety instructions.')
        messages = [original, Message(role='user',content='Compare vacancy.'), Message(role='tool',tool_name='search_market_evidence',content=json.dumps({'analysis_contract': {'fields':['key_findings']}}))]
        kwargs = dict(messages=messages, run_response=SimpleNamespace(run_id='offline-claude-contract'))
        model._reserve((),kwargs)
        assert 'REPORT_INTERPRETATION_WIRE_V1' in kwargs['messages'][0].content
        assert original.content == 'Base safety instructions.'
    finally: ACTIVE_CONNECTION.reset(token)
