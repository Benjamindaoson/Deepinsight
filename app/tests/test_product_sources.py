import asyncio
import importlib.util
from io import BytesIO
from pathlib import Path

import httpx
import pytest


def test_source_module_provides_real_adapters():
    assert importlib.util.find_spec('london_product.sources') is not None


def test_catalog_has_official_sources_and_required_categories():
    from london_product.sources import catalog
    rows = catalog()
    assert {'research', 'macro', 'planning', 'owner', 'news'} <= {r['category'] for r in rows}
    assert {'jll', 'savills', 'cbre', 'knightfrank', 'bnp', 'boe', 'ons', 'planning', 'gpe', 'britishland', 'citylondon', 'bbc-rss'} <= {r['id'] for r in rows}
    assert len({r['id'] for r in rows}) == len(rows)


def test_html_parser_omits_scripts_and_pdf_keeps_page_evidence():
    import pymupdf
    from london_product.sources import parse_content
    html = parse_content(b'<main><h1>London</h1><p>West End 8.6%</p><script>secret()</script></main>', 'text/html')
    assert 'West End 8.6%' in html[0]['text']
    assert 'secret' not in html[0]['text']
    doc = pymupdf.open()
    doc.new_page().insert_text((40, 40), 'City vacancy 8.6%')
    doc.new_page().insert_text((40, 40), 'West End supply')
    segments = parse_content(doc.tobytes(), 'application/pdf')
    assert segments[1]['page'] == 2
    assert segments[1]['locator'] == 'pdf:page:2'
    assert 'West End supply' in segments[1]['text']


def test_tabular_json_and_rss_parsers_preserve_locators():
    from london_product.sources import parse_content
    csv = parse_content(b'period,value\n2026Q2,8.6\n', 'text/csv')
    assert csv[0]['locator'] == 'csv:row:2'
    assert 'period: 2026Q2' in csv[0]['text']
    rows = parse_content(b'{"items":[{"title":"Canary Wharf"}]}', 'application/json')
    assert 'Canary Wharf' in rows[0]['text']
    rss = parse_content(b'<rss><channel><item><title>Lease agreed</title><pubDate>Fri, 16 Oct 2026 12:00:00 GMT</pubDate><description>London pre-let</description><link>https://www.bbc.co.uk/news/a</link></item></channel></rss>', 'application/rss+xml')
    assert 'Lease agreed' in rss[0]['text']
    assert rss[0]['locator'] == 'feed:item:1'


def test_xlsx_parser_preserves_sheet_and_row():
    from openpyxl import Workbook
    from london_product.sources import parse_content
    book = Workbook()
    book.active.title = 'Rates'
    book.active.append(['Period', 'Value'])
    book.active.append(['2026Q2', 8.6])
    data = BytesIO()
    book.save(data)
    rows = parse_content(data.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    assert rows[0]['locator'] == 'xlsx:Rates:row:2'
    assert '8.6' in rows[0]['text']


def test_fetch_rejects_private_and_non_allowlisted_urls():
    from london_product.sources import fetch_source
    for url in ('file:///c:/Windows/win.ini', 'https://127.0.0.1/', 'http://www.jll.com/', 'https://www.jll.com.evil.invalid/'):
        with pytest.raises(ValueError, match='SOURCE_POLICY'):
            asyncio.run(fetch_source({'id': 'test', 'url': url}))


def test_conditional_get_and_redirect_guard(monkeypatch):
    from london_product import sources
    seen = []
    def respond(request):
        seen.append(request)
        if request.url.path == '/redirect':
            return httpx.Response(302, headers={'location':'https://127.0.0.1/private'})
        return httpx.Response(304, headers={'etag':'"abc"'})
    monkeypatch.setattr(sources, '_make_transport', lambda: httpx.MockTransport(respond))
    row = {'id': 'test', 'url': 'https://www.jll.com/report'}
    result = asyncio.run(sources.fetch_source(row, etag='"abc"', last_modified='Fri, 16 Oct 2026 00:00:00 GMT'))
    assert result['status_code'] == 304 and result['content'] == b''
    assert seen[0].headers['if-none-match'] == '"abc"'
    assert 'if-modified-since' in seen[0].headers
    with pytest.raises(ValueError, match='SOURCE_POLICY'):
        asyncio.run(sources.fetch_source({**row, 'url':'https://www.jll.com/redirect'}))
    assert len(seen) == 2


def test_seed_preserves_original_six_review_and_provenance():
    from london_product.seed import seed_records
    records = seed_records(Path(__file__).resolve().parents[2])
    original = [f for f in records['facts'] if f['id'].startswith('BNP-')]
    assert len(original) == 6
    assert all(f['status'] != 'validated' for f in records['facts'])
    rents = [f for f in original if f['metric'] == 'rent']
    assert all(f['normalized_value'] is None for f in rents)
    docs = {d['id']:d for d in records['documents']}
    for fact in records['facts']:
        document = docs[fact['document_id']]
        assert Path(document['path']).is_file()
        assert fact['source_id'] == document['source_id']
        quote = ' '.join(fact['evidence']['quote'].split())
        assert any(quote in ' '.join(seg['text'].split()) for seg in document['segments'])
    assert {'West End', 'Midtown', 'Canary Wharf'} <= {f['geography'] for f in records['facts']}


def test_public_dns_fallback_only_for_synthetic_tun_range(monkeypatch):
    from london_product import sources
    async def doh(host):
        return {'104.20.42.97'}
    monkeypatch.setattr(sources, '_resolve_doh', doh, raising=False)
    monkeypatch.setattr(sources.socket, 'getaddrinfo', lambda *a: [(2, 1, 6, '', ('198.18.0.200', 443)), (23, 1, 6, '', ('2001:2::c3', 443, 0, 0))])
    assert hasattr(sources, '_resolve_public'), 'Verified public DNS resolver missing'
    assert asyncio.run(sources._resolve_public('www.gpe.co.uk', 443)) == {'104.20.42.97'}
    monkeypatch.setattr(sources.socket, 'getaddrinfo', lambda *a: [(2, 1, 6, '', ('127.0.0.1', 443))])
    with pytest.raises(ValueError, match='SOURCE_POLICY'):
        asyncio.run(sources._resolve_public('www.gpe.co.uk', 443))



def test_json_timeseries_rows_have_separate_evidence_locations():
    from london_product.sources import parse_content
    rows = parse_content(b'{"months":[{"date":"2026 AUG","value":"3.3"}],"description":{"unit":"%"}}','application/json')
    assert any(row['locator'] == 'json:/months/0' for row in rows)
    assert any(row['locator'] == 'json:/description' for row in rows)


def test_rss_and_atom_preserve_article_provenance_and_safe_links():
    from london_product.sources import parse_content
    rss = b'<rss><channel><item><title>Lease agreed</title><pubDate>Fri, 16 Oct 2026 12:00:00 GMT</pubDate><description>London pre-let</description><link>https://www.bbc.co.uk/news/articles/abc</link></item><item><title>Unsafe link</title><link>javascript:alert(1)</link></item></channel></rss>'
    rows = parse_content(rss, 'application/rss+xml')
    assert rows[0].get('url') == 'https://www.bbc.co.uk/news/articles/abc'
    assert rows[0].get('title') == 'Lease agreed'
    assert rows[0].get('published_at') == '2026-10-16T12:00:00+00:00'
    assert rows[1].get('url') is None
    atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Planning decision</title><published>2026-10-16T13:00:00+01:00</published><link rel="self" href="https://www.bbc.co.uk/feed"/><link rel="alternate" href="https://www.bbc.co.uk/news/articles/xyz"/><summary>Office approval</summary></entry></feed>'
    row = parse_content(atom, 'application/atom+xml')[0]
    assert row.get('url') == 'https://www.bbc.co.uk/news/articles/xyz'
    assert row.get('published_at') == '2026-10-16T12:00:00+00:00'


def test_listing_discovery_uses_saved_official_cards_without_generic_navigation():
    from london_product import sources
    assert hasattr(sources, 'discover_article_sources'), 'Listing article discovery is missing'
    root = Path(__file__).resolve().parents[1] / 'data/product/source-qualification'
    cases = [
        ('gpe', 'https://www.gpe.co.uk/news-media/news/', '/news-media/news/2026/'),
        ('britishland', 'https://www.britishland.com/news/', '/news/'),
        ('citylondon', 'https://news.cityoflondon.gov.uk/', 'https://news.cityoflondon.gov.uk/'),
    ]
    for name, url, prefix in cases:
        rows = sources.discover_article_sources((root / (name + '.html')).read_bytes(), url)
        assert 1 <= len(rows) <= 2
        assert all(len(row['title']) >= 15 for row in rows)
        assert all(prefix in row['url'] and row['url'] != url for row in rows)
        assert all(row['title'].lower() not in {'news releases', 'press releases', 'news', 'our offices'} for row in rows)
        assert len({row['url'] for row in rows}) == len(rows)
    city = sources.discover_article_sources((root / 'citylondon.html').read_bytes(), cases[2][1])
    assert any('City Plan 2040' in row['title'] for row in city)
    assert next(row for row in city if 'City Plan 2040' in row['title']).get('published_at') == '2026-09-24'
    assert all('Chief Commoner' not in row['title'] for row in city)
    british = sources.discover_article_sources((root / 'britishland.html').read_bytes(), cases[1][1])
    assert next(row for row in british if row['title'] == 'Q2 trading update').get('published_at') == '2026-10-15'
    assert sources.discover_article_sources((root / 'gpe-city-tower.html').read_bytes(), 'https://www.gpe.co.uk/news-media/news/2026/gpe-secures-fully-managed-pre-lets-at-city-tower-ec2-ahead-of-launch/') == []


def test_listing_discovery_rejects_external_navigation_and_deduplicates_urls():
    from london_product.sources import discover_article_sources
    html = b'''<main><nav><a href="/news/nav-office-menu/">Our office property news</a></nav>
    <a href="https://evil.invalid/news/office-lease/">London office lease signed</a>
    <a href="/news/press-releases/">Property press releases</a>
    <a href="javascript:alert(1)">Office development</a>
    <a href="/news/office-lease/#first">London office lease agreed</a>
    <a href="/news/office-lease/#duplicate">London office lease agreed</a>
    <a href="/news/new-workspace/">New London workspace development</a>
    <a href="/news/third-project/">Another London property development</a></main>'''
    rows = discover_article_sources(html, 'https://www.britishland.com/news/', max_items=100)
    assert [row['url'] for row in rows] == ['https://www.britishland.com/news/office-lease/', 'https://www.britishland.com/news/new-workspace/']
    assert discover_article_sources(html, 'https://www.britishland.com/news/', max_items=1) == rows[:1]


def test_research_discovery_follows_only_actual_registered_london_pdf_anchors():
    from london_product.sources import discover_article_sources
    root = Path(__file__).resolve().parents[2]
    html = (root / 'b1/g0-review/2026-10-17/raw/bnp-q2-2026.html').read_bytes()
    rows = discover_article_sources(html, 'https://www.realestate.bnpparibas.co.uk/insights/central-london-office-market-update-q2-2026')
    assert any(row['url'] == 'https://www.realestate.bnpparibas.co.uk/sites/default/files/2026-08/Q22026CentralLondonMarketUpdate.pdf' for row in rows)
    assert len(rows) <= 2
    hostile = b'<main><a href="https://evil.invalid/london-office-report.pdf">London office market report</a><a href="/contact">London office market report</a><a href="/assets/retail-only.pdf">Retail guide</a></main>'
    assert discover_article_sources(hostile, 'https://www.jll.com/en-uk/insights/market-dynamics/central-london-office') == []


def test_original_bnp_takeup_keeps_display_scale_separate_from_full_area():
    from london_product.seed import seed_records
    root = Path(__file__).resolve().parents[2]
    rows = {fact['id']: fact for fact in seed_records(root)['facts']}
    q1, q2 = rows['BNP-2026Q1-TAKEUP'], rows['BNP-2026Q2-TAKEUP']
    assert q1['value'] == '2.5' and q2['value'] == '3.0'
    assert q1['unit'] == 'million sqft for a single quarter'
    assert q1['normalized_value'] == '2500000' and q2['normalized_value'] == '3000000'
    assert q1['normalized_unit'] == 'sqft' and q1['basis'] == 'quarter'
    assert q1['precision'] == '0.1' and q1['normalized_precision'] == '100000'
    assert q1['raw_display'] == '2.5m sq ft'
    assert q1['original_annotation']['numeric_value'] == '2500000'
    assert q1['original_annotation']['normalized_unit'] == 'sqft/quarter'
    assert q1['series'] == 'UK Central London Office Market Update'
    assert q1['currency'] is None and q1['temporal_basis'] == 'single_quarter_flow'
    rent = rows['BNP-2026Q1-RENT']
    assert rent['value'] == '92.50' and rent['normalized_value'] is None
    assert rent['currency'] == 'GBP'
    assert all(rows[key]['human_review_status'] == 'pending_review' for key in rows if key.startswith('BNP-'))


def test_actual_employment_seed_preserves_three_month_period_label():
    from london_product.sources import catalog
    from london_product.seed import seed_records
    assert any(s['id'] == 'ons-employment' and s['category'] == 'macro' for s in catalog())
    rows = seed_records(Path(__file__).resolve().parents[2])
    employment = next(f for f in rows['facts'] if f['source_id'] == 'ons-employment')
    assert employment['metric'] == 'employment' and employment['value'] == '75.1'
    assert employment['period'] == '2026 MAY-JUL' and employment['raw_period'] == '2026 JUN'
    assert employment['basis'] == 'rolling_three_month_average'
    assert employment['human_review_status'] == 'pending_review'
    assert '16-64' in employment['definition'] and 'seasonally adjusted' in employment['definition']
