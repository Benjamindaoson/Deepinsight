"""Actual AgentOS Workflow HTTP execution; requires explicit real-model flag.

Core workflows are followed by a repeated import, checking database identities and
provider-attempt counts rather than inferring idempotence from HTTP 200.
"""
import argparse,json,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from london_data.pipeline import repository
from london_data.extraction import ROOT

p=argparse.ArgumentParser();p.add_argument('--execute-real-models',action='store_true',required=True);args=p.parse_args()
directory=ROOT/'b1/evidence/api'/('live-'+time.strftime('%Y%m%d-%H%M%S'));directory.mkdir(exist_ok=True)
summary={'runs':[]}
with httpx.Client(base_url='http://127.0.0.1:7778',timeout=490) as client:
    for key in ['bnp-q1-2026','bnp-q2-2026','bnp-q2-2026']:
        before=repository().all('attempts');started=time.time()
        r=client.post('/workflows/london-foundation/runs',data={'message':json.dumps({'document_key':key}),'stream':'false'})
        body=r.json();label='live-'+str(len(summary['runs'])+1)
        (directory/(label+'.json')).write_text(json.dumps(body,ensure_ascii=False,indent=2),encoding='utf8')
        ok=r.status_code==200 and body.get('status')=='COMPLETED' and all(s.get('success') for s in body.get('step_results',[])) and len(body.get('step_results',[]))==7
        after=repository().all('attempts');content=body.get('content',{})
        row={'document':key,'http_status':r.status_code,'status':body.get('status'),'run_id':body.get('run_id'),'elapsed_seconds':time.time()-started,'new_attempts':len(after)-len(before),'cached':content.get('cached'),'path':str(directory/(label+'.json'))}
        if len(summary['runs'])==2:ok=ok and row['cached'] is True and row['new_attempts']==0
        row['pass']=ok;summary['runs'].append(row)
        (directory/'live-workflows.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
        print(json.dumps(row),flush=True)
        if not ok:raise SystemExit(1)
    r=client.post('/workflows/london-foundation/runs',data={'message':json.dumps({'document_key':'unregistered-invalid-input'}),'stream':'false'})
    (directory/'live-invalid-workflow.json').write_text(r.text,encoding='utf8')
    summary['unregistered_input_rejected']=r.status_code!=200 or r.json().get('status')!='COMPLETED'
    (directory/'live-workflows.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    assert summary['unregistered_input_rejected']
    (ROOT/'b1/evidence/api/latest-live-workflows.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
