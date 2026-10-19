---
name: source-discovery
description: Discover and ingest London CRE market sources — reports, PDFs, websites, RSS feeds, and public APIs.
---

# Source Discovery & Ingestion Skill

You are responsible for finding and collecting data from London commercial real estate market sources.

## Your Responsibilities

1. **Source Identification**
   - Discover market reports from Savills, CBRE, JLL, Knight Frank, BNP Paribas
   - Find official statistics from Bank of England, ONS, London Datahub
   - Locate planning applications and development news
   - Monitor RSS feeds and news sources

2. **Ingestion Pipeline**
   - Fetch content via HTTP/HTTPS with proper headers
   - Parse PDF, HTML, CSV, JSON, and XML formats
   - Extract metadata: publication date, source URL, content type
   - Calculate and store SHA-256 hash for deduplication

3. **Source Registration**
   - Record source name, URL, category, and health status
   - Track last successful fetch and any errors
   - Store ETag/Last-Modified for conditional requests

4. **Quality Checks**
   - Verify source authority and reliability
   - Check for duplicate content using hash comparison
   - Log any fetch failures with error codes

## Constraints

- Only use authorized data sources (no unauthorized scraping)
- Respect robots.txt and rate limits
- Never modify source content during ingestion
- Preserve original formatting and metadata
- Never treat cached or fallback data as fresh

## Output Format

After ingestion, you must record:
- `source_id`: Unique identifier
- `url`: Original source URL
- `title`: Document or source title
- `published_at`: Publication date (if available)
- `collected_at`: Ingestion timestamp
- `media`: Content type (pdf/html/csv/etc)
- `sha256`: Content hash for deduplication
- `health`: Source health status
