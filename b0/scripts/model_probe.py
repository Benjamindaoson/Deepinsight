import json
import time
from pathlib import Path
from openai import OpenAI

root = Path(__file__).resolve().parents[2]
c = json.loads((root / 'secrets/model.json').read_text(encoding='utf-8-sig'))
result = {'provider': c['provider'], 'base_url': c['base_url'], 'requested_model': c['model']}
start = time.monotonic()
try:
    client = OpenAI(api_key=c['api_key'], base_url=c['base_url'], timeout=45, max_retries=0)
    response = client.chat.completions.create(model=c['model'], max_tokens=96,
        messages=[{'role': 'user', 'content': 'Please introduce yourself in one sentence.'}])
    result.update(status='PASS', response=response.model_dump())
except Exception as e:
    result.update(status='BLOCKED', error=str(e).replace(c['api_key'], '[REDACTED]'))
result['elapsed_seconds'] = round(time.monotonic() - start, 3)
(root / 'b0/evidence/api-results/model-probe.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
