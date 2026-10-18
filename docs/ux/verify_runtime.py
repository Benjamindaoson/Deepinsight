"""Read-only UX acceptance receipts. Never submits a model or changes settings."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import urllib.request
import zipfile

root = Path(__file__).parents[2]
out = root / 'docs/ux/evidence'
frontend = root / 'app/frontend'

def get(path, port=7780):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=30) as response:
        body = response.read()
        return response.status, body

def data(path):
    return json.loads(get('/api/market/' + path)[1])

identity = json.loads((frontend / 'FRONTEND_BUILD_IDENTITY.json').read_text())
drift = [item['path'] for item in identity['files'] if hashlib.sha256((frontend / item['path']).read_bytes()).hexdigest() != item['sha256']]
with zipfile.ZipFile(out / 'before-source.zip') as archive:
    dependencies = {name: archive.read(name) == (frontend / name).read_bytes() for name in ['package.json', 'pnpm-lock.yaml']}
settings = data('settings')
before_settings = json.loads((out / 'baseline-settings.json').read_text(encoding='utf-8-sig'))
keys = ['news_interval_hours', 'market_interval_hours', 'geographies', 'metrics', 'rent_threshold_pct', 'takeup_threshold_pct', 'vacancy_threshold_pp', 'notifications_enabled', 'monitoring_enabled']
preferences = {key: before_settings.get(key) == settings.get(key) for key in keys}
facts = data('facts?limit=100')
before_facts = json.loads((out / 'baseline-facts.json').read_text(encoding='utf-8-sig'))
old_facts = {item['id']: item for item in before_facts['items']}
new_facts = {item['id']: item for item in facts['items']}
def canonical(value):
    if isinstance(value, dict):
        return {key: canonical(item) for key, item in value.items()}
    if isinstance(value, list):
        return [canonical(item) for item in value]
    if isinstance(value, str) and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)', value):
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat()
    return value
routes = [{'route': path, 'status': get(path, 3101)[0]} for path in ['/', '/chat', '/overview', '/market-data', '/events', '/ask', '/reports', '/settings', '/jobs']]
receipt = {
    'captured_at': datetime.now(timezone.utc).isoformat(),
    'manifest_sha256': identity['manifest_sha256'],
    'source_files': len(identity['files']),
    'source_drift_since_build': drift,
    'dependency_files_unchanged': dependencies,
    'monitoring_business_preferences_unchanged': preferences,
    'baseline_fact_count': len(old_facts),
    'current_fact_count': len(new_facts),
    'baseline_facts_preserved_exactly': all(new_facts.get(key) == value for key, value in old_facts.items()),
    'baseline_facts_equivalent_after_iso_timezone_normalization': canonical(old_facts) == canonical(new_facts),
    'routes': routes,
    'notes': 'Later coordinated delivery work may change source/build. This receipt is timestamped and makes no claim about later builds.'
}
(out / 'runtime-final.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
(out / 'after-settings.json').write_text(json.dumps(settings, indent=2), encoding='utf-8')
(out / 'ux-build-identity.json').write_text(json.dumps(identity, indent=2), encoding='utf-8')
print(json.dumps(receipt, indent=2))
