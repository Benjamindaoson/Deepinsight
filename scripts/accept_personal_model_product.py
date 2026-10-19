"""Authorized bounded acceptance against the running product, no mock model output."""
import base64, json, sys, time
from pathlib import Path
import httpx
sys.path.insert(0, str(Path('app').resolve()))
from london_product.model_connections import _dpapi

out = Path(Path('docs/delivery/ACTIVE_CHAT_MODELS_DELIVERY.txt').read_text().strip())
connections = json.loads(_dpapi(base64.b64decode((out/'PRIVATE_CONNECTION_IMPORT.dpapi').read_bytes()), True))
receipts = []
with httpx.Client(base_url='http://127.0.0.1:7788', timeout=210) as client:
    client.get('/api/market/model-connections').raise_for_status()
    profiles = []
    for data in connections:
        r = client.post('/api/market/model-connections', json=data); r.raise_for_status()
        row = r.json()
        discovered = client.post('/api/market/model-connections/' + row['id'] + '/discover'); discovered.raise_for_status()
        profiles.append(discovered.json())
    upload = client.post('/api/market/attachments', files={'file': ('user-scope.txt', b'Research scope: compare the City and West End. Use original market evidence; disclose missing data and never approve unreviewed facts.', 'text/plain')})
    upload.raise_for_status()
    for mode, question in [('standard', 'Compare City and West End vacancy and leasing take-up in Q1 and Q2 2026. Explain supported risks and opportunities and disclose limitations.'), ('deep', 'Compare City and West End vacancy in Q1 and Q2 2026 and explain the limitations of this comparison.')]:
        payload = dict(message=question, mode='agent', connection_id=profiles[0]['id'], model='deepseek-flash', thinking=mode,
                       attachment_ids=[upload.json()['id']] if mode == 'standard' else [])
        started=time.perf_counter()
        r=client.post('/api/market/ask', json=payload)
        events=[]
        for block in r.text.split('\n\n'):
            if block.startswith('data: '): events.append(json.loads(block[6:]))
        receipt=dict(mode=mode,status=r.status_code,seconds=time.perf_counter()-started,request=payload,events=events)
        receipts.append(receipt)
        (out/'PERSONAL_CHAT_ACCEPTANCE.json').write_text(json.dumps(dict(profiles=profiles,upload=upload.json(),runs=receipts),ensure_ascii=False,indent=2),encoding='utf-8')
        print(mode,r.status_code,[(e.get('type'),e.get('code'),e.get('outcome')) for e in events if e.get('type') in ['done','error']],flush=True)
