"""Read-only real-document/cache check. Never permits a model or database write."""
import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from london_product import intelligence

ROOT = Path(__file__).resolve().parents[1] / 'data/product'
DEST = ROOT / 'evidence/market-closure-20261018/extract'


class ReadOnlyStore:
    root = ROOT

    def __init__(self):
        self.connection = sqlite3.connect((ROOT / 'market.sqlite3').as_uri() + '?mode=ro', uri=True)

    def get(self, table, identity):
        assert table in {'sources', 'documents', 'extractions'}
        row = self.connection.execute(f'SELECT payload FROM {table} WHERE id=? OR identity=?', (identity, identity)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self, table):
        assert table == 'extractions'
        return [json.loads(row[0]) for row in self.connection.execute('SELECT payload FROM extractions ORDER BY rowid DESC')]

    def put(self, *args, **kwargs):
        raise AssertionError('Read-only cache verification must not write records')

    update = put


def main():
    store = ReadOnlyStore()
    previous = json.loads((ROOT / 'evidence/real-extraction-v2.json').read_text(encoding='utf-8'))
    doc = store.get('documents', previous['document_id'])
    digest = hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest()
    assert digest == doc['sha256']
    service = SimpleNamespace(store=store, _lock=threading.RLock(), extraction_locks={})
    with patch.object(intelligence, 'configured_model', side_effect=AssertionError('No model request authorized')):
        first = intelligence.extract_document(service, doc['id'], 'read-only-cache-verification')
        second = intelligence.extract_document(service, doc['id'], 'read-only-cache-verification-repeat')
    assert first['cached'] and second['cached'] and first == second
    receipt = dict(status='PASS', scope='real saved-document/cache read; not a fresh model extraction',
        document_id=doc['id'], document_sha256=digest, original_run_id=previous['run_id'],
        first=first, second=second, model_requests=0, database_writes=0,
        fresh_model_extraction='NOT_EXECUTED_THIS_ROUND', human_review='pending_review')
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / 'real-cache-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    store.connection.close()


if __name__ == '__main__':
    main()
