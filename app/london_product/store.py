"""Product persistence: atomic JSON records with indexed identities, immutable originals."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, text

TABLES = ('sources', 'documents', 'facts', 'extractions', 'comparisons', 'events', 'jobs', 'reports', 'notifications', 'settings', 'reviews')


def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid4())


class Store:
    def __init__(self, directory):
        self.root = Path(directory).resolve(); self.root.mkdir(parents=True, exist_ok=True)
        self.artifacts = self.root / 'artifacts'; self.artifacts.mkdir(exist_ok=True)
        self.engine = create_engine('sqlite:///' + str(self.root / 'market.sqlite3'), connect_args={'timeout': 10})
        migration = Path(__file__).parents[1] / 'migrations/002_product.sql'
        with self.engine.begin() as c:
            c.execute(text('PRAGMA journal_mode=WAL'))
            for statement in migration.read_text(encoding='utf-8').split(';'):
                if statement.strip(): c.execute(text(statement))

    def _table(self, table):
        if table not in TABLES: raise ValueError('Unknown table')
        return table

    def put(self, table, identity, payload):
        self._table(table)
        data = dict(payload, id=payload.get('id') or uid(), created_at=payload.get('created_at') or now())
        with self.engine.begin() as c:
            c.execute(text(f'INSERT OR IGNORE INTO {table}(id,identity,payload) VALUES(:id,:identity,:payload)'),
                      dict(id=data['id'], identity=identity, payload=json.dumps(data, ensure_ascii=False, default=str)))
            return json.loads(c.execute(text(f'SELECT payload FROM {table} WHERE identity=:identity'), dict(identity=identity)).scalar_one())

    def get(self, table, identity):
        self._table(table)
        with self.engine.connect() as c:
            value = c.execute(text(f'SELECT payload FROM {table} WHERE id=:i OR identity=:i LIMIT 1'), {'i': identity}).scalar()
        return json.loads(value) if value else None

    def all(self, table):
        self._table(table)
        with self.engine.connect() as c: return [json.loads(r[0]) for r in c.execute(text(f'SELECT payload FROM {table} ORDER BY rowid DESC'))]

    def update(self, table, identity, changes):
        self._table(table)
        with self.engine.begin() as c:
            old = c.execute(text(f'SELECT payload FROM {table} WHERE id=:i'), {'i': identity}).scalar()
            if not old: raise KeyError(identity)
            data = dict(json.loads(old), **changes, updated_at=now())
            c.execute(text(f'UPDATE {table} SET payload=:p WHERE id=:i'), {'p': json.dumps(data, ensure_ascii=False, default=str), 'i': identity})
        return data

    def snapshot(self, source, url, content, media, segments, **metadata):
        digest = hashlib.sha256(content).hexdigest()
        ext = '.pdf' if 'pdf' in media else '.bin'
        path = self.artifacts / (digest + ext)
        # Serialize original creation inside a write transaction: readers only receive a
        # committed snapshot after the entire immutable original exists.
        with self.engine.begin() as c:
            c.execute(text('BEGIN IMMEDIATE'))
            if not path.exists():
                with path.open('xb') as file:file.write(content)
            if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('ORIGINAL_HASH_MISMATCH')
        return self.put('documents', source['id'] + ':' + digest, dict(
            source_id=source['id'], publisher=source.get('name', source['id']), title=metadata.pop('title', source.get('name', url)),
            url=url, sha256=digest, media=media, path=str(path), segments=segments,
            parser_version='product-parse-v1',parser_sha256=hashlib.sha256((Path(__file__).parent/'sources.py').read_bytes()).hexdigest(),
            collected_at=now(), published_at=metadata.pop('published_at', None), **metadata))
