"""Public source qualification only; never switches the production registry."""
import argparse,json,hashlib,re,sys
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from london_data.documents import fetch,parse_document
from london_data.extraction import ROOT

sources={
 'savills-q1-2026.html':'https://www.savills.com/research_articles/255800/390337-0',
 'savills-q2-2026.html':'https://www.savills.com/research_articles/255800/393427-0',
 'savills-q1-2026.pdf':'https://pdf.euro.savills.co.uk/uk/office-reports/central-london-q1-2026-report.pdf',
 'savills-q2-2026.pdf':'https://pdf.euro.savills.co.uk/uk/office-reports/central-london-q2-2026-report.pdf',
 'carter-q2-2026.html':'https://www.carterjonas.co.uk/insights/the-london-office-market-q2-2026',
 'carter-q2-2026.pdf':'https://assets.ctfassets.net/2u48p9m6vmwh/5Ymend84Hb1yj14ZyVft3d/22899ab95a46713f0f1641a6ae90478a/Guide_To_London_Office_Rents__Rent_Free_Periods___Market_Trends_-_Q2_2026.pdf',
 'cbre-q2-2026.html':'https://www.cbre.com/insights/figures/central-london-office-figures-q2-2026',
 'cbre-download-gate.html':'https://cloud.cbrecommunications.com/hq-figure-page-form-submission',
}
p=argparse.ArgumentParser();p.add_argument('--fetch-public',action='store_true');args=p.parse_args()
directory=ROOT/'b1/data/raw';receipt={'checked_at':datetime.now(timezone.utc).isoformat(),'registry_changed':False,'form_submissions':0,'purchases':0,'documents':[]}
for name,url in sources.items():
    file=directory/name;row={'file':str(file),'url':url,'purpose':'candidate qualification only'}
    try:
        if args.fetch_public:
            content,media,final=fetch(url,{urlparse(url).hostname},[urlparse(url).path]);file.write_bytes(content)
            row.update(collected_at=datetime.now(timezone.utc).isoformat(),final_url=final,media=media)
        else:content=file.read_bytes();media='application/pdf' if name.endswith('.pdf') else 'text/html'
        row.update(sha256=hashlib.sha256(content).hexdigest(),bytes=len(content),status='fetched')
        segments=parse_document(content,media)
        row['metric_segments']=[s for s in segments if re.search(r'prime rent|vacan|take.up|per annum|per year|psf|sq ft',s['text'],re.I)]
    except Exception as e:row.update(status='failed',error_type=type(e).__name__)
    receipt['documents'].append(row)
    print(name,row['status'],flush=True)
for name in ['bnp-q1-2026.pdf','bnp-q2-2026.pdf','bnp-europe-q1-2026.pdf','carter-q1-2026.pdf']:
    file=directory/name;content=file.read_bytes();segs=parse_document(content,'application/pdf')
    receipt['documents'].append({'file':str(file),'sha256':hashlib.sha256(content).hexdigest(),'pages_checked':len(segs),'all_page_text':segs,'annual_phrase_matches':[s['segment_id'] for s in segs if re.search(r'per annum|per year|/year|p\.a\.',s['text'],re.I)]})
(ROOT/'b1/evidence/g0/source-qualification-details.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
