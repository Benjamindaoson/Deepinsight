"""Deterministic per-finding verification. The model proposes; only this code disposes.

A finding enters a report's conclusions only when every check passes:
evidence IDs exist and are in scope, numbers match cited disclosures exactly,
geography/period terms match the cited records, and the text never asserts
approval, coverage or acquisition state that belongs to the system alone.
"""
import re
from decimal import Decimal, InvalidOperation
from .normalization import current_fact
from .qa_context import verified
from .store import now

VERSION = 'finding-verifier-v3-state-assertions'

AREAS = ['City', 'West End', 'Canary Wharf', 'Midtown / Fringe', 'Midtown', 'Fringe',
         'Central London', 'London', 'United Kingdom']
AUTHORITY = re.compile(r'已审核|已批准|已确认|已核验|审核通过|人工复核通过|\bapproved\b|\bverified\b|\bhuman[- ]reviewed\b', re.I)
COVERAGE = re.compile(r'全部覆盖|完整覆盖|没有缺口|无缺口|覆盖所有|所有指标|fully covered|complete coverage|no (?:data )?gaps?|all metrics', re.I)
SOURCE_COUNT = re.compile(r'\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:个|家|条)?\s*(?:来源|机构|sources?|publishers?)\b', re.I)
CAUSAL = re.compile(r'caus|because|driv[ei]|led to|resulted in|due to|导致|由于|原因是|带来|使得|归因于', re.I)
MULTIPLIER = re.compile(r'\b(doubl\w*|tripl\w*|quadrupl\w*|halv\w*)\b|翻番|翻倍|减半', re.I)
NUMBER = re.compile(r'-?\d+(?:\.\d+)?')
PERIOD_TOKEN = re.compile(r'20\d{2}\s*Q[1-4]|Q[1-4]\s*20\d{2}', re.I)
DIRECTION = re.compile(r'\b(rise|rises|risen|rising|rose|increas\w*|growth|grew|fall|falls|fallen|falling|fell|declin\w*|decreas\w*|tighten\w*|shrink\w*|stable|flat)\b|上涨|上升|增长|下降|降低|减少|持平|稳定', re.I)
UP = re.compile(r'\b(rise|rises|risen|rising|rose|increas\w*|growth|grew|tighten\w*)\b|上涨|上升|增长', re.I)
DOWN = re.compile(r'\b(fall|falls|fallen|falling|fell|declin\w*|decreas\w*|shrink\w*)\b|下降|降低|减少', re.I)
FLAT = re.compile(r'\b(stable|flat)\b|持平|稳定', re.I)


def _quantities(text):
    scrubbed = re.sub(r'https?://\S+', '', str(text))
    scrubbed = PERIOD_TOKEN.sub(' ', scrubbed)
    scrubbed = re.sub(r'\b20\d{2}\b', ' ', scrubbed)
    return NUMBER.findall(scrubbed)


def _periods(text):
    found = []
    for token in PERIOD_TOKEN.findall(str(text)):
        match = re.search(r'(20\d{2})\s*Q([1-4])|Q([1-4])\s*(20\d{2})', token)
        found.append((match[1] or match[4]) + 'Q' + (match[2] or match[3]))
    return found


def _decimal_set(values):
    parsed = []
    for value in values:
        if value in [None, '']:
            continue
        try:
            parsed.append(Decimal(str(value).replace(',', '')))
        except InvalidOperation:
            continue
    return parsed


def verify_finding(item, report, store, origin='model_interpretation', category=None):
    """Return verification metadata for one finding; never raises on content."""
    reasons = []
    text = str((item or {}).get('text') or '')
    ids = list((item or {}).get('evidence_ids') or [])
    classification = (item or {}).get('classification')
    deterministic = origin == 'deterministic'
    if classification not in ['fact', 'calculation', 'inference', 'scenario']:
        reasons.append('CLASSIFICATION_UNKNOWN')
    if not deterministic and classification in ['fact', 'calculation']:
        reasons.append('MODEL_FACT_PROMOTION_BLOCKED')
    report_evidence = {e['id'] for e in report.get('evidence', [])}
    facts, events = [], []
    if not ids and not deterministic:
        reasons.append('EVIDENCE_MISSING')
    for identity in ids:
        fact = store.get('facts', identity)
        event = None if fact else store.get('events', identity)
        row = fact or event
        if not row or row.get('status') in ['rejected', 'superseded'] or row.get('human_review_status') == 'rejected':
            reasons.append('EVIDENCE_ID_UNKNOWN')
            continue
        if identity not in report_evidence:
            reasons.append('EVIDENCE_OUTSIDE_REPORT')
        (facts if fact else events).append(current_fact(fact) if fact else event)
    bindings=[];state_checks=[];state_only=False
    if not deterministic:
        from .claim_binding import bind_finding
        binding=bind_finding(item,report,store)
        reasons.extend(binding['reasons']);bindings=binding['claims']
        state_checks=binding.get('state_checks',[])
        state_only=bool(bindings) and all(c['kind']=='state_assertion' for c in bindings)
    if not deterministic:
        # The model never decides system state. It may only reference it.
        if AUTHORITY.search(text) and not state_only:
            reasons.append('AUTHORITY_STATUS_CLAIM')
        if COVERAGE.search(text) and not state_only:
            reasons.append('COVERAGE_CLAIM')
        if SOURCE_COUNT.search(text):
            reasons.append('SOURCE_COUNT_CLAIM')
        if MULTIPLIER.search(text):
            reasons.append('UNVERIFIED_MULTIPLIER_CLAIM')
    # Every quantity in the text must be an exact cited disclosure or a cited
    # deterministic calculation. Nothing may come from model memory.
    allowed = []
    for fact in facts:
        allowed += _decimal_set([fact.get('value'), fact.get('raw_value'), fact.get('normalized_value')])
    for event in events:
        allowed += _decimal_set([event.get('reported_value'), event.get('reported_change'), event.get('value')])
    cited = set(ids)
    comparisons = [c for c in report.get('calculations', []) if {c.get('old_id'), c.get('new_id')} <= cited]
    if not deterministic:
        for claim in bindings:
            if claim['kind']=='conditional_scenario' and category is not None:
                expected='risks' if claim.get('perspective')=='occupier_risk' else 'opportunities'
                if category!=expected:reasons.append('CONDITIONAL_CATEGORY_MISMATCH')
    for calc in comparisons:
        allowed += _decimal_set([calc.get('absolute_change'), calc.get('relative_change_pct')])
    if deterministic:
        allowed += _decimal_set([len(report.get('data_gaps', []))])
    unmatched = []
    for raw in _quantities(text):
        try:
            value = Decimal(raw)
        except InvalidOperation:
            unmatched.append(raw)
            continue
        if not any(value == candidate for candidate in allowed):
            unmatched.append(raw)
    if unmatched:
        reasons.append('QUANTITATIVE_CLAIM_MISMATCH')
    # Geography and period words must agree with the cited records.
    cited_geos = {f.get('geography') for f in facts} | {e.get('geography') for e in events}
    for area in AREAS:
        if re.search(r'(?<!\w)' + re.escape(area) + r'(?!\w)', text, re.I):
            if not any(g and (g == area or g.startswith(area + ' (') or
                              (area == 'Midtown / Fringe' and g in ['Midtown', 'Fringe']) or
                              (area == 'London' and 'London' in g)) for g in cited_geos):
                reasons.append('GEOGRAPHY_MISMATCH')
    cited_periods = {f.get('period') for f in facts} | {e.get('period') for e in events}
    for calc in comparisons:
        cited_periods |= {calc.get('old_period'), calc.get('new_period')}
    for period in _periods(text):
        if period not in cited_periods:
            reasons.append('PERIOD_MISMATCH')
            break
    if classification == 'fact' and facts and not all(verified(f) for f in facts):
        reasons.append('EVIDENCE_NOT_APPROVED')
    if classification == 'calculation' and not comparisons:
        reasons.append('CALCULATION_NOT_FOUND')
    if classification in ['inference', 'scenario'] and ids and not state_only:
        supported = any(verified(f) for f in facts) or any(
            e.get('classification') == 'publisher_reported_change' and
            e.get('evidence_validation') == 'exact_quote_in_hash_verified_original' for e in events)
        if not supported:
            reasons.append('EVIDENCE_NOT_APPROVED')
    if not deterministic and CAUSAL.search(text):
        attributed = any(e.get('classification') == 'publisher_reported_change' for e in events) and \
            re.search(r'reported|disclosed|披露|据.*(?:机构|发布)|publisher', text, re.I)
        if not attributed:
            reasons.append('CAUSAL_CLAIM_REQUIRES_REVIEW')
    # A direction claim must agree with a cited deterministic calculation or be
    # an explicitly attributed publisher-reported change. Text that contradicts
    # the authoritative system state is rejected, never silently rewritten.
    typed_direction=bool(bindings) and not reasons and all(c['kind'] in ['change','regional_ordering','conditional_scenario','observation'] for c in bindings)
    if not deterministic and DIRECTION.search(text) and not typed_direction:
        signed = []
        for calc in comparisons:
            for key in ['absolute_change', 'relative_change_pct']:
                try:
                    if calc.get(key) not in [None, '']:
                        signed.append(Decimal(str(calc[key])))
                except InvalidOperation:
                    continue
        if comparisons:
            if UP.search(text) and signed and not all(v > 0 for v in signed):
                reasons.append('DIRECTION_CONTRADICTS_CALCULATION')
            if DOWN.search(text) and signed and not all(v < 0 for v in signed):
                reasons.append('DIRECTION_CONTRADICTS_CALCULATION')
            if FLAT.search(text) and signed and not all(v == 0 for v in signed):
                reasons.append('DIRECTION_CONTRADICTS_CALCULATION')
        elif not any(e.get('classification') == 'publisher_reported_change' for e in events):
            reasons.append('DIRECTION_WITHOUT_COMPARISON')
    return dict(status='verified' if not reasons else 'rejected', reasons=list(dict.fromkeys(reasons)),bindings=bindings,
                state_checks=state_checks,checked_at=now(), verifier=VERSION, origin=origin)
