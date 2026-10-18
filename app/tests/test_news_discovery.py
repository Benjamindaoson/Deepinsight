"""Offline fixtures; no Tavily, paid model or external notification requests."""
import asyncio
import importlib.util
import json

import httpx
import pytest

from london_product.service import MarketService
from london_product.store import Store
from london_product.sources import catalog


def test_discovery_adapter_exists():
    assert importlib.util.find_spec('london_product.discovery') is not None


def test_notification_configuration_exception_is_recorded(tmp_path, monkeypatch):
    import apprise
    monkeypatch.setenv('LONDON_NOTIFICATION_URL', 'invalid://offline-secret')
    service = MarketService(Store(tmp_path))
    service.save_settings({'notifications_enabled': True})
    report = service.report('weekly')
    monkeypatch.setattr(apprise.Apprise, 'add', lambda *a, **kw: (_ for _ in ()).throw(ValueError('offline-secret')))
    result = service.notify(report['id'])
    assert result['status'] == 'failed'
    assert result['error'] == 'ValueError'
    assert 'offline-secret' not in json.dumps(result)
    assert not any(n['status'] == 'sending' for n in service.store.all('notifications'))


@pytest.fixture
def fixture_service(tmp_path, monkeypatch):
    monkeypatch.delenv('LONDON_TAVILY_API_KEY', raising=False)
    monkeypatch.delenv('LONDON_TAVILY_ENABLED', raising=False)
    service = MarketService(Store(tmp_path))
    for source in catalog():
        service.store.put('sources', source['id'], source)
    yield service
    service.pool.shutdown()


def test_generic_key_is_never_used(fixture_service, monkeypatch):
    from london_product import discovery
    monkeypatch.setenv('TAVILY_API_KEY', 'old-key-do-not-use')
    monkeypatch.setenv('LONDON_TAVILY_ENABLED', '1')
    monkeypatch.setattr(discovery, '_transport', lambda: pytest.fail('No network permitted'))
    result = asyncio.run(discovery.refresh_candidates(fixture_service))
    assert result['status'] == 'configuration_missing' and result['requests'] == 0
    assert not fixture_service.store.all('events')


def test_search_contract_filters_urls_and_drops_snippets(fixture_service, monkeypatch):
    from london_product import discovery, sources
    calls = []
    monkeypatch.setenv('LONDON_TAVILY_API_KEY', 'new-offline-fixture')
    monkeypatch.setenv('LONDON_TAVILY_ENABLED', '1')
    def handler(request):
        calls.append(request)
        data = json.loads(request.content)
        assert data['search_depth'] == 'fast' and data['topic'] == 'news'
        assert data['max_results'] == 5 and data['include_answer'] is False
        assert data['include_raw_content'] is False and data['auto_parameters'] is False
        assert 'www.knightfrank.co.uk' not in data['include_domains']
        return httpx.Response(200, json={'request_id': 'offline-receipt', 'usage': {'credits': 1}, 'results': [
            {'url': 'https://www.gpe.co.uk/news-media/news/2026/office-lease/?utm_source=x', 'content': 'UNTRUSTED SEARCH CLAIM', 'title': 'SEARCH TITLE'},
            {'url': 'https://www.gpe.co.uk/news-media/news/2026/office-lease/#duplicate'},
            {'url': 'https://www.knightfrank.co.uk/research/london'},
            {'url': 'https://www.gpe.co.uk.evil.invalid/london'},
            {'url': 'https://127.0.0.1/london'}]})
    monkeypatch.setattr(discovery, '_transport', lambda: httpx.MockTransport(handler))
    async def fetch(source, **kwargs):
        assert source['allowed_hosts'] == ['www.gpe.co.uk']
        return dict(status_code=200, url=source['url'], content=b'<main><h1>Original London office letting</h1><p>London office lease agreed in this offline fixture, subject to human review.</p></main>', media='text/html')
    monkeypatch.setattr(sources, 'fetch_source', fetch)
    first = asyncio.run(discovery.refresh_candidates(fixture_service))
    second = asyncio.run(discovery.refresh_candidates(fixture_service))
    assert len(calls) == 1 and second['requests'] == 0 and second['reused_search']
    assert first['provider_request_id'] == 'offline-receipt'
    assert first['usage'] == {'credits': 1}
    assert len(first['candidates']) == 1 and first['rejected_count'] == 3
    assert len(fixture_service.store.all('documents')) == 1
    assert len(fixture_service.store.all('events')) == 1
    event = fixture_service.store.all('events')[0]
    assert event['status'] == 'pending_review'
    assert 'UNTRUSTED SEARCH CLAIM' not in json.dumps(fixture_service.store.all('jobs'))
    assert 'SEARCH TITLE' not in event['title']
    assert fixture_service.store.all('facts') == []


def test_unavailable_original_is_candidate_not_event_and_retry_recovers(fixture_service, monkeypatch):
    from london_product import discovery, sources
    monkeypatch.setenv('LONDON_TAVILY_API_KEY', 'new-offline-fixture')
    monkeypatch.setenv('LONDON_TAVILY_ENABLED', '1')
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'results': [
            {'url': 'https://www.gpe.co.uk/news-media/news/2026/lease/'},
            {'url': 'https://www.britishland.com/news/office-lease/'}]})
    monkeypatch.setattr(discovery, '_transport', lambda: httpx.MockTransport(handler))
    failures = [True]
    async def fetch(source, **kwargs):
        if source['id'] == 'gpe' and failures[0]: raise TimeoutError('offline source timeout')
        return dict(status_code=200, url=source['url'], content=b'<main>London office lease agreed. Original evidence from an offline fixture.</main>', media='text/html')
    monkeypatch.setattr(sources, 'fetch_source', fetch)
    first = asyncio.run(discovery.refresh_candidates(fixture_service))
    assert first['status'] == 'partial'
    missing = next(c for c in first['candidates'] if c['source_id'] == 'gpe')
    assert missing['status'] == 'needs_review' and missing['document_id'] is None
    assert len(fixture_service.store.all('events')) == 1
    failures[0] = False
    second = asyncio.run(discovery.refresh_candidates(fixture_service))
    assert second['status'] == 'succeeded' and len(requests) == 1
    assert len(fixture_service.store.all('events')) == 2
    assert all(e['status'] == 'pending_review' for e in fixture_service.store.all('events'))


@pytest.mark.parametrize('status', [302, 401, 429, 500])
def test_failed_search_not_retried_in_window(fixture_service, monkeypatch, status):
    from london_product import discovery
    monkeypatch.setenv('LONDON_TAVILY_API_KEY', 'new-offline-fixture')
    monkeypatch.setenv('LONDON_TAVILY_ENABLED', '1')
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={'location': 'https://evil.invalid/'})
    monkeypatch.setattr(discovery, '_transport', lambda: httpx.MockTransport(handler))
    assert asyncio.run(discovery.refresh_candidates(fixture_service))['status'] == 'failed'
    assert asyncio.run(discovery.refresh_candidates(fixture_service))['status'] == 'failed'
    assert len(calls) == 1


def test_redirect_cannot_switch_publisher_or_restricted_source(monkeypatch):
    from london_product import sources
    for target in ['https://www.knightfrank.co.uk/report', 'https://www.britishland.com/news/office/']:
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(302, headers={'location': target})
        monkeypatch.setattr(sources, '_make_transport', lambda: httpx.MockTransport(handler))
        with pytest.raises(ValueError, match='SOURCE_POLICY'):
            asyncio.run(sources.fetch_source({'id': 'gpe', 'url': 'https://www.gpe.co.uk/news/', 'allowed_hosts': ['www.gpe.co.uk']}))
        assert len(calls) == 1


def test_news_refresh_reuses_adapter_without_new_scheduler(fixture_service, monkeypatch):
    from london_product import discovery, sources
    calls = []
    async def candidates(service):
        calls.append(service)
        return dict(status='failed', requests=1, candidates=[], error='offline-search-failure', failures=1, successes=0)
    async def fetch(source, **kwargs):
        if source['id'].startswith('planning-api-'):
            return dict(status_code=200, url=source['url'],
                        content=b'{"hits":{"hits":[]}}', media='application/json')
        return dict(status_code=200, url=source['url'], content=b'<main>Offline listing with no links.</main>', media='text/html')
    monkeypatch.setattr(discovery, 'refresh_candidates', candidates)
    monkeypatch.setattr(sources, 'fetch_source', fetch)
    result = asyncio.run(fixture_service.refresh({'category': 'news'}))
    assert result['successes'] > 0 and result['failures'] == 1
    assert len(calls) == 1 and result['discovery']['status'] == 'failed'
    asyncio.run(fixture_service.refresh({'source_id': 'gpe'}))
    assert len(calls) == 1  # individual source retry never spends search credits


def test_notification_preflight_is_redacted_and_never_sends(fixture_service, monkeypatch):
    import apprise
    monkeypatch.delenv('LONDON_NOTIFICATION_URL', raising=False)
    assert fixture_service.notification_configuration()['status'] == 'configuration_missing'
    monkeypatch.setenv('LONDON_NOTIFICATION_URL', 'json://127.0.0.1:12345/private-token')
    monkeypatch.setattr(apprise.Apprise, 'notify', lambda *a, **kw: pytest.fail('Preflight cannot send'))
    result = fixture_service.notification_configuration()
    assert result['status'] == 'configured' and result['destinations'] == 1
    assert result['connection_tested'] is False and result['external_delivery_verified'] is False
    assert 'private-token' not in json.dumps(result)
    monkeypatch.setenv('LONDON_NOTIFICATION_URL', 'not-an-apprise-url')
    assert fixture_service.notification_configuration()['status'] == 'configuration_invalid'


def test_send_exception_keeps_unknown_outcome_and_prevents_retry(fixture_service, monkeypatch):
    import apprise
    monkeypatch.setenv('LONDON_NOTIFICATION_URL', 'json://127.0.0.1:12345/offline')
    fixture_service.save_settings({'notifications_enabled': True})
    report = fixture_service.report('weekly')
    calls = []
    def send(*a, **kw):
        calls.append(1)
        raise TimeoutError('Could have reached receiver; offline fixture')
    monkeypatch.setattr(apprise.Apprise, 'notify', send)
    first = fixture_service.notify(report['id'])
    second = fixture_service.notify(report['id'])
    assert first['status'] == second['status'] == 'delivery_unknown'
    assert first['id'] == second['id'] and len(calls) == 1


def test_discovery_requires_enable_and_pins_api_destination(fixture_service, monkeypatch):
    from london_product import discovery, sources
    monkeypatch.setenv('LONDON_TAVILY_API_KEY', 'offline-new')
    monkeypatch.setattr(discovery, '_transport', lambda: pytest.fail('Disabled means no HTTP'))
    assert asyncio.run(discovery.refresh_candidates(fixture_service))['status'] == 'disabled'
    monkeypatch.setattr(sources.socket, 'getaddrinfo', lambda *a: [(2, 1, 6, '', ('127.0.0.1', 443))])
    with pytest.raises(ValueError, match='DNS destination is not public'):
        asyncio.run(sources._resolve_public('api.tavily.com', 443, {'api.tavily.com'}))


def test_failed_search_survives_restart_and_registry_changes(fixture_service, monkeypatch):
    from london_product import discovery
    monkeypatch.setenv('LONDON_TAVILY_API_KEY', 'offline-new')
    monkeypatch.setenv('LONDON_TAVILY_ENABLED', '1')
    calls = []
    def timeout(request):
        calls.append(1)
        raise httpx.ReadTimeout('offline only')
    monkeypatch.setattr(discovery, '_transport', lambda: httpx.MockTransport(timeout))
    assert asyncio.run(discovery.refresh_candidates(fixture_service))['status'] == 'failed'
    fixture_service.store.update('sources', 'gpe', {'enabled': False})
    restarted = MarketService(Store(fixture_service.store.root))
    restarted.recover_jobs()
    try:
        result = asyncio.run(discovery.refresh_candidates(restarted))
        assert result['requests'] == 0 and result['reused_search']
        assert len(calls) == 1
    finally:
        restarted.pool.shutdown()
