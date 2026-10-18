"""Preserve review annotations; no model calls and no source-fact changes."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from london_product.store import Store,now

root=Path(__file__).resolve().parents[1]/'data/product'
s=Store(root); out=root/'evidence'; p=out/'ai-semantic-review-v2.json'
review=json.loads(p.read_text(encoding='utf-8'))
issue='Supply wording implies a contraction across BNP Q1 and JLL Q2 despite unconfirmed cross-publisher comparability; this is not an approved market change.'
if issue not in review['remaining_issues']:review['remaining_issues'].append(issue)
review['reviewed_at']=now()
s.update('jobs',review['analysis_id'],dict(quality_status='REVIEW_REQUIRED',known_quality_issues=review['remaining_issues']))
p.write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8')
revisions=[]
for report in s.all('reports'):
    if report.get('analysis_id')==review['analysis_id']:
        s.update('reports',report['id'],dict(known_quality_issues=review['remaining_issues']))
    obsolete_facts=[i for i in report.get('fact_ids',[]) if (s.get('facts',i) or {}).get('status')=='superseded']
    obsolete_events=[i for i in report.get('event_ids',[]) if (s.get('events',i) or {}).get('status')=='superseded']
    if report.get('status')!='superseded' and (obsolete_facts or obsolete_events):
        s.update('reports',report['id'],dict(status='superseded',revision_reason='Saved historical snapshot includes subsequently superseded records; original report bytes retained'))
        revisions.append(dict(report_id=report['id'],obsolete_facts=obsolete_facts,obsolete_events=obsolete_events))
(out/'final-report-review.json').write_text(json.dumps(dict(recorded_at=now(),revisions=revisions,raw_report_bytes_unchanged=True,raw_model_output_unchanged=True,further_model_requests=0),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(report_annotations=len(revisions),analysis_status='REVIEW_REQUIRED',model_requests=0)))
