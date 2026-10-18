"""Observe one natural native cron firing, disable at first claim, retain history."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / 'b0/evidence/api-results/T07-scheduler.json'
receipt = {'started_utc':datetime.now(timezone.utc).isoformat(), 'observations':[]}

def checkpoint():
    PATH.write_text(json.dumps(receipt, indent=2), encoding='utf-8')

sid = None
with httpx.Client(base_url='http://127.0.0.1:7777', timeout=20, trust_env=False) as client:
    try:
        payload={'name':'b0-natural-'+str(int(time.time())), 'cron_expr':'* * * * *',
                 'endpoint':'/agents/b0-agent/runs', 'method':'POST',
                 'payload':{'message':'Confirm this scheduled test in five words.', 'session_id':'b0-natural-schedule'},
                 'timezone':'UTC', 'max_retries':0, 'timeout_seconds':90}
        r=client.post('/schedules',json=payload)
        receipt['create']={'status':r.status_code,'body':r.json()}
        checkpoint()
        r.raise_for_status()
        sid=r.json()['id']
        receipt['schedule_id']=sid
        print('Waiting for natural cron firing:',sid,flush=True)
        deadline=time.monotonic()+160
        disabled=False
        while time.monotonic()<deadline:
            r=client.get(f'/schedules/{sid}/runs')
            r.raise_for_status()
            data=r.json()
            receipt['observations'].append({'utc':datetime.now(timezone.utc).isoformat(), 'history':data})
            rows=data.get('data',[])
            if rows and not disabled:
                d=client.post(f'/schedules/{sid}/disable')
                receipt['disable_on_first_claim']={'status':d.status_code,'body':d.json()}
                d.raise_for_status()
                disabled=True
            checkpoint()
            terminal=[row for row in rows if row['status'] in ('success','failed','timeout','paused')]
            if terminal:
                receipt['natural_run']=terminal[0]
                receipt['result']='PASS' if terminal[0]['status']=='success' and terminal[0].get('run_id') else 'FAIL'
                break
            time.sleep(2)
        else:
            receipt['result']='BLOCKED'
            receipt['error']='No terminal natural run observed within 160 seconds'
    except Exception as e:
        receipt['result']='FAIL'
        receipt['error']=str(e)
    finally:
        if sid:
            try:
                r=client.post(f'/schedules/{sid}/disable')
                receipt['final_disabled']={'status':r.status_code,'body':r.json()}
                receipt['final_history']=client.get(f'/schedules/{sid}/runs').json()
            except Exception as e:
                receipt['cleanup_error']=str(e)
        if receipt.get('cleanup_error') or receipt.get('final_disabled',{}).get('body',{}).get('enabled') is not False:
            receipt['result']='FAIL'
        checkpoint()
print(json.dumps({k:v for k,v in receipt.items() if k!='observations'},indent=2),flush=True)
raise SystemExit(0 if receipt.get('result')=='PASS' else 1)
