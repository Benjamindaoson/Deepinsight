"""Bounded engineering regressions on frozen code; not real-provider acceptance."""
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/delivery/unified-release-20261019-r1'
APP=OUT/'accepted-backend/app'
sys.dont_write_bytecode=True
sys.path.insert(0,str(APP))
os.environ.pop('LONDON_RELEASE_MANIFEST',None)
with tempfile.TemporaryDirectory(prefix='unified-regression-') as temporary:
    config=Path(temporary)/'model.json'
    calibration=json.loads((APP/'london_product/qa-token-calibration.json').read_text())
    config.write_text(json.dumps(dict(model=calibration['model'],base_url=calibration['endpoint'],api_key='offline-regression-not-a-provider-key')))
    os.environ['LONDON_MODEL_CONFIG']=str(config)
    for key in ['LONDON_TAVILY_ENABLED','LONDON_JEV_ROUTING_ENABLED','LONDON_JEV_SHADOW_ENABLED']:os.environ[key]='0'
    import pytest
    from london_product import intelligence
    assert Path(intelligence.__file__).is_relative_to(APP)
    tests=['test_unified_release.py','test_skill_execution.py','test_skill_runtime_guardrails.py',
        'test_native_saved_query.py','test_personal_models.py','test_request_report_reuse.py',
        'test_skill_scope_regression.py','test_explicit_period_comparison.py']
    print('Frozen source:',intelligence.__file__)
    print('Engineering evidence only. Existing fixture transport tests do not establish real model success.')
    raise SystemExit(pytest.main(['-q','-o','pythonpath='+str(APP),*[str(ROOT/'app/tests'/name) for name in tests]]))
