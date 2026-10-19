"""Explicitly authorized finite provider probes. Keys are read without echo; never recorded."""
import asyncio, getpass, json, time
from pathlib import Path
import httpx

async def main():
    relay = getpass.getpass('Toapis key (hidden): ')
    official = getpass.getpass('Official DeepSeek key (hidden): ')
    output = Path('docs/delivery/ACTIVE_CHAT_MODELS_DELIVERY.txt').read_text().strip()
    rows = []
    async def probe(base, key, model, extra=None):
        payload=dict(model=model, messages=[dict(role='user',content='Reply with exactly READY.')],max_tokens=128,stream=False)
        payload.update(extra or {})
        started=time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=45,follow_redirects=False) as client:
                r=await client.post(base+'/chat/completions',headers={'Authorization':'Bearer '+key},json=payload)
            body=r.json()
            # Provider bodies must never carry the submitted credential into receipts.
            safe=json.loads(json.dumps(body).replace(key,'[REDACTED]'))
            row=dict(endpoint=base,requested_model=model,status=r.status_code,seconds=time.perf_counter()-started,request=payload,response=safe)
        except Exception as exc:row=dict(endpoint=base,requested_model=model,status='transport_error',error_type=type(exc).__name__)
        rows.append(row)
        print(json.dumps({k:row[k] for k in ['endpoint','requested_model','status','seconds'] if k in row}),flush=True)
    catalogs={}
    for base,key in [('https://toapis.cn/v1',relay),('https://api.deepseek.com',official)]:
        try:
            async with httpx.AsyncClient(timeout=25) as client:r=await client.get(base+'/models',headers={'Authorization':'Bearer '+key})
            ids=sorted(x['id'] for x in r.json().get('data',[])) if r.status_code==200 else []
            catalogs[base]=dict(status=r.status_code,models=ids)
            print(base,'discovery',r.status_code,len(ids),'models',flush=True)
        except Exception as exc:catalogs[base]=dict(status='transport_error',error_type=type(exc).__name__)
    ids=catalogs.get('https://toapis.cn/v1',{}).get('models',[])
    selected=[]
    for family,preferred in [('gpt',['gpt-4.1-mini','gpt-4o-mini','gpt-5-mini']),('gemini',['gemini-2.5-flash','gemini-2.0-flash']),('claude',['claude-sonnet-4-6','claude-haiku-4-5-20251001','claude-sonnet-4-5-20250929'])]:
        selected.append(next((m for m in preferred if m in ids),next((m for m in ids if m.startswith(family)),None)))
    for model in selected:
        if model:await probe('https://toapis.cn/v1',relay,model)
    if 'deepseek-flash' in catalogs.get('https://api.deepseek.com',{}).get('models',[]):
        await probe('https://api.deepseek.com',official,'deepseek-flash',{'thinking':{'type':'disabled'}})
        await probe('https://api.deepseek.com',official,'deepseek-flash',{'thinking':{'type':'enabled'},'reasoning_effort':'high','max_tokens':1024})
    Path(output,'PROVIDER_PROBES.json').write_text(json.dumps(dict(catalogs=catalogs,probes=rows),ensure_ascii=False,indent=2),encoding='utf-8')
    # Encrypted import bundle, bound to this Windows account. Not an environment file.
    import sys
    sys.path.insert(0,str(Path('app').resolve()))
    from london_product.model_connections import _dpapi
    import base64
    Path(output,'PRIVATE_CONNECTION_IMPORT.dpapi').write_bytes(base64.b64encode(_dpapi(json.dumps([
        dict(name='DeepSeek Official',base_url='https://api.deepseek.com',api_key=official),
        dict(name='Toapis',base_url='https://toapis.cn/v1',api_key=relay)]).encode())))

asyncio.run(main())
