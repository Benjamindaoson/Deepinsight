import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[2]
receipt={'checked_utc':datetime.now(timezone.utc).isoformat(),'requests':{}}
with httpx.Client(timeout=60,trust_env=False) as client:
    for label,url in {'ui':'http://127.0.0.1:3100','health':'http://127.0.0.1:7777/health',
        'info':'http://127.0.0.1:7777/info','schedules':'http://127.0.0.1:7777/schedules'}.items():
        start=time.monotonic()
        try:
            r=client.get(url)
            value={'status':r.status_code,'seconds':round(time.monotonic()-start,3)}
            if label=='ui':
                value['title']=re.search(r'<title>(.*?)</title>',r.text).group(1)
            else:
                value['body']=r.json()
            receipt['requests'][label]=value
        except Exception as e:
            receipt['requests'][label]={'error':str(e)}
checks={k:v.get('status')==200 for k,v in receipt['requests'].items()}
checks['all_schedules_disabled']=all(not x['enabled'] for x in receipt['requests'].get('schedules',{}).get('body',{}).get('data',[])) and 'body' in receipt['requests'].get('schedules',{})
receipt['checks']=checks
receipt['all_pass']=all(checks.values())
(root/'b0/evidence/api-results/final-live-check.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2))
raise SystemExit(0 if receipt['all_pass'] else 1)
