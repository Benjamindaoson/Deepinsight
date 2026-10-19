"""Offline replay of saved real evidence. Mock Agent; never a model evaluation."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from london_product import intelligence
from london_product.service import MarketService
from london_product.store import Store

EVIDENCE = Path(__file__).parents[1] / 'data/product/evidence'
REAL = json.loads((EVIDENCE / 'real-extraction-v2.json').read_text(encoding='utf-8'))
DOCUMENT = json.loads((EVIDENCE / 'market-closure-20261018/extract/saved-real-document.json').read_text(encoding='utf-8'))


@pytest.fixture
def service(tmp_path):
    result = MarketService(Store(tmp_path))
    result.store.put('sources', DOCUMENT['source']['id'], DOCUMENT['source'])
    result.store.put('documents', DOCUMENT['document']['id'], DOCUMENT['document'])
    return result


def replay(monkeypatch, payload):
    monkeypatch.setattr(intelligence, 'configured_model', lambda *a, **k: None)
    monkeypatch.setattr(intelligence, 'Agent', lambda **k: SimpleNamespace(
        run=lambda _: SimpleNamespace(content=copy.deepcopy(payload), run_id='offline-mock-replay')))


def test_wrong_schema_cannot_cache_empty_success(service, monkeypatch):
    replay(monkeypatch, {'observations': [{'value': '8.4'}]})
    with pytest.raises(RuntimeError, match='EXTRACTION_FAILED'):
        intelligence.extract_document(service, REAL['document_id'], 'offline-workflow')
    attempt = service.store.all('extractions')[0]
    assert attempt['status'] == 'failed'
    assert attempt['error_code'] == 'EXTRACTION_SCHEMA_INVALID'
    assert attempt['raw_output'] == {'observations': [{'value': '8.4'}]}
    assert service.store.all('facts') == []


def test_all_unbound_quotes_cannot_succeed(service, monkeypatch):
    raw = copy.deepcopy(REAL['raw_output'])
    raw['facts'] = raw['facts'][:1]
    raw['facts'][0]['quote'] = 'A fabricated quotation with 8.4%.'
    replay(monkeypatch, raw)
    with pytest.raises(RuntimeError, match='EXTRACTION_FAILED'):
        intelligence.extract_document(service, REAL['document_id'], 'offline-workflow')
    attempt = service.store.all('extractions')[0]
    assert attempt['error_code'] == 'EXTRACTION_NO_VALID_FACTS'
    assert attempt['rejected_candidates'][0]['reason'] == 'QUOTE_OR_SEGMENT_NOT_EXACT'
    assert service.store.all('facts') == []


def test_saved_real_response_replay_and_idempotency(service, monkeypatch):
    replay(monkeypatch, REAL['raw_output'])
    result = intelligence.extract_document(service, REAL['document_id'], 'offline-workflow')
    assert len(result['fact_ids']) == 8
    facts = service.store.all('facts')
    assert all(f['human_review_status'] == 'pending_review' for f in facts)
    assert all(f['status'] != 'approved' for f in facts)
    # The annual basis is always recorded; a convention-derived value stays
    # pending review and is flagged, never silently promoted.
    rents = [f for f in facts if f['metric'] == 'rent']
    assert rents, 'fixture must contain at least one rent observation'
    for fact in rents:
        assert fact['annualization'] in ('explicit', 'industry_convention', 'unknown')
        assert fact['status'] in ('pending_review', 'needs_review')
        if fact['annualization'] == 'unknown':
            assert fact['normalized_value'] is None
            assert 'ANNUAL_TIME_DENOMINATOR_NOT_CONFIRMED' in fact['normalization_notes']
        else:
            assert fact['normalized_value'] is not None
            assert fact['normalized_unit'].endswith('/year')
            assert 'ANNUAL_TIME_DENOMINATOR_NOT_CONFIRMED' not in fact['normalization_notes']
        if fact['annualization'] == 'industry_convention':
            assert 'ANNUAL_BASIS_ASSUMED_BY_CONVENTION' in fact['normalization_notes']
    monkeypatch.setattr(intelligence, 'configured_model', lambda *a, **k: pytest.fail('cached import invoked model'))
    again = intelligence.extract_document(service, REAL['document_id'], 'offline-workflow-2')
    assert again['cached'] and again['model_requests'] == 0
    assert service.store.all('facts') == facts


def test_existing_success_cache_remains_usable_without_model(service, monkeypatch):
    import hashlib
    current = dict(REAL, version='product-extract-v2-'+hashlib.sha256((intelligence.APP/'product_skills/fact-extraction/SKILL.md').read_bytes()).hexdigest()[:12])
    service.store.put('extractions', 'current-version-cache-control', current)
    monkeypatch.setattr(intelligence, 'configured_model', lambda *a, **k: pytest.fail('historical cache invoked model'))
    result = intelligence.extract_document(service, REAL['document_id'], 'offline-cache')
    assert result['cached'] and result['model_requests'] == 0
    assert result['extraction_id'] == REAL['id']
