# Product API contract v1

Base: http://127.0.0.1:7780/api/market. Dates ISO8601 with timezone; null means unknown. Pydantic request validation; errors {detail: string}. No browser secrets. GET is read-only.

- GET /overview -> {updated_at, facts:[Fact], events:[Event], sources:[Source], counts:{facts,events,documents,reports,needs_review}, comparisons:[Comparison], jobs:[Job]}
- GET /facts?geography=&metric=&period=&status=&source_id=&limit=100&offset=0 -> {items:[Fact],total,updated_at}
  Fact pagination accepts limit 1–500; larger limits return422. Geography grouping in search does not change source labels or comparison dimensions.
- GET /facts/{id}/evidence -> {fact,document:{id,title,url,published_at,collected_at,sha256,media},evidence:{quote,page,locator},download_url}
- GET /sources -> {items:[Source]}; Source={id,name,category,url,enabled,health,last_success,last_error}
- POST /sources/{id}/refresh -> Job; POST /refresh -> Job. Both accept Idempotency-Key; no model extraction by default.
- POST /documents/{id}/extract -> Job (explicit bounded native LLM extraction).
- GET /documents -> {items:[Document]}; GET /documents/{id}/file -> original bytes
- GET /events?geography=&kind=&importance=&status= -> {items:[Event],total}; POST /events/{id}/ack -> Event
- GET /comparisons -> {items:[Comparison]}; POST /compare {old_id,new_id} -> Comparison
- GET /reports -> {items:[Report]}; POST /reports {period:"weekly"|"daily",include_analysis:false} -> Report (deterministic by default); GET /reports/{id}?format=html|markdown -> attachment/rendered output
- GET /jobs -> {items:[Job]}; GET /jobs/{id} -> Job; POST /jobs/{id}/retry -> Job
- GET /settings -> {news_interval_hours,market_interval_hours,notifications_enabled,notification_configured,geographies,metrics,schedules:[...]}; PUT /settings accepts same editable fields (no secrets)
- POST /notifications {report_id} -> attempt with status configuration_missing|sent|failed; GET /notifications -> {items:[...]}
- POST /ask {message,mode:"saved"|"agent"} -> SSE events: {type:"token",content:string}, {type:"done",citations:[...],run_id,metrics}, {type:"error",message}. Saved mode deterministic; agent mode actual native Agent+Tools and streaming.
- POST /reports with include_analysis=true returns202 Job (kind report_analysis); native Agent interpretation runs in the background, caches successful unchanged evidence, and remains REVIEW_REQUIRED. include_analysis=false returns a fast deterministic Report. Known draft quality issues and superseded versions are explicitly labelled on export.
- Native AgentOS standard routes retained, Agent id london-market-agent; official chat accessible at /chat on business UI.

Fact fields: id,metric,value,normalized_value,unit,precision,geography,period,status,publisher,source_id,document_id,evidence:{quote,page,locator},definition,grade,method,run_id,published_at,collected_at. Values decimal strings or null; statuses include pending_review/needs_review/validated; no automatic human signoff.
Event fields: id,title,summary,kind,importance,status,geography,published_at,source_id,url,evidence,document_id. Job fields: id,kind,status,stage,progress,started_at,finished_at,error,attempts,result,run_id. Report fields: id,title,created_at,period,markdown_url,html_url.

Backend module ownership: root london_product/store.py,contracts.py,service.py,runtime.py plus tests; source implementer london_product/sources.py,seed.py and test_product_sources.py only; frontend implementer app/frontend only plus frontend commands/docs under frontend. Source interface: catalog()->list[dict]; async fetch_source(source:dict,etag=None,last_modified=None)->dict with status_code,content:bytes,media,url,etag,last_modified,collected_at; parse_content(content:bytes,media:str)->list[{segment_id,text,page,locator}]; seed_records(root:Path)->dict {sources:[],documents:[],facts:[],events:[]} with document content/path, sha256, source_id and genuine fact statuses. Root persists these records. No source code imports product Store.
