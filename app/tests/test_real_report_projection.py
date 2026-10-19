"""Regression for actual accepted DeepSeek run restored as 'draft withheld'."""
import copy
import json
from pathlib import Path

import pytest
from london_product.safe_answer import project_run
from london_product.store import Store


@pytest.mark.parametrize('ai_status,accepted,report_status,gate,expected', [
    ('published', True, 'partial', 'evidence_checked', 'ai_limited_checks'),
    ('published', True, 'success', 'evidence_checked', 'ai_limited_checks'),
    ('withheld', False, 'partial', 'evidence_checked', 'deterministic_evidence_fallback'),
    ('failed', False, 'partial', 'evidence_checked', 'deterministic_evidence_fallback'),
    ('pending', False, 'partial', 'evidence_checked', 'deterministic_evidence_fallback'),
    ('published', False, 'partial', 'evidence_checked', 'deterministic_evidence_fallback'),
    ('published', True, 'insufficient_evidence', 'withheld', 'deterministic_evidence_fallback'),
    ('published', True, 'partial', 'withheld', 'deterministic_evidence_fallback'),
])
def test_saved_real_report_projection(tmp_path, monkeypatch, ai_status, accepted, report_status, gate, expected):
    fixture = json.loads((Path(__file__).parent / 'fixtures/real_report_projection.json').read_text(encoding='utf-8'))
    report = copy.deepcopy(fixture['report'])
    report['ai_analysis']['status'] = ai_status
    if not accepted:
        report['ai_analysis']['accepted'] = []
    report['generation_status'] = report_status
    report['publication_review']['status'] = gate
    checked = []
    def revalidated(store, identity):
        checked.append(identity)
        return report
    monkeypatch.setattr('london_product.chat_report.read_report', revalidated)
    store = Store(tmp_path)
    try:
        result = project_run(fixture['run'], store)
        assert checked == [report['report_id']]
        assert result['answer_origin'] == expected
        assert result['publication_review']['status'] == ('limited_checks_passed' if expected == 'ai_limited_checks' else 'withheld')
        assert result['publication_review']['semantic_approval'] is False
        assert result['report_id'] == report['report_id']
        assert 'raw_answer' not in result
        assert fixture['run']['content'] not in result['answer']
    finally:
        store.engine.dispose()
