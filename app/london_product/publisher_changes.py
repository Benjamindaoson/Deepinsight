"""Narrow, source-specific reported changes; never computed or approved facts.

Only the explicit quarterly take-up sentence in JLL Central London PDF reports
is currently supported. Other publishers/metrics remain visible as candidates.
"""
import hashlib
import re
from pathlib import Path


TAKEUP = re.compile(r'Take-up reached (?P<level>\d+(?:\.\d+)?) million sq\.ft\. in Q(?P<quarter>[1-4]) (?P<year>20\d{2})\s*[—-]\s*up (?P<change>\d+(?:\.\d+)?)% quarter-on-quarter')


def discover_reported_changes(store, run_id=None):
    import fitz
    results = []
    source = store.get('sources', 'jll') or {}
    if source.get('allow_llm') is False:
        return results
    for doc in store.all('documents'):
        if doc.get('source_id') != 'jll' or doc.get('media') != 'application/pdf':
            continue
        path = Path(doc.get('path', ''))
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != doc.get('sha256'):
            continue
        try:
            with fitz.open(path) as pdf:
                for segment in doc.get('segments', []):
                    text = segment.get('text', '')
                    page = segment.get('page')
                    if not page or not 1 <= page <= len(pdf) or 'Central London' not in text:
                        continue
                    match = TAKEUP.search(text)
                    if not match or match.group() not in pdf[page-1].get_text():
                        continue
                    quarter, year = int(match['quarter']), int(match['year'])
                    if f'Office | Q{quarter} {year}' not in text:
                        continue
                    previous = f'{year}Q{quarter-1}' if quarter > 1 else f'{year-1}Q4'
                    identity = 'publisher-change:' + hashlib.sha256((doc['source_id'] + doc['sha256'] + match.group()).encode()).hexdigest()
                    row = store.put('events', identity, dict(
                        kind='publisher_reported_change', classification='publisher_reported_change',
                        title=f'JLL reported Central London take-up up {match["change"]}% quarter-on-quarter · {year}Q{quarter}',
                        summary=match.group(), importance='normal', status='pending_review',
                        human_review_status='pending_review', geography='Central London', metric='takeup',
                        definition='JLL reported quarterly office take-up; publisher methodology, not reconciled across sources',
                        period=f'{year}Q{quarter}', comparison_period=previous, basis='quarter_on_quarter',
                        reported_value=match['level'], reported_unit='million sqft', reported_change=match['change'],
                        change_unit='percent', calculation_performed=False, system_change_value=None,
                        limitation='Attributed publisher statement, not a system-calculated change or approved fact. No inferred prior-quarter value.',
                        source_id=doc['source_id'], document_id=doc['id'], document_sha256=doc['sha256'],
                        url=doc['url'], published_at=doc.get('published_at'), collected_at=doc.get('collected_at'),
                        report_title=doc.get('title'), run_id=run_id,
                        evidence_validation='exact_quote_in_hash_verified_original',
                        evidence=dict(quote=match.group(), page=page,
                            locator=f'pdf:page:{page}:chars:{match.start()}-{match.end()}')))
                    results.append(row)
        except (RuntimeError, ValueError):
            continue
    return results


def saved_reported_changes(store):
    return [e for e in store.all('events') if e.get('classification') == 'publisher_reported_change'
            and e.get('status') not in ['rejected', 'superseded']
            and e.get('human_review_status') != 'rejected'
            and e.get('evidence_validation') == 'exact_quote_in_hash_verified_original']
