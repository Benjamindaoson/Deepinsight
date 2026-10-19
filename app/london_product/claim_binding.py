"""Positive claim language: unknown prose is never proof of source support.

This is a small claim compiler, not a general natural-language entailment model.
Every published clause has a typed binding and a fully checked surface form.
"""
import re
from decimal import Decimal, InvalidOperation
from .normalization import current_fact
from .qa_context import verified
from .safe_answer import safe_evidence

VERSION='claim-binding-v3-temporal-coverage'
AREAS=['City','West End','Canary Wharf','Midtown / Fringe','Midtown','Fringe','Central London','United Kingdom']
GEO='(?:'+'|'.join(re.escape(a) for a in sorted(AREAS,key=len,reverse=True))+')'
PERIOD=r'20\d{2}Q[1-4]'
OBS=re.compile(r'(?P<geo>'+GEO+r') (?P<metric>[a-z_]+)(?: in (?P<before>'+PERIOD+r'))? (?:is|was|stood at|reached) (?P<value>-?\d+(?:\.\d+)?) (?P<unit>[^.;]+?)(?: in (?P<after>'+PERIOD+r'))?\.?'+r'(?:; (?P<advice>monitor))?\.?',re.I)
CHANGE=re.compile(r'(?P<geo>'+GEO+r') (?P<metric>[a-z_]+) (?P<direction>fell|rose|remained stable) from (?P<old>'+PERIOD+r') to (?P<new>'+PERIOD+r')(?:; monitor whether this holds)?\.?',re.I)
RESEARCH=re.compile(r'Further study could investigate (?P<geo>'+GEO+r') (?P<topic>demand|supply|comparability)\.?',re.I)


def state_claim(text, report, ids):
    """Compile complete status sentences; a keyword never grants authority.

    These predicates describe storage/review state, never market truth. Their
    scope derives from the report. Unknown/additional clauses remain unbound.
    """
    scope=report['scope'];state=None;expected=True;geos=scope['geographies'];metrics=scope['metrics']
    if re.fullmatch(r'All requested regions have approved observations\.|所有请求区域均有已批准观测。',text,re.I):state='regions_approved'
    elif re.fullmatch(r'There is complete coverage across all requested regions and indicators\.|所有请求区域和指标均已完整覆盖。',text,re.I):state='coverage_complete'
    elif re.fullmatch(r'Independent semantic review has approved all findings\.|独立语义审核已批准全部发现。',text,re.I):state='semantic_approved'
    else:
        patterns=[
            ('saved_presence',False,r'There are no saved (?P<geo>'+GEO+r') (?P<metric>[a-z_]+) observations\.'),
            ('approved_presence',True,r'A reviewed (?P<geo>'+GEO+r') (?P<metric>[a-z_]+) observation is available; broader market conclusions require additional evidence\.'),
            ('pending_presence',True,r'A saved (?P<geo>'+GEO+r') (?P<metric>[a-z_]+) observation is available; it remains pending human review\.'),
            ('saved_presence',True,r'A saved (?P<geo>'+GEO+r') (?P<metric>[a-z_]+) observation is available\.'),
        ]
        for candidate,value,pattern in patterns:
            match=re.fullmatch(pattern,text,re.I)
            if match:
                state=candidate;expected=value
                geos=[next(g for g in AREAS if g.casefold()==match['geo'].casefold())]
                metrics=[match['metric'].lower()];break
    if state is None:return None
    return dict(kind='state_assertion',state=state,expected=expected,
        geography=geos[0] if len(geos)==1 else 'requested scope',metric=metrics[0] if len(metrics)==1 else None,
        observation_period=report.get('observation_period'),scope_geographies=list(geos),scope_metrics=list(metrics),evidence_ids=list(ids))


def _bind_state(item, claim, report, store):
    """Evaluate a typed predicate against authoritative scope-bound records."""
    geos=claim['scope_geographies'];metrics=claim['scope_metrics'];period=claim['observation_period'];reasons=[]
    scope=report['scope']
    coverage=claim['state']=='coverage_complete'
    requested_periods=list(scope.get('requested_periods') or [period]) if coverage else [period]
    if not set(geos)<=set(scope['geographies']) or not set(metrics)<=set(scope['metrics']):reasons.append('STATE_SCOPE_OUTSIDE_REQUEST')
    # Combined markets and source-labelled candidates cannot fill exact cells.
    from .normalization import derive
    from .chat_report import candidate_in_area
    raw=[];malformed=[];saved_ids=[]
    for row in store.all('facts'):
        if (row.get('status') in ['rejected','superseded'] or row.get('human_review_status')=='rejected'
                or not any(candidate_in_area(row,g) for g in geos) or row.get('metric') not in metrics):continue
        try:
            observed=derive(row)['normalized_period']
            if observed not in requested_periods:
                # An implicit historical request also needs the earlier
                # observations that support its deterministic comparison.
                if not (coverage and scope.get('needs_history') and not scope.get('requested_periods') and observed and period and observed<period):continue
            saved_ids.append(row['id']);raw.append(current_fact(row))
        except (ValueError,TypeError,InvalidOperation):
            if row.get('period')==period:
                saved_ids.append(row['id']);malformed.append(dict(id=row['id'],reason='NORMALIZATION_INVALID'))
    groups,omitted=safe_evidence(store,[dict(facts=raw)])
    grounded_ids={r['id'] for rows in groups.values() for r in rows}
    grounded=[r for r in raw if r['id'] in grounded_ids]
    report_approved={e['id'] for e in report['evidence'] if e.get('review_status')=='approved'}
    approved=[r for r in grounded if verified(r) and r['id'] in report_approved]
    # An eligibility failure (for example a missing rent denominator) cannot
    # rewrite an existing human decision into a pending-review state.
    pending=[r for r in grounded if (store.get('facts',r['id']) or {}).get('human_review_status')=='pending_review']
    missing=[dict(geography=g,metric=m,period=p) for g in geos for m in metrics for p in requested_periods
             if not any(r['geography']==g and r['metric']==m and r['period']==p for r in approved)]
    # Completeness includes the requested analytical coverage, not merely an
    # observation at the endpoint. The artifact's deterministic gate checks
    # required history pairs, compatible definitions and regional charts.
    analytical_coverage=(report.get('generation_status')=='success'
        and not report.get('data_gaps') and not report.get('conflicts'))
    # The existing product records fact review, not independent semantic review.
    # A model-written report flag or fact approval never establishes the latter.
    actual={'regions_approved':all(any(r['geography']==g for r in approved) for g in geos),
        'coverage_complete':not missing and analytical_coverage,'saved_presence':bool(saved_ids),'approved_presence':bool(approved),
        'pending_presence':bool(pending),'semantic_approved':False}[claim['state']]
    check=dict(assertion=claim['state'],expected=claim['expected'],actual=actual,
        scope=dict(geographies=geos,metrics=metrics,observation_period=period,requested_periods=requested_periods),
        analytical_coverage_complete=analytical_coverage,
        saved_ids=saved_ids,grounded_ids=sorted(grounded_ids),approved_ids=[r['id'] for r in approved],
        pending_ids=[r['id'] for r in pending],missing_eligible_cells=missing,excluded=omitted+malformed,
        semantic_approval=False,semantic_review_available=False,report_publication_status=report['publication_review']['status'])
    code={'regions_approved':'STATE_APPROVAL_CONTRADICTION','coverage_complete':'STATE_COVERAGE_CONTRADICTION',
        'saved_presence':'STATE_EXISTENCE_CONTRADICTION','approved_presence':'STATE_APPROVAL_CONTRADICTION',
        'pending_presence':'STATE_PENDING_REVIEW_CONTRADICTION','semantic_approved':'STATE_SEMANTIC_APPROVAL_CONTRADICTION'}[claim['state']]
    if actual is not claim['expected']:reasons.append(code)
    cited=set(item.get('evidence_ids') or []);report_ids={e['id'] for e in report['evidence']}
    if not cited or not cited<=grounded_ids or not cited<=report_ids:reasons.append('STATE_CITATION_NOT_GROUNDED')
    if claim['state'] in ['regions_approved','coverage_complete','approved_presence']:
        if not cited<={r['id'] for r in approved}:reasons.append('STATE_APPROVAL_CITATION_NOT_ELIGIBLE')
        required=[(g,m,p) for g in geos for m in metrics for p in requested_periods] if coverage else [(g,None,period) for g in geos]
        if any(not any(r['id'] in cited and r['geography']==g and (m is None or r['metric']==m) and r['period']==p for r in approved) for g,m,p in required):
            reasons.append('STATE_CITATION_SCOPE_INCOMPLETE')
    if claim['state']=='pending_presence' and not cited<={r['id'] for r in pending}:reasons.append('STATE_PENDING_CITATION_MISMATCH')
    supplied=item.get('claims') or []
    if supplied:
        clean=lambda c:{k:v for k,v in c.items() if v is not None}
        if [clean(c) for c in supplied]!=[clean(claim)]:reasons.append('STATE_CLAIM_CONTRACT_MISMATCH')
    return dict(claims=[claim],reasons=list(dict.fromkeys(reasons)),state_checks=[check],compiler=VERSION)


def canonical(claim):
    c=claim;geo=c['geography'];period=c.get('observation_period')
    if c['kind'] in ['conditional_scenario','regional_ordering']:
        from .conditional_analysis import scenario_text,ordering_text
        return scenario_text(c) if c['kind']=='conditional_scenario' else ordering_text(c)
    if c['kind']=='state_assertion':
        state=c['state']
        if state=='regions_approved' and c['expected'] is True:return 'All requested regions have approved observations.'
        if state=='coverage_complete' and c['expected'] is True:return 'There is complete coverage across all requested regions and indicators.'
        if state=='semantic_approved' and c['expected'] is True:return 'Independent semantic review has approved all findings.'
        if state=='saved_presence':return (f'A saved {geo} {c["metric"]} observation is available.' if c['expected'] else f'There are no saved {geo} {c["metric"]} observations.')
        if state=='approved_presence' and c['expected'] is True:return f'A reviewed {geo} {c["metric"]} observation is available; broader market conclusions require additional evidence.'
        if state=='pending_presence' and c['expected'] is True:return f'A saved {geo} {c["metric"]} observation is available; it remains pending human review.'
        raise ValueError('STATE_ASSERTION_UNKNOWN')
    if c['kind']=='observation':return f"{geo} {c['metric']} in {period} was {c['value']} {c['unit']}."
    if c['kind']=='source_statement':return f"{geo} / {period}: source statement: “{c['quote']}”"
    if c['kind']=='research_action':
        return {'monitor':f'Monitor comparable observations for {geo}.',
            'investigate_demand':f'Further study could investigate {geo} demand.',
            'review_supply':f'Further study could investigate {geo} supply.',
            'check_comparability':f'Further study could investigate {geo} comparability.'}[c['action']]
    if c['kind']=='change':
        direction={'increase':'rose','decrease':'fell','unchanged':'remained stable'}[c['direction']]
        return f"{geo} {c['metric']} {direction} from {c['old_observation_period']} to {period}."
    raise ValueError('CLAIM_KIND_UNKNOWN')


def _number(value):
    try:
        value=Decimal(str(value))
        return value if value.is_finite() else None
    except (InvalidOperation,ValueError):return None


def _unit(unit):return 'percent' if unit in ['%','percent'] else unit


def _tuple_matches(claim,row):
    if any(claim.get(k)!=row.get(field) for k,field in [
        ('metric','metric'),('geography','geography'),('observation_period','period'),
        ('definition','definition'),('method','method')]):return False
    if claim.get('locator')!=(row.get('evidence') or {}).get('locator'):return False
    if claim['kind']=='source_statement':
        if claim.get('quote')!=(row.get('evidence') or {}).get('quote'):return False
        if claim.get('value') is None and claim.get('unit') is None:return True
    pairs=[(row.get('value'),row.get('unit')),(row.get('raw_value'),row.get('raw_unit')),
           (row.get('normalized_value'),row.get('normalized_unit'))]
    return any(_number(claim.get('value')) is not None and _number(claim.get('value'))==_number(value)
               and str(claim.get('value'))==str(value)
               and _unit(claim.get('unit'))==_unit(unit) for value,unit in pairs)


def _bound(row,kind='observation',**extra):
    return dict(kind=kind,metric=row.get('metric'),value=str(row.get('value')),unit=row.get('unit'),
        geography=row.get('geography'),observation_period=row.get('period'),definition=row.get('definition'),
        method=row.get('method'),evidence_ids=[row['id']],locator=(row.get('evidence') or {}).get('locator'),**extra)


def _legacy(text,classification,rows,report):
    """Only complete recognized clauses qualify; a correct prefix grants nothing."""
    match=OBS.fullmatch(text)
    if match:
        candidates=[]
        for row in rows:
            if row.get('geography','').casefold()!=match['geo'].casefold() or row.get('metric','').casefold()!=match['metric'].casefold():continue
            p=match['before'] or match['after'] or report.get('observation_period')
            if (match['before'] and match['after'] and match['before'].upper()!=match['after'].upper()):continue
            c=_bound(row);c.update(value=match['value'],unit=match['unit'],observation_period=p.upper() if p else None)
            if _tuple_matches(c,row):candidates.append(c)
        if len(candidates)!=1:return None,['CLAIM_TUPLE_MISMATCH']
        return candidates,[]
    match=RESEARCH.fullmatch(text)
    if match and classification=='scenario':
        candidates=[r for r in rows if r.get('geography','').casefold()==match['geo'].casefold()]
        if not candidates:return None,['RESEARCH_SCOPE_UNSUPPORTED']
        action={'demand':'investigate_demand','supply':'review_supply','comparability':'check_comparability'}[match['topic'].lower()]
        return [dict(kind='research_action',geography=candidates[0]['geography'],
            observation_period=report.get('observation_period'),evidence_ids=[r['id'] for r in candidates],action=action)],[]
    match=CHANGE.fullmatch(text)
    if match:
        for calc in report.get('calculations',[]):
            old=next((r for r in rows if r['id']==calc.get('old_id')),None)
            new=next((r for r in rows if r['id']==calc.get('new_id')),None)
            if not old or not new:continue
            if old.get('geography','').casefold()!=match['geo'].casefold() or new.get('geography')!=old['geography']:continue
            if old.get('metric','').casefold()!=match['metric'].casefold() or new.get('metric')!=old['metric']:continue
            if old.get('period')!=match['old'].upper() or new.get('period')!=match['new'].upper():continue
            delta=_number(calc.get('absolute_change'))
            if delta is None:continue
            expected='fell' if delta<0 else 'rose' if delta>0 else 'remained stable'
            if match['direction'].lower()!=expected:return None,['DIRECTION_CONTRADICTS_CALCULATION']
            c=_bound(new,kind='change');c.update(old_id=old['id'],new_id=new['id'],old_observation_period=old['period'],
                direction='decrease' if delta<0 else 'increase' if delta>0 else 'unchanged',evidence_ids=[old['id'],new['id']])
            return [c],[]
        return None,['CHANGE_BINDING_MISSING']
    return None,['CLAIM_SUPPORT_UNKNOWN']


def bind_finding(item,report,store):
    from .chat_report import in_area
    if report.get('publication_review',{}).get('status')=='withheld':return dict(claims=[],reasons=['REPORT_EVIDENCE_WITHHELD'])
    ids=item.get('evidence_ids') or [];reasons=[]
    state=state_claim(str(item.get('text') or ''),report,ids)
    if state:return _bind_state(item,state,report,store)
    rows=[current_fact(store.get('facts',i)) for i in ids if store.get('facts',i)]
    groups,_=safe_evidence(store,[dict(facts=rows)])
    report_eligible={e['id'] for e in report.get('evidence',[]) if e.get('review_status')=='approved'}
    safe={r['id'] for r in groups['verified_fact']} & report_eligible
    rows=[r for r in rows if r['id'] in safe and verified(r) and
          r.get('metric') in report.get('scope',{}).get('metrics',[]) and
          any(in_area(r,area) for area in report.get('geographies',[]))]
    if len(rows)!=len(set(ids)):return dict(claims=[],reasons=['CLAIM_EVIDENCE_NOT_ELIGIBLE'])
    claims=item.get('claims') or []
    if claims:
        # Supplied type fields cannot authorize contradictory or additional prose.
        try:expected=' '.join(canonical(c) for c in claims)
        except (KeyError,ValueError,TypeError):return dict(claims=[],reasons=['CLAIM_CONTRACT_INVALID'])
        if item.get('text')!=expected:
            legacy,errors=_legacy(str(item.get('text') or ''),item.get('classification'),rows,report)
            clean=lambda values:[{k:v for k,v in c.items() if v is not None} for c in values]
            if errors or clean(legacy or [])!=clean(claims):reasons.append('CLAIM_TEXT_MISMATCH')
    else:
        claims,errors=_legacy(str(item.get('text') or ''),item.get('classification'),rows,report)
        reasons.extend(errors)
        if not claims:return dict(claims=[],reasons=list(dict.fromkeys(reasons)))
    bound_ids=set()
    for claim in claims:
        fields={'kind','geography','observation_period','evidence_ids'}
        if claim['kind']=='conditional_scenario':
            fields|={'rule','perspective','takeup_old_id','takeup_new_id','vacancy_old_id','vacancy_new_id'}
        elif claim['kind']=='regional_ordering':
            fields|={'metric','other_geography','left_id','right_id','relative_direction'}
        elif claim['kind']=='research_action':fields.add('action')
        else:
            fields|={'metric','value','unit','definition','method','locator'}
            if claim['kind']=='change':fields|={'old_id','new_id','old_observation_period','direction'}
            if claim['kind']=='source_statement':fields.add('quote')
        if any(k not in fields and v is not None for k,v in claim.items()):reasons.append('CLAIM_FIELD_ROLE_MISMATCH')
        cids=claim.get('evidence_ids') or [];bound_ids.update(cids)
        selected=[r for r in rows if r['id'] in cids]
        if not cids or len(selected)!=len(set(cids)):reasons.append('CLAIM_EVIDENCE_NOT_ELIGIBLE');continue
        if claim['kind'] in ['conditional_scenario','regional_ordering']:
            from .conditional_analysis import validate_premises
            reasons.extend(validate_premises(claim,report,store))
            if claim['kind']=='conditional_scenario' and item.get('classification')!='scenario':reasons.append('CONDITIONAL_CLASSIFICATION_MISMATCH')
        elif claim['kind']=='research_action':
            if item.get('classification')!='scenario':reasons.append('RESEARCH_CLASSIFICATION_MISMATCH')
            if any(r.get('geography')!=claim['geography'] for r in selected):reasons.append('RESEARCH_SCOPE_UNSUPPORTED')
            if claim.get('observation_period')!=report.get('observation_period'):reasons.append('CLAIM_PERIOD_MISMATCH')
            # Research actions assert no metric, number, unit, event or system state.
            if any(claim.get(k) is not None for k in ['metric','value','unit','quote','old_id','new_id','definition','method','locator']):reasons.append('RESEARCH_CONTAINS_FACT_FIELDS')
        elif claim['kind']=='change':
            calc=next((c for c in report.get('calculations',[]) if c.get('old_id')==claim.get('old_id') and c.get('new_id')==claim.get('new_id')),None)
            if not calc or set(cids)!={claim.get('old_id'),claim.get('new_id')}:reasons.append('CHANGE_BINDING_MISSING')
            new=next((r for r in selected if r['id']==claim.get('new_id')),None)
            if not new or not _tuple_matches(dict(claim,kind='observation'),new):reasons.append('CLAIM_TUPLE_MISMATCH')
            old=next((r for r in selected if r['id']==claim.get('old_id')),None)
            if not old or claim.get('old_observation_period')!=old.get('period'):reasons.append('CLAIM_PERIOD_MISMATCH')
            from .conditional_analysis import recompute_pair
            actual,errors=recompute_pair(claim.get('old_id'),claim.get('new_id'),report,store)
            reasons.extend(errors)
            delta=_number((actual or {}).get('absolute_change'))
            expected='decrease' if delta is not None and delta<0 else 'increase' if delta is not None and delta>0 else 'unchanged'
            if delta is None or claim.get('direction')!=expected:reasons.append('CHANGE_DIRECTION_MISMATCH')
        elif claim['kind'] in ['observation','source_statement']:
            if len(selected)!=1 or not _tuple_matches(claim,selected[0]):reasons.append('CLAIM_TUPLE_MISMATCH')
        else:reasons.append('CLAIM_KIND_UNKNOWN')
    if bound_ids!=set(ids):reasons.append('UNBOUND_EVIDENCE_IDS')
    return dict(claims=claims,reasons=list(dict.fromkeys(reasons)),compiler=VERSION)
