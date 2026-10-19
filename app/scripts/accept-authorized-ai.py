"""Exactly four explicitly authorized questions; no retries, search or messages.

Run only after the user authorizes the 240k input / 32k output envelope. The
existing production QuestionBudget enforces 3 requests, 60k/8k per question.
"""
import json
import os
import sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
if len(sys.argv)!=3 or sys.argv[2]!='--authorized-four-questions':raise SystemExit('Explicit authorization flag required')
out=Path(sys.argv[1]).resolve()
if not out.is_relative_to(ROOT/'docs/delivery'):raise SystemExit('Isolated delivery directory required')
receipt_path=out/'authorized-ai-acceptance.json'
if receipt_path.exists():raise SystemExit('Receipt exists: no automatic repeat paid run')
os.environ['LONDON_TAVILY_ENABLED']='0';os.environ.pop('LONDON_NOTIFICATION_URL',None)
from fastapi.testclient import TestClient
from london_product.runtime import create_app
app=create_app(out/'isolated',seed=False,scheduler=False)
service=app.state.market
questions=[
 'What is the recent trend in prime office rents in London West End?',
 'Compare the City and Canary Wharf office markets in terms of rents, vacancy and leasing activity.',
 'What are the latest notable changes in the Canary Wharf office market?',
 'What major office developments, leasing deals or market events should a London CRE manager pay attention to? Explain one conditional risk and opportunity from saved evidence.'
]
receipt=dict(authorized_at='2026-10-18; explicit user approval in current chat',started_at=datetime.now(timezone.utc).isoformat(),
             scope='Four real Agno saved-evidence research questions; no paid search or external notifications',
             limits=dict(questions=4,requests_per_question=3,input_tokens=240000,output_tokens=32000,retries=0),runs=[])
def persist():receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
persist()
with TestClient(app) as client:
 for index,question in enumerate(questions,1):
  response=client.post('/api/market/ask',json=dict(message=question,mode='agent'))
  events=[]
  for line in response.text.splitlines():
   if line.startswith('data: '):events.append(json.loads(line[6:]))
  final=next((e for e in reversed(events) if e.get('type') in ['done','error']),{})
  answer=''.join(e.get('content','') for e in events if e.get('type')=='token')
  job=service.store.get('jobs',final.get('submission_id',''))
  run=dict(index=index,question=question,http_status=response.status_code,final=final,answer=answer,
           job=job,at=datetime.now(timezone.utc).isoformat())
  receipt['runs'].append(run);persist()
  metrics=final.get('metrics',{})
  print(json.dumps(dict(question=index,type=final.get('type'),run_id=final.get('run_id'),requests=metrics.get('requests'),input=metrics.get('input_tokens'),output=metrics.get('output_tokens'),publication=final.get('publication_review'),answer_chars=len(answer)),ensure_ascii=False),flush=True)
  if metrics.get('input_tokens') is None or metrics.get('output_tokens') is None:
   receipt['stopped_reason']='Provider usage missing; remaining paid questions not attempted';persist();break
  if metrics.get('requests',0)>3 or metrics['input_tokens']>60000 or metrics['output_tokens']>8000:
   receipt['stopped_reason']='Provider exceeded authorized per-question envelope';persist();break
 if receipt['runs'] and receipt['runs'][-1]['final'].get('type')=='done':
  last=receipt['runs'][-1];analysis=dict(last['job']['result'],run_id=last['final']['run_id'],analysis_id=last['job']['id'])
  report=service.report('weekly',key='authorized-ai-reused-'+last['final']['run_id'],analysis=analysis)
  receipt['reused_analysis_report_id']=report['id']
  html=client.get('/api/market/reports/'+report['id']+'?format=html')
  (out/'accepted-ai-report.html').write_text(html.text,encoding='utf-8')
receipt['totals']={k:sum(r['final'].get('metrics',{}).get(k) or 0 for r in receipt['runs']) for k in ['requests','input_tokens','output_tokens']}
receipt['finished_at']=datetime.now(timezone.utc).isoformat();persist()
