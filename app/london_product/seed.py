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


def _offline_fixture_records(root: Path, product_root: Path) -> dict:
    """Load distributable evidence receipts without embedding answers in code.

    The fixture contains public-source metadata and short evidence excerpts, not
    publisher PDFs.  Each document becomes a deterministic local receipt whose
    own bytes are hash-checked by the normal evidence pipeline.  The upstream
    document hash remains separately available as ``source_document_sha256``.
    """
    fixture_path = root / 'app' / 'fixtures' / 'offline_evidence.json'
    if not fixture_path.is_file():
        return dict(sources=catalog(), documents=[], facts=[], events=[])
    payload = json.loads(fixture_path.read_text(encoding='utf-8'))
    if payload.get('schema_version') != 1:
        raise ValueError('OFFLINE_FIXTURE_SCHEMA_UNSUPPORTED')
    required = {'sources', 'documents', 'facts', 'events', 'provenance'}
    if not required <= payload.keys():
        raise ValueError('OFFLINE_FIXTURE_INCOMPLETE')
    documents = []
    receipt_root = product_root / 'offline-receipts'
    receipt_root.mkdir(parents=True, exist_ok=True)
    for source_document in payload['documents']:
        document = dict(source_document)
        receipt = json.dumps({
            'provenance': payload['provenance'],
            'source_document_sha256': document.get('source_document_sha256'),
            'source_id': document.get('source_id'),
            'title': document.get('title'),
            'url': document.get('url'),
            'published_at': document.get('published_at'),
            'collected_at': document.get('collected_at'),
            'segments': document.get('segments', []),
        }, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        receipt_sha = _hash(receipt)
        receipt_path = receipt_root / f'{document["id"]}-{receipt_sha[:12]}.json'
        if not receipt_path.exists():
            receipt_path.write_bytes(receipt)
        elif _hash(receipt_path.read_bytes()) != receipt_sha:
            raise ValueError('OFFLINE_FIXTURE_RECEIPT_HASH_MISMATCH')
        document.update(path=str(receipt_path.resolve()), sha256=receipt_sha,
                        receipt_sha256=receipt_sha, media='application/json')
        documents.append(document)
    fixture_sources = {source['id']: source for source in payload['sources']}
    sources = [dict(source, **fixture_sources.pop(source['id'], {})) for source in catalog()]
    sources.extend(fixture_sources.values())
    return dict(sources=sources, documents=documents,
                facts=list(payload['facts']), events=list(payload['events']))


def seed_records(root: Path) -> dict:
    root = Path(root).resolve()
    if not (root / 'b1').is_dir() and root.name == 'app':
        root = root.parent
    product_root = root / 'app' / 'data' / 'product'
    packet = root / 'b1' / 'g0-review' / '2026-10-17'
    fixture = _offline_fixture_records(root, product_root)
    result = dict(sources=catalog(), documents=[], facts=[], events=[])
    gold_path = packet / 'GOLDEN_FACTS.json'
    if not gold_path.exists():
        return fixture
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
    # Merge distributable receipts by identity. When a full licensed original
    # is present, its document record wins; otherwise the receipt supplies the
    # clean-checkout fallback. Business values live in the fixture, not code.
    for key in ('sources', 'documents', 'facts', 'events'):
        existing = {item['id'] for item in result[key]}
        result[key].extend(item for item in fixture[key] if item['id'] not in existing)
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
