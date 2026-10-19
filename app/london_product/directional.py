"""Deterministic directional assessment — the middle publication tier.

The product historically had two outcomes: publish a fully checked answer, or
withhold everything. With no human-approved fact that meant every question was
answered with an evidence dump. This module adds the missing middle: a
*computed* statement of direction that never promotes a fact, never claims a
confirmed market change, and always names the records it compared.

Rules are intentionally narrow:
  * only saved observations with a numeric value are considered;
  * both sides must share metric, geography, definition and normalized unit;
  * periods must be orderable and different;
  * the result is labelled candidate / unreviewed everywhere;
  * no causal, forward-looking or investment language is generated here.
"""
import re
from decimal import Decimal, InvalidOperation

from .qa_context import verified

VERSION = 'directional-v2-series-identity'

# Direction of the number is not the direction of the market. Keep both.
SIGNAL = {
    'rent': ('firmer', 'softer', 'Rent'),
    'vacancy': ('looser', 'tighter', 'Vacancy'),
    'availability': ('looser', 'tighter', 'Availability'),
    'takeup': ('stronger', 'weaker', 'Leasing take-up'),
    'supply': ('more_pipeline', 'less_pipeline', 'Supply'),
    'prelet': ('more_pipeline', 'less_pipeline', 'Pre-let'),
    'prelet_share': ('more_pipeline', 'less_pipeline', 'Pre-let share'),
    'grade_a_share': ('higher_share', 'lower_share', 'Grade A share'),
    'interest_rate': ('tighter_money', 'looser_money', 'Interest rate'),
    'inflation_rate': ('higher', 'lower', 'Inflation'),
    'inflation_cpih': ('higher', 'lower', 'Inflation'),
    'employment': ('stronger', 'weaker', 'Employment'),
}

FLAT_BAND = {
    'vacancy': Decimal('0.05'),          # percentage points
    'availability': Decimal('0.05'),
    'interest_rate': Decimal('0.01'),
    'inflation_rate': Decimal('0.05'),
    'inflation_cpih': Decimal('0.05'),
    'employment': Decimal('0.05'),
}
DEFAULT_FLAT_BAND = Decimal('0.0001')


def _group_key(fact):
    return (
        fact.get('metric'),
        fact.get('normalized_geography') or fact.get('geography') or '',
        fact.get('definition') or '',
        fact.get('normalized_unit') or fact.get('unit') or '',
        *(fact.get(k) for k in ['source_id', 'series', 'method', 'basis', 'grade', 'currency']),
    )


def _value(fact):
    raw = fact.get('normalized_value')
    if raw in (None, ''):
        raw = fact.get('value')
    if raw in (None, ''):
        return None
    try:
        return Decimal(str(raw))
    except Exception:
        return None


def _period_rank(fact):
    from .qa_context import period_order
    return period_order(fact)


def _confidence(rows):
    """Low for two points, medium for a consistent run of three or more."""
    if len(rows) < 3:
        return 'low'
    signs = []
    for old, new in zip(rows, rows[1:]):
        delta = _value(new) - _value(old)
        signs.append((delta > 0) - (delta < 0))
    return 'medium' if len(set(signs)) == 1 else 'low'


def assess(store):
    """Return a directional assessment for every comparable candidate series."""
    from .qa_context import period_order
    from .normalization import current_fact
    facts=[]
    for fact in store.all('facts'):
        try:facts.append(current_fact(fact))
        except (ValueError,TypeError,InvalidOperation):
            # Malformed candidates cannot participate in arithmetic. Their
            # originals remain stored; report/state verification audits them.
            continue
    facts = [
        f for f in facts
        if f.get('status') not in ['rejected', 'superseded']
        and f.get('human_review_status') != 'rejected'
        and (f.get('metric') != 'rent' or f.get('annualization') == 'explicit')
        and _value(f) is not None
    ]
    groups = {}
    for fact in facts:
        if any(fact.get(k) in (None,'','unknown') for k in ['source_id','series','method','basis','grade','definition']):
            continue
        groups.setdefault(_group_key(fact), []).append(fact)

    series = []
    for key, rows in groups.items():
        metric, geography, definition, unit = key[:4]
        rows = sorted(rows, key=period_order)
        # Deduplicate the same period; a later collection replaces nothing.
        by_period = {}; conflicts = set()
        for row in rows:
            period = row.get('normalized_period') or row.get('period')
            if period in by_period and _value(by_period[period]) != _value(row):
                conflicts.add(period)
            by_period.setdefault(period, row)
        if conflicts:
            continue
        ordered = [by_period[p] for p in sorted(by_period, key=lambda p: period_order({'normalized_period': p}))]
        ordered = [r for r in ordered if _value(r) is not None]
        if len(ordered) < 2:
            continue
        old, new = ordered[-2], ordered[-1]
        old_period = old.get('normalized_period') or old.get('period')
        new_period = new.get('normalized_period') or new.get('period')
        if old_period == new_period:
            continue
        a, b = _value(old), _value(new)
        if a is None or b is None:
            continue
        delta = b - a
        band = FLAT_BAND.get(metric, DEFAULT_FLAT_BAND)
        direction = 'flat' if abs(delta) <= band else ('up' if delta > 0 else 'down')
        pct = None
        if a != 0:
            pct = (delta / a * 100).quantize(Decimal('0.01'))
        up_label, down_label, cn = SIGNAL.get(metric, ('higher', 'lower', metric))
        signal = 'flat' if direction == 'flat' else (up_label if direction == 'up' else down_label)
        series.append(dict(
            metric=metric, metric_label=cn, geography=geography, definition=definition,
            unit=unit, direction=direction, signal=signal,
            absolute_change=str(delta.quantize(Decimal('0.0001'))),
            relative_change_pct=None if pct is None else str(pct),
            change_unit='pp' if (unit or '') in ['percent', '%'] else (unit or ''),
            from_period=old.get('normalized_period') or old.get('period'),
            to_period=new.get('normalized_period') or new.get('period'),
            fact_ids=[old.get('id'), new.get('id')],
            periods=sorted({r.get('normalized_period') or r.get('period') for r in ordered}),
            points=len(ordered),
            confidence=_confidence(ordered),
            reviewed=verified(new) and verified(old),
            basis='candidate_observations_only' if not (verified(new) and verified(old)) else 'human_approved',
            assumption=old.get('annualization') or new.get('annualization'),
        ))

    series.sort(key=lambda s: (s['metric'] not in ['rent', 'vacancy', 'takeup'], s['metric'], s['geography']))

    if not series:
        return dict(version=VERSION, status='insufficient', series=[],
                    reviewed_series=0, candidate_series=0,
                    summary='Insufficient comparable two-period observations to determine direction.')

    reviewed = sum(s['basis'] == 'human_approved' for s in series)
    upside = [s for s in series if s['direction'] == 'up']
    downside = [s for s in series if s['direction'] == 'down']
    if len(upside) and len(downside):
        stance = 'mixed'
    elif len(upside):
        stance = 'upward'
    elif len(downside):
        stance = 'downward'
    else:
        stance = 'unchanged'
    core = [s for s in series if s['metric'] in ['rent', 'vacancy', 'takeup']]
    summary = (f"Saved candidate direction: {stance}. {len(core)} core series; "
        f"{len(series)-reviewed}/{len(series)} series lack human approval. "
        "Arithmetic differences are not confirmed market changes.")
    return dict(version=VERSION, status='available', series=series,
                reviewed_series=reviewed, candidate_series=len(series) - reviewed,
                stance=stance, summary=summary)


def render(assessment, lang='en'):
    """English presentation of deterministic candidate arithmetic."""
    if not assessment or assessment.get('status') != 'available':return ''
    lines=['## Candidate direction — deterministic calculation; human review required',assessment['summary'],
        '| Metric | Area | Periods | Change | Direction | Evidence IDs | Review |','|---|---|---|---|---|---|---|']
    for row in assessment['series'][:12]:
        state='Human reviewed' if row['basis']=='human_approved' else 'Pending review'
        lines.append(f"| {row['metric']} | {row['geography']} | {row['from_period']} to {row['to_period']} | {row['absolute_change']} {row.get('change_unit') or ''} | {row['direction']} | {', '.join(row['fact_ids'])} | {state} |")
    lines += ['Only compatible saved series are subtracted. Conflicting periods are excluded. This calculation does not approve a fact or establish a causal or investment conclusion.']
    return '\n'.join(lines)
