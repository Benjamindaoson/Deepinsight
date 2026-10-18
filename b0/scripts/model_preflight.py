"""Read only locally authorized credentials; never print their values."""
import json
import urllib.request
import urllib.error
from pathlib import Path

root = Path(__file__).resolve().parents[2]
config = json.loads((root / 'secrets/model.json').read_text(encoding='utf-8-sig'))
result = {'base_url': config['base_url'], 'configured_model': config['model']}
for endpoint in ('models', 'user/balance'):
    request = urllib.request.Request(config['base_url'].rstrip('/') + '/' + endpoint,
        headers={'Authorization': 'Bearer ' + config['api_key']})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
            result[endpoint] = {'status': response.status, 'response': data}
    except urllib.error.HTTPError as error:
        result[endpoint] = {'status': error.code, 'response': error.read().decode()}
    except Exception as error:
        result[endpoint] = {'error': str(error).replace(config['api_key'], '[REDACTED]')}
path = root / 'b0/evidence/api-results/model-preflight.json'
path.write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
