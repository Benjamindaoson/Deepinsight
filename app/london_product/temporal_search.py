"""Bounded, time-aware FTS5 projection over the existing product database.

The index is a search aid, not a source of approval or comparable market facts.
Every row points back to an immutable original or a saved business record.
"""

import json
import re
from pathlib import Path

from sqlalchemy import text


SEARCH_TABLES = ('documents', 'facts', 'events')
QUERY_WORDS = re.compile(r'[^\W_]+', re.UNICODE)
STOP_WORDS = {'or', 'and', 'not', 'near'}


def _string(value):
    return str(value) if value is not None else ''


def _rows(table, record):
    """Return explicit locators and searchable text without inventing metadata."""
    common = dict(record_type=table[:-1] if table != 'documents' else 'document',
                  record_id=record['id'], source_id=_string(record.get('source_id')),
                  geography=_string(record.get('geography')),
                  period=_string(record.get('period') or record.get('normalized_period')),
                  metric=_string(record.get('metric')),
                  review_status=_string(record.get('human_review_status') or record.get('status') or 'unreviewed'),
                  published_at=_string(record.get('published_at')))
    if table == 'documents':
        prefix = ' '.join(_string(record.get(field)) for field in ('title', 'publisher'))
        for index, segment in enumerate(record.get('segments') or []):
            if not isinstance(segment, dict):
                continue
            body = _string(segment.get('text') or segment.get('content'))
            if not body:
                continue
            locator = (f"page:{segment['page']}" if segment.get('page') is not None else
                       _string(segment.get('locator') or segment.get('selector') or f'segment:{index}'))
            yield dict(common, locator=locator, body=(prefix + ' ' + body)[:12000])
    elif table == 'facts':
        evidence = record.get('evidence') or {}
        if not isinstance(evidence, dict):
            evidence = {}
        locator = (f"page:{evidence['page']}" if evidence.get('page') is not None else
                   _string(evidence.get('locator') or evidence.get('selector') or 'fact'))
        body = ' '.join(_string(value) for value in (
            record.get('metric'), record.get('geography'), record.get('period'),
            record.get('definition'), record.get('title'), evidence.get('quote')))
        yield dict(common, locator=locator, body=body[:12000])
    else:
        evidence = record.get('evidence') or {}
        body = ' '.join(_string(value) for value in (
            record.get('title'), record.get('summary'), record.get('geography'),
            evidence.get('quote') if isinstance(evidence, dict) else None))
        yield dict(common, locator=_string(record.get('locator') or 'event'), body=body[:12000])


def sync_record(connection, table, record):
    if table not in SEARCH_TABLES:
        return
    kind = 'document' if table == 'documents' else table[:-1]
    connection.execute(text('DELETE FROM market_search WHERE record_type=:t AND record_id=:i'),
                       {'t': kind, 'i': record['id']})
    statement = text('''INSERT INTO market_search
        (record_type,record_id,locator,source_id,geography,period,metric,review_status,published_at,body)
        VALUES(:record_type,:record_id,:locator,:source_id,:geography,:period,:metric,:review_status,:published_at,:body)''')
    for row in _rows(table, record):
        connection.execute(statement, row)


def ensure_index(connection):
    migration = Path(__file__).parents[1] / 'migrations/003_temporal_search.sql'
    for statement in migration.read_text(encoding='utf-8').split(';'):
        if statement.strip():
            connection.execute(text(statement))
    exists = connection.execute(text('SELECT 1 FROM product_schema WHERE version=3')).scalar()
    if exists:
        return
    for table in SEARCH_TABLES:
        for (payload,) in connection.execute(text(f'SELECT payload FROM {table}')):
            sync_record(connection, table, json.loads(payload))
    connection.execute(text('INSERT INTO product_schema(version) VALUES(3)'))


def search(engine, query, *, record_type=None, source_id=None, geography=None,
           period=None, metric=None, review_status=None, limit=20):
    """Text-match saved evidence with exact structured filters; never infer approval."""
    if not isinstance(query, str):
        return []
    terms = [word.lower() for word in QUERY_WORDS.findall(query[:300]) if word.lower() not in STOP_WORDS]
    if not terms:
        return []
    expression = ' OR '.join('"' + term + '"' for term in terms[:8])
    allowed = {'document', 'fact', 'event'}
    if record_type and record_type not in allowed:
        raise ValueError('Unknown search record type')
    filters = dict(record_type=record_type, source_id=source_id, geography=geography,
                   period=period, metric=metric, review_status=review_status)
    clauses = ['market_search MATCH :query']
    parameters = {'query': expression, 'limit': min(max(int(limit), 1), 50)}
    for field, value in filters.items():
        if value is not None:
            clauses.append(f'{field}=:{field}')
            parameters[field] = value
    statement = text('''SELECT record_type,record_id,locator,source_id,geography,period,
        metric,review_status,published_at,substr(body,1,500) AS excerpt
        FROM market_search WHERE ''' + ' AND '.join(clauses) +
        ' ORDER BY bm25(market_search), published_at DESC LIMIT :limit')
    with engine.connect() as connection:
        return [dict(row._mapping) for row in connection.execute(statement, parameters)]
