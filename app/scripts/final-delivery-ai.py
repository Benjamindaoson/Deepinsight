"""Small real AgentOS acceptance, preserving terminal failure and no provider retries."""
import json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
OUT=ROOT/'docs/delivery/final-delivery-20261019'
os.environ['LONDON_TAVILY_ENABLED']='0';os.environ['LONDON_JEV_ROUTING_ENABLED']='0'
os.environ['LONDON_JEV_SHADOW_ENABLED']='0';os.environ.pop('LONDON_NOTIFICATION_URL',None)
from fastapi.testclient import TestClient
from london_product.runtime import create_app
from london_product.store import now
app=create_app(OUT/'isolated',seed=False,scheduler=False,frontend_port=3106)
service=app.state.market
cases=[('A','What was the West End overall office vacancy rate in Q2 2026? Give the period, geographic definition, unit and source.'),
 ('B','Compare City prime office rent Q1 2026 and Q2 2026. Calculate a change only if source, annual unit and review status are comparable.'),
 ('C','Explain one saved London office development or leasing event. Separate sourced event facts from possible tenant and landlord implications.'),
 ('D','What is the exact Canary Wharf Grade A vacancy rate for October 2026 and its change from September? State explicitly if the saved evidence cannot answer.'),
 ('E','Prepare a Q2 2026 City office market report from saved verified evidence and identify evidence gaps.')]
receipt=dict(started_at=now(),scope='User requested targeted real-model A-E acceptance, existing credentials only; no external search or notifications.',runs=[])
path=OUT/'real-ai-acceptance.json'
if path.exists():raise SystemExit('Preserve previous calls; no automatic rerun')
def persist():path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
with TestClient(app) as client:
 for label,question in cases:
    started=time.monotonic()
    response=client.post('/api/market/ask',json=dict(message=question,mode='agent'))
    events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    final=next((e for e in reversed(events) if e.get('type') in ['done','error']),{})
    job=service.store.get('jobs',final.get('submission_id',''))
    receipt['runs'].append(dict(case=label,question=question,http_status=response.status_code,seconds=round(time.monotonic()-started,3),events=events,final=final,job=job))
    persist();print(json.dumps(dict(case=label,terminal=final.get('type'),code=final.get('code'),requests=final.get('metrics',{}).get('requests')),ensure_ascii=False),flush=True)
    if final.get('code') in ['PROVIDER_QUOTA_EXHAUSTED','PROVIDER_ERROR','MODEL_TIMEOUT']:
        receipt['blocked_remaining_cases']=[x[0] for x in cases if x[0]>label]
        receipt['stop_reason']=final.get('code');break
receipt['finished_at']=now();persist()
