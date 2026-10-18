"""Evidence-backed product bootstrap, independent of the frozen B1 store.

This module copies original bytes into product storage and transcribes only
source-located statements. It never grants human validation or infers annual
rent units. Network acquisition is explicit and separate from startup.
"""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

from .sources import catalog, parse_content


def _hash(content):
    return hashlib.sha256(content).hexdigest()


def _document(path, source_id, url, product_root, published_at=None, collected_at=None, expected_sha=None):
    content = path.read_bytes()
    sha = _hash(content)
    if expected_sha and sha != expected_sha:
        raise ValueError(f'SEED_PROVENANCE_HASH_MISMATCH: {path.name}')
    media = 'application/pdf' if content.startswith(b'%PDF-') else 'text/html'
    document_id = f'doc-{source_id}-{sha[:20]}'
    destination = product_root / 'originals' / f'{document_id}{path.suffix}'
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(content)
    elif _hash(destination.read_bytes()) != sha:
        raise ValueError('SEED_PRODUCT_COPY_HASH_MISMATCH')
    return dict(id=document_id, title=path.stem.replace('-', ' ').replace('_', ' '),
                source_id=source_id, url=url, path=str(destination.resolve()), sha256=sha,
                media=media, published_at=published_at, collected_at=collected_at,
                segments=parse_content(content, media))


def _fact(document, fact_id, metric, value, unit, geography, period, page, quote,
          definition, precision=None, grade='unknown', status='pending_review', normalized_value=None):
    segment = next(s for s in document['segments'] if s['page'] == page)
    # Preserve exact source characters including PDF whitespace in evidence.
    expression = r'\s+'.join(re.escape(token) for token in quote.split())
    match = re.search(expression, segment['text'])
    if match is None:
        raise ValueError(f'SEED_EVIDENCE_NOT_FOUND: {fact_id}, page {page}')
    exact = match.group(0)
    return dict(id=fact_id, metric=metric, value=value, normalized_value=normalized_value,
                unit=unit, precision=precision, geography=geography, period=period,
                status=status, publisher=document.get('publisher', document['source_id']),
                source_id=document['source_id'], document_id=document['id'],
                evidence=dict(quote=exact, page=page, locator=f"pdf:page:{page}:chars:{match.start()}-{match.end()}"),
                definition=definition, grade=grade, method='unknown', run_id='product-seed-transcription-v1',
                published_at=document['published_at'], collected_at=document['collected_at'],
                eligible_for_comparison=False)


def seed_records(root: Path) -> dict:
    root = Path(root).resolve()
    if not (root / 'b1').is_dir() and root.name == 'app':
        root = root.parent
    product_root = root / 'app' / 'data' / 'product'
    packet = root / 'b1' / 'g0-review' / '2026-10-17'
    supplement = root / 'b1' / 'g0-review' / '2026-10-17-supplement' / 'alternatives'
    result = dict(sources=catalog(), documents=[], facts=[], events=[])
    gold_path = packet / 'GOLDEN_FACTS.json'
    if not gold_path.exists():
        return result
    annotated = json.loads(gold_path.read_text(encoding='utf-8'))['facts']
    by_path = {}
    for old in annotated:
        oldpath = Path(old['document_path'])
        if oldpath.name not in by_path:
            document = _document(packet / 'raw' / oldpath.name, 'bnp', old['source_url'], product_root,
                                 old['published_at'], old['collected_at'], old['document_sha256'])
            document['publisher'] = old['publisher']
            by_path[oldpath.name] = document
            result['documents'].append(document)
        document = by_path[oldpath.name]
        display_value = old['numeric_value']
        display_precision = old['disclosure_increment']
        normalized_unit = old['normalized_unit']
        if old['metric'] == 'takeup' and old['raw_unit'] == 'million sqft for a single quarter':
            # The frozen annotation numeric_value is already expanded to sqft,
            # whereas its raw_display/raw_unit are in millions. Preserve both
            # representations explicitly rather than multiplying the UI twice.
            match = re.fullmatch(r'(\d+(?:\.\d+)?)m\s+sq\s+ft', old['raw_display'])
            if not match or Decimal(match[1]) * 1000000 != Decimal(old['numeric_value']):
                raise ValueError('SEED_ANNOTATION_SCALE_MISMATCH')
            display_value = match[1]
            display_precision = str(Decimal(1).scaleb(Decimal(display_value).as_tuple().exponent))
            normalized_unit = 'sqft'
        fact = _fact(document, old['fact_id'], old['metric'], display_value,
                     old['raw_unit'], old['geography'], old['period'], old['evidence']['page'],
                     old['evidence']['exact_excerpt'], old['definition'], display_precision,
                     old['grade'], old['validation_status'], old['normalized_value'])
        # Keep every qualification issue and approval boundary from the original.
        fact.update(issues=old['issues'], original_annotation_path=str(gold_path),
                    original_annotation=dict(old), raw_display=old['raw_display'],
                    raw_value=display_value, raw_unit=old['raw_unit'], raw_period=old['period'],
                    normalized_unit=normalized_unit, normalized_period=old['period'],
                    normalized_precision=old['disclosure_increment'], normalization_version='product-seed-annotation-v1',
                    series=old['series'], currency=old['currency'], temporal_basis=old['temporal_basis'],
                    period_start=old['period_start'], period_end=old['period_end'],
                    basis='quarter' if old['temporal_basis'] == 'single_quarter_flow' else old['temporal_basis'],
                    human_review_status=old['human_review_status'], method=old.get('method_version') or 'unknown')
        result['facts'].append(fact)
    bnp_q2 = by_path['bnp-q2-2026.pdf']
    specifications = [
        ('westend-takeup', 'takeup', '1000000', 'sqft', 'West End', 5,
         'with take-up reaching approximately 1.0 million sq ft', 'West End quarterly take-up, approximate narrative value', '100000'),
        ('westend-vacancy', 'vacancy', '6.7', 'percent', 'West End', 5,
         'Overall vacancy held at a low 6.7%', 'West End overall vacancy; source-defined market', '0.1'),
        ('westend-supply', 'supply', '6200000', 'sqft', 'West End', 5,
         'to 6.2 million sq ft', 'West End available office supply, rounded narrative value', '100000'),
        ('midtown-takeup', 'takeup', '207000', 'sqft', 'Midtown', 7,
         'take-up reaching approximately 207,000 sq ft', 'Midtown quarterly take-up, approximate narrative value', '1000'),
        ('midtown-vacancy', 'vacancy', '7.0', 'percent', 'Midtown', 7,
         'As a result, vacancy reduced to 7.0%', 'Midtown vacancy; original narrative retained without reconciling direction versus Q1', '0.1'),
        ('canary-rent', 'rent', '58.50', 'GBP/sqft, time denominator not stated', 'Canary Wharf', 9,
         'Prime rents across Canary Wharf remained stable during the quarter at £58.50 psf', 'Canary Wharf prime rent; annual denominator unconfirmed', '0.01'),
        ('docklands-vacancy', 'vacancy', '9.7', 'percent', 'Canary Wharf & Docklands', 9,
         'vacancy has continued to fall, reaching 9.7% at the end of Q2 2026', 'Combined Canary Wharf and Docklands overall vacancy', '0.1'),
        ('docklands-takeup', 'takeup', '166000', 'sqft', 'Canary Wharf & Docklands', 9,
         'take-up reaching approximately 166,000 sq ft', 'Combined submarket narrative take-up; key card states 167k, unresolved discrepancy', '1000'),
    ]
    for suffix, metric, value, unit, geography, page, quote, definition, precision in specifications:
        fact = _fact(bnp_q2, f'seed-bnp-2026Q2-{suffix}', metric, value, unit, geography,
                     '2026Q2', page, quote, definition, precision, status='needs_review' if metric == 'rent' or suffix == 'docklands-takeup' else 'pending_review',
                     normalized_value=None if metric == 'rent' else value)
        if suffix == 'docklands-takeup':
            fact['issues'] = ['NARRATIVE_166K_VS_KEY_CARD_167K']
        if suffix == 'midtown-vacancy':
            fact['issues'] = ['SOURCE_DIRECTION_NARRATIVE_REQUIRES_REVIEW']
        result['facts'].append(fact)
    # The JLL report is an additional publisher with explicit quarter/YTD labels.
    jll_path = supplement / 'jll_2026q2.pdf'
    if jll_path.exists():
        jll = _document(jll_path, 'jll', 'https://www.jll.com/content/dam/jllcom/en/uk/documents/reports/research-reports/26-insights-central-london-office-q2-2026.pdf', product_root,
                        collected_at='2026-10-17T13:03:57.635946+00:00',
                        expected_sha='e2eaadc6049e717d5ebc1375630fae9424b6ba9f463e2040fea00343316a6cc9')
        jll['publisher'] = 'JLL'
        result['documents'].append(jll)
        for suffix, metric, value, unit, geography, page, quote, definition in [
            ('takeup', 'takeup', '2600000', 'sqft', 'Central London', 1, 'Take-up reached 2.6 million sq.ft. in Q2 2026', 'Quarterly narrative take-up; not YTD Fundamentals card'),
            ('vacancy', 'vacancy', '8.6', 'percent', 'Central London', 1, 'resulting in a vacancy rate of 8.6%', 'Overall source-defined vacancy, full methodology unconfirmed'),
            ('supply', 'supply', '21600000', 'sqft', 'Central London', 1, 'Supply contracted for a third consecutive quarter to 21.6 million sq.ft.', 'Available supply at quarter end'),
            ('prelet', 'prelet_share', '80', 'percent', 'Central London', 1, '80% of delivered space pre-let or under offer', 'Share of delivered space pre-let or under offer; not solely pre-let'),
            ('westend-rent', 'rent', '190.00', 'GBP/sqft, time denominator not stated', 'West End', 1, 'Prime rents rose to £190.00 per sq.ft. in the West End', 'West End prime rent, annual denominator unconfirmed'),
        ]:
            result['facts'].append(_fact(jll, f'seed-jll-2026Q2-{suffix}', metric, value, unit, geography, '2026Q2', page, quote, definition,
                                         status='needs_review' if metric == 'rent' else 'pending_review', normalized_value=None if metric == 'rent' else value))
    savills_path = packet / 'raw' / 'savills-q2-2026.pdf'
    if savills_path.exists():
        savills = _document(savills_path, 'savills', 'https://pdf.euro.savills.co.uk/uk/office-reports/central-london-q2-2026-report.pdf', product_root,
                           collected_at='2026-10-17T12:33:28.407043+00:00',
                           expected_sha='1a03080fb582af334a74bb8239cb299581022ef1f81acb9200219bf1561853e3')
        savills['publisher'] = 'Savills'
        result['documents'].append(savills)
        result['facts'].append(_fact(savills, 'seed-savills-2026H1-gradea', 'grade_a_share', '94', 'percent', 'Central London', '2026H1', 3,
            'Grade A office space, which accounted for 94% of H1 take -up', 'Grade A share of H1 take-up; half-year period retained', grade='Grade A', normalized_value='94'))
        result['facts'].append(_fact(savills, 'seed-savills-2026Q2-westend-vacancy', 'vacancy', '7.5', 'percent', 'West End', '2026Q2', 6,
            'West End vacancy rate 7.5%', 'Source-defined West End vacancy; do not equate with BNP/JLL definitions', '0.1', normalized_value='7.5'))
    qualification = product_root / 'source-qualification' / 'manifest.json'
    if qualification.exists():
        acquired = json.loads(qualification.read_text(encoding='utf-8'))
        result['documents'].extend(acquired.get('documents', []))
        result['events'].extend(acquired.get('events', []))
        result['facts'].extend(acquired.get('facts', []))
        health = {r['source_id']: r for r in acquired.get('receipts', [])}
        for source in result['sources']:
            if source['id'] in health:
                receipt = health[source['id']]
                source.update(health='healthy' if receipt.get('status_code') == 200 else 'failed',
                              last_success=receipt.get('collected_at') if receipt.get('status_code') == 200 else None,
                              last_error=receipt.get('error'))
    return result
