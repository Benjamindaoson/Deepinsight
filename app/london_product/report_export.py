"""Self-contained, escaped institutional report export; never changes eligibility."""
import html
from urllib.parse import urlsplit

LABELS={'rent':'Office rent','vacancy':'Vacancy','availability':'Available area','takeup':'Leasing take-up','supply':'Supply / pipeline'}
def esc(value):
    from .safe_answer import english_text
    return html.escape(english_text(value),quote=True)
def period(value):
    return value[4:]+' '+value[:4] if value and len(value)==6 and value[4]=='Q' else value or 'Period unconfirmed'

def chart_svg(chart):
    """Use only released structured points; retain the source table below."""
    from decimal import Decimal,InvalidOperation
    if chart['status']!='ready' or chart['type']=='event_timeline':return ''
    points=chart['points']
    try:values=[Decimal(p['value']) for p in points]
    except (InvalidOperation,KeyError,TypeError):return ''
    if not values or any(not v.is_finite() or v<0 for v in values):return ''
    top=float(max(values))*1.15 or 1
    xy=[(70+i*500/max(1,len(points)-1),190-float(v)/top*140) for i,v in enumerate(values)]
    svg='<svg role="img" aria-label="'+esc(chart['title'])+'" viewBox="0 0 640 240" style="width:100%;max-height:320px"><title>'+esc(chart['title'])+'</title>'
    for tick in range(5):
        y=190-tick*35
        svg+=f'<path d="M60 {y} H600" stroke="#d9e1e7"/><text x="50" y="{y+4}" text-anchor="end" font-size="11" fill="#586979">{top*tick/4:.2f}</text>'
    if chart['type']=='time_series':
        svg+='<polyline fill="none" stroke="#345b7e" stroke-width="3" points="'+' '.join(f'{x:.2f},{y:.2f}' for x,y in xy)+'"/>'
    for p,v,(x,y) in zip(points,values,xy):
        label=esc(p['label']);value=esc(str(v))
        if chart['type']=='time_series':svg+=f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="#345b7e"><title>{label}: {value}</title></circle>'
        else:svg+=f'<rect x="{x-16:.2f}" y="{y:.2f}" width="32" height="{190-y:.2f}" fill="#345b7e"><title>{label}: {value}</title></rect>'
        svg+=f'<text x="{x:.2f}" y="{y-12:.2f}" text-anchor="middle" font-size="13" fill="#172d43">{value}</text><text x="{x:.2f}" y="216" text-anchor="middle" font-size="11" fill="#586979">{label}</text>'
    return svg+'</svg>'
def render(report):
    from .report_contracts import ReportArtifact
    report=ReportArtifact.model_validate(report).model_dump(mode='json')
    status={'success':'Evidence coverage complete','partial':'Partial research coverage','insufficient_evidence':'Evidence insufficient for confirmed conclusions','failed':'Generation failed'}[report['generation_status']]
    index={e['id']:i+1 for i,e in enumerate(report['evidence'])}
    def refs(ids):return ' '.join(f'<a href="#source-{index[x]}">[{index[x]}]</a>' for x in ids if x in index)
    def findings(items):
        def tag(f):
            label=f['classification']+(' · AI interpretation' if f.get('origin')=='model_interpretation' else ' · deterministic')
            verdict=(f.get('verification') or {}).get('status')
            return esc(label+(' · '+verdict if verdict else ''))
        return ''.join('<p><small>['+tag(f)+']</small> '+esc(f['text'])+' '+refs(f['evidence_ids'])+'</p>' for f in items)
    metrics=report['scope']['metrics']
    matrix='<table><caption>Source-reported observations</caption><thead><tr><th>Submarket</th>'+''.join('<th>'+esc(LABELS.get(m,m))+'</th>' for m in metrics)+'</tr></thead><tbody>'
    for geo in report['geographies']:
        matrix+='<tr><th scope="row">'+esc(geo)+'</th>'
        for metric in metrics:
            rows=[f for f in report['market_snapshot'] if f['metric']==metric and (f['geography']==geo or f['geography'].startswith(geo+' ('))]
            matrix+='<td>'
            if not rows:matrix+='<span class="muted">No eligible disclosure in this scope</span>'
            for row in rows:
                matrix+='<p><strong>'+esc(row['value'])+'</strong> '+esc(row['unit'])+' '+refs(row['evidence_ids'])+'<small>'+('Reviewed' if row['review_status']=='approved' else 'Pending review')+' · '+esc(row['definition'])+'</small><small>Observed period: '+esc(row['period'])+'</small></p>'
            matrix+='</td>'
        matrix+='</tr>'
    matrix+='</tbody></table>'
    from .chat_report import scope_summary
    body='<header><div class="brand">DeepInsight Lite <span>Market intelligence</span></div><p class="edition">'+esc(period(report['observation_period']))+' / London offices</p><h1>'+esc(report['title'])+'</h1><p>'+esc(' / '.join(report['geographies']))+'</p><p class="muted">Prepared '+esc(report['generated_at'])+'</p><p class="muted">Research scope: '+esc(scope_summary(report))+'</p></header>'
    body+='<aside><strong>'+esc(status)+'</strong><p>Source-reported figures retain their original definitions and review status. Pending observations do not support confirmed comparisons or investment conclusions.</p>'
    ai=report.get('ai_analysis') or {}
    if ai.get('status'):body+='<p>Model interpretation: '+esc(ai.get('status'))+' — '+esc(ai.get('answer'))+'</p>'
    body+='</aside>'
    body+='<section><h2>Executive brief</h2>'+findings(report['executive_summary'])+'</section><section>'+matrix+'<p class="muted">Values are original disclosures. Different publisher definitions are retained separately; missing annual rent denominators are not inferred. Available stock is not a development pipeline.</p></section>'
    related=report.get('related_observations',[])
    if related:
        body+='<section><h2>Related geography context</h2><p>Combined submarkets are shown separately and do not fill standalone regional gaps.</p>'
        for f in related:body+='<p>'+esc(f['geography'])+' — '+esc(LABELS.get(f['metric'],f['metric']))+': <strong>'+esc(f['value'])+'</strong> '+esc(f['unit'])+' '+refs(f['evidence_ids'])+' <small>'+esc(f['review_status'])+' · '+esc(f['definition'])+' · '+esc(f['period'])+'</small><small>'+esc(f.get('scope_note',''))+'</small></p>'
        body+='</section>'
    comparison_rows=report.get('regional_comparison',[])
    if comparison_rows:
        body+='<section><h2>Regional comparison</h2><table><thead><tr><th>Submarket</th><th>Metric</th><th>Period</th><th>Status</th><th>Evidence</th></tr></thead><tbody>'
        for row in comparison_rows:
            body+='<tr><td>'+esc(row['geography'])+'</td><td>'+esc(LABELS.get(row['metric'],row['metric']))+'</td><td>'+esc(period(row['period']))+'</td><td>'+esc(row['status'])+'</td><td>'+refs(row['fact_ids'])+'</td></tr>'
        body+='</tbody></table><p class="muted">Only eligible, reviewed and definition-matching observations are compared; unavailable cells are explained in the coverage detail.</p></section>'
    if report.get('calculations'):
        body+='<section><h2>Deterministic calculations</h2><ul>'
        for c in report['calculations']:
            display=c.get('display') or {}
            evidence_by_id={e['id']:e for e in report['evidence']}
            old=evidence_by_id.get(c.get('old_id'),{});new=evidence_by_id.get(c.get('new_id'),{})
            body+='<li>'+esc(f"{c.get('metric') or new.get('metric','')} · {c.get('geography') or new.get('geography','')}: {c.get('old_period') or old.get('period')} → {c.get('new_period') or new.get('period')} = {display.get('absolute_change') or c.get('absolute_change')} {c.get('change_unit') or ''} [{c.get('status')}]; arithmetic on disclosed values, no causal claim.")+' '+refs([c.get('old_id'),c.get('new_id')])+'</li>'
        body+='</ul></section>'
    body+='<section><h2>Market exhibits</h2>'
    for c in report['charts']:
        metadata='<p class="muted">Metric: '+esc(c.get('metric') or 'n/a')+' / Unit: '+esc(c.get('unit') or 'n/a')+' / Period: '+esc(c.get('observation_period') or 'unknown')+' / Areas: '+esc(', '.join(c['geographies']))+' / Status: '+esc(c['status'])+'</p>'
        if c['status']!='ready':
            body+='<figure><figcaption>'+esc(c['title'])+' <small>not released</small></figcaption>'+metadata+'<p class="muted">'+esc(c.get('reason') or 'Insufficient compatible evidence.')+'</p></figure>'
            continue
        body+='<figure><figcaption>'+esc(c['title'])+'</figcaption>'+metadata+chart_svg(c)+'<table><thead><tr><th>Observation</th><th>Value</th><th>Sources</th></tr></thead><tbody>'
        for p in c['points']:body+='<tr><td>'+esc(p['label'])+'</td><td>'+esc(p.get('value') or p.get('date'))+'</td><td>'+refs(p['evidence_ids'])+'</td></tr>'
        body+='</tbody></table></figure>'
    if not report['charts']:body+='<p>No market chart is released. Compatible reviewed observations are insufficient; no trend line, regional ranking or supply aggregation is inferred.</p>'
    body+='</section>'
    if report.get('conflicts'):
        body+='<section><h2>Conflicting observations — never averaged</h2><p>Statistical periods, definitions, units, geographies or methods differ. Records are listed side by side and excluded from charts, rankings and trends.</p><ul>'
        for conflict in report['conflicts']:
            body+='<li>'+esc(conflict['metric']+' ('+conflict['component']+')')+'<ul>'
            for o in conflict['observations']:
                body+='<li>'+esc(f"{o['geography']} {o['period']} = {o['value']} {o['unit']} — {o['definition']}")+' '+refs([o['fact_id']])+'</li>'
            body+='</ul></li>'
        body+='</ul></section>'
    for title,key in [('Key findings','key_findings'),('Risks','risks'),('Opportunities','opportunities'),('Outlook','outlook')]:
        if report[key]:body+='<section><h2>'+title+'</h2>'+findings(report[key])+'</section>'
    body+='<section><h2>Research limitations</h2><ul>'+''.join('<li>'+esc(s)+'</li>' for s in report['limitations'] if not s.startswith('Excluded evidence:'))+'</ul><details><summary>Detailed coverage and audit checks</summary><ul>'+''.join('<li>'+esc(g['geography']+' / '+g['metric']+': '+g['reason'])+'</li>' for g in report['data_gaps'])+'</ul><p>'+esc((report.get('acquisition') or {}).get('notice') or 'Acquisition notice not recorded.')+'</p></details></section>'
    health=(report.get('acquisition') or {}).get('source_health') or []
    if health:
        body+='<section><h2>Source freshness</h2><p class="muted">A recent collection success is not the market statistical period; a failed check is not a successful one.</p><ul>'
        for s in health:
            body+='<li>'+esc(s['name'])+': health '+esc(s['health'])+' · last success '+esc(s.get('last_success') or 'unknown')+' · last attempt '+esc(s.get('last_attempt') or 'unknown')+'</li>'
        body+='</ul></section>'
    body+='<section><h2>Sources & evidence</h2>'
    for i,e in enumerate(report['evidence'],1):
        url=e.get('url') or '';parts=urlsplit(url)
        link='<a href="'+esc(url)+'" rel="noreferrer">Original source</a>' if parts.scheme in ['https','http'] and parts.hostname and not parts.username else 'Original URL unavailable'
        body+='<details id="source-'+str(i)+'"><summary>['+str(i)+'] '+esc(e.get('report_title'))+' · '+esc(period(e['period']))+' · '+esc(e['review_status'].replace('_',' '))+'</summary><blockquote>'+esc(e['quote'])+'</blockquote><p>'+link+'</p><small>Observed period: '+esc(e.get('period') or 'unknown')+' / Publication: '+esc(e.get('published_at') or 'unknown')+' / Collected: '+esc(e.get('collected_at') or 'unknown')+' / Source last checked: '+esc(e.get('source_last_checked_at') or 'unknown')+' / Evidence integrity checked at: '+esc(e.get('evidence_integrity_checked_at') or 'unknown')+' ('+esc(e.get('evidence_integrity_status') or 'unknown')+')'+'</small><small>Page: '+esc(e.get('page'))+' / Locator: '+esc(e.get('locator'))+'</small><small>SHA-256: '+esc(e['document_sha256'])+'</small><small>Review actor: '+esc(e.get('reviewed_by') or 'Not recorded')+' / Basis: '+esc(e.get('review_note') or 'Not recorded')+'</small></details>'
    body+='</section><footer>DeepInsight Lite · Research evidence record / '+esc(report['report_id'])+'</footer>'
    css='''*{box-sizing:border-box}body{margin:0;background:#edf2f5;color:#172d43;font:15px/1.65 Arial,sans-serif}article{max-width:1140px;margin:36px auto;background:white;padding:64px 70px}header{border-top:5px solid #172d43;padding-top:24px;margin-bottom:32px}.brand{font-weight:bold;font-size:20px}.brand span{float:right;font-size:13px;font-weight:normal}.edition{margin-top:45px;color:#345b7e}h1{font:46px/1.12 Georgia,serif;max-width:680px;margin:16px 0}h2{font:27px/1.25 Georgia,serif;margin:0 0 20px}section{margin:36px 0}aside{background:#f7f4ed;border-left:3px solid #946c22;padding:18px 24px}aside p{margin:5px 0}.muted,small{color:#586979;font-size:12px}small{display:block;margin:5px 0}table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:12px}caption{text-align:left;font:27px Georgia,serif;margin-bottom:20px}th{text-align:left;background:#edf2f5}td,th{vertical-align:top;padding:14px 10px;border-bottom:1px solid #d9e1e7}td strong{font-size:18px;font-variant-numeric:tabular-nums}a{color:#345b7e}details{border-top:1px solid #d9e1e7;padding:14px 0;overflow-wrap:anywhere}summary{cursor:pointer;font-weight:bold}blockquote{white-space:pre-wrap;border-left:2px solid #345b7e;margin:18px 0;padding-left:18px}footer{border-top:1px solid #172d43;margin-top:50px;padding-top:18px;font-size:11px}@media(max-width:700px){article{margin:0;padding:28px 18px}h1{font-size:34px}table{table-layout:auto;display:block;overflow:auto}.brand span{float:none;display:block}}@media print{body{background:white}article{margin:0;padding:0;max-width:none}details{break-inside:avoid}section{break-inside:auto}a{color:inherit}aside{background:none}table{font-size:10px}h1{font-size:36px}}'''
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(report['title'])+'</title><style>'+css+'</style></head><body><article>'+body+'</article></body></html>'
