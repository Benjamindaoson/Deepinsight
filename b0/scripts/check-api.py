import json
import time
import urllib.request
import urllib.error
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = {}
for route in ('health', 'info', 'config', 'docs', 'agents', 'teams', 'workflows', 'openapi.json'):
    start = time.monotonic()
    try:
        with urllib.request.urlopen('http://localhost:7777/' + route, timeout=20) as r:
            body = r.read().decode()
            try:
                body = json.loads(body)
            except ValueError:
                pass
            out[route] = {'status': r.status, 'seconds': round(time.monotonic()-start, 3), 'body': body}
    except urllib.error.HTTPError as e:
        out[route] = {'status': e.code, 'body': e.read().decode()}
    except Exception as e:
        out[route] = {'error': str(e)}
(root / 'b0/evidence/api-results/runtime-api.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps({k:{x:y for x,y in v.items() if x!='body'} for k,v in out.items()}, indent=2))
