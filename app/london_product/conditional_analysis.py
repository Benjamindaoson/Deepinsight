"""Bounded, conditional business implications from fully checked premises.

These are research scenarios, never predictions, causal proofs or investment
recommendations. The model selects an applicable proposition; the system binds
and checks its complete premises again before publishing it.
"""
import copy
import hashlib
import json
from decimal import Decimal, InvalidOperation


def scenario_text(claim):
    geo = claim['geography']
    premise = f'If the observed combination of higher leasing take-up and lower vacancy in {geo} persists, '
    if claim['perspective'] == 'occupier_risk':
        return (premise + 'occupiers could face fewer suitable leasing options; assess live listings and forthcoming completions before committing. '
            'This is a conditional risk, not a forecast.')
    if claim['perspective'] == 'landlord_opportunity':
        return (premise + 'landlords could investigate a letting or refurbishment strategy; validate asset quality, costs and actual tenant requirements before acting. '
            'This is a research opportunity, not an investment recommendation.')
    raise ValueError('CONDITIONAL_PERSPECTIVE_UNKNOWN')


def ordering_text(claim):
    return (f"In {claim['observation_period']}, {claim['geography']} {claim['metric']} was {claim['relative_direction']} than "
        f"{claim['other_geography']} {claim['metric']} on a matched publisher basis; this does not establish investment attractiveness.")


def _rows(ids, report, store):
    from .normalization import current_fact
    from .qa_context import verified
    from .safe_answer import safe_evidence
    eligible = {e['id'] for e in report['evidence'] if e.get('review_status') == 'approved'}
    rows = [store.get('facts', identity) for identity in ids]
    if not rows or any(not r for r in rows):return None
    try:
        rows = [current_fact(r) for r in rows]
        groups, _ = safe_evidence(store, [dict(facts=rows)])
        safe = {r['id'] for r in groups['verified_fact']} & eligible
        if any(r['id'] not in safe or not verified(r) for r in rows):return None
    except (ValueError, TypeError, InvalidOperation):return None
    return rows


def validate_premises(claim, report, store):
    """Recompute each complete premise; never combine unrelated signs/units."""
    from .chat_report import normalized, signature
    from london_data.comparison import compare
    if report['publication_review']['status'] == 'withheld':return ['REPORT_EVIDENCE_WITHHELD']
    ids = claim.get('evidence_ids') or []
    rows = _rows(ids, report, store)
    if rows is None:return ['CLAIM_EVIDENCE_NOT_ELIGIBLE']
    period = claim.get('observation_period');geo = claim.get('geography')
    if period != report['observation_period']:return ['CLAIM_PERIOD_MISMATCH']
    if geo not in report['geographies']:return ['CONDITIONAL_SCOPE_MISMATCH']
    by_id = {r['id']: r for r in rows}
    if claim['kind'] == 'regional_ordering':
        left = by_id.get(claim.get('left_id'));right = by_id.get(claim.get('right_id'))
        if not left or not right or set(ids) != {left['id'], right['id']}:return ['REGIONAL_PAIR_INCOMPLETE']
        a, b = normalized(left), normalized(right)
        if (a['geography'] != geo or b['geography'] != claim.get('other_geography') or a['geography'] == b['geography']
                or b['geography'] not in report['geographies'] or a['period'] != period or b['period'] != period
                or a['metric'] != claim.get('metric') or signature(a, regional=True) != signature(b, regional=True)):
            return ['REGIONAL_PAIR_INCOMPATIBLE']
        delta = Decimal(a['value']) - Decimal(b['value'])
        direction = 'higher' if delta > 0 else 'lower' if delta < 0 else None
        if direction is None or claim.get('relative_direction') != direction:return ['REGIONAL_DIRECTION_MISMATCH']
        return []
    if claim['kind'] != 'conditional_scenario' or claim.get('rule') != 'takeup_up_vacancy_down':return ['CONDITIONAL_RULE_UNKNOWN']
    if claim.get('perspective') not in ['occupier_risk', 'landlord_opportunity']:return ['CONDITIONAL_PERSPECTIVE_UNKNOWN']
    pairs = [(metric, claim.get(metric + '_old_id'), claim.get(metric + '_new_id')) for metric in ['takeup', 'vacancy']]
    required = {identity for _, old, new in pairs for identity in [old, new]}
    if len(required) != 4 or set(ids) != required:return ['CONDITIONAL_PAIR_INCOMPLETE']
    if len({r['source_id'] for r in rows}) != 1:return ['CONDITIONAL_PUBLISHER_MISMATCH']
    periods = []
    for metric, old_id, new_id in pairs:
        old, new = by_id.get(old_id), by_id.get(new_id)
        if not old or not new or any(r['metric'] != metric or r['geography'] != geo for r in [old, new]):
            return ['CONDITIONAL_SCOPE_MISMATCH']
        calculation, errors = recompute_pair(old_id, new_id, report, store)
        if errors:return errors
        delta = Decimal(calculation['absolute_change'])
        if (metric == 'takeup' and delta <= 0) or (metric == 'vacancy' and delta >= 0):return ['CONDITIONAL_DIRECTION_MISMATCH']
        periods.append((old['period'], new['period']))
    if periods[0] != periods[1] or periods[0][1] != period:return ['CONDITIONAL_PERIOD_MISMATCH']
    return []


def recompute_pair(old_id, new_id, report, store):
    """Stored arithmetic is never authority over the source-bound observations."""
    from .chat_report import normalized
    from london_data.comparison import compare
    rows=_rows([old_id,new_id],report,store)
    if rows is None:return None,['CLAIM_EVIDENCE_NOT_ELIGIBLE']
    calculation=compare(normalized(rows[0]),normalized(rows[1]))
    saved=next((c for c in report['calculations'] if c.get('old_id')==old_id and c.get('new_id')==new_id),None)
    if calculation['status']!='comparable' or not saved or saved.get('status')!='comparable':return None,['COMPARISON_NOT_REPRODUCIBLE']
    for key in ['absolute_change','relative_change_pct']:
        expected=calculation.get(key);actual=saved.get(key)
        if expected is None:
            if actual is not None:return None,['SAVED_CALCULATION_MISMATCH']
        else:
            try:
                if Decimal(str(actual))!=Decimal(str(expected)):return None,['SAVED_CALCULATION_MISMATCH']
            except InvalidOperation:return None,['SAVED_CALCULATION_MISMATCH']
    if saved.get('change_unit')!=calculation['change_unit']:return None,['SAVED_CALCULATION_MISMATCH']
    if 'display' in saved and saved['display']!=calculation.get('display'):return None,['SAVED_CALCULATION_PRESENTATION_MISMATCH']
    for label,expected in [('metric',rows[1]['metric']),('geography',rows[1]['geography']),
        ('old_period',rows[0]['period']),('new_period',rows[1]['period'])]:
        if label in saved and saved[label]!=expected:return None,['SAVED_CALCULATION_SCOPE_MISMATCH']
    for side in ['old','new']:
        if side in saved:
            for key in ['id','source_id','metric','value','unit','period','geography','series','definition','basis','grade','method','currency']:
                if saved[side].get(key)!=calculation[side].get(key):return None,['SAVED_CALCULATION_SNAPSHOT_MISMATCH']
    return calculation,[]


def analysis_choices(report, store):
    """A deterministic proposal catalog. Nothing here is auto-published."""
    from .claim_binding import _bound, canonical
    result = []
    def add(claim, categories, classification='scenario'):
        digest = hashlib.sha256(json.dumps(claim, sort_keys=True).encode()).hexdigest()[:12]
        result.append(dict(candidate_id='c' + digest, categories=categories,
            finding=dict(text=canonical(claim), classification=classification, evidence_ids=claim['evidence_ids'], claims=[claim])))
    for chart in report['charts']:
        if chart['type'] != 'regional_comparison' or chart['status'] != 'ready':continue
        points = sorted(chart['points'], key=lambda p:p['geography'])
        for a, b in zip(points, points[1:]):
            delta = Decimal(a['value']) - Decimal(b['value'])
            if not delta:continue
            claim = dict(kind='regional_ordering', geography=a['geography'], other_geography=b['geography'],
                metric=chart['metric'], observation_period=report['observation_period'], left_id=a['fact_id'], right_id=b['fact_id'],
                evidence_ids=[a['fact_id'], b['fact_id']], relative_direction='higher' if delta > 0 else 'lower')
            if not validate_premises(claim, report, store):add(claim, ['key_findings'], 'inference')
    for calc in report['calculations']:
        old, new = store.get('facts', calc['old_id']), store.get('facts', calc['new_id'])
        if not old or not new:continue
        recalculated, errors=recompute_pair(old['id'],new['id'],report,store)
        if errors:continue
        delta = Decimal(recalculated['absolute_change'])
        claim = _bound(new, kind='change', old_id=old['id'], new_id=new['id'], old_observation_period=old['period'],
            direction='decrease' if delta < 0 else 'increase' if delta > 0 else 'unchanged')
        claim['evidence_ids'] = [old['id'], new['id']]
        add(claim, ['key_findings'], 'inference')
    for evidence in report['evidence']:
        if evidence.get('review_status')!='approved' or evidence.get('period')!=report['observation_period']:continue
        row=store.get('facts',evidence['id'])
        if row and _rows([row['id']],report,store) is not None:
            add(_bound(row),['key_findings'],'inference')
    for geo in report['geographies']:
        by_metric = {}
        for metric in ['takeup', 'vacancy']:
            by_metric[metric] = [c for c in report['calculations'] if (store.get('facts', c['new_id']) or {}).get('geography') == geo
                and (store.get('facts', c['new_id']) or {}).get('metric') == metric]
        for t in by_metric['takeup']:
            for v in by_metric['vacancy']:
                claim = dict(kind='conditional_scenario', rule='takeup_up_vacancy_down', geography=geo,
                    observation_period=report['observation_period'], takeup_old_id=t['old_id'], takeup_new_id=t['new_id'],
                    vacancy_old_id=v['old_id'], vacancy_new_id=v['new_id'], evidence_ids=[t['old_id'],t['new_id'],v['old_id'],v['new_id']])
                for perspective, category in [('occupier_risk','risks'),('landlord_opportunity','opportunities')]:
                    proposal = dict(claim, perspective=perspective)
                    if not validate_premises(proposal, report, store):add(proposal, [category])
    return result


def expand_choices(content, report, store):
    if not isinstance(content, dict):return content
    catalog = {c['candidate_id']:c for c in analysis_choices(report, store)}
    expanded = copy.deepcopy(content)
    for category in ['key_findings','risks','opportunities','outlook']:
        if not isinstance(expanded.get(category, []), list):continue
        for index, item in enumerate(expanded.get(category, [])):
            if not isinstance(item, dict) or 'candidate_id' not in item:continue
            if set(item) != {'candidate_id'}:raise ValueError('MODEL_CANDIDATE_EXTRA_FIELDS')
            selected = catalog.get(item['candidate_id'])
            if not selected or category not in selected['categories']:raise ValueError('MODEL_CANDIDATE_NOT_ELIGIBLE')
            expanded[category][index] = copy.deepcopy(selected['finding'])
    return expanded
