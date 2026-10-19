"""Explicit, individually justified source review; never approve a search result list."""
import hashlib,json,re,sys
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
from london_product.store import Store,now
from london_product.service import MarketService
from london_product.indicator_ingestion import _save,_quote
from london_product.safe_answer import safe_evidence
from london_product.chat_report import build_report,render_html,render_markdown
OUT=ROOT/'docs/delivery/regional-real-20261019';store=Store(OUT/'runtime');svc=MarketService(store)
fresh=json.loads((OUT/'FRESH_ACQUISITION.json').read_text(encoding='utf-8'))
q2page=store.get('documents',fresh[0]['document_id']);soup=BeautifulSoup(Path(q2page['path']).read_bytes(),'html.parser')
assert any(t.get_text(strip=True)=='05.08.2026' for t in soup.select('div.date'))
assert any(a.get('href')==fresh[1]['url'] for a in soup.find_all('a'))
q1=store.get('documents',fresh[2]['document_id']);q2=store.get('documents',fresh[1]['document_id'])
q2=store.update('documents',q2['id'],dict(published_at='2026-08-05',publication_provenance=dict(
    evidence_document_id=q2page['id'],sha256=q2page['sha256'],url=q2page['url'],quote='05.08.2026',
    binding='Official report landing page contains this date and the exact PDF download URL.')))
docs={'2026Q1':q1,'2026Q2':q2}
# Every item below was inspected as a complete rendered original page; each
# carries a separate rationale. No other candidate inherits the decision.
items=[
 dict(period='2026Q1',page=6,geography='City',metric='vacancy',value='9.8',unit='percent',basis='stock_rate',definition='Overall vacancy; submarket narrative',
      phrase='vacancy decreasing from 11.0% in Q1 2025 to 9.8% at the close of Q1 2026.',
      rationale='The City heading, Q1 banner, vacancy card and narrative agree at 9.8%; 11.0% is a separate prior-year reference.'),
 dict(period='2026Q2',page=6,geography='City',metric='vacancy',value='9.4',unit='percent',basis='stock_rate',definition='Overall vacancy; submarket narrative',
      phrase='overall vacancy has continued to improve, falling to 9.4% during Q2 2026, 43 basis points below Q1',
      rationale='City overall rate, not City Core or Grade A. Card agrees at 9.4%. The source-reported 43 bps differs from arithmetic on rounded 9.8/9.4 (40 bps); retain both meanings separately.'),
 dict(period='2026Q1',page=6,geography='City',metric='takeup',value='1.0',unit='million sq ft',basis='quarter',definition='Quarterly office take-up; BNP named submarket narrative',
      phrase='City office take-up totalled 1.0 million sq ft during Q1 2026',
      rationale='Named City quarterly flow in narrative; not H1, YTD, under offer or an individual deal. Card has a typographic period label; rely on explicit narrative and page banner.'),
 dict(period='2026Q2',page=6,geography='City',metric='takeup',value='1.1',unit='million sq ft',basis='quarter',definition='Quarterly office take-up; BNP named submarket narrative',
      phrase='take-up reaching approximately 1.1 million sq ft, representing a 15.2% increase on the previous quarter.',
      rationale='City page explicitly describes Q2 flow. Approximate 1.1m and Q1 1.0m do not reproduce the source 15.2%; system arithmetic is on disclosed rounded values only.'),
 dict(period='2026Q1',page=5,geography='West End',metric='takeup',value='810000',unit='sqft',basis='quarter',definition='Quarterly office take-up; BNP named submarket narrative',
      phrase='West End office take-up reached approximately 810,000 sq ft during Q1 2026',
      rationale='Use the more precise named narrative 810,000, not the separately rounded 0.8m headline. Same provider, geography, definition and quarterly basis as Q2; no exact transaction total is asserted.'),
 dict(period='2026Q2',page=5,geography='West End',metric='takeup',value='1.0',unit='million sq ft',basis='quarter',definition='Quarterly office take-up; BNP named submarket narrative',
      phrase='take-up reaching approximately 1.0 million sq ft, representing a 25.9% increase on the previous quarter.',
      rationale='Named West End Q2 paragraph and card support approximate 1.0m. Disclosed-value arithmetic gives 23.46%, distinct from publisher 25.9%; neither is relabelled as the other. The unmodified 10% signal threshold is exceeded even with ordinary rounding uncertainty.'),
 dict(period='2026Q1',page=6,geography='City',metric='availability',value='9.3',unit='million sq ft',basis='available_area',definition='Available office area; BNP named submarket stock; not pipeline',
      phrase='Available supply in the City reduced to 9.3 million sq ft during Q1 2026',
      rationale='Available stock at Q1, not vacancy percentage, construction or development completions.'),
 dict(period='2026Q2',page=6,geography='City',metric='availability',value='8.9',unit='million sq ft',basis='available_area',definition='Available office area; BNP named submarket stock; not pipeline',
      phrase='available office space reducing to 8.9 million sq ft, representing a 4.4% decline compared with the previous quarter.',
      rationale='Q2 available stock, distinct from the report separate construction/project discussion. Rounded level need not reproduce source 4.4% change.'),
 dict(period='2026Q1',page=5,geography='West End',metric='availability',value='6.2',unit='million sq ft',basis='available_area',definition='Available office area; BNP named submarket stock; not pipeline',
      phrase='Supply across the West End continued to tighten during Q1 2026, declining 3.6% q-o-q to 6.2 million sq ft.',
      rationale='Available stock explained in the next sentence; not the future construction pipeline.'),
 dict(period='2026Q2',page=5,geography='West End',metric='availability',value='6.2',unit='million sq ft',basis='available_area',definition='Available office area; BNP named submarket stock; not pipeline',
      phrase='Office supply across the West End remained broadly stable during Q2, increasing marginally by 0.4% quarter-on-quarter to 6.2 million sq ft.',
      rationale='Available stock retained at original rounded 6.2m. Rounded levels imply flat arithmetic, not rejection of the separately source-reported 0.4%.'),
]
packet=[]
for item in items:
 doc=docs[item['period']];assert hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest()==doc['sha256']
 segment=next(s for s in doc['segments'] if s.get('page')==item['page'])
 quote=_quote(segment['text'],item['phrase']) or _quote(segment['text'],item['phrase'].replace('take-up','take- up'))
 assert quote,(item['geography'],item['period'],item['metric'],item['phrase'])
 fact=_save(store,doc,store.get('sources','bnp'),segment,item['metric'],item['value'],item['unit'],item['period'],item['geography'],item['definition'],quote,basis=item['basis'])
 packet.append(dict(fact_id=fact['id'],**item,quote=quote,document_id=doc['id'],sha256=doc['sha256'],url=doc['url']))
(OUT/'INDIVIDUAL_REVIEW_PACKET.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2),encoding='utf-8')
receipts=[]
for item in packet:
 fact=store.get('facts',item['fact_id']);assert fact.get('normalized_value') is not None
 groups,omitted=safe_evidence(store,[dict(facts=[fact])]);assert any(r['id']==fact['id'] for rows in groups.values() for r in rows),omitted
 note=('User explicitly requested individual evidence verification on 2026-10-19. Codex inspected original PDF page '+str(item['page'])
       +', source-defined geography/period, exact quote, original hash, original units and metadata. '+item['rationale']
       +' This is delegated source-evidence review in a new isolated acceptance copy, not user-performed PDF inspection or semantic/investment approval. Other pending records retain their states.')
 if fact.get('human_review_status')=='approved':raise RuntimeError('Refuse duplicate review execution')
 receipt=svc.review_fact(item['fact_id'],'approve','Codex - user-delegated individual source-evidence review',note)
 receipts.append(dict(fact_id=item['fact_id'],decision='approve',rationale=item['rationale'],at=now()))
query='Prepare a Q2 2026 London office market report comparing City, West End and Canary Wharf, covering rents, vacancy, availability, leasing take-up and development pipeline, with Q1 historical trends, conditional risks and opportunities and source limitations.'
report=build_report(svc,query)
(OUT/'REGIONAL_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'REGIONAL_REPORT.html').write_text(render_html(report),encoding='utf-8')
(OUT/'REGIONAL_REPORT.md').write_text(render_markdown(report),encoding='utf-8')
(OUT/'INDIVIDUAL_REVIEW_RECEIPT.json').write_text(json.dumps(dict(reviews=receipts,count=len(receipts),baseline_preserved=True,model_calls=0),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(new_reviews=len(receipts),report_id=report['report_id'],status=report['generation_status'],charts=[dict(type=c['type'],metric=c['metric'],areas=c['geographies']) for c in report['charts'] if c['status']=='ready'],calculations=[dict(old=c['old_id'],new=c['new_id'],change=c['display']) for c in report['calculations']]),ensure_ascii=False))
svc.pool.shutdown(wait=True);store.engine.dispose()
