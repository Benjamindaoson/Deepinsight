"""Public first-party source catalog, bounded acquisition and evidence parsers.

Only registered HTTPS hosts can be fetched. The transport pins the socket to a
public IP returned by DNS, preserving the original TLS SNI and host header.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import ipaddress
import json
import re
import socket
import os
import zipfile
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import httpcore
import httpx
from bs4 import BeautifulSoup

MAX_BYTES = 15 * 1024 * 1024
MAX_SEGMENTS = 10000
MAX_PAGES = 100


def catalog() -> list[dict]:
    entries = [
        ('bnp', 'BNP Paribas Real Estate', 'research', 'https://www.realestate.bnpparibas.co.uk/insights/central-london-office-market-update-q2-2026'),
        ('jll', 'JLL', 'research', 'https://www.jll.com/en-uk/insights/market-dynamics/central-london-office'),
        ('savills', 'Savills', 'research', 'https://pdf.euro.savills.co.uk/uk/office-reports/central-london-q2-2026-report.pdf'),
        ('savills-html', 'Savills Central London Q2 2026 HTML', 'research', 'https://www.savills.com/research_articles/255800/393427-0'),
        ('cbre', 'CBRE', 'research', 'https://www.cbre.com/insights/figures/central-london-office-figures-q2-2026'),
        ('knightfrank', 'Knight Frank', 'research', 'https://www.knightfrank.co.uk/research/reports/the-london-office-market-report-104'),
        ('boe', 'Bank of England Bank Rate', 'macro', 'https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2025&Dateto=now&SeriesCodes=IUDBEDR&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N'),
        ('ons', 'ONS CPIH annual rate', 'macro', 'https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/l55o/mm23/data'),
        ('ons-employment', 'ONS employment rate (16-64, seasonally adjusted)', 'macro', 'https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/timeseries/lf24/lms/data'),
        ('ons-gva', 'ONS monthly GVA period-on-period growth', 'macro', 'https://www.ons.gov.uk/economy/grossdomesticproductgdp/timeseries/ecyx/mgdp/data'),
        ('ons-hybrid', 'ONS characteristics of homeworkers, September 2022 to January 2023', 'research', 'https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/articles/characteristicsofhomeworkersgreatbritain/september2022tojanuary2023'),
        ('planning', 'London Planning Datahub', 'planning', 'https://data.london.gov.uk/dataset/planning-london-datahub'),
        ('gpe', 'GPE', 'owner', 'https://www.gpe.co.uk/news-media/news/'),
        ('britishland', 'British Land', 'owner', 'https://www.britishland.com/news/'),
        ('citylondon', 'City of London Corporation', 'planning', 'https://news.cityoflondon.gov.uk/'),
        ('bbc-rss', 'BBC Business RSS', 'news', 'https://feeds.bbci.co.uk/news/business/rss.xml'),
        ('nomis-london', 'Nomis BRES London workplace employment', 'macro', 'https://www.nomisweb.co.uk/api/v01/dataset/NM_189_1.data.csv?geography=2013265927&industry=37748736&employment_status=4&measure=1&measures=20100&time=latest,previous&select=date,geography_name,industry_name,employment_status_name,obs_value'),
        ('planning-api-city', 'Planning London Datahub · City of London', 'planning', 'https://planningdata.london.gov.uk/api-guest/applications/_search?size=5&q=lpa_name%3A%22City%20of%20London%22%20AND%20description%3Aoffice&sort=last_updated%3Adesc'),
        ('planning-api-westminster', 'Planning London Datahub · Westminster', 'planning', 'https://planningdata.london.gov.uk/api-guest/applications/_search?size=5&q=lpa_name%3AWestminster%20AND%20description%3Aoffice&sort=last_updated%3Adesc'),
        ('planning-api-tower-hamlets', 'Planning London Datahub · Tower Hamlets', 'planning', 'https://planningdata.london.gov.uk/api-guest/applications/_search?size=5&q=lpa_name%3A%22Tower%20Hamlets%22%20AND%20description%3Aoffice&sort=last_updated%3Adesc'),
        ('planning-api-camden', 'Planning London Datahub · Camden', 'planning', 'https://planningdata.london.gov.uk/api-guest/applications/_search?size=5&q=lpa_name%3ACamden%20AND%20description%3Aoffice&sort=last_updated%3Adesc'),
        ('epc-nondomestic', 'Official non-domestic EPC · City of London', 'macro', 'https://api.get-energy-performance-data.communities.gov.uk/api/non-domestic/search?council%5B%5D=City%20of%20London&page_size=5&current_page=1'),
    ]
    rows = [dict(id=i, name=n, category=c, url=u, enabled=True, allow_llm=True,
                 health='not_checked', last_success=None, last_error=None) for i, n, c, u in entries]
    kf = next(r for r in rows if r['id'] == 'knightfrank')
    kf.update(enabled=False, allow_llm=False, health='policy_restricted',
              policy_note='London Office Market Report Q2 2026 PDF page 17 General Note prohibits AI-platform use and reproduction without written approval; historical original preserved, automatic acquisition disabled.')
    epc = next(r for r in rows if r['id'] == 'epc-nondomestic')
    epc.update(enabled=bool(os.environ.get('LONDON_EPC_TOKEN', '').strip()), allow_llm=False,
               health='not_checked' if os.environ.get('LONDON_EPC_TOKEN', '').strip() else 'configuration_missing',
               policy_note='Government bearer token required; certificates are property-level candidates, not office-market ESG trends.')
    return rows


ALLOWED_HOSTS = frozenset({urlsplit(r['url']).hostname for r in catalog()} | {
    'www.colliers.com', 'www.carterjonas.co.uk',
    'www.jll.co.uk', 'www.savills.co.uk', 'research.euro.savills.co.uk',
    'www.cbre.com', 'data.london.gov.uk', 'planning.london.gov.uk',
    'api.ons.gov.uk', 'www.bbc.co.uk', 'www.bbc.com', 'www.bankofengland.co.uk',
    'www.gpe.co.uk', 'www.britishland.com',
})


def _check_url(url: str):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in ALLOWED_HOSTS
            or parsed.hostname == 'www.knightfrank.co.uk'
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError('SOURCE_POLICY: allowlisted public HTTPS URL required')
    return parsed


async def _resolve_doh(host: str) -> set[str]:
    # The local TUN can make numeric 1.1.1.1 unreachable. A TLS-authenticated
    # public DoH hostname still supplies real A records; the fetched publisher
    # connection is subsequently pinned to a validated public address.
    async with httpx.AsyncClient(trust_env=False, timeout=10, follow_redirects=False) as client:
        response = await client.get('https://cloudflare-dns.com/dns-query', params={'name': host, 'type': 'A'},
                                    headers={'Accept': 'application/dns-json'})
        response.raise_for_status()
        payload = response.json()
    if payload.get('Status') != 0:
        raise ValueError('SOURCE_POLICY: public DNS resolution failed')
    return {answer['data'] for answer in payload.get('Answer', []) if answer.get('type') == 1}


async def _resolve_public(host: str, port: int, allowed_hosts=None) -> set[str]:
    if host not in (ALLOWED_HOSTS if allowed_hosts is None else allowed_hosts) or port != 443:
        raise ValueError('SOURCE_POLICY: connection destination is not registered')
    addresses = await asyncio.to_thread(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM)
    ips = {a[4][0] for a in addresses}
    # Mihomo TUN returns RFC2544 synthetic addresses on this workstation. Use
    # independently authenticated public DNS only for that specific range.
    synthetic = (ipaddress.ip_network('198.18.0.0/15'), ipaddress.ip_network('2001:2::/48'))
    if ips and all(any(ipaddress.ip_address(ip) in network for network in synthetic) for ip in ips):
        ips = await _resolve_doh(host)
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError('SOURCE_POLICY: DNS destination is not public')
    return ips


class _PublicBackend:
    """Validate every actual connection and pin the numeric destination."""
    def __init__(self, allowed_hosts=None):
        self._backend = httpcore.AnyIOBackend()
        self.allowed_hosts = allowed_hosts

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        hostname = host.decode() if isinstance(host, bytes) else host
        ips = await _resolve_public(hostname, port) if self.allowed_hosts is None else await _resolve_public(hostname, port, self.allowed_hosts)
        return await self._backend.connect_tcp(sorted(ips)[0], port, timeout, local_address, socket_options)

    async def connect_unix_socket(self, *args, **kwargs):
        raise ValueError('SOURCE_POLICY: Unix sockets are forbidden')

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


def _make_transport(allowed_hosts=None):
    transport = httpx.AsyncHTTPTransport(retries=0, limits=httpx.Limits(max_connections=4, max_keepalive_connections=2))
    transport._pool._network_backend = _PublicBackend(allowed_hosts)
    return transport


async def fetch_source(source: dict, etag=None, last_modified=None) -> dict:
    """One source with conditional GET; callers bound cross-source concurrency.

    Non-2xx/304 responses raise HTTPStatusError so the caller can mark a failed
    source/job. No retries, credentials, environment proxy, or paywall bypass.
    """
    if source.get('enabled') is False:
        raise ValueError('SOURCE_POLICY: source is disabled')
    url = source['url']
    headers = {'User-Agent': 'DeepInsightLite/1.0 (bounded public market research)',
               'Accept': 'application/pdf,text/html,text/csv,application/json,application/rss+xml,*/*;q=0.1'}
    if source['id'].startswith('planning-api-'):
        if urlsplit(url).hostname != 'planningdata.london.gov.uk' or not urlsplit(url).path.startswith('/api-guest/applications/_search'):
            raise ValueError('SOURCE_POLICY: unexpected planning API endpoint')
        # Published by the GLA in its read-only API connection document.
        headers['X-API-AllowRequest'] = 'be2rmRnt&'
    if source['id'] == 'epc-nondomestic':
        if urlsplit(url).hostname != 'api.get-energy-performance-data.communities.gov.uk' or urlsplit(url).path != '/api/non-domestic/search':
            raise ValueError('SOURCE_POLICY: unexpected EPC API endpoint')
        token = os.environ.get('LONDON_EPC_TOKEN', '').strip()
        if not token: raise ValueError('CONFIGURATION_MISSING: LONDON_EPC_TOKEN')
        headers['Authorization'] = 'Bearer ' + token
    if etag:
        headers['If-None-Match'] = etag
    if last_modified:
        headers['If-Modified-Since'] = last_modified
    async with asyncio.timeout(65):
        async with httpx.AsyncClient(transport=_make_transport(), follow_redirects=False,
                                    trust_env=False, timeout=httpx.Timeout(25, connect=12)) as client:
            for _ in range(5):
                _check_url(url)
                if source.get('allowed_hosts') is not None and urlsplit(url).hostname not in source['allowed_hosts']:
                    raise ValueError('SOURCE_POLICY: redirect left the approved publisher')
                async with client.stream('GET', url, headers=headers) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        target = urljoin(url, response.headers['location'])
                        _check_url(target)
                        if urlsplit(target).hostname != urlsplit(url).hostname:
                            headers.pop('If-None-Match', None)
                            headers.pop('If-Modified-Since', None)
                        url = target
                        continue
                    if response.status_code != 304:
                        response.raise_for_status()
                    data = bytearray()
                    if response.status_code != 304:
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > MAX_BYTES:
                                raise ValueError('DOCUMENT_TOO_LARGE')
                    media = response.headers.get('content-type', '').split(';')[0].strip().lower()
                    if bytes(data).startswith(b'%PDF-'):
                        media = 'application/pdf'
                    return dict(status_code=response.status_code, content=bytes(data), media=media,
                                url=str(response.url), etag=response.headers.get('etag', etag if response.status_code == 304 else None),
                                last_modified=response.headers.get('last-modified', last_modified if response.status_code == 304 else None),
                                collected_at=datetime.now(timezone.utc).isoformat())
    raise ValueError('TOO_MANY_REDIRECTS')


def _segment(text: str, locator: str, page=None) -> dict:
    return {'segment_id': hashlib.sha256((locator + '\0' + text).encode()).hexdigest()[:24],
            'text': text.strip(), 'page': page, 'locator': locator}


def discover_article_sources(content: bytes, base_url: str, max_items: int = 2) -> list[dict]:
    """Discover at most two relevant article anchors from known public listings.

    DOM order is retained (these publisher listings display newest first).
    This is deterministic link discovery, not article/event classification, and
    never fetches a link. Individual article pages cannot trigger recursion.
    """
    if len(content) > MAX_BYTES:
        raise ValueError('DOCUMENT_TOO_LARGE')
    limit = min(max(int(max_items), 0), 2)
    if not limit:
        return []
    base = _check_url(base_url)
    research_groups = (
        {'www.realestate.bnpparibas.co.uk'},
        {'www.jll.com', 'www.jll.co.uk'},
        {'www.savills.co.uk', 'research.euro.savills.co.uk', 'pdf.euro.savills.co.uk'},
        {'www.cbre.com', 'www.cbre.co.uk'},
    )
    research_hosts = next((group for group in research_groups if base.hostname in group), None)
    if research_hosts:
        soup = BeautifulSoup(content, 'html.parser')
        rows = []
        seen = set()
        for anchor in soup.select('a[href]')[:3000]:
            if anchor.find_parent(['nav', 'header', 'footer']):
                continue
            try:
                parsed = _check_url(urljoin(base_url, anchor['href']))
            except ValueError:
                continue
            if parsed.hostname not in research_hosts or not parsed.path.lower().endswith('.pdf'):
                continue
            label = ' '.join(anchor.get_text(' ', strip=True).split())
            filename = unquote(parsed.path.rsplit('/', 1)[-1])
            subject = (label + ' ' + filename).lower()
            if 'london' not in subject or not any(word in subject for word in ('office', 'market')):
                continue
            url = urlunsplit(('https', parsed.netloc, parsed.path, parsed.query, ''))
            if url in seen:
                continue
            seen.add(url)
            title = label if len(label) >= 15 and 'london' in label.lower() else filename
            rows.append(dict(url=url, title=title, media='application/pdf'))
            if len(rows) == limit:
                break
        return rows
    listing_paths = {
        'www.gpe.co.uk': {'/news-media/news'},
        'www.britishland.com': {'/news'},
        'news.cityoflondon.gov.uk': {''},
    }
    if base.path.rstrip('/') not in listing_paths.get(base.hostname, set()):
        return []
    relevant = re.compile(
        r'\b(?:offices?|leasing|lettings?|leases?|pre[- ]?lets?|pre[- ]?lettings?|'
        r'workspaces?|developments?|redevelopment|refurbishment|planning|propert(?:y|ies)|'
        r'city\s+plan|business\s+update|trading\s+update|topping\s+out|fully\s+let|rents?)\b', re.I)
    excluded = {'news', 'news-media', 'press-releases', 'news-releases', 'privacy',
                'privacy-policy', 'contact', 'about-us', 'rss', 'sitemap', 'tagfeed'}
    soup = BeautifulSoup(content, 'html.parser')
    rows = []
    seen = set()
    for anchor in soup.select('a[href]')[:3000]:
        if anchor.find_parent(['nav', 'header', 'footer']) or any(
                parent.get('role') == 'navigation' for parent in anchor.parents if hasattr(parent, 'get')):
            continue
        href = anchor.get('href', '').strip()
        if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            continue
        url = urljoin(base_url, href)
        try:
            parsed = _check_url(url)
        except ValueError:
            continue
        if parsed.hostname != base.hostname:
            continue
        parts = [part for part in parsed.path.split('/') if part]
        if not parts or parts[-1].lower() in excluded or '.' in parts[-1]:
            continue
        if base.hostname == 'www.gpe.co.uk' and not re.fullmatch(r'/news-media/news/\d{4}/[^/]+/?', parsed.path):
            continue
        if base.hostname == 'www.britishland.com' and not re.fullmatch(r'/news/[^/]+/?', parsed.path):
            continue
        if base.hostname == 'news.cityoflondon.gov.uk' and len(parts) != 1:
            continue
        heading = anchor.find(['h1', 'h2', 'h3', 'h4'])
        title = ' '.join((heading.get_text(' ', strip=True) if heading else anchor.get('title') or anchor.get('aria-label') or anchor.get_text(' ', strip=True)).split())
        category = anchor.select_one('.news__card-category')
        subject = title + (' ' + category.get_text(' ', strip=True) if category else '')
        if not 15 <= len(title) <= 300 or not relevant.search(subject):
            continue
        # Canonical article paths retain neither tracking parameters nor fragments.
        url = urlunsplit(('https', parsed.netloc, parsed.path, '', ''))
        if url in seen:
            continue
        seen.add(url)
        row = dict(url=url, title=title)
        time_tag = anchor.find('time')
        if time_tag and time_tag.get('datetime'):
            row['published_at'] = time_tag['datetime']
        else:
            short_date = anchor.select_one('.news__card-date')
            city_parts = [anchor.select_one('.pp-block-item-date-' + part) for part in ('day', 'month', 'year')]
            try:
                if short_date:
                    row['published_at'] = datetime.strptime(short_date.get_text(strip=True), '%d.%m.%Y').date().isoformat()
                elif all(part is not None for part in city_parts):
                    row['published_at'] = datetime.strptime(' '.join(part.get_text(strip=True) for part in city_parts), '%d %B %Y').date().isoformat()
            except ValueError:
                pass
        rows.append(row)
        if len(rows) == limit:
            break
    return rows


def document_metadata(content: bytes, media: str) -> dict:
    """Explicit publisher metadata only; HTTP dates are not publication dates."""
    if media.split(';')[0] not in ['text/html','application/xhtml+xml']:return {}
    soup=BeautifulSoup(content,'html.parser')
    for node in soup.select('meta[property="article:published_time"], meta[itemprop="datePublished"]'):
        value=node.get('content','')
        try:datetime.fromisoformat(value.replace('Z','+00:00'))
        except ValueError:continue
        return dict(published_at=value)
    for script in soup.select('script[type="application/ld+json"]'):
        try:data=json.loads(script.get_text())
        except (ValueError,TypeError):continue
        nodes=data if isinstance(data,list) else [data]
        for node in nodes:
            if not isinstance(node,dict):continue
            value=node.get('datePublished')
            if not isinstance(value,str):continue
            try:datetime.fromisoformat(value.replace('Z','+00:00'))
            except ValueError:continue
            return dict(published_at=value)
    return {}


def parse_content(content: bytes, media: str) -> list[dict]:
    """Parse originals without interpreting page text as executable instructions."""
    if len(content) > MAX_BYTES:
        raise ValueError('DOCUMENT_TOO_LARGE')
    media = media.split(';')[0].lower().strip()
    if media == 'application/pdf' or content.startswith(b'%PDF-'):
        import pymupdf
        with pymupdf.open(stream=content, filetype='pdf') as doc:
            if len(doc) > MAX_PAGES:
                raise ValueError('DOCUMENT_TOO_MANY_PAGES')
            return [_segment(p.get_text(), f'pdf:page:{i}', i) for i, p in enumerate(doc, 1)]
    if 'spreadsheetml' in media or media == 'application/vnd.ms-excel':
        from openpyxl import load_workbook
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if sum(z.file_size for z in archive.infolist()) > 80 * 1024 * 1024:
                raise ValueError('DOCUMENT_TOO_LARGE_UNCOMPRESSED')
        book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        output = []
        try:
            for sheet in book:
                rows = sheet.iter_rows(values_only=True)
                header = next(rows, ())
                for index, row in enumerate(rows, 2):
                    text = '; '.join(f'{key}: {value}' for key, value in zip(header, row) if value is not None)
                    if text:
                        output.append(_segment(text, f'xlsx:{sheet.title}:row:{index}'))
                    if len(output) >= MAX_SEGMENTS:
                        raise ValueError('DOCUMENT_TOO_MANY_ROWS')
        finally:
            book.close()
        return output
    text = content.decode('utf-8-sig', errors='replace')
    if media in ('text/csv', 'application/csv'):
        rows = csv.DictReader(io.StringIO(text))
        output = []
        for i, row in enumerate(rows, 2):
            output.append(_segment('; '.join(f'{k}: {v}' for k, v in row.items()), f'csv:row:{i}'))
            if len(output) >= MAX_SEGMENTS:
                raise ValueError('DOCUMENT_TOO_MANY_ROWS')
        return output
    if media == 'application/json' or media.endswith('+json'):
        data = json.loads(text)
        if isinstance(data, dict):
            rows = []
            for key, value in data.items():
                escaped = key.replace('~', '~0').replace('/', '~1')
                if isinstance(value, list):
                    rows.extend((f'json:/{escaped}/{i}', row) for i, row in enumerate(value))
                else:
                    rows.append((f'json:/{escaped}', value))
        elif isinstance(data, list):
            rows = [(f'json:/{i}', row) for i, row in enumerate(data)]
        else:
            rows = [('json:/', data)]
        if len(rows) > MAX_SEGMENTS:
            raise ValueError('DOCUMENT_TOO_MANY_ROWS')
        return [_segment(json.dumps(row, ensure_ascii=False), locator) for locator, row in rows]
    if media in ('application/rss+xml', 'application/atom+xml', 'text/xml', 'application/xml'):
        import xml.etree.ElementTree as ET
        if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
            raise ValueError('SOURCE_POLICY: XML entities are forbidden')
        tree = ET.fromstring(text)
        items = tree.findall('.//item') or tree.findall('{http://www.w3.org/2005/Atom}entry')
        if len(items) > MAX_SEGMENTS:
            raise ValueError('DOCUMENT_TOO_MANY_ROWS')
        output = []
        atom_ns = '{http://www.w3.org/2005/Atom}'
        for i, item in enumerate(items, 1):
            segment = _segment(' '.join(' '.join(item.itertext()).split()), f'feed:item:{i}')
            title = item.findtext('title') or item.findtext(atom_ns + 'title')
            link = item.findtext('link')
            if not link:
                alternate = next((node for node in item.findall(atom_ns + 'link')
                                  if node.get('rel', 'alternate') == 'alternate'), None)
                link = alternate.get('href') if alternate is not None else None
            try:
                if link:
                    _check_url(link)
            except ValueError:
                link = None
            raw_date = item.findtext('pubDate') or item.findtext(atom_ns + 'published') or item.findtext(atom_ns + 'updated')
            published_at = None
            if raw_date:
                try:
                    is_iso = raw_date[:4].isdigit() and raw_date[4:5] == '-'
                    date = datetime.fromisoformat(raw_date.replace('Z', '+00:00')) if is_iso else parsedate_to_datetime(raw_date)
                    if date.tzinfo is not None:
                        published_at = date.astimezone(timezone.utc).isoformat()
                except (ValueError, TypeError, OverflowError):
                    pass
            segment.update(title=title, url=link, published_at=published_at)
            output.append(segment)
        return output
    if media in ('text/html', 'application/xhtml+xml'):
        soup = BeautifulSoup(content, 'html.parser')
        for tag in soup(['script', 'style', 'noscript', 'nav', 'footer', 'header']):
            tag.decompose()
        main = soup.find('main') or soup.find('article') or soup.body or soup
        return [_segment(main.get_text(' ', strip=True), 'html:main')]
    if media == 'text/plain':
        return [_segment(text, 'text:all')]
    raise ValueError(f'UNSUPPORTED_MEDIA: {media}')
