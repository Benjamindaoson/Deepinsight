"""Reproduce the frozen offline regression without a real model key or paid calls."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RELEASE = Path((ROOT / 'docs/delivery/ACTIVE_CHAT_MODELS_DELIVERY.txt').read_text().strip())
APP = RELEASE / 'accepted-backend/app'
sys.path.insert(0, str(APP))

if __name__ == '__main__':
    import pytest
    from london_product import intelligence
    assert Path(intelligence.__file__).is_relative_to(APP)
    fixture = RELEASE / 'data/product/market.sqlite3'
    if not fixture.exists():
        fixture.parent.mkdir(parents=True, exist_ok=True)
        original = ROOT / 'app/data/product/market.sqlite3'
        with sqlite3.connect(original.as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(fixture) as target:
            source.backup(target)
    # The tests replace transports/SDK calls; this is a synthetic test credential,
    # not a provider-validation result and never the production configuration.
    calibration = json.loads((APP / 'london_product/qa-token-calibration.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='deepinsight-offline-verification-') as temporary:
        config = Path(temporary) / 'offline-model.json'
        config.write_text(json.dumps(dict(model=calibration['model'], base_url=calibration['endpoint'], api_key='offline-test-credential')), encoding='utf-8')
        os.environ['LONDON_MODEL_CONFIG'] = str(config)
        names = ['test_personal_models.py', 'test_response_output_bounds.py', 'test_usage_receipts.py',
                 'test_state_assertions.py', 'test_chat_report.py', 'test_request_report_reuse.py',
                 'test_conditional_report_analysis.py', 'test_qa_context_budget.py']
        print('Frozen adapter:', intelligence.__file__)
        raise SystemExit(pytest.main(['-q', *[str(RELEASE / 'accepted-tests' / name) for name in names]]))
