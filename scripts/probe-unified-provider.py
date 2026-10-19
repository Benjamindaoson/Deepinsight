"""One authorized minimal real provider request. Never print credentials or raw headers."""
import datetime
import json
import pathlib
import sys
import httpx

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/delivery/unified-release-20261019-r1'
receipt=OUT/'PROVIDER_PROBE.json'
if receipt.exists():raise SystemExit('Probe already has a receipt; do not silently repeat it.')
config=json.loads((ROOT/'secrets/model.deepseek-acceptance-20261019.json').read_text(encoding='utf-8-sig'))
url=config['base_url'].rstrip('/')+'/chat/completions'
if not config['base_url'].rstrip('/').endswith('/v1'):url=config['base_url'].rstrip('/')+'/chat/completions'
result=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),endpoint=config['base_url'],model=config['model'],purpose='One minimal provider availability probe; not browser/business acceptance.')
try:
    response=httpx.post(url,headers={'Authorization':'Bearer '+config['api_key']},
        json=dict(model=config['model'],messages=[dict(role='user',content='Reply OK')],max_tokens=1,thinking={'type':'disabled'},stream=False),timeout=45)
    result['http_status']=response.status_code
    payload=response.json()
    if response.status_code==200:
        result.update(provider_response_id=payload.get('id'),actual_model=payload.get('model'),usage=payload.get('usage'),result='returned')
    else:
        error=payload.get('error',{})
        result.update(result='failed',error_type=error.get('type'),error_code=error.get('code'),
            message=str(error.get('message','Provider request failed')).replace(config['api_key'],'[REDACTED]')[:350])
except Exception as exc:
    result.update(result='failed',error_type=type(exc).__name__,usage=None)
receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
if result.get('http_status')!=200 or not result.get('usage'):sys.exit(1)
