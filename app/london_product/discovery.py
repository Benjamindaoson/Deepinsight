"""Optional URL discovery inside the existing monitoring acquisition step.

Search responses are untrusted candidate metadata, never original evidence.
Receipts/candidates use existing jobs; originals/events use existing stores.
"""
import asyncio
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from . import sources
from .store import now, uid

ENDPOINT = 'https://api.tavily.com/search'
QUERY = 'London office market leasing take-up vacancy rents supply development corporate relocation ESG hybrid working'
WINDOW_SECONDS = 6 * 3600
MAX_RESULTS = 5
ALIASES = {
    'jll': {'www.jll.com', 'www.jll.co.uk'},
    'savills': {'www.savills.co.uk', 'pdf.euro.savills.co.uk', 'research.euro.savills.co.uk'},
    'bbc-rss': {'feeds.bbci.co.uk', 'www.bbc.co.uk', 'www.bbc.com'},
    'planning': {'data.london.gov.uk', 'planning.london.gov.uk'},
}


def configuration():
    # Never fall back to an inherited generic/previous-project Tavily key.
    configured = bool(os.environ.get('LONDON_TAVILY_API_KEY', '').strip())
    enabled = os.environ.get('LONDON_TAVILY_ENABLED') == '1'
    return dict(status='configuration_missing' if not configured else ('ready' if enabled else 'disabled'),
                configured=configured, enabled=enabled, endpoint=ENDPOINT,
                max_requests_per_window=1, window_seconds=WINDOW_SECONDS,
                max_results=MAX_RESULTS, automatic_retries=0, model_requests=0)


def approved_hosts(registry):
    approved = {}
    for source in registry:
        if (not source.get('enabled') or source.get('allow_llm') is False
                or source['id'] == 'knightfrank' or source.get('category') == 'macro'):
            continue
        host = urlsplit(source['url']).hostname
        hosts = ({host} | ALIASES.get(source['id'], set())) & sources.ALLOWED_HOSTS
        hosts.discard('www.knightfrank.co.uk')
        for host in hosts:
            approved[host] = dict(source, allowed_hosts=sorted(hosts))
    return approved


def canonical_url(url):
    parsed = sources._check_url(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in {'gclid', 'fbclid'}]
    return urlunsplit(('https', parsed.hostname, parsed.path or '/', urlencode(query), ''))


def _transport():
    # Same public-IP-pinned transport, with a separate fixed API host allowlist.
    # The API host is never added to the original-document source allowlist.
    return sources._make_transport(frozenset({'api.tavily.com'}))


async def _search(hosts):
    payload = dict(query=QUERY, topic='news', time_range='week', search_depth='fast',
                   max_results=MAX_RESULTS, include_domains=sorted(hosts), chunks_per_source=1,
                   include_domains_mode='restrict', include_answer=False, include_raw_content=False,
                   include_images=False, auto_parameters=False, include_usage=True)
    async with asyncio.timeout(25):
        async with httpx.AsyncClient(transport=_transport(), trust_env=False, follow_redirects=False,
                                     timeout=httpx.Timeout(20, connect=8)) as client:
            async with client.stream('POST', ENDPOINT, json=payload,
                    headers={'Authorization': 'Bearer ' + os.environ['LONDON_TAVILY_API_KEY'].strip()}) as response:
                response.raise_for_status()  # includes redirects; never forward credentials
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 1024 * 1024: raise ValueError('DISCOVERY_RESPONSE_TOO_LARGE')
                data = json.loads(body)
    if not isinstance(data, dict) or not isinstance(data.get('results'), list):
        raise ValueError('DISCOVERY_SCHEMA_INVALID')
    return data


async def refresh_candidates(service):
    config = configuration()
    empty = dict(requests=0, candidates=[], successes=0, failures=0, model_requests=0)
    if config['status'] != 'ready': return dict(empty, status=config['status'])
    hosts = approved_hosts(service.store.all('sources'))
    if not hosts: return dict(empty, status='no_approved_sources')
    # A durable claim before HTTP prevents concurrent jobs, scheduler retries and
    # restarts from repeating a potentially charged search within this window.
    policy = hashlib.sha256(json.dumps([QUERY, sorted(hosts)]).encode()).hexdigest()[:16]
    identity = f'news-discovery:{int(time.time() // WINDOW_SECONDS)}'
    owner = uid()
    row = service.store.put('jobs', identity, dict(id=owner, kind='news_discovery', status='running',
        stage='search_request_claimed', started_at=now(), progress=0, attempts=1,
        result=dict(empty, status='request_pending', query=QUERY, domains=sorted(hosts), policy=policy)))
    fresh = row['id'] == owner
    if not fresh and row.get('status') in {'running', 'interrupted'}:
        return dict(empty, status='delivery_unknown', receipt_id=row['id'],
                    error='Search in progress or interrupted; no automatic resubmission', failures=1)
    result = dict(row.get('result') or empty)
    if fresh:
        result.update(requests=1, query=QUERY, domains=sorted(hosts), started_at=now())
        search_started = time.perf_counter()
        try:
            response = await _search(hosts)
            candidates, seen, rejected = [], set(), 0
            for item in response['results'][:MAX_RESULTS]:
                try:
                    url = canonical_url(item['url'])
                    source = hosts[urlsplit(url).hostname]
                    if url in seen: continue
                    seen.add(url)
                    candidates.append(dict(url=url, source_id=source['id'], status='candidate',
                        discovered_at=now(), document_id=None))
                except (KeyError, TypeError, ValueError): rejected += 1
            result.update(status='discovered', candidates=candidates, rejected_count=rejected,
                search_elapsed_ms=round((time.perf_counter()-search_started)*1000, 2),
                provider_request_id=str(response.get('request_id', ''))[:200],
                usage={'credits': response['usage']['credits']} if isinstance(response.get('usage'), dict)
                    and isinstance(response['usage'].get('credits'), (int, float)) else None,
                finished_at=now())
            # Do not persist provider snippets, generated answers or unverified dates/titles.
            service.store.update('jobs', row['id'], dict(result=result, stage='fetch_originals'))
        except Exception as exc:
            result.update(status='failed', error=type(exc).__name__,
                search_elapsed_ms=round((time.perf_counter()-search_started)*1000, 2),
                status_code=getattr(getattr(exc, 'response', None), 'status_code', None),
                failures=1, finished_at=now())
            service.store.update('jobs', row['id'], dict(status='failed', stage='search_failed', result=result, finished_at=now(), progress=100))
            return dict(result, receipt_id=row['id'])
    elif result.get('status') == 'failed':
        return dict(result, requests=0, reused_search=True, receipt_id=row['id'])

    semaphore = asyncio.Semaphore(4)
    async def acquire(candidate):
        async with semaphore:
            candidate = dict(candidate)
            try:
                source = hosts[urlsplit(candidate['url']).hostname]
                # Revalidate registry every run; cached candidates confer no permission.
                previous = next((d for d in service.store.all('documents')
                    if d['source_id'] == source['id'] and d.get('url') == candidate['url']), None)
                doc = service.store.get('documents', candidate.get('document_id') or '')
                if doc is not None:
                    if hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest() != doc['sha256']:
                        raise ValueError('ORIGINAL_HASH_MISMATCH')
                else:
                    fetched = await sources.fetch_source(dict(source, url=candidate['url']),
                        etag=(previous or {}).get('etag'), last_modified=(previous or {}).get('last_modified'))
                    if fetched['status_code'] == 304:
                        if not previous or hashlib.sha256(Path(previous['path']).read_bytes()).hexdigest() != previous['sha256']:
                            raise ValueError('CACHED_ORIGINAL_UNAVAILABLE')
                        doc = previous
                    else:
                        segments = sources.parse_content(fetched['content'], fetched['media'])
                        if not segments or not any(s.get('text', '').strip() for s in segments):
                            raise ValueError('ORIGINAL_TEXT_EMPTY')
                        title, published = source['name'], None
                        if 'html' in fetched['media']:
                            soup = BeautifulSoup(fetched['content'], 'html.parser')
                            heading = soup.find('h1') or soup.find('title')
                            if heading: title = heading.get_text(' ', strip=True)[:300]
                            date = soup.find('meta', attrs={'property': 'article:published_time'})
                            published = date.get('content') if date else None
                        doc = service.store.snapshot(source, fetched['url'], fetched['content'], fetched['media'], segments,
                            title=title, published_at=published, etag=fetched.get('etag'), last_modified=fetched.get('last_modified'))
                text = ' '.join(s.get('text', '') for s in doc['segments']).lower()
                relevant = re.search(r'london|west end|canary wharf|midtown', text) and re.search(r'office|leas|rent|vacan|supply|relocat|esg|hybrid|workspace', text)
                if relevant: service.events_from_document(doc, source)
                return dict(candidate, status='pending_review' if relevant else 'out_of_scope',
                            document_id=doc['id'], sha256=doc['sha256'], original_url=doc['url'],
                            collected_at=doc['collected_at'], error=None)
            except Exception as exc:
                return dict(candidate, status='needs_review', document_id=None, error=type(exc).__name__)
    candidates = await asyncio.gather(*(acquire(c) for c in result.get('candidates', [])))
    failures = sum(c['status'] == 'needs_review' for c in candidates)
    result.update(candidates=candidates, successes=len(candidates)-failures, failures=failures,
                  status='partial' if failures else 'succeeded', finished_at=now())
    service.store.update('jobs', row['id'], dict(status=result['status'], result=result, stage='complete', progress=100, finished_at=now()))
    service.invalidate()
    return dict(result, requests=1 if fresh else 0, reused_search=not fresh, receipt_id=row['id'])
