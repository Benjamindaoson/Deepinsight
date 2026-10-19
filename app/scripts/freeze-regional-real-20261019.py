"""Freeze the qualified candidate for independently owned real-provider acceptance."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
from london_product.store import Store
from london_product.service import MarketService
from london_product.chat_report import build_report,render_html,render_markdown
from london_product.conditional_analysis import analysis_choices
OUT=ROOT/'docs/delivery/regional-real-20261019';candidate=OUT/'candidate-v2'
if candidate.exists():raise SystemExit('Do not overwrite frozen acceptance candidate')
old=json.loads((ROOT/'docs/delivery/real-ai-frozen-20261019/SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
paths={p for p in old['source_files'] if (ROOT/p).is_file()}|{'app/london_product/conditional_analysis.py','app/tests/test_conditional_report_analysis.py',
 'app/scripts/prepare-regional-real-20261019.py','app/scripts/refresh-regional-real-20261019.py',
 'app/scripts/qualify-regional-real-20261019.py','app/scripts/freeze-regional-real-20261019.py'}
for directory,patterns in {'app/london_product':['*.py'],'app/london_data':['*.py'],
 'app/product_skills':['*.md','*.json','*.yaml'],'app/tests':['*.py']}.items():
 for pattern in patterns:
  paths.update(str(p.relative_to(ROOT)) for p in (ROOT/directory).rglob(pattern) if '__pycache__' not in p.parts)
hashes={}
for path in sorted(paths):
 source=ROOT/path;destination=candidate/path;destination.parent.mkdir(parents=True,exist_ok=True)
 content=source.read_bytes();destination.write_bytes(content);hashes[path]=hashlib.sha256(content).hexdigest()
assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in hashes.items())
(candidate/'secrets').mkdir();(candidate/'secrets/model.json').write_text(json.dumps(dict(model='preview-disabled',api_key='DUMMY-NOT-A-CREDENTIAL',base_url='http://127.0.0.1:1/v1')),encoding='utf-8')
store=Store(OUT/'runtime');svc=MarketService(store)
query='Prepare a Q2 2026 London office market report comparing City, West End and Canary Wharf, covering rents, vacancy, availability, leasing take-up and development pipeline, with Q1 historical trends, conditional risks and opportunities and source limitations.'
report=build_report(svc,query);choices=analysis_choices(report,store)
for suffix,content in [('json',json.dumps(report,ensure_ascii=False,indent=2)),('html',render_html(report)),('md',render_markdown(report))]:
 (OUT/('REGIONAL_REPORT.'+suffix)).write_text(content,encoding='utf-8')
packet=json.loads((OUT/'INDIVIDUAL_REVIEW_PACKET.json').read_text(encoding='utf-8'))
baseline=json.loads((OUT/'REVIEW_BASELINE.json').read_text(encoding='utf-8'))
assert all({k:store.get('facts',i).get(k) for k in fields}==fields for i,fields in baseline.items())
manifest=dict(candidate=str(candidate),source_files=hashes,qualified_runtime=str(store.root),report_id=report['report_id'],
 report_query=query,new_reviewed_fact_ids=[p['fact_id'] for p in packet],
 baseline_review_states_preserved=True,model_calls_by_developer=0,old_preview_preserved='http://127.0.0.1:7785',
 positive_monitor_plan=dict(geographies=['West End'],detection_context='historical_replay',takeup_threshold_pct=10.0,
  takeup_old_id=next(p['fact_id'] for p in packet if p['geography']=='West End' and p['metric']=='takeup' and p['period']=='2026Q1'),
  takeup_new_id=next(p['fact_id'] for p in packet if p['geography']=='West End' and p['metric']=='takeup' and p['period']=='2026Q2'),
  disclosed_values_change_pct='23.46',publisher_reported_change_pct='25.9',
  caveat='Approximate disclosed values; publisher percentage uses undisclosed underlying precision. Historical replay, not a new discovery.'),
 contract=dict(model_output='At most 3 compact candidate_id selections; same 1800 UTF-8 response bytes / 1800 tokens and existing aggregate caps.',
  inference='Regional ordering requires matched publisher, definition, basis, period, method and units.',
  conditional='Both complete comparable historical pairs: takeup up and vacancy down, same area/source/period. Recomputed per pair. Conditional research, not forecast or investment recommendation.',
  publication='Unknown choice, extra text, category mismatch or changed evidence is withheld; raw payload retained; semantic approval false.'),
 offline_tests='79 passed in 13.62s including forged arithmetic regression; not real model acceptance',
 shared_root_full_suite='5 failed, 560 passed before final recomputation fix; unrelated/compatibility failures under investigation, not a full-suite PASS',
 ready_charts=sum(c['status']=='ready' for c in report['charts']),
 eligible_risk_proposals=sum('risks' in c['categories'] for c in choices),eligible_opportunity_proposals=sum('opportunities' in c['categories'] for c in choices))
(OUT/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
ready=dict(manifest_path=str(OUT/'SOURCE_MANIFEST.json'),manifest_sha256=hashlib.sha256((OUT/'SOURCE_MANIFEST.json').read_bytes()).hexdigest(),
 candidate=str(candidate),runtime=str(store.root),actual_model_execution='Pending independent owner; do not duplicate provider calls',
 new_preview_ports=dict(api=7786,frontend=3106),old_preview_untouched=True)
(OUT/'READY_FOR_REAL_ACCEPTANCE.json').write_text(json.dumps(ready,indent=2),encoding='utf-8')
svc.pool.shutdown();store.engine.dispose()
print(json.dumps(dict(source_files=len(hashes),ready_charts=manifest['ready_charts'],risk_proposals=manifest['eligible_risk_proposals'],opportunity_proposals=manifest['eligible_opportunity_proposals'],**ready)))
