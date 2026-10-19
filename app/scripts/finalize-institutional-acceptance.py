"""Reproducible read-only model receipts and a clearly labelled evidence update."""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
from london_product.store import Store,now
from london_product.service import MarketService
from london_product.chat_report import build_report,read_report,render_markdown,render_html

out=(ROOT/'docs/delivery/institutional-report-acceptance').resolve()
store=Store(out/'runtime');service=MarketService(store)
parent=read_report(store,'bc145e16-f6cf-407e-8072-895a87a02b80')
report=build_report(service,parent['query'],parent_report_id=parent['report_id'],
    key='post-native-evidence-update',acquisition=dict(mode='source_refresh_followup',
    notice='Evidence update after the genuine native model run failed its output usage gate. Uses newly projected original disclosures. No additional model request; no review status changed.'))
for name,artifact in [('native-report',parent),('evidence-update',report)]:
    for suffix,data in [('json',json.dumps(artifact,ensure_ascii=False,indent=2)),('html',render_html(artifact)),('md',render_markdown(artifact))]:
        (out/(name+'.'+suffix)).write_text(data,encoding='utf-8')
baseline=json.loads((out/'review-baseline.json').read_text());changes=[]
for key,original in baseline.items():
    table,identity=key.split(':',1);row=store.get(table,identity)
    if {k:row.get(k) for k in original}!=original:changes.append(key)
ledgers=[]
for path in (store.root/'model-ledgers').glob('*.json'):
    data=json.loads(path.read_text())
    item={k:data.get(k) for k in ['run_id','model','requests','input_tokens','output_tokens','elapsed_seconds','terminal_error','monetary_cost']}
    item['calls']=[{k:c.get(k) for k in ['number','estimated_input','max_output','status','input_tokens','output_tokens','error_type','provider_response_id','provider_model','raw_provider_usage']} for c in data['calls']]
    item['ledger_file']=str(path.relative_to(out));ledgers.append(item)
receipt=dict(at=now(),native_session='e14b1f03-85db-437c-a37d-68cc7e4fd36c',
    native_report_id=parent['report_id'],native_model_run='03fc587a-87c4-4910-94b8-55dbbf3aa998',
    native_run_status='failed_provider_reported_output_limit',native_report_status=parent['generation_status'],
    evidence_update_report_id=report['report_id'],evidence_update_is_model_generated=False,
    existing_review_state_changes=changes,model_runs=ledgers,missing_usage_is_not_zero=True,monetary_cost='N/A',
    native_counts={k:len(parent[k]) for k in ['market_snapshot','related_observations','evidence','data_gaps']},
    updated_counts={k:len(report[k]) for k in ['market_snapshot','related_observations','evidence','data_gaps']},
    charts_released=sum(c['status']=='ready' for c in report['charts']),
    source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'app/london_product').glob('*.py')},
    frontend_build_id=(ROOT/'app/frontend/.next-institutional/BUILD_ID').read_text().strip())
(out/'receipt.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k!='source_sha256'},ensure_ascii=False,indent=2))
service.pool.shutdown(wait=False)
