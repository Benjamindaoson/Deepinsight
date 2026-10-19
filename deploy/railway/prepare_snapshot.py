"""Relocate only a copied SQLite snapshot for Railway; never touch source DBs."""
import hashlib
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'backend' / 'seed-data'
DB = DATA / 'market.sqlite3'
TABLES = ('sources', 'documents', 'facts', 'extractions', 'comparisons',
          'events', 'jobs', 'reports', 'notifications', 'settings', 'reviews')
OLD = 'D:/deepinsight-lite/'


def relocate(value):
    if isinstance(value, dict):
        return {k: relocate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [relocate(v) for v in value]
    if not isinstance(value, str):
        return value
    normalized = value.replace('\\', '/')
    if not normalized.lower().startswith(OLD.lower()):
        return value
    suffix = normalized[len(OLD):]
    if suffix.startswith('app/data/product/'):
        return '/persist/' + suffix[len('app/data/product/'):]
    return '/srv/' + suffix


def main():
    if not DB.is_file():
        raise SystemExit('Snapshot DB missing')
    conn = sqlite3.connect(DB)
    updated = {}
    for table in TABLES:
        count = 0
        for rowid, raw in conn.execute(f'SELECT rowid,payload FROM {table}').fetchall():
            old = json.loads(raw)
            new = relocate(old)
            if new != old:
                conn.execute(f'UPDATE {table} SET payload=? WHERE rowid=?',
                             (json.dumps(new, ensure_ascii=False, default=str), rowid))
                count += 1
        updated[table] = count
    # Workstation browser credentials and uploaded personal attachments are
    # never part of the market-data deployment. The source DB is untouched.
    removed_private_settings = 0
    for rowid, raw in conn.execute('SELECT rowid,payload FROM settings').fetchall():
        item = json.loads(raw)
        if item.get('kind') not in {'model_connection', 'user_attachment'}:
            continue
        path = item.get('path', '')
        if path.startswith('/persist/artifacts/upload-'):
            candidate = DATA / path[len('/persist/'):]
            if candidate.is_file() and candidate.parent == DATA / 'artifacts':
                candidate.unlink()
        conn.execute('DELETE FROM settings WHERE rowid=?', (rowid,))
        removed_private_settings += 1
    conn.commit()
    documents = [json.loads(r[0]) for r in conn.execute('SELECT payload FROM documents')]
    missing = []
    mismatched = []
    for doc in documents:
        path = doc.get('path', '')
        if path.startswith('/persist/'):
            local = DATA / path[len('/persist/'):]
        elif path.startswith('/srv/'):
            local = ROOT / 'backend' / path[len('/srv/'):]
        else:
            missing.append(doc['id'])
            continue
        if not local.is_file():
            missing.append(doc['id'])
        elif hashlib.sha256(local.read_bytes()).hexdigest() != doc.get('sha256'):
            mismatched.append(doc['id'])
    conn.close()
    receipt = dict(updated_records=updated,
                   removed_private_settings=removed_private_settings,
                   documents=len(documents),
                   verified_documents=len(documents)-len(missing)-len(mismatched),
                   missing_document_ids=missing, hash_mismatch_ids=mismatched)
    print(json.dumps(receipt, indent=2))
    if missing or mismatched:
        raise SystemExit('Snapshot originals are incomplete; deployment stopped')


if __name__ == '__main__':
    main()
