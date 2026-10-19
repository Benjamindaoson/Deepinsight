"""Evidence-first reports. No model arithmetic, synthetic chart data or new storage."""
import copy
import hashlib
import html
import json
import re
from collections import defaultdict
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .normalization import current_fact, derive
from .qa_context import verified
from .safe_answer import safe_evidence, join_blocks
from .store import now, uid
from .report_contracts import ReportArtifact, Scope
from .finding_verification import verify_finding
from london_data.comparison import compare as strict_compare
from london_data.comparison import SQM_TO_SQFT

# The HTTP orchestrator owns this artifact and its final analysis attachment.
# Native AgentOS runs without this context keep their normal creation path.
ACTIVE_REPORT = ContextVar('active_market_report', default=None)


def scope_summary(report):
    scope=report.get('scope') or {}
    return (', '.join(scope.get('geographies') or report.get('geographies') or ['London offices'])
        +' — '+', '.join(scope.get('metrics') or [])+' — '
        +str(scope.get('observation_period') or report.get('observation_period') or 'latest saved evidence'))


def respond_to_action(service, question, parent_report_id=None, session_id=None, requested_mode='auto'):
    """Focused read operations over authoritative storage; never create a report or approve a fact."""
    from .routing import request_action
    store=service.store
    if not parent_report_id and session_id:
        pointer=store.get('settings','conversation:'+session_id) or {}
        parent_report_id=pointer.get('report_id')
        if not parent_report_id:
            parent_report_id=next((r['id'] for r in store.all('reports') if
                (r.get('artifact',{}).get('ai_analysis') or {}).get('session_id')==session_id),None)
    action=request_action(question,bool(parent_report_id))
    if action=='data_question' and requested_mode=='agent':return dict(handled=False,operation=action,report_id=parent_report_id)
    if action in ['new_report','model_analysis']:return dict(handled=False,operation=action,report_id=parent_report_id)
    result=dict(handled=True,operation=action,report_id=parent_report_id,sources=[],model_requests=0,report_created=False)
    explanations={
        'clarification':'Which rent measure should I use: Prime or Grade A, asking/face rent or achieved/effective rent? Please also specify the submarket and reporting period (or latest saved evidence). These measures are not interchangeable.',
        'future_uncertainty':'A guaranteed future office rent cannot be established from historical market evidence. I can show dated source disclosures or clearly labelled published forecasts, but neither guarantees a 2027 rent.',
        'out_of_domain':'This workspace covers London office market evidence, analysis and monitoring. That request is outside its supported scope.',
        'private_contact':'No private tenant contact details can be inferred from the saved market evidence. I will not invent email addresses. Use an authorized published contact directory if available.'}
    if action in explanations:
        result.update(answer=explanations[action],status='CLARIFICATION_REQUIRED' if action=='clarification' else 'INSUFFICIENT_EVIDENCE',outcome='CLARIFICATION_REQUIRED' if action=='clarification' else 'INSUFFICIENT_EVIDENCE')
        return result
    if action=='monitor_rule':
        scope=resolve_scope(question);match=re.search(r'(\d+(?:\.\d+)?)\s*%',question)
        threshold=float(match[1]) if match else None
        rule=dict(geographies=scope['geographies'],metric='rent',grade='Prime',period='monthly',
            threshold_pct=threshold,operator='strictly_greater_than',calculation='100 * (new - old) / old',
            status='waiting_for_comparable_monthly_evidence',active=False,
            notification_configured=service.settings()['notification_configured'])
        saved=store.put('settings','monitor-rule:'+hashlib.sha256(json.dumps(rule,sort_keys=True).encode()).hexdigest(),dict(rule=rule))
        result.update(status='INSUFFICIENT_EVIDENCE',rule_id=saved['id'],rule=rule,
            answer=f"Monitoring rule saved: {saved['id']}. Scope: {', '.join(scope['geographies'])}, Prime rent, monthly, strictly greater than {threshold}% month over month. Calculation: 100 × (new − old) / old. Status: waiting for comparable, reviewed monthly observations; inactive. Quarterly data cannot satisfy this rule. Notification destination: {'configured; external receipt not verified' if rule['notification_configured'] else 'not configured'}. No alert or delivery has been claimed.")
        return result
    if action=='schedule_request':
        config=service.settings()
        if service.schedule_manager is None:
            result['answer']='Schedule not created: the scheduler is not running in this runtime. Open Monitoring settings in a scheduler-enabled runtime; no execution has been simulated.'
            result['status']='blocked'
        else:
            if re.search(r'Monday|Europe/London|09:00',question,re.I):
                scheduled=service.schedule_manager.create(name='london-user-monday-briefing',cron='0 9 * * 1',
                    timezone='Europe/London',endpoint='/api/market/scheduled/report-weekly',payload={},max_retries=0,if_exists='update')
                result['schedule_id']=scheduled.id
                result['schedule']=scheduled.to_dict()
                result['answer']=f"Briefing schedule saved: {scheduled.id}. Every Monday at 09:00 Europe/London, using the scheduler's IANA timezone rules for daylight saving. This confirms configuration, not execution or notification delivery."
            else:
                config=service.save_settings(dict(market_interval_hours=24,monitoring_enabled=True))
                result['answer']='Daily market monitoring saved using the existing scheduler (07:00 UTC). This confirms configuration, not a completed run or delivery.\n'+json.dumps(config['schedules'],default=str)
            result['status']='configured'
        return result
    if action=='monitoring_status':
        jobs=[j for j in store.all('jobs') if j.get('kind') in ['refresh','monitor','monitoring','workflow']]
        completed=[j for j in jobs if j.get('status')=='succeeded']
        lines=['## Monitoring records']
        if completed:
            j=completed[0];lines += [f"Latest completed run: {j['id']} | {j.get('kind')} | finished {j.get('finished_at') or 'not recorded'} | status {j['status']}"]
        else:lines+=['No completed monitoring run is recorded in this database.']
        for j in jobs[:5]:lines += [f"- Job {j['id']}: {j.get('status')} | started {j.get('started_at')} | finished {j.get('finished_at')} | error {j.get('error_code') or j.get('error') or 'none recorded'}"]
        events=[e for e in store.all('events') if e.get('kind')=='metric_change']
        events=[e for e in events if e.get('signal_status')=='active' and e.get('status')!='superseded']
        config=service.settings()
        lines += ['Configured schedules: '+json.dumps(config['schedules'],default=str),
            'Saved metric rules: '+json.dumps(config.get('monitoring_rules',[]),default=str),
            'Notification destination: '+('configured; recipient delivery not confirmed' if config['notification_configured'] else 'not configured'),
            f"Active confirmed metric-change events: {len(events)}. These are saved records; a new monitoring run was not triggered."]
        for e in events[:5]:lines += [f"- Event {e['id']} | {e.get('geography')} | {e.get('metric')} | report {e.get('report_id') or 'none'}"]
        result.update(answer='\n\n'.join(lines),status='records_returned',jobs=[j['id'] for j in jobs[:5]])
        return result
    if action in ['evidence_audit','follow_up'] and not parent_report_id:
        result.update(answer='No previous report is linked to this conversation. Open the report and choose Ask a follow-up, or provide its report ID. No replacement report was created.',status='context_required')
        return result
    report=read_report(store,parent_report_id) if parent_report_id else None
    scope=resolve_scope(question,report)
    candidates=[f for f in store.all('facts') if f.get('metric') in scope['metrics'] and
        any(in_area(f,g) for g in scope['geographies']) and
        (not scope['observation_period'] or f.get('period')==scope['observation_period'])]
    if action=='evidence_audit':
        evidence=report['evidence'];lines=['## Evidence audit',f"Existing report: {report['report_id']}", 'Scope: '+scope_summary(report),
            '','| Evidence | Observation | Original / quote | Value in quote | Review | Source |','|---|---|---|---|---|---|']
        failures=[]
        for e in evidence:
            row=store.get('facts',e.get('fact_id') or e['id'])
            groups,omitted=safe_evidence(store,[dict(facts=[row] if row else [])])
            integrity=any(groups.values())
            quote=str(e.get('quote') or '')
            numeric=False
            if row and row.get('value') is not None:
                try:numeric=any(Decimal(v.replace(',',''))==Decimal(str(row['value'])) for v in re.findall(r'(?<![\w.])-?\d[\d,]*(?:\.\d+)?(?![\w.])',quote))
                except InvalidOperation:pass
            approved=bool(row and verified(current_fact(row)))
            outcome='matched' if integrity else 'failed'
            if not integrity or not numeric or not approved:failures.append(e['id'])
            lines += [f"| {e['id']} | {e.get('geography')} / {e.get('metric')} / {e.get('period')} | {outcome} | {'literal value matched; semantic scope not approved' if numeric else 'not established'} | {'approved' if approved else 'Pending review; cannot publish as confirmed'} | {e.get('url')} |"]
        checked=[]
        for key in ['executive_summary','key_findings','risks','opportunities','outlook']:
            for f in report.get(key,[]):checked.append(dict(section=key,**verify_finding(f,report,store,origin=f.get('origin','deterministic'))))
        rejected=sum(c.get('status')!='verified' for c in checked)
        lines += ['## Claim-by-claim checks',
            '| Exact claim | Value / unit | Geography | Reporting period | Publisher / document | URL / evidence | Verification | Review | Failure reason |',
            '|---|---|---|---|---|---|---|---|---|']
        for key in ['executive_summary','key_findings','risks','opportunities','outlook']:
            for claim in report.get(key,[]):
                review=verify_finding(claim,report,store,origin=claim.get('origin','deterministic'))
                bound=[e for e in evidence if e['id'] in claim.get('evidence_ids',[])]
                proof='; '.join(str(e.get('url'))+' '+str(e.get('locator'))+' '+str(e.get('quote')) for e in bound)
                cells=[claim.get('text',''),'; '.join(str(e.get('value'))+' '+str(e.get('unit')) for e in bound),
                    '; '.join(str(e.get('geography')) for e in bound),'; '.join(str(e.get('period')) for e in bound),
                    '; '.join(str((store.get('documents',e.get('document_id','')) or {}).get('publisher') or 'Publisher not recorded')+' / '+str(e.get('report_title')) for e in bound),proof,
                    'Supported' if review.get('status')=='verified' else 'Unsupported' if not bound else 'Unverified',
                    '; '.join(str(e.get('review_status')) for e in bound) or 'No bound evidence',
                    str(review.get('codes') or review.get('reasons') or ('None identified by deterministic checks' if review.get('status')=='verified' else 'Missing, pending or incompatible evidence'))]
                lines.append('| '+' | '.join(str(c).replace('|','/').replace('\n',' ') for c in cells)+' |')
        lines += [f"Audit result: {len(evidence)} evidence records inspected; {len(failures)} have integrity, literal-value or approval limitations; {rejected}/{len(checked)} findings failed current deterministic claim checks.",
            'Quote/hash and literal-number checks establish traceability only. They do not prove every semantic definition, rent denominator or geographic boundary. Pending records remain pending; no review decisions were changed.',
            'Next action: inspect the listed original quotations and unresolved definitions, then request item-level human review. No replacement report or model call was made.']
        result.update(answer=join_blocks(lines),status='audit_failures' if failures or rejected else 'limited_checks_passed',audit=dict(evidence_count=len(evidence),limited_or_failed_ids=failures,findings=checked))
        result['sources']=report['sources']
        return result
    groups,omitted=safe_evidence(store,[dict(facts=candidates)])
    rows=[x for items in groups.values() for x in items]
    if action=='data_question' and rows:
        latest=max(str(r.get('period') or '') for r in rows);rows=[r for r in rows if str(r.get('period') or '')==latest]
    lines=['## '+('Report follow-up' if report else 'Focused market evidence')]
    if report:lines += [f"Existing report: {report['report_id']}",'Scope: '+scope_summary(report)]
    if re.search(r'pending review|why.*review',question,re.I):
        lines += ['Pending review means the authoritative record has not passed item-level human approval. A matching quotation and original-file hash do not approve its statistical definition, geographic scope or unit. No approval has been added.']
    if re.search(r'missing|gap|缺',question,re.I) and report:
        lines += [f"- {g['geography']} / {g['metric']}: {g['reason']}" for g in report['data_gaps']]
        lines += report['limitations']
    elif rows:
        table=['| Area | Metric | Period | Original value | Review | Evidence |','|---|---|---|---|---|---|']
        for r in rows[:12]:
            review='Approved observation' if (r['human_review_status'] or r['status'])=='approved' else 'Pending review'
            table.append(f"| {r['geography']} | {r['metric']} | {r['period']} | {r['value']} {r['unit']} | {review} | {r['url']} |")
        lines.append('\n'.join(table))
        for r in rows[:12]:
            lines += [str(r.get('report_title'))+' | published '+str(r.get('published_at') or 'unknown')+' | '+str(r.get('locator'))+' | '+str(r['url']),'> '+r['quote']]
    else:lines+=['Insufficient evidence: no matching observation passed the current original-hash and quotation checks for this scope.']
    lines += ['Latest saved evidence is not necessarily the latest public release. Pending observations are disclosures, not confirmed findings. No new report or model response was generated.']
    result.update(answer='\n\n'.join(lines),status='evidence_returned' if rows else 'insufficient_evidence')
    result['sources']=list({r['document_id']:dict(document_id=r['document_id'],url=r['url'],title=r['report_title']) for r in rows}.values())
    return result

AREAS = ['City','West End','Canary Wharf','Midtown / Fringe','Midtown','Fringe','Central London']
METRICS = {'rent':r'rent|租金', 'vacancy':r'vacan|空置', 'availability':r'availab|可租',
    'takeup':r'take.?up|leasing|成交|租赁活动', 'supply':r'pipeline|supply|development|供应|管线',
    'prelet':r'pre.?let|预租', 'interest_rate':r'interest|利率|base rate|bank rate', 'employment':r'employment|就业',
    'inflation_rate':r'inflation|通胀', 'flight_to_quality':r'flight.to.quality',
    'esg':r'\besg\b|\bepc\b|sustainab', 'hybrid_working':r'hybrid.work|混合办公'}


def resolve_scope(query, parent=None):
    parent = (parent or {}).get('scope', parent or {})
    # English area names may be adjacent to Chinese prose ("West End在...").
    geos = [g for g in AREAS if re.search(r'(?<![A-Za-z0-9_])'+re.escape(g)+r'(?![A-Za-z0-9_])',query,re.I)]
    # A source/report title may name a broader market before the user's explicit
    # restriction. Resolve the restrictive clause instead of widening its scope.
    restriction=re.search(r'(?:只|仅)(?:分析|针对|限于|限|关注)|\bonly\s+(?:analyse|analyze|consider|for)\b|\bfocus\s+only\s+on\b',query,re.I)
    restricted_geos=[]
    if restriction:
        clause=re.split(r'[。；;\n.!?]',query[restriction.end():],maxsplit=1)[0]
        area=r'(?<![A-Za-z0-9_])(?:'+'|'.join(re.escape(g) for g in sorted(AREAS,key=len,reverse=True))+r')(?![A-Za-z0-9_])'
        geography_list=re.search(area+r'(?:\s*(?:(?:,|，|、|and\b|&|和|与|及)\s*)+'+area+r')*',clause,re.I)
        clause=geography_list.group() if geography_list else ''
        restricted_geos=[g for g in AREAS if re.search(r'(?<![A-Za-z0-9_])'+re.escape(g)+r'(?![A-Za-z0-9_])',clause,re.I)]
        if restricted_geos:geos=restricted_geos
    if 'Midtown / Fringe' in geos:
        geos=[g for g in geos if g not in ['Midtown','Fringe']]
    from .routing import positive_metric_text
    metrics=[k for k,pattern in METRICS.items() if re.search(pattern,positive_metric_text(query),re.I)]
    if parent and geos and not restricted_geos and re.search(r'how does that compare|compare.*with|versus|\bboth\b',query,re.I):
        geos=list(dict.fromkeys(list(parent.get('geographies') or [])+geos))
    matches=list(re.finditer(r'(20\d{2})\s*Q([1-4])|Q([1-4])\s*(20\d{2})|(20\d{2})\s*年第?([1-4一二三四])季度',query,re.I))
    requested_periods=set()
    for match in matches:
        year=match[1] or match[4] or match[5]
        q=match[2] or match[3] or match[6]
        requested_periods.add(year+'Q'+str({'一':1,'二':2,'三':3,'四':4}.get(q,q)))
    # In "Q1 and Q2 2026" the trailing year applies to both quarters. Do not
    # guess a shared year when the question explicitly names different years.
    years=set(re.findall(r'\b20\d{2}\b',query))
    if len(years)==1:
        year=next(iter(years))
        requested_periods.update(year+'Q'+q for q in re.findall(r'\bQ([1-4])\b',query,re.I))
    months=['January','February','March','April','May','June','July','August','September','October','November','December']
    for m in re.finditer(r'(?<![A-Za-z0-9_])('+'|'.join(months)+r')\s+(20\d{2})(?![0-9])',query,re.I):
        requested_periods.add(m[2]+'-'+str(next(i+1 for i,n in enumerate(months) if n.lower()==m[1].lower())).zfill(2))
    requested_periods.update(m[1]+'-'+m[2] for m in re.finditer(r'(?<![0-9])(20\d{2})-(0[1-9]|1[0-2])(?![0-9])',query))
    requested_periods.update(m[1]+'-'+m[2].zfill(2) for m in
        re.finditer(r'(20\d{2})\s*年\s*(0?[1-9]|1[0-2])\s*月',query))
    if not requested_periods and len(years)==1 and re.search(r'\bin\s+20\d{2}\b|20\d{2}\s*年',query,re.I):requested_periods.update(years)
    period=None
    if requested_periods:
        period=max(requested_periods)
    elif not re.search(r'latest|最新',query,re.I):
        period=parent.get('observation_period')
        shorthand=re.search(r'\bQ([1-4])\b|第?([一二三四1-4])季度',query,re.I)
        if shorthand and period:
            q=shorthand[1] or shorthand[2]
            period=period[:4]+'Q'+str({'一':1,'二':2,'三':3,'四':4}.get(q,q))
            requested_periods.add(period)
        elif period:
            # A neutral follow-up keeps the original comparison's entire set,
            # rather than silently reducing it to the latest endpoint.
            requested_periods.update(parent.get('requested_periods') or [])
    complete=bool(re.search(r'market\s+report|quarterly.*report|\bbriefing\b|市场.*报告|季度.*报告|市场综述',query,re.I))
    inventory=bool(re.search(r'market\s+indicators?|市场指标',query,re.I) and
        re.search(r'summari[sz]e|\blist\b|\ball\b|\bevery\b|inventory|汇总|列出|每项|所有|全部',query,re.I))
    event_inquiry=bool(re.search(r'新闻|事件|\bnews\b|\bevents?\b',query,re.I))
    thematic=bool(re.search(r'analys|compare|why|trend|risk|opportun|分析|对比|比较|为什么|变化|风险|机会',query,re.I))
    effective_metrics=metrics or ([] if event_inquiry else list(METRICS) if inventory else
        ['rent','vacancy','availability','takeup','supply'] if complete else parent.get('metrics') or ['rent'])
    macro_only=bool(effective_metrics) and set(effective_metrics)<= {'interest_rate','employment','inflation_rate'}
    if not geos and macro_only:
        # Macro series retain the publisher's UK or workplace-London area.
        # They are context for the office market, not Central London office facts.
        effective_geos=[]
        if set(effective_metrics) & {'interest_rate','inflation_rate'}:
            effective_geos.append('United Kingdom')
        if 'employment' in effective_metrics:
            effective_geos.append('London (workplace)' if re.search(r'London|伦敦',query,re.I) else 'United Kingdom')
        effective_geos=list(dict.fromkeys(effective_geos))
    else:
        inventory_geos=([g for g in AREAS if g not in ['Midtown','Fringe']] +
            ['United Kingdom','London (workplace)']) if inventory else None
        # An event may be stored under the publisher's London-wide label.
        event_geos=([g for g in AREAS if g not in ['Midtown','Fringe']]+['London']) if event_inquiry else None
        effective_geos=geos or parent.get('geographies') or event_geos or inventory_geos or ['Central London']
        if not macro_only:
            # Mixed explanations retrieve macro context under its publisher's
            # geography while retaining the user's office-market area.
            macro_geos=[]
            if set(effective_metrics) & {'interest_rate','inflation_rate'}:
                macro_geos.append('United Kingdom')
            if 'employment' in effective_metrics:
                macro_geos.append('London (workplace)')
            effective_geos=list(dict.fromkeys(list(effective_geos)+macro_geos))
    kind='market_report' if complete else 'topic_analysis' if event_inquiry or thematic or len(requested_periods)>1 or len(effective_metrics)>1 or len(effective_geos)>1 else 'fact_answer'
    return Scope(report_type=kind,geographies=effective_geos,
        observation_period=period,metrics=effective_metrics,
        requested_periods=sorted(requested_periods),
        needs_comparison=len(effective_geos)>1,
        needs_history=len(requested_periods)>1 or bool(re.search(r'trend|histor|change|why|previous\s+quarter|prior\s+quarter|趋势|历史|变化|为什么|上一?季度',query,re.I))).model_dump()


def in_area(row, area):
    geo=row.get('geography')
    return geo==area or (area=='Midtown / Fringe' and geo in ['Midtown','Fringe'])


def candidate_in_area(row, area):
    """Retain publisher-labelled candidates without equating their geography."""
    return in_area(row,area) or str(row.get('geography') or '').startswith(area+' (')


def normalized(row):
    derived=derive(row)
    value,unit=derived['normalized_value'],derived['normalized_unit']
    if value is not None and unit=='sqm' and row.get('metric') in ['takeup','supply','prelet','availability']:
        value=str(Decimal(value)*SQM_TO_SQFT);unit='sqft'
    elif value is not None and unit=='GBP/sqm/year' and row.get('metric')=='rent':
        value=str(Decimal(value)/SQM_TO_SQFT);unit='GBP/sqft/year'
    # Merge original fact with normalized fields plus metadata needed for approval checks
    return dict(row,value=value,unit=unit,period=derived['normalized_period'],
                status='validated',
                source_id=row.get('source_id'),
                series=row.get('series'),
                definition=row.get('definition'),
                basis=derived.get('basis') or row.get('basis'),
                grade=row.get('grade'),
                method=row.get('method'))


def signature(row, *, regional=False):
    keys=['source_id','series','metric','definition','basis','grade','method','currency','unit']
    keys+=['period'] if regional else ['geography']
    return tuple(row.get(k) for k in keys)


def finding(text, ids, classification='fact'):
    return dict(text=text,classification=classification,evidence_ids=ids)


def build_report(service, query, parent_report_id=None, *, key=None, acquisition=None, analysis_context=None):
    store=service.store
    parent=store.get('reports',parent_report_id) if parent_report_id else None
    if parent_report_id and (not parent or not parent.get('artifact')):
        raise ValueError('PARENT_REPORT_NOT_FOUND')
    scope=resolve_scope(query,(parent or {}).get('artifact'))
    identity='chat-report:'+key if key else uid()
    existing=store.get('reports',identity)
    if existing:
        if existing['artifact']['query']!=query or existing['artifact'].get('parent_report_id')!=parent_report_id:
            raise ValueError('REPORT_IDEMPOTENCY_SCOPE_MISMATCH')
        return read_report(store,existing['id'])
    facts=[];related=[];malformed=[]
    for original in store.all('facts'):
        if original.get('status') in ['rejected','superseded'] or original.get('human_review_status')=='rejected':continue
        if original.get('metric') not in scope['metrics']:continue
        is_related='Canary Wharf' in scope['geographies'] and original.get('geography')=='Canary Wharf & Docklands'
        if not any(candidate_in_area(original,g) for g in scope['geographies']) and not is_related:continue
        try:
            f=current_fact(original)
            # A prime/Grade A question must not silently substitute a different rent series.
            if f.get('metric')=='rent' and re.search(r'prime|grade\s*a',query,re.I):
                descriptor=' '.join(str(f.get(k) or '') for k in ['definition','grade'])
                target=r'prime' if re.search('prime',query,re.I) else r'grade\s*a'
                if not re.search(target,descriptor,re.I):continue
            if is_related:related.append(f)
            else:facts.append(f)
        except (ValueError,TypeError,InvalidOperation):malformed.append(original['id'])
    macro_only=set(scope['metrics'])<= {'interest_rate','employment','inflation_rate'}
    periods=sorted({derive(f)['normalized_period'] for f in facts if derive(f)['normalized_period'] and
        (macro_only or re.fullmatch(r'20\d{2}Q[1-4]',str(derive(f)['normalized_period'])))})
    context_periods=sorted({derive(f)['normalized_period'] for f in related if re.fullmatch(r'20\d{2}Q[1-4]',str(derive(f)['normalized_period']))})
    period=scope['observation_period'] or (periods[-1] if periods else context_periods[-1] if context_periods else None)
    # Resolve latest saved period explicitly, never pretend it is current calendar data.
    scope=dict(scope,observation_period=period)
    facts=[f for f in facts if period and (derive(f)['normalized_period']==period or
        (scope['needs_history'] and str(derive(f)['normalized_period'] or '')<period))]
    if len(scope['requested_periods'])>1:
        facts=[f for f in facts if derive(f)['normalized_period'] in scope['requested_periods']]
    selected=[f for f in facts if period and derive(f)['normalized_period']==period]
    related=[f for f in related if period and derive(f)['normalized_period']==period]
    events=[e for e in store.all('events') if e.get('kind') not in ['source_update','publisher_reported_change']
        and e.get('status') not in ['rejected','superseded'] and e.get('human_review_status')!='rejected'
        and any(in_area(e,g) for g in scope['geographies'])]
    def event_date(e):
        # Publication/collection is not the date of the described market event.
        date=e.get('event_date') or e.get('date')
        if not date or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(date)):return None
        from datetime import date as Date
        try:Date.fromisoformat(date)
        except ValueError:return None
        quarter=date[:4]+'Q'+str((int(date[5:7])-1)//3+1)
        return date if not period or quarter==period else None
    events=[e for e in events if event_date(e)]
    if scope['report_type']=='fact_answer':events=[]
    groups,omitted=safe_evidence(store,[dict(facts=facts+related,events=events)])
    safe={e['id']:e for rows in groups.values() for e in rows}
    approved=[]
    for f in facts:
        if f['id'] not in safe or not verified(f) or not any(in_area(f,g) for g in scope['geographies']):continue
        n=normalized(f)
        try:
            if n['value'] is None or not Decimal(n['value']).is_finite():continue
        except (ValueError,InvalidOperation):continue
        # For non-rent metrics (interest_rate, employment, etc.), series/basis may be absent
        is_macro_metric = f.get('metric') in ('interest_rate', 'employment', 'inflation_rate')
        required_fields = ['source_id', 'definition', 'unit'] if is_macro_metric else ['source_id', 'series', 'definition', 'unit', 'basis', 'grade', 'method']
        if any(n.get(k) in [None,'','unknown'] for k in required_fields):continue
        approved.append(n)
    approved_ids={f['id'] for f in approved}
    snapshots=[]
    related_snapshots=[]
    for f in selected:
        if f['id'] not in safe:continue
        n=normalized(f)
        snapshots.append(dict(fact_id=f['id'],metric=f['metric'],geography=f['geography'],period=f['period'],
            value=str(f.get('value')),unit=f.get('unit'),normalized_value=n['value'],normalized_unit=n['unit'],
            definition=f.get('definition'),review_status='approved' if f['id'] in approved_ids else 'pending_review',
            evidence_ids=[f['id']]))
    for f in related:
        if f['id'] not in safe:continue
        related_snapshots.append(dict(fact_id=f['id'],metric=f['metric'],geography=f['geography'],period=f['period'],
            value=str(f.get('value')),unit=f.get('unit'),definition=f.get('definition'),
            review_status='pending_review',evidence_ids=[f['id']],
            scope_note='Combined publisher geography; never substituted for Canary Wharf-only coverage.'))
    # Collapse only duplicate disclosures from the same original and business
    # tuple. Preserve every fact ID, and never merge differing review states.
    def display_unique(rows):
        result=[];index={}
        for row in rows:
            raw=store.get('facts',row['fact_id']) or {}
            doc=store.get('documents',raw.get('document_id','')) or {}
            key=json.dumps([doc.get('sha256'),row['metric'],row['geography'],row['period'],row['value'],
                row['unit'],row.get('definition'),raw.get('method'),raw.get('basis'),raw.get('grade'),
                raw.get('series'),{k:(raw.get('evidence') or {}).get(k) for k in ['quote','locator','page']},row['review_status']],sort_keys=True,default=str)
            if key in index:index[key]['evidence_ids']+=row['evidence_ids']
            else:
                index[key]=row;result.append(row)
        return result
    snapshots=display_unique(snapshots)
    related_snapshots=display_unique(related_snapshots)
    gaps=[]
    comparison=[]
    for geo in scope['geographies']:
        for metric in scope['metrics']:
            matches=[f for f in selected if candidate_in_area(f,geo) and f['metric']==metric]
            eligible=[f for f in matches if f['id'] in approved_ids]
            if not eligible:
                reason='No saved observation for requested area, metric and period.' if not matches else 'Saved candidates require approval, valid units/definitions and hash-verified original evidence.'
                gaps.append(dict(geography=geo,metric=metric,period=period,reason=reason,candidate_ids=[f['id'] for f in matches]))
            comparison.append(dict(geography=geo,metric=metric,period=period,fact_ids=[f['id'] for f in eligible],
                status='eligible' if eligible else 'unavailable',ranking=None))
    calculations=[];findings=[];charts=[];conflicts=[]
    def conflict(metric,scope_kind,rows):
        # Never average or silently select. Report the divergence explicitly.
        entry=dict(metric=metric,component=scope_kind,fact_ids=[f['id'] for f in rows],
            observations=[dict(fact_id=f['id'],geography=f['geography'],period=f['period'],value=str(f['value']),
                unit=f['unit'],definition=f['definition']) for f in rows],
            reason='Observations diverge in value, definition, unit, period or method. They are listed side by side, never averaged, and excluded from charts and rankings.')
        key=(metric,scope_kind,entry['fact_ids'])
        if not any((c['metric'],c['component'],c['fact_ids'])==key for c in conflicts):conflicts.append(entry)
    # Same area, metric and period with divergent values is a cross-record
    # conflict (e.g. different publisher definitions); explain, never merge.
    cells=defaultdict(list)
    for f in approved:
        if f['period']==period:cells[(f['metric'],f['geography'])].append(f)
    for (cell_metric,cell_geo),rows in cells.items():
        if len(rows)>1 and len({str(r['value']) for r in rows})>1:conflict(cell_metric,'observation',rows)
    for f in approved:
        if f['period']==period:
            findings.append(finding(f"{f['geography']} · {f['metric']}: {f['value']} {f['unit']} ({f['period']}; {f['definition']}).",[f['id']]))
    def chart(kind,metric=None):
        return dict(id=kind+'-'+str(metric),type=kind,title=(metric+' · ' if metric else '')+kind.replace('_',' '),
            metric=metric,unit=None,geographies=scope['geographies'],observation_period=period,status='unavailable',
            reason='Insufficient compatible, reviewed and source-verified observations.',points=[])
    def point(f,label):
        return dict(label=label,value=str(f['value']),fact_id=f['id'],evidence_ids=[f['id']],geography=f['geography'],period=f['period'])
    for metric in scope['metrics']:
        regional=chart('regional_comparison',metric)
        pools=defaultdict(list)
        for f in approved:
            if f['metric']==metric and f['period']==period:pools[signature(f,regional=True)].append(f)
        for sig,pool in pools.items():
            # A conflicting duplicate is not silently selected or averaged.
            by_geo=defaultdict(list)
            for f in pool:by_geo[f['geography']].append(f)
            unique=[rows[0] for rows in by_geo.values() if len({r['value'] for r in rows})==1]
            for rows in by_geo.values():
                if len({r['value'] for r in rows})>1:conflict(metric,'regional_comparison',rows)
            if len(unique)>=2:
                regional.update(id=regional['id']+'-'+str(len(charts)),status='ready',reason=None,unit=unique[0]['unit'],geographies=[f['geography'] for f in unique],points=[point(f,f['geography']) for f in unique])
                charts.append(copy.deepcopy(regional))
        if regional['status']!='ready':charts.append(regional)
        history=chart('time_series',metric)
        series=defaultdict(list)
        for f in approved:
            if f['metric']==metric and (not period or f['period']<=period):series[signature(f)].append(f)
        for rows in series.values():
            by_period=defaultdict(list)
            for f in rows:by_period[f['period']].append(f)
            for period_rows in by_period.values():
                if len({f['value'] for f in period_rows})>1:conflict(metric,'time_series',period_rows)
            rows=sorted([r[0] for r in by_period.values() if len({f['value'] for f in r})==1],key=lambda f:f['period'])
            segment=[]
            for a,b in zip(rows,rows[1:]):
                calculation=strict_compare(a,b)
                if calculation['status']!='comparable':continue
                calculation=dict(calculation,old_id=a['id'],new_id=b['id'])
                calculations.append(calculation)
                # Each segment contains exactly one compatible consecutive pair;
                # missing quarters and conflicting records cannot be bridged.
                segment=[a,b]
                charts.append(dict(history,id=history['id']+'-'+a['id']+'-'+b['id'],status='ready',reason=None,
                    unit=a['unit'],geographies=[a['geography']],points=[point(f,f['period']) for f in segment]))
                if b['period']==period:
                    findings.append(finding(f"{b['geography']} · {metric}: change {calculation['display']['absolute_change']} {calculation['change_unit']} from {a['period']} to {b['period']}. Arithmetic on disclosed values; no causal claim.",[a['id'],b['id']],'calculation'))
            if segment:history['status']='ready'
        if history['status']!='ready':charts.append(history)
    supply=chart('supply_structure','supply')
    # Category aggregation is opt-in through a reviewed source's explicit partition contract.
    supplies=[f for f in approved if f['metric']=='supply' and f['period']==period]
    partitions=defaultdict(list)
    for f in supplies:
        if f.get('mutually_exclusive') is True and f.get('partition_id') and f.get('supply_category'):
            partitions[(signature(f),f['partition_id'])].append(f)
    for rows in partitions.values():
        if len(rows)>=2 and len({f['supply_category'] for f in rows})==len(rows):
            supply.update(status='ready',reason=None,unit=rows[0]['unit'],points=[dict(point(f,f['supply_category']),category=f['supply_category']) for f in rows])
            break
    if supply['status']!='ready':supply['reason']='No reviewed, explicitly mutually exclusive source partition. Planning, completed, available and pre-let areas are never added together.'
    if 'supply' in scope['metrics']:charts.append(supply)
    timeline=chart('event_timeline')
    seen=set()
    for e in sorted(events,key=lambda e:event_date(e)):
        if e['id'] not in safe:continue
        key=(event_date(e),e.get('url'),safe[e['id']]['quote'])
        if key in seen:continue
        seen.add(key)
        timeline['points'].append(dict(label=e.get('title','Reported event'),date=event_date(e),geography=e.get('geography'),
            evidence_ids=[e['id']],category='reported event · '+str(e.get('human_review_status') or 'pending_review')))
    if timeline['points']:timeline.update(status='ready',reason=None)
    if scope['report_type']!='fact_answer':charts.append(timeline)
    current=[f for f in approved if f['period']==period]
    if scope['needs_history']:
        for metric in scope['metrics']:
            for geo in scope['geographies']:
                present={f['period'] for f in approved if f['metric']==metric and f['geography']==geo}
                missing=sorted(set(scope['requested_periods'])-present)
                ready=[c for c in charts if c['type']=='time_series' and c['metric']==metric and c['status']=='ready' and geo in c['geographies']]
                covered={tuple(p['period'] for p in c['points']) for c in ready}
                required=list(zip(scope['requested_periods'],scope['requested_periods'][1:]))
                missing_pairs=[list(pair) for pair in required if pair not in covered]
                if missing or missing_pairs or not ready:
                    reason=('Requested periods lack eligible evidence: '+', '.join(missing)) if missing else 'Not all requested period pairs have compatible reviewed consecutive-quarter evidence.'
                    gaps.append(dict(geography=geo,metric=metric,period=period,component='history',missing_periods=missing,
                        missing_comparisons=missing_pairs,reason=reason))
    comparison_blocked=scope['needs_comparison'] and any(not any(c['type']=='regional_comparison' and c['metric']==m and c['status']=='ready' for c in charts) for m in scope['metrics'])
    status='insufficient_evidence' if not current else 'partial' if gaps or comparison_blocked else 'success'
    evidence=[]
    used={f['id'] for f in facts+related} | {e['id'] for e in events}
    for fid,item in safe.items():
        if fid not in used:continue
        doc=store.get('documents',item['document_id'])
        original=store.get('facts' if fid in {f['id'] for f in facts+related} else 'events',fid)
        source=store.get('sources',(original or {}).get('source_id','')) or {}
        evidence.append(dict(item,fact_id=fid if fid in {f['id'] for f in facts+related} else None,collected_at=doc.get('collected_at'),
            reviewed_by=(original or {}).get('reviewed_by'),review_note=(original or {}).get('review_note'),reviewed_at=(original or {}).get('reviewed_at'),
            source_last_checked_at=source.get('last_checked_at') or source.get('last_success'),evidence_integrity_checked_at=now(),evidence_integrity_status='verified',
            review_status='approved' if fid in approved_ids else 'pending_review'))
    sources=list({e['document_id']:dict(document_id=e['document_id'],title=e['report_title'],url=e['url'],
        published_at=e['published_at'],collected_at=e['collected_at'],
        sha256=e.get('source_document_sha256') or e['document_sha256'],
        receipt_sha256=e.get('receipt_sha256')) for e in evidence}.values())
    summary=findings[:3] or [finding('No reviewed and source-verified observations support a confirmed market conclusion in this scope.',[])]
    if gaps:summary=summary+[finding(f'{len(gaps)} requested coverage components (metric, area or history) lack eligible evidence; see data gaps.',[])]
    outlook=[finding('Further direction and causal explanations require additional comparable observations and reviewed demand/supply evidence.',[],'scenario')]
    limitations=['Latest means latest saved observation, not necessarily the latest publication or calendar quarter.',
        'Generation success describes evidence coverage, not semantic approval or an investment recommendation.',
        'Vacancy and availability remain separate. Incompatible definitions are not ranked.',
        'Model interpretation is recorded separately and remains subject to semantic publication review.',
        'No supported causal explanation or investment opportunity is inferred from a single indicator.']
    if omitted:limitations.append('Excluded evidence: '+json.dumps(omitted,ensure_ascii=False))
    if malformed:limitations.append('Malformed observations excluded: '+', '.join(malformed))
    # Deterministic findings go through the same per-finding verifier as model
    # prose. A failed deterministic conclusion is dropped, never promoted.
    probe=dict(evidence=evidence,calculations=calculations,data_gaps=gaps)
    def checked(item):
        item=dict(item)
        item['verification']=verify_finding(item,probe,store,origin='deterministic')
        return item
    def verified_findings(items,label):
        dropped=[f for f in items if verify_finding(f,probe,store,origin='deterministic')['status']!='verified']
        if dropped:limitations.append(f'{len(dropped)} internally generated {label} conclusion(s) failed deterministic verification and were removed.')
        return [checked(f) for f in items if f.get('text') not in {d['text'] for d in dropped}]
    findings=verified_findings(findings,'key finding')
    summary=verified_findings(summary,'summary')
    outlook=verified_findings(outlook,'outlook')
    acquisition=dict({**dict(mode='saved_snapshots',network_requests=0,notice='Existing snapshots used; Sources/Jobs can refresh missing evidence. No live retrieval is claimed.'),**(acquisition or {})},
        source_health=[dict(source_id=s['id'],name=s.get('name',s['id']),health=s.get('health','not_checked'),
            last_success=s.get('last_success'),last_attempt=s.get('last_attempt')) for s in store.all('sources')])
    if acquisition.get('research_required_failures'):
        if status=='success':status='partial'
        limitations.append('Required investigation branches did not complete: '+', '.join(acquisition['research_required_failures'])+'. Saved observations remain inspectable; complete research is not claimed.')
    rid=uid()
    report=ReportArtifact(report_id=rid,title=('London Office Market Report' if scope['report_type']=='market_report' else 'Market Analysis' if scope['report_type']=='topic_analysis' else 'Market Evidence Answer'),
        report_type=scope['report_type'],generated_at=now(),query=query,parent_report_id=parent_report_id,scope=scope,
        geographies=scope['geographies'],observation_period=period,executive_summary=summary,market_snapshot=snapshots,related_observations=related_snapshots,
        regional_comparison=comparison,calculations=calculations,conflicts=conflicts,charts=charts,key_findings=findings,risks=[],opportunities=[],
        outlook=outlook,
        data_gaps=gaps,limitations=limitations,sources=sources,evidence=evidence,generation_status=status,
        publication_review=dict(status='evidence_checked',semantic_approval=False,human_review_complete=False,codes=[],
            fact_fingerprints={f['id']:fact_fingerprint(store.get('facts',f['id'])) for f in facts+related if f['id'] in safe}),
        acquisition=acquisition).model_dump(mode='json')
    if analysis_context and scope['report_type']!='fact_answer':
        report['ai_analysis']=dict(status='pending',**analysis_context)
        if report['generation_status']=='success':report['generation_status']='partial'
    markdown=render_markdown(report)
    row=store.put('reports',identity,dict(id=rid,title=report['title'],period=period or 'unknown',status='current',
        artifact=report,markdown=markdown,html=render_html(report),report_type=scope['report_type'],generation_status=report['generation_status']))
    return row['artifact']


def read_report(store, identity):
    row=store.get('reports',identity)
    if not row:raise KeyError(identity)
    if not row.get('artifact'):raise ValueError('LEGACY_REPORT_HAS_NO_STRUCTURED_ARTIFACT')
    report=copy.deepcopy(row['artifact'])
    stale=False
    for item in report['evidence']:
        doc=store.get('documents',item['document_id'])
        original=store.get('facts' if item.get('fact_id') else 'events',item['id'])
        source=store.get('sources',original.get('source_id','')) if original else None
        try:
            matches=doc and original and source and source.get('allow_llm') is not False and doc.get('sha256')==item['document_sha256'] and hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest()==item['document_sha256']
            matches=matches and original.get('document_id')==item['document_id']
            matches=matches and any(item['quote'] in s.get('text','') and (not item.get('page') or s.get('page')==item['page']) for s in doc.get('segments',[]))
            if original and item.get('fact_id'):
                matches=matches and all(original.get(k)==item.get(k) for k in ['value','unit','period','geography','definition'])
                if item['review_status']=='approved':matches=matches and verified(current_fact(original))
                matches=matches and (original.get('evidence') or {}).get('quote')==item['quote']
            matches=matches and original.get('status') not in ['rejected','superseded'] and original.get('human_review_status')!='rejected'
        except (OSError,KeyError,ValueError):matches=False
        item.update(source_last_checked_at=(source or {}).get('last_checked_at') or (source or {}).get('last_success'),
            evidence_integrity_checked_at=now(),evidence_integrity_status='verified' if matches else 'failed')
        if not matches:stale=True
    if stale:
        report.update(generation_status='insufficient_evidence',executive_summary=[finding('Source evidence or review state changed since generation. Generate a new report before using these conclusions.',[])],
            key_findings=[],market_snapshot=[],related_observations=[],regional_comparison=[],calculations=[],risks=[],opportunities=[],outlook=[],ai_analysis=None)
        for chart in report['charts']:chart.update(status='unavailable',points=[],reason='Evidence changed since generation.')
        report['publication_review'].update(status='withheld',codes=['EVIDENCE_CHANGED'])
        report['limitations'].append('Frozen source quotations retained for audit; current verification failed.')
    analysis=report.get('ai_analysis') or {}
    if analysis.get('status')=='pending' and analysis.get('session_id'):
        from agno.db.sqlite import SqliteDb
        from agno.db.base import SessionType
        session=SqliteDb(db_file=str(store.root/'agno.sqlite3')).get_session(analysis['session_id'],session_type=SessionType.AGENT,deserialize=False)
        run=next((r for r in (session or {}).get('runs',[]) if r.get('run_id')==analysis.get('run_id')),None)
        state=str((run or {}).get('status','')).upper()
        if state in ['ERROR','CANCELLED','CANCELED','FAILED']:
            report['ai_analysis']=dict(analysis,status='failed',answer='Model execution failed; deterministic evidence is retained. No automatic retry.')
    # Validate the entire record fingerprint, including comparison taxonomy.
    for fid,digest in report['publication_review'].get('fact_fingerprints',{}).items():
        original=store.get('facts',fid)
        if not original or fact_fingerprint(original)!=digest:
            if 'EVIDENCE_CHANGED' not in report['publication_review']['codes']:
                report['publication_review']['codes'].append('EVIDENCE_CHANGED')
            report.update(generation_status='insufficient_evidence',executive_summary=[finding('Evidence definition or source binding changed. Generate a new report.',[])],key_findings=[],market_snapshot=[],related_observations=[],regional_comparison=[],calculations=[],risks=[],opportunities=[],outlook=[],ai_analysis=None)
            report['publication_review']['status']='withheld'
            for c in report['charts']:c.update(status='unavailable',points=[],reason='Evidence changed since generation.')
    if report['publication_review']['status']!='withheld':
        from .conditional_analysis import recompute_pair
        invalid_calculation=any(recompute_pair(c.get('old_id'),c.get('new_id'),report,store)[1] for c in report['calculations'])
        if invalid_calculation:
            report.update(generation_status='insufficient_evidence',executive_summary=[finding('Saved calculations no longer reproduce the original observations. Generate a new report.',[])],
                key_findings=[],market_snapshot=[],related_observations=[],regional_comparison=[],calculations=[],risks=[],opportunities=[],outlook=[],ai_analysis=None)
            report['publication_review'].update(status='withheld',codes=['CALCULATION_CHANGED'])
            for chart in report['charts']:chart.update(status='unavailable',points=[],reason='Saved calculation failed source-based recomputation.')
    rejections=[];rejected_texts=set()
    for category in ['executive_summary','key_findings','risks','opportunities','outlook']:
        retained=[]
        for item in report[category]:
            if item.get('origin')!='model_interpretation':retained.append(item);continue
            verdict=verify_finding(item,report,store,origin='model_interpretation',category=category)
            if verdict['status']=='verified':
                retained.append(dict(item,claims=verdict['bindings'],verification=verdict))
            else:
                rejected_texts.add(item['text'])
                rejections.append(dict(category=category,text_sha256=hashlib.sha256(item['text'].encode()).hexdigest(),reasons=verdict['reasons']))
        report[category]=retained
    if rejections:
        report['publication_review']['revalidation_rejections']=rejections
        ai=report.get('ai_analysis') or {}
        accepted=[f for f in ai.get('accepted',[]) if f.get('text') not in rejected_texts]
        report['ai_analysis']=dict(ai,accepted=accepted,status='published' if accepted else 'withheld',
            answer='Previously published model conclusions were rechecked under the current claim verifier; unsupported items are withheld.',
            blocked=list(ai.get('blocked',[]))+rejections)
        if report['generation_status']=='success':report['generation_status']='partial'
    return ReportArtifact.model_validate(report).model_dump(mode='json')


def fact_fingerprint(row):
    keys=['source_id','document_id','metric','value','unit','period','geography','series','definition','basis','grade','method','currency','evidence','raw_value','raw_unit','raw_period','supply_category','partition_id','mutually_exclusive']
    return hashlib.sha256(json.dumps({k:row.get(k) for k in keys},sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def attach_analysis(store, identity, content=None, *, run_id=None, error=None):
    """Per-finding deterministic verification of model interpretation.

    The model proposes inference/scenario findings bound to approved evidence
    IDs. Only findings whose evidence exists, whose quantities match the cited
    disclosures exactly, and whose geography/period terms agree with the cited
    records are published — clearly labelled as model interpretation. Authority,
    coverage, source-count, causal and unbounded quantitative claims are
    withheld with reasons. The model never decides approval or system state.
    """
    from .report_contracts import ReportInterpretation
    from .analysis_guard import review_analysis
    report=read_report(store,identity)
    allowed={e['id'] for e in report['evidence'] if e['review_status']=='approved'} if report['publication_review']['status']!='withheld' else set()
    accepted=[];blocked=[];validation_audit=[]
    original_payload=copy.deepcopy(content)
    try:
        if error:raise ValueError(error)
        if isinstance(content,str):
            content=content.strip()
            if content.startswith('```json') and content.endswith('```'):content=content[7:-3].strip()
            content=json.loads(content)
        from .conditional_analysis import expand_choices
        parsed=ReportInterpretation.model_validate(expand_choices(content,report,store))
        for category in ['key_findings','risks','opportunities','outlook']:
            for f in getattr(parsed,category):
                item=dict(text=f.text,classification=f.classification,evidence_ids=list(f.evidence_ids),claims=[c.model_dump(exclude_none=True) for c in f.claims])
                reason=None
                verdict=verify_finding(item,report,store,origin='model_interpretation',category=category)
                state_only=bool(verdict.get('bindings')) and all(c['kind']=='state_assertion' for c in verdict['bindings'])
                if re.search(r'[\u3400-\u9fff]',f.text):reason='NON_ENGLISH_MODEL_OUTPUT'
                elif verdict['status']!='verified':reason=';'.join(verdict['reasons'])
                elif not state_only and (not f.evidence_ids or not set(f.evidence_ids)<=allowed):reason='UNSUPPORTED_EVIDENCE_IDS'
                elif f.classification not in ['inference','scenario']:reason='MODEL_FACT_PROMOTION_BLOCKED'
                else:
                    verdict=verify_finding(item,report,store,origin='model_interpretation',category=category)
                    if verdict['status']!='verified':reason=';'.join(verdict['reasons'])
                    else:
                        # The finding verifier already bound every quantity,
                        # direction, geography and period to cited records. The
                        # publication guard still applies to semantic traps it
                        # alone covers: pre-let/under-offer quantity splits,
                        # planning-status certainty and model-written source
                        # counts.
                        checks=review_analysis(f.text,store)
                        trapped=[c for c in checks['publication_review']['hard_codes']
                            if c in {'LEASE_STATUS_QUANTITY','UNVERIFIED_PLANNING_STATUS','MODEL_SOURCE_COUNT'}]
                        if trapped:reason='PUBLICATION_GUARD_WITHHELD:'+','.join(trapped)
                validation_audit.append(dict(category=category,original_text=f.text,evidence_ids=list(f.evidence_ids),
                    original_claims=item['claims'],verification=copy.deepcopy(verdict),outcome='rejected' if reason else 'accepted',reason=reason))
                if reason:blocked.append(dict(category=category,reason=reason,text_sha256=hashlib.sha256(f.text.encode()).hexdigest(),evidence_ids=list(f.evidence_ids)))
                else:accepted.append(dict(category=category,**dict(item,claims=verdict['bindings'])))
        status='published' if accepted else 'withheld'
    except (ValueError,TypeError) as exc:
        status='blocked' if error=='NO_VERIFIED_EVIDENCE' else 'failed' if error else 'schema_invalid'
        code=str(exc) if str(exc).startswith('MODEL_CANDIDATE_') else 'MODEL_SCHEMA_INVALID'
        blocked.append(dict(reason=error if error else code))
    for entry in accepted:
        category=entry['category'];finding_item={k:v for k,v in entry.items() if k!='category'}
        verdict=verify_finding(finding_item,report,store,origin='model_interpretation',category=category)
        report[category].append(dict(finding_item,origin='model_interpretation',verification=verdict))
    report['ai_analysis']=dict(status=status,run_id=run_id,accepted=accepted,draft=[],blocked=blocked,
        original_payload=original_payload,validation_audit=validation_audit,
        answer=(f'{len(accepted)} model interpretation finding(s) passed per-finding deterministic verification and are published as labelled evidence-bound proposals; '
                f'{len(blocked)} withheld. Publication is not semantic or human approval.') if status=='published'
                else 'Model interpretation is withheld from published conclusions: no finding passed per-finding deterministic verification.',semantic_approval=False)
    if status!='published' and report['generation_status']=='success':report['generation_status']='partial'
    report['publication_review'].update(semantic_approval=False,human_review_complete=False,ai_status=status)
    markdown=render_markdown(report)
    store.update('reports',identity,dict(artifact=report,generation_status=report['generation_status'],markdown=markdown,html=render_html(report)))
    return report


def render_markdown(report):
    report=ReportArtifact.model_validate(report).model_dump(mode='json')
    def freshness(e):
        return (f"Observed period: {e.get('period') or 'unknown'} · Published: {e.get('published_at') or 'unknown'}"
            f" · Collected: {e.get('collected_at') or 'unknown'} · Source last checked: {e.get('source_last_checked_at') or 'unknown'}"
            f" · Evidence integrity checked at: {e.get('evidence_integrity_checked_at') or 'unknown'} ({e.get('evidence_integrity_status') or 'unknown'})"
            f" · Review actor: {e.get('reviewed_by') or 'Not recorded'} · Review basis: {e.get('review_note') or 'Not recorded'}")
    lines=['# '+report['title'],'',f"Research scope: {scope_summary(report)}",
        f"Generated: {report['generated_at']} · Observation period: {report['observation_period'] or 'unknown'}",
        'Scope: '+', '.join(report['geographies']), 'Status: '+report['generation_status']]
    if report.get('parent_report_id'):lines+=['Parent report: '+report['parent_report_id']]
    ai=report.get('ai_analysis') or {}
    if ai.get('status'):lines+=['Model interpretation: '+str(ai.get('status'))+' — '+str(ai.get('answer',''))]
    def finding_line(f):
        tag=f['classification']+(' · AI interpretation' if f.get('origin')=='model_interpretation' else ' · deterministic')
        verdict=(f.get('verification') or {}).get('status')
        return f"- [{tag}{' · '+verdict if verdict else ''}] {f['text']} Evidence: {', '.join(f['evidence_ids']) or 'none'}"
    for title,key in [('Executive Summary','executive_summary'),('Key Findings','key_findings'),('Risks','risks'),('Opportunities','opportunities'),('Outlook','outlook')]:
        lines+=['','## '+title]+[finding_line(f) for f in report[key]]
        if not report[key]:lines+=['No evidence-supported conclusion available.']
    lines+=['','## Market Snapshot','| Area | Metric | Period | Original value / unit | Review | Definition | Evidence |','|---|---|---|---|---|---|---|']
    def cell(value):return str(value).replace('|','\\|').replace('\n',' ')
    for f in report['market_snapshot']:
        lines+=['| '+' | '.join(cell(f[k]) for k in ['geography','metric','period'])+' | '+cell(f['value'])+' '+cell(f['unit'])+' | '+f['review_status']+' | '+cell(f['definition'])+' | '+cell(', '.join(f['evidence_ids']))+' |']
    if not report['market_snapshot']:lines+=['No matching saved facts with verifiable source evidence in this scope.']
    if report.get('related_observations'):
        lines+=['','## Related geography context','Combined publisher geographies are shown separately; they never fill standalone regional coverage.']
        for f in report['related_observations']:
            lines+=[f"- {f['geography']} · {f['metric']} · {f['period']}: {f['value']} {f['unit']} [{f['review_status']}] Definition: {f['definition']}. {f.get('scope_note','')} Evidence: {', '.join(f['evidence_ids'])}"]
    lines+=['','## Regional Comparison','| Area | Metric | Period | Status | Facts |','|---|---|---|---|---|']
    for row in report.get('regional_comparison',[]):
        lines+=['| '+' | '.join(cell(row[k]) for k in ['geography','metric','period'])+' | '+row['status']+' | '+cell(', '.join(row['fact_ids']) or 'none')+' |']
    if not report.get('regional_comparison'):lines+=['No comparison was requested in this scope.']
    if report.get('calculations'):
        lines+=['','## Deterministic Calculations']
        for c in report['calculations']:
            display=c.get('display') or {}
            evidence_by_id={e['id']:e for e in report['evidence']}
            old=evidence_by_id.get(c.get('old_id'),{});new=evidence_by_id.get(c.get('new_id'),{})
            lines+=[f"- {c.get('metric') or new.get('metric','')} · {c.get('geography') or new.get('geography','')}: {c.get('old_period') or old.get('period')} → {c.get('new_period') or new.get('period')} = {display.get('absolute_change') or c.get('absolute_change')} {c.get('change_unit') or ''} [{c.get('status')}]. Facts: {c.get('old_id')}, {c.get('new_id')}"]
    lines+=['','## Charts']
    for c in report.get('charts',[]):
        lines+=[f"### {c['title']} [{c['status']}]",f"Metric: {c.get('metric') or 'n/a'} · Unit: {c.get('unit') or 'n/a'} · Period: {c.get('observation_period') or 'unknown'} · Areas: {', '.join(c.get('geographies') or [])}"]
        if c.get('reason'):lines+=['Reason: '+c['reason']]
        for p in c.get('points',[]):
            lines+=[f"- {p['label']}: {p.get('value') or p.get('date') or 'n/a'} (evidence: {', '.join(p.get('evidence_ids') or [])})"]
        if not c.get('points'):lines+=['No releasable data points.']
    if report.get('conflicts'):
        lines+=['','## Conflicting Observations — never averaged','Statistical periods, definitions, units, geographies or methods differ; records are listed side by side and excluded from charts, rankings and trends.']
        for conflict in report['conflicts']:
            lines+=[f"- {conflict['metric']} ({conflict['component']}): "+'; '.join(f"{o['geography']} {o['period']} = {o['value']} {o['unit']} ({o['definition']})" for o in conflict['observations'])]
    lines+=['','## Data Gaps']+['- '+g['geography']+' / '+g['metric']+': '+g['reason'] for g in report['data_gaps']]
    lines+=['','## Limitations']+['- '+s for s in report['limitations']]
    health=(report.get('acquisition') or {}).get('source_health') or []
    if health:
        lines+=['','## Source Freshness']
        for s in health:
            lines+=[f"- {s['name']}: health {s['health']} · last success {s.get('last_success') or 'unknown'} · last attempt {s.get('last_attempt') or 'unknown'}"]
    lines+=['','## Sources & Evidence']
    for e in report['evidence']:
        integrity='Source document SHA-256: '+str(e.get('source_document_sha256') or e['document_sha256'])
        if e.get('receipt_sha256'):
            integrity+=' · Offline receipt SHA-256: '+e['receipt_sha256']+' · Publisher bytes are not redistributed; local integrity covers the receipt.'
        lines += ['',e['report_title'] or e['document_id'],'Evidence ID: '+e['id'],str(e['url']),freshness(e),f"Page: {e['page']} · Locator: {e['locator']}",'> '+e['quote'],integrity,'Review: '+e['review_status']]
    return '\n'.join(lines)


def render_notification(report,max_bytes=12000):
    """A bounded evidence envelope; never slice a report through its sources."""
    report=ReportArtifact.model_validate(report).model_dump(mode='json')
    evidence={e['id']:e for e in report['evidence']}
    header=(f"Notification summary — not the full report.\n{report['title']}\n"
        f"Report ID: {report['report_id']}\nStatus: {report['generation_status']}\n"
        f"Observation period: {report['observation_period']}\nAreas: {', '.join(report['geographies'])}\n"
        f"Generated: {report['generated_at']}\nModel interpretation: {(report.get('ai_analysis') or {}).get('status','not requested')}\n"
        f"Data gaps: {len(report['data_gaps'])}. Evidence coverage is not independent semantic or investment approval.\n")
    if report.get('acquisition',{}).get('detection_context')=='historical_replay':
        header+='Historical replay of saved observations; not a new market discovery.\n'
    footer=(f"\nSummary only: detailed tables, limitations and other observations are not included. "
        f"Open the saved report in this workspace: /reports?report={report['report_id']}\n")
    def sources(ids):
        lines=[]
        for identity in ids:
            e=evidence[identity]
            lines.append(f"Source [{identity}]: {e.get('report_title') or e['document_id']}\n"
                f"Observation: {e.get('period') or 'unknown'}; publication: {e.get('published_at') or 'unknown'}; "
                f"review: {e['review_status']}; page {e.get('page')}; locator: {e.get('locator') or 'unknown'}\n"
                f"{e.get('url') or 'Original URL not supplied'}\nSource document SHA-256: {e.get('source_document_sha256') or e['document_sha256']}"
                + (f"\nOffline receipt SHA-256: {e['receipt_sha256']} (publisher bytes not redistributed)" if e.get('receipt_sha256') else ''))
        return '\n\n'.join(lines)
    candidates=[]
    for category in ['key_findings','risks','opportunities']:
        for f in report[category]:
            if f.get('origin')=='model_interpretation':
                candidates.append((f"[{category}; {f['classification']}; evidence-bound AI proposal] {f['text']}",f['evidence_ids']))
    for chart in report['charts']:
        if chart['status']!='ready':continue
        ids=list(dict.fromkeys(i for p in chart['points'] for i in p['evidence_ids']))
        text=chart['title']+' / '+', '.join(chart['geographies'])+' / '+str(chart.get('unit') or 'dated event')+': '
        text+='; '.join(f"{p['label']} = {p.get('value') or p.get('date')}" for p in chart['points'])
        candidates.append((text,ids))
    for f in report['executive_summary']:
        candidates.append((f"[{f['classification']}; {f['origin']}] {f['text']}",f['evidence_ids']))
    blocks=[];used=[];omitted=0
    for text,ids in candidates:
        if any(i not in evidence for i in ids):raise ValueError('NOTIFICATION_EVIDENCE_UNAVAILABLE')
        trial=list(dict.fromkeys(used+ids))
        body=header+'\n\n'.join(blocks+[text])+'\n\n'+sources(trial)+footer
        if len(body.encode('utf-8'))+100>max_bytes:
            omitted+=1;continue
        blocks.append(text);used=trial
    body=header+'\n\n'.join(blocks)+'\n\n'+sources(used)+footer
    if omitted:body+=f"Additional summary items omitted to meet the notification byte limit: {omitted}.\n"
    if len(body.encode('utf-8'))>max_bytes or (any(ids for _,ids in candidates) and not used):
        raise ValueError('NOTIFICATION_EVIDENCE_ENVELOPE_EXCEEDED')
    return body


def render_html(markdown):
    if isinstance(markdown,dict):
        from .report_export import render
        return render(markdown)
    return '<!doctype html><html lang="en"><meta charset="utf-8"><title>Market report</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><pre>'+html.escape(markdown)+'</pre></html>'
