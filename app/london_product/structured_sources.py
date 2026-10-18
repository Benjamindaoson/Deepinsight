"""Deterministic projections of official structured originals.

Raw responses remain immutable Store snapshots. These records are candidates for
human review and never become comparable market rent/vacancy/take-up facts.
"""
import csv
import hashlib
import io
import json
import re
from decimal import Decimal, InvalidOperation

from .sources import _segment
from .store import now


def segments(source, content):
    if source['id'].startswith('planning-api-'):
        data = json.loads(content)
        hits = data.get('hits', {}).get('hits', [])
        if not isinstance(hits, list) or len(hits) > 5:
            raise ValueError('PLANNING_SCHEMA_INVALID')
        if any(not isinstance(hit, dict) or not isinstance(hit.get('_source'), dict) for hit in hits):
            raise ValueError('PLANNING_SCHEMA_INVALID')
        return [_segment(str(hit['_source'].get('description') or '')[:5000],
                         f'json:/hits/hits/{i}/_source/description')
                for i, hit in enumerate(hits)]
    if source['id'] == 'epc-nondomestic':
        data = json.loads(content)
        records = data.get('data', [])
        if not isinstance(records, list) or len(records) > 5:
            raise ValueError('EPC_SCHEMA_INVALID')
        return [_segment(json.dumps(record, ensure_ascii=False), f'json:/data/{i}')
                for i, record in enumerate(records)]
    raise ValueError('Unknown structured source')


def planning_events(store, doc, source, content):
    data = json.loads(content)
    hits = data.get('hits', {}).get('hits', [])
    if not isinstance(hits, list) or len(hits) > 5:
        raise ValueError('PLANNING_SCHEMA_INVALID')
    count = 0
    for index, hit in enumerate(hits):
        if not isinstance(hit, dict) or not isinstance(hit.get('_source'), dict):
            continue
        record = hit['_source']
        identifier = str(hit.get('_id') or '')
        description = str(record.get('description') or '')
        council = str(record.get('lpa_name') or '')
        # Elasticsearch matches "home office" and even the retailer Office
        # Shoes. They are not evidence of commercial office supply.
        if (not identifier or len(identifier) > 180 or
                not re.search(r'\boffice\s+(?:space|floorspace|accommodation|building|use|development)\b|\bcommercial\s+offices?\b', description, re.I) or
                re.search(r'\bhome office\b|\boffice shoes\b', description, re.I)):
            continue
        if source['id'] == 'planning-api-city' and council != 'City of London': continue
        if source['id'] == 'planning-api-westminster' and council != 'Westminster': continue
        if source['id'] == 'planning-api-tower-hamlets' and council != 'Tower Hamlets': continue
        if source['id'] == 'planning-api-camden' and council != 'Camden': continue
        excerpt = description[:1000]
        if not excerpt or excerpt not in doc['segments'][index]['text']:
            continue
        status = str(record.get('status') or record.get('decision') or 'unknown')[:160]
        identity = 'planning-record:' + identifier
        previous = store.get('events', identity)
        payload = dict(kind='planning', title=f'{council} planning application {identifier}',
                       summary=excerpt, importance='high', status='pending_review',
                       human_review_status='pending_review', geography=council,
                       source_id=source['id'], document_id=doc['id'], url=doc['url'],
                       published_at=record.get('last_updated'), application_id=identifier,
                       application_status=status, application_reference=record.get('lpa_app_no'),
                       application_url=record.get('url_planning_app'),
                       evidence=dict(quote=excerpt, page=None,
                                     locator=doc['segments'][index]['locator']),
                       classification_method='official_record_office_text_candidate_v1',
                       interpretation_limit='Planning status is not completed office supply or a pre-let.')
        if previous:
            if previous.get('document_id') == doc['id']:
                continue
            history = list(previous.get('version_history', []))
            history.append(dict(document_id=previous['document_id'],
                                application_status=previous.get('application_status'),
                                observed_at=previous.get('updated_at') or previous.get('created_at')))
            # Preserve any human review decision on the old version in history;
            # the new version must be reviewed again.
            history[-1]['human_review_status'] = previous.get('human_review_status')
            store.update('events', previous['id'], dict(payload, version_history=history,
                         content_change_status='needs_review', last_seen=now()))
        else:
            store.put('events', identity, payload)
        count += 1
    return count


def nomis_employment(store, doc, source, content):
    rows = list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))
    expected = {'DATE', 'GEOGRAPHY_NAME', 'INDUSTRY_NAME', 'EMPLOYMENT_STATUS_NAME', 'OBS_VALUE'}
    if not rows or len(rows) > 5 or not expected <= set(rows[0]):
        raise ValueError('NOMIS_SCHEMA_INVALID')
    count = 0
    for index, row in enumerate(rows, 2):
        if row['GEOGRAPHY_NAME'] != 'London' or row['INDUSTRY_NAME'] != 'Total' or row['EMPLOYMENT_STATUS_NAME'] != 'Employment':
            raise ValueError('NOMIS_SERIES_MISMATCH')
        period = row['DATE']
        if not re.fullmatch(r'20\d{2}', period):
            raise ValueError('NOMIS_PERIOD_INVALID')
        try: value = Decimal(row['OBS_VALUE'])
        except InvalidOperation: raise ValueError('NOMIS_VALUE_INVALID') from None
        if value < 0 or value != value.to_integral_value():
            raise ValueError('NOMIS_VALUE_INVALID')
        quote = doc['segments'][index - 2]['text']
        identity = 'nomis-bres-london:' + period + ':' + hashlib.sha256(quote.encode()).hexdigest()[:16]
        fact = store.put('facts', identity, dict(metric='employment', value=str(value), raw_value=row['OBS_VALUE'],
            normalized_value=str(value), unit='jobs', precision='rounded_as_published',
            geography='London (workplace)', period=period, raw_period=period,
            definition='Nomis BRES open access, all industries, employment at workplace, rounded estimate',
            grade='not_applicable', method='official_open_access_rounded_series',
            basis='annual_workplace_employment', source_id=source['id'], publisher=source['name'],
            series='NM_189_1 / geography 2013265927 / industry Total / employment status Employment',
            document_id=doc['id'], status='pending_review', human_review_status='pending_review',
            eligible_for_comparison=False, published_at=doc.get('published_at'),
            collected_at=doc['collected_at'], extraction_version='deterministic-nomis-v1',
            evidence=dict(quote=quote, page=None, locator=f'csv:row:{index}')))
        # A later official revision becomes a new pending-review candidate;
        # retain the old row and its original evidence as an explicit version.
        if fact.get('status') != 'superseded':
            for older in store.all('facts'):
                if (older['id'] != fact['id'] and older.get('source_id') == source['id']
                        and older.get('period') == period and older.get('metric') == 'employment'
                        and older.get('status') != 'superseded'):
                    store.update('facts', older['id'], dict(status='superseded', superseded_by=fact['id']))
        count += 1
    return count
