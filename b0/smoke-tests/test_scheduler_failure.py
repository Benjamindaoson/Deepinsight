"""Native schedule enable/disable/manual-trigger/failure-state test; no model request."""
import json
import time
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[2]
receipt={}
sid=None
with httpx.Client(base_url='http://127.0.0.1:7777',trust_env=False,timeout=10) as c:
    try:
        r=c.post('/schedules',json={'name':'b0-failure-'+str(int(time.time())),
            'cron_expr':'0 0 1 1 *','endpoint':'/agents/b0-intentionally-missing/runs',
            'payload':{'message':'B0 failure-state check'},'timeout_seconds':15,'max_retries':0})
        r.raise_for_status()
        receipt['created']=r.json()
        sid=r.json()['id']
        for action in ('disable','enable','trigger'):
            r=c.post(f'/schedules/{sid}/{action}')
            receipt[action]={'status':r.status_code,'body':r.json()}
            r.raise_for_status()
        for _ in range(25):
            r=c.get(f'/schedules/{sid}/runs')
            rows=r.json()['data']
            if rows and rows[0]['status'] not in ('pending','running'):
                receipt['history']=r.json()
                break
            time.sleep(1)
        receipt['result']='PASS' if receipt.get('history',{}).get('data',[{}])[0].get('status')=='failed' else 'FAIL'
    except Exception as e:
        receipt.update(result='FAIL',error=str(e))
    finally:
        if sid:
            try:
                r=c.post(f'/schedules/{sid}/disable')
                receipt['final_disabled']={'status':r.status_code,'body':r.json()}
                r.raise_for_status()
            except Exception as e:
                receipt['cleanup_error']=str(e)
if receipt.get('final_disabled',{}).get('body',{}).get('enabled') is not False:
    receipt['result']='FAIL'
(root/'b0/evidence/api-results/T07-scheduler-failure.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2))
raise SystemExit(0 if receipt.get('result')=='PASS' else 1)
