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
from decimal import Decimal

from .qa_context import verified

VERSION = 'directional-v1'

# Direction of the number is not the direction of the market. Keep both.
SIGNAL = {
    'rent': ('firmer', 'softer', '租金'),
    'vacancy': ('looser', 'tighter', '空置'),
    'availability': ('looser', 'tighter', '可用'),
    'takeup': ('stronger', 'weaker', '成交'),
    'supply': ('more_pipeline', 'less_pipeline', '供应'),
    'prelet': ('more_pipeline', 'less_pipeline', '预租'),
    'prelet_share': ('more_pipeline', 'less_pipeline', '预租占比'),
    'grade_a_share': ('higher_share', 'lower_share', 'A 级占比'),
    'interest_rate': ('tighter_money', 'looser_money', '利率'),
    'inflation_rate': ('higher', 'lower', '通胀'),
    'inflation_cpih': ('higher', 'lower', '通胀'),
    'employment': ('stronger', 'weaker', '就业'),
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
    facts = [
        f for f in store.all('facts')
        if f.get('status') not in ['rejected', 'superseded']
        and f.get('human_review_status') != 'rejected'
        and (f.get('metric') != 'rent' or f.get('annualization') in ('explicit', 'industry_convention'))
        and _value(f) is not None
    ]
    groups = {}
    for fact in facts:
        groups.setdefault(_group_key(fact), []).append(fact)

    series = []
    for (metric, geography, definition, unit), rows in groups.items():
        rows = sorted(rows, key=period_order)
        # Deduplicate the same period; a later collection replaces nothing.
        by_period = {}
        for row in rows:
            by_period.setdefault(row.get('normalized_period') or row.get('period'), row)
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
                    summary='没有同一口径、同一地域、可排序的两期候选记录，无法给出方向性判断。')

    reviewed = sum(s['basis'] == 'human_approved' for s in series)
    upside = [s for s in series if s['direction'] == 'up']
    downside = [s for s in series if s['direction'] == 'down']
    if len(upside) and len(downside):
        stance = '混合'
    elif len(upside):
        stance = '偏上行'
    elif len(downside):
        stance = '偏下行'
    else:
        stance = '基本持平'
    core = [s for s in series if s['metric'] in ['rent', 'vacancy', 'takeup']]
    summary = (
        f"候选记录显示{stance}：{len(core)} 组核心指标中有 {len([s for s in core if s['direction']=='up'])} 组上行、"
        f"{len([s for s in core if s['direction']=='down'])} 组下行、{len([s for s in core if s['direction']=='flat'])} 组基本持平。"
        f"以上均基于未审核候选记录（{len(series)-reviewed}/{len(series)} 组未获人工批准），不构成已确认的市场变化。"
    )
    return dict(version=VERSION, status='available', series=series,
                reviewed_series=reviewed, candidate_series=len(series) - reviewed,
                stance=stance, summary=summary)


def render(assessment, lang='zh'):
    """Render the assessment as a Markdown section. Deterministic text only."""
    if not assessment or assessment.get('status') != 'available':
        return ''
    lines = ['## 方向性判断（确定性计算 · 未经人工复核）', assessment['summary'], '',
             '| 指标 | 地域 | 对比期 | 变化 | 方向 | 依据记录 | 审核状态 |', '|---|---|---|---|---|---|---|']
    for s in assessment['series'][:12]:
        change = s['absolute_change']
        unit = s['change_unit'] or ''
        pct = s['relative_change_pct']
        shown = f"{change} {unit}" if unit else change
        if pct and unit not in ['pp', 'percent']:
            shown += f"（{pct}%）"
        arrow = {'up': '↑', 'down': '↓', 'flat': '→'}[s['direction']]
        periods = f"{s['from_period']} → {s['to_period']}"
        state = '已人工审核' if s['basis'] == 'human_approved' else '待审核'
        lines.append(f"| {s['metric_label']} | {s['geography'] or '未标注'} | {periods} | "
                     f"{shown} {arrow} {s['signal']} | {arrow} {s['direction']} | "
                     f"{', '.join(str(i)[:8] for i in s['fact_ids'])} | {state} |")
    lines += ['', '计算口径：同一 metric、同一地域、同一定义、同一归一化单位下，取最新两期候选记录做减法；'
              '空置率与利率按百分点，其余按相对变化。置信度：两点为 low，三点以上且同向为 medium。',
              '本段由 Python 计算，不使用模型生成文本，不代表审核通过，不得作为投资或决策依据。']
    return '\n'.join(lines)
