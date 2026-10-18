# Product source adapters and genuine bootstrap evidence

Scope: independent London product under `app/london_product` and `app/data/product`. The B0 framework and historical B1/G0 originals, gold annotations, registry, and evidence remain read-only. No paid API, model call, account registration, contact submission, message, or notification occurred in this source work.

## Implemented contracts

- `catalog()` returns 12 first-party sources across research, macro, planning, owner, and news: BNP, JLL, Savills, CBRE, Knight Frank, Bank of England, ONS, London Planning Datahub, GPE, British Land, City of London, BBC Business RSS.
- `async fetch_source(source, etag=None, last_modified=None)` returns status_code, content bytes, media, final URL, ETag, Last-Modified, and UTC collection time. HTTP errors propagate to the product job/source-health handler. HTTP 304 returns zero bytes; it never creates an empty replacement document.
- `parse_content(bytes, media)` supports HTML, text PDF, CSV, XLSX, JSON, RSS/Atom and plain text. PDF pages are one-based; CSV/XLSX rows, sheet names, JSON pointers and feed entry indices are retained as locators. Scanned PDFs have no invented OCR output. Unsupported/broken formats raise errors.
- `seed_records(project_root)` returns 12 sources, 9 original documents, 23 facts and 3 events after source qualification. IDs derive from original hashes or frozen annotation IDs. All original byte copies remain inside product storage. Existing product persistence is the parent service's responsibility.

## Acquisition boundaries

Only exact registered HTTPS hosts on port 443 are permitted. Credentials, file URLs, local addresses, arbitrary domains and Unix sockets are rejected. Every redirect must remain allowlisted; actual TCP connections resolve again and pin to a validated public numeric IP while keeping original-host TLS verification/SNI. No environment proxy, automatic retry, login or paywall bypass is used. Limits: 65 seconds total per source, 12 second TCP connect, 25 second I/O, 5 redirect/request iterations, 15 MiB decoded content, 100 PDF pages, 10,000 tabular/JSON/feed segments and 80 MiB uncompressed XLSX archive. The parent refresh routine bounds source concurrency.

This Windows workstation uses Mihomo synthetic DNS: IPv4 `198.18.0.0/15` and IPv6 `2001:2::/48`. Initial attempts were correctly blocked. A narrow fallback now queries public Cloudflare DNS over verified HTTPS to numeric `1.1.1.1` only when every local answer belongs to those synthetic ranges. All resulting A records must be globally routable, and the socket connects directly to the checked IP. Ordinary private/loopback answers still fail closed. The initial blocked receipts remain available for inspection.

Knight Frank Q2 2026 PDF page 17 General Note explicitly prohibits AI-platform use and reproduction without written approval. The catalog registers its official series but sets `enabled=false`, `allow_llm=false`, `health=policy_restricted` and a page-specific policy_note. No Knight Frank full text, fact transcription or PDF copy enters the product seed or model context. The historical original is untouched.

## Actual evidence and qualification

Qualification directory: `D:\deepinsight-lite\app\data\product\source-qualification`.

Eleven distinct official URLs were attempted in the bounded live source exercise. Eight returned HTTP 200 and their actual bytes, hashes, headers and collection times are retained:

1. GPE news listing.
2. GPE City Tower pre-let announcement, reported publication 24 September 2026.
3. British Land news listing.
4. British Land Q2 trading update, reported publication 15 October 2026.
5. City of London news homepage.
6. City of London Silk Street planning announcement, published 28 May 2026 at 15:22 Europe/London.
7. Bank of England daily official Bank Rate CSV, series IUDBEDR; latest collected observation 15 October 2026, 3.75 percent.
8. ONS CPIH annual rate JSON, series L55O/MM23; latest collected observation August 2026, 3.3 percent. Source release timestamp 2026-09-15T23:00:00Z. This is CPIH, not CPI, and UK-wide context rather than a London-office observation.

Three failures remain visible, with no fabricated substitute originals: CBRE official Q2 figures returned 403; London Planning Datahub returned 403; BBC Business RSS timed out. Source catalog presence is not a successful live acquisition claim. A separate conditional ONS request with its actual ETag returned HTTP 304 and 0 bytes (`conditional-ons-receipt.json`).

`fetch-receipts.json` and `article-receipts.json` hold final attempts; `attempts-initial-blocked.json` and `attempts-ipv6-blocked.json` retain earlier guard rejections. `manifest.json` contains five acquired evidence documents (three articles, two macro series), three genuine source-located events and two macro facts. Listing originals are retained as acquisition evidence but are not counted as article events.

The other four product documents are verified byte copies of historical BNP Q1/Q2, JLL Q2 and Savills Q2 originals. The original BNP six annotation IDs, displayed precision, unresolved issues, annual-unit unknowns and pending human review survive import. Additional exact page-located facts cover West End, Midtown, Canary Wharf, combined Canary Wharf & Docklands, supply, pre-let-or-under-offer share and Grade A share. JLL 80 percent refers to delivered space pre-let **or under offer**, not solely pre-let; Savills 94 percent Grade A share refers to H1, not Q2. Different publisher definitions are kept distinct.

No fact is validated. Rent normalization remains null when the annual denominator is unconfirmed. Method is unknown. BNP Q2 Canary Wharf & Docklands take-up narrative 166k versus key-card 167k is retained as an explicit needs_review discrepancy. BNP Midtown's directional vacancy narrative is also flagged rather than reconciled silently. Article dates known only to the day retain date precision instead of inventing a publication time.

## Commands and observed verification

Run from `D:\deepinsight-lite` unless stated otherwise:

```powershell
codegraph status
codegraph explore "app London market sources seed ingest and source qualification main entry points"
app/.venv/Scripts/python.exe -m pytest app/tests/test_product_sources.py -q
$env:PYTHONPATH='app'
app/.venv/Scripts/python.exe -c "from pathlib import Path; from london_product.seed import seed_records; r=seed_records(Path('.')); print({k:len(v) for k,v in r.items()})"
```

Test-first failures were observed for the initially absent adapters, the synthetic-public-DNS resolver, mixed synthetic IPv4/IPv6 and JSON timeseries row locators. Final source suite: **10 passed**. It checks required categories, active parsing behavior, page and row evidence, script omission, unsafe URL and redirect rejection, conditional GET headers/304 handling, the narrow synthetic-DNS exception, original-six preservation, full seed quote-to-original matching and geographical coverage.

Full project suite, run from `D:\deepinsight-lite\app`:

```powershell
.venv/Scripts/python.exe -m pytest
```

Observed: **89 passed in 7.79 seconds** on Python 3.12.10. One preceding command mistakenly repeated the `app/` prefix while already inside `app`; PowerShell rejected that path before test execution, and the command above corrected it. No dependencies were installed globally.

The source adapters are libraries; local API/UI entrypoints and browser validation are handled in the parent product runbook. Source integration must seed/restart the product runtime before expecting the newer manifest records in an already running database. Engineering tests and real collection prove adapter behavior and provenance; human fact review and formal market comparisons remain pending.

## Independent integration review follow-up

RSS/Atom segments now additionally retain `title`, safe registered HTTPS article `url`, and timezone-aware `published_at` normalized to UTC. RSS pubDate and Atom published/updated dates are supported; absent, invalid or timezone-less dates remain null. Atom rel=alternate links take precedence over self-feed links. Unsafe/nonregistered links remain null; no article is fetched by parsing a feed. The event integration should prefer this per-entry metadata over the feed document URL/date.

A test-first regression covers RSS and Atom article links/dates plus javascript-link rejection. Updated source test result: **11 passed in 1.30 seconds**. No new source or model requests occurred during this review/fix.

After integration fixes, the full app command `.venv/Scripts/python.exe -m pytest` was rerun from `D:\deepinsight-lite\app`: **94 passed in 7.94 seconds**. Offline overlapping async-task checks now retain separate RunBoundedModel budgets after aging the initial budget beyond 480 seconds; SDK client timeout remains 180 seconds. No network/model request was issued by these checks. Current reviewed code includes resource-bound idempotency checks, serialized immutable snapshot creation, active extraction deduplication and per-document locks, context-bounded query evidence, and per-entry feed metadata consumption. No additional concrete P1/P2 review blocker remained in the bounded backend review at that snapshot.

## Listing-to-article discovery correction

`discover_article_sources(content, base_url, max_items=2)` now performs deterministic, bounded article discovery for the saved GPE, British Land and City of London news listings. It returns at most two same-host registered HTTPS article URLs in existing DOM order, with real headline text and source-reported day-precision publication dates when available. It excludes navigation/header/footer, generic index/privacy links, unsafe/external URLs, repeated fragment/tracking URLs and irrelevant civic-office-holder headlines. Individual article base URLs return no discovery results, preventing recursive crawling. This helper only returns links; parent service performs any explicitly bounded acquisition and article event classification.

Two new regression tests use the actual saved listing originals plus unsafe/deduplication fixtures. A further date assertion initially failed, then passed after adding the observed British Land and City date markup. Updated source suite: **13 passed in 1.52 seconds**. No external acquisition/model call was made in this helper task.

## Research PDF discovery and original BNP scale correction

Research HTML discovery now follows only explicit PDF anchors for registered BNP/JLL/Savills/CBRE publisher families, requires London plus office/market report naming, and caps acquisition candidates at two. It never guesses quarter URLs or invokes extraction. The saved BNP Q2 HTML fixture resolves its real `Q22026CentralLondonMarketUpdate.pdf` anchor. Knight Frank remains excluded by policy. The catalog BNP Q2 landing URL is static; selecting a future quarter remains an explicit catalog maintenance step.

Original BNP take-up seed display and normalization are now separate. Q1 displays `2.5` and Q2 `3.0` with the exact original raw unit `million sqft for a single quarter`; normalized values remain `2500000` and `3000000` with unit `sqft` and basis `quarter`. Raw precision is `0.1` million, normalized precision `100000` sqft. The full frozen `original_annotation` remains embedded, including its prior expanded numeric_value and `sqft/quarter` normalization label. Series, currency, temporal_basis, period_start/end and review state are retained. Annual-unknown rent normalization stays null. A failing display-scale regression was observed before the correction. Updated source suite: **15 passed in 1.63 seconds**. Existing product-row migration/revision history is handled by root; the reviewer independently read back both corrected product take-up rows with pending human review and revision_history. Historical G0 files were not edited.


## Targeted employment context addition

An explicitly bounded live safe fetch acquired official ONS LF24/LMS JSON. Employment rate is UK age 16-64, seasonally adjusted, percent, three-month average: latest label May-July 2026 =75.1%, with central index date June 2026 and release2026-09-14T23:00Z. The seed uses the source three-month label, retains the raw index month, and remains pending human review. The catalog source ID is ons-employment. Actual original/hash/receipt and manifest revision are under source-qualification/; the prior manifest is preserved by byte copy and hash. Source suite now16passed2.27s. This addition made one public data acquisition and no model call.
