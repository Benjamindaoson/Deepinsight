"""Bounded existing acquisition; no model, review or notification side effects."""
import asyncio,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
from london_product.store import Store,now
from london_product.sources import fetch_source,parse_content,document_metadata
OUT=ROOT/'docs/delivery/regional-real-20261019';store=Store(OUT/'runtime')
targets=[
 ('bnp','https://www.realestate.bnpparibas.co.uk/insights/central-london-office-market-update-q2-2026'),
 ('bnp','https://www.realestate.bnpparibas.co.uk/sites/default/files/2026-08/Q22026CentralLondonMarketUpdate.pdf'),
 ('bnp','https://www.realestate.bnpparibas.co.uk/sites/default/files/2026-05/Q12026CentralLondonMarketUpdate.pdf'),
 ('savills-html','https://www.savills.com/research_articles/255800/393427-0'),
]
async def one(sid,url):
 source=store.get('sources',sid);source=dict(source,url=url)
 try:
  fetched=await fetch_source(source);content=fetched['content'];meta=document_metadata(content,fetched['media'])
  doc=store.snapshot(source,fetched['url'],content,fetched['media'],parse_content(content,fetched['media']),**meta)
  return dict(source_id=sid,url=url,status='saved',http_status=fetched['status_code'],document_id=doc['id'],sha256=doc['sha256'],metadata=meta,bytes=len(content),at=now())
 except Exception as exc:
  return dict(source_id=sid,url=url,status='failed',error_type=type(exc).__name__,at=now())
async def main():
 result=await asyncio.gather(*(one(*item) for item in targets))
 (OUT/'FRESH_ACQUISITION.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(result,indent=2));store.engine.dispose()
asyncio.run(main())
