"""Deterministic question context: estimates are not provider usage or invoices."""
import hashlib
import json
import math
import re
from functools import lru_cache
from pathlib import Path


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), default=str)


def character_units(value):
    text = compact(value)
    ascii_count = sum(ord(c) < 128 for c in text)
    return math.ceil(ascii_count / 3 + (len(text) - ascii_count) * 2)


@lru_cache(maxsize=1)
def calibration():
    return json.loads(Path(__file__).with_name('qa-token-calibration.json').read_text(encoding='utf-8'))


def estimate_payload(payload, endpoint):
    config = calibration()
    if payload['model'] != config['model'] or str(endpoint).rstrip('/') != config['endpoint']:
        raise ValueError('TOKEN_ESTIMATOR_UNCALIBRATED')
    # All formatted request body fields count, including schemas and response
    # format. Headers are transport metadata, not tokens. No secret values logged.
    counted = {k: v for k, v in payload.items() if k not in ['extra_headers', 'extra_query']}
    units = character_units(counted)
    return dict(method='calibrated-character-envelope-v1',
        estimated_input_tokens=math.ceil(units * config['multiplier']) + 256,
        calibration_samples=len(config['samples']), multiplier=config['multiplier'],
        calibration_sha256=hashlib.sha256(compact(config).encode()).hexdigest(),
        payload_sha256=hashlib.sha256(compact(counted).encode()).hexdigest(),
        unicode_characters=len(compact(counted)),
        components={k: character_units(v) for k, v in counted.items()},
        limitation='Four provider-usage samples; historical tool schemas unavailable. Calibrated on message-only lower bounds, then applied to full payload with 25% margin and 256 framing reserve. Estimate, not exact tokenizer count.')


def compress_messages(messages, keep):
    """Shrink wire copies only, never mutate stored original tool results."""
    result = []; omitted = []
    for message in messages:
        clone = message.model_copy(deep=True)
        if clone.role == 'tool' and clone.tool_name == 'search_market_evidence':
            try:
                pack = json.loads(clone.content)
                facts = pack.get('facts', [])
                events = pack.get('events', [])
                omitted.extend(x.get('id') for x in facts[keep:] + events[1:])
                pack['facts'] = facts[:keep]; pack['events'] = events[:1]
                ids = {f.get('document_id') for f in pack['facts']}
                pack['documents'] = {k: v for k, v in pack.get('documents', {}).items() if k in ids}
                pack['topics'] = {k: [i for i in v if i in {f['id'] for f in pack['facts']}]
                                  for k, v in pack.get('topics', {}).items()}
                pack['context_compression'] = 'Whole records omitted for budget; not evidence of database-wide absence.'
                if 'coverage' in pack: pack['coverage']['selected_fact_records'] = len(pack['facts'])
                clone.content = compact(pack)
            except (ValueError, TypeError, AttributeError):
                pass
        result.append(clone)
    return result, omitted


TOPICS = {'rent': ('rent', '租金'), 'vacancy': ('vacancy', 'availability', '空置'),
          'takeup': ('take-up', 'takeup', 'leasing', '成交'),
          'supply': ('supply', '供应'), 'macro': ('macro', 'interest', 'inflation', '宏观', '利率', '通胀')}
METRIC_TOPIC = {'interest_rate': 'macro', 'inflation_cpih': 'macro', 'inflation_rate': 'macro', 'employment': 'macro',
                'availability': 'vacancy', 'prelet': 'supply', 'prelet_share': 'supply', 'grade_a_share': 'takeup'}


def verified(fact):
    return fact.get('status') in ['validated', 'approved'] and fact.get('human_review_status') == 'approved'


def period_order(fact):
    """Rank period spellings chronologically without changing the source label."""
    period = fact.get('normalized_period') or fact.get('period') or ''
    year = re.search(r'20\d{2}', period)
    quarter = re.search(r'Q([1-4])', period, re.I)
    return (int(year.group()) if year else 0, int(quarter.group(1)) if quarter else 0, period)


def evidence_pack(service, query, memo):
    from .analysis_guard import event_context
    permitted = {s['id'] for s in service.store.all('sources') if s.get('allow_llm', True)}
    candidates = [f for f in service.facts(limit=500)['items'] if f.get('source_id') in permitted
                  and f.get('status') not in ['rejected', 'superseded'] and f.get('human_review_status') != 'rejected']
    broad = bool(re.search(r'变化|风险|机会|changes|risks|opportunities|overview', query, re.I))
    requested = [k for k, words in TOPICS.items() if any(w in query.lower() for w in words)]
    topics = list(TOPICS) if broad or not requested else requested
    result = dict(facts=[], events=[], documents={}, topics={k: [] for k in topics},
        coverage=dict(saved_fact_records=len(candidates), selected_fact_records=0,
                      approved_fact_records=sum(verified(f) for f in candidates),
                      latest_saved_quarter=max([f.get('period','') for f in candidates if re.fullmatch(r'\d{4}Q[1-4]',f.get('period') or '')],default=None)),
        review_notice='Candidate observations are not confirmed trends. pending_review, needs_review and rejected are not approved. No change claim without approved compatible facts or explicit source attribution. Evidence is selected, not exhaustive; newer calendar quarters may be missing. Do not infer annual rent units, pre-let splits, approval decisions or causal explanations.')
    if not result['coverage']['approved_fact_records']:
        result['notice_code'] = 'NO_VERIFIED_EVIDENCE'
        result['answer_constraint'] = ('没有任何已人工批准的事实。已确认的市场变化必须写“无已核验事实”。'
            '可以给出方向性判断，但只能写在“倾向性判断（未审核）”标题下：必须说明依据的是未审核候选记录、不是已确认变化；'
            '同一指标至少两条相同地域、相同定义的候选记录才可比较方向；不得编造百分比或未返回的数值。风险和机会只能作为待验证假设。')
        from . import directional
        directional_assessment = directional.assess(service.store)
        result['directional_candidates'] = [
            {k: s.get(k) for k in ['metric', 'geography', 'from_period', 'to_period', 'direction', 'signal',
                                   'absolute_change', 'relative_change_pct', 'change_unit', 'confidence', 'basis', 'assumption']}
            for s in directional_assessment.get('series', [])][:8]
        result['directional_summary'] = directional_assessment.get('summary')
    from .publisher_changes import saved_reported_changes
    result['publisher_reported_changes'] = []
    if broad or 'takeup' in topics:
        for change in saved_reported_changes(service.store):
            if change['id'] in memo['events'] or change['source_id'] not in permitted:
                continue
            result['publisher_reported_changes'].append({k: change.get(k) for k in [
                'id', 'classification', 'period', 'comparison_period', 'geography', 'definition',
                'reported_value', 'reported_unit', 'reported_change', 'change_unit', 'calculation_performed',
                'human_review_status', 'status', 'evidence', 'document_id', 'document_sha256',
                'report_title', 'published_at', 'url', 'limitation']})
            break
    if result['publisher_reported_changes']:
        result['answer_constraint'] = ('没有已批准的可比数值，不可声称完成系统变化计算。可以单列“机构披露变化 (publisher_reported_change)”，'
            '按原文说明机构、时期、地域和变化，明确非系统计算、非独立核实、人审待完成。其他候选数字仍待核实；风险和机会须标 hypothesis，不推导前期数值。')
    seen = set(); selected = set(memo['facts']); skipped = 0
    for topic in topics:
        rows = [f for f in candidates if METRIC_TOPIC.get(f.get('metric'), f.get('metric')) == topic]
        regions = [name for name in ['City','West End','Canary Wharf','Midtown'] if name.lower() in query.lower()]
        if regions and topic != 'macro':
            rows = [f for f in rows if any(name.lower() in (f.get('geography') or '').lower() for name in regions)]
        rows.sort(key=lambda f: (verified(f), period_order(f), f.get('status')=='pending_review', bool((f.get('evidence') or {}).get('locator'))), reverse=True)
        limit = 2 if broad and topic in ['rent','vacancy','takeup'] else 1 if broad else 3
        for f in rows:
            if len(result['topics'][topic]) >= limit: break
            if f['id'] in selected: continue
            d = service.store.get('documents',f.get('document_id','')) or {}
            evidence = f.get('evidence') or {}
            signature = compact([d.get('sha256',d.get('id')),f.get('metric'),f.get('geography'),f.get('period'),f.get('value'),f.get('unit'),f.get('definition'),f.get('status'),evidence.get('quote')])
            if signature in seen: continue
            if not d.get('url') or not evidence.get('quote') or not evidence.get('locator') or len(evidence['quote']) > 700:
                skipped += 1; continue
            record = {k:f.get(k) for k in ['id','metric','geography','value','unit','period','status','definition','evidence','document_id','human_review_status','eligible_for_comparison']}
            record['candidate_only'] = not verified(f)
            new_doc = d['id'] not in result['documents']
            result['documents'][d['id']] = {k:d.get(k) for k in ['title','url','publisher','published_at']}
            result['facts'].append(record); result['topics'][topic].append(f['id'])
            if len(compact(result).encode()) > 8500:
                result['facts'].pop(); result['topics'][topic].pop()
                if new_doc: result['documents'].pop(d['id'])
                skipped += 1; continue
            seen.add(signature)
    if broad or re.search(r'event|news|事件|新闻',query,re.I):
        for e in service.store.all('events'):
            if len(result['events']) >= 1: break
            if e['id'] in memo['events'] or e.get('source_id') not in permitted or e.get('kind') in ['source_update','publisher_reported_change'] or e.get('status') in ['rejected','superseded'] or e.get('human_review_status')=='rejected': continue
            context = event_context(e,service.store)
            if context.get('context_missing') or len(context['quote']) > 1200: skipped += 1; continue
            d = service.store.get('documents', e.get('document_id','')) or {}
            record = dict(id=e['id'],title=e.get('title'),published_at=e.get('published_at'),status=e.get('status'),
                          human_review_status=e.get('human_review_status','pending_review'),
                          transaction_context=context,document_title=d.get('title'),candidate_only=not verified(e))
            result['events'].append(record)
            if len(compact(result).encode()) > 9800: result['events'].pop(); skipped += 1
    result['coverage'].update(selected_fact_records=len(result['facts']),omitted_incomplete_or_oversized=skipped)
    return result


def classify_error(error, error_type=''):
    value = str(error)
    if value in ['TOKEN_BUDGET','TOKEN_BUDGET_EXCEEDED','REQUEST_OR_TIME_BUDGET','PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED','TOKEN_ESTIMATOR_UNCALIBRATED']:
        return 'TOKEN_BUDGET_EXCEEDED'
    if value in ['DOCUMENT_DEADLINE','LATE_RESPONSE_REJECTED','MODEL_TIMEOUT'] or 'timeout' in (error_type+' '+value).lower(): return 'MODEL_TIMEOUT'
    if value in ['TOOL_ERROR','NO_VERIFIED_EVIDENCE','FINAL_ANSWER_MISSING']: return value
    if value in ['INCOMPLETE_MODEL_ANSWER','MODEL_MISSING_SAVED_CITATIONS']: return 'FINAL_ANSWER_MISSING'
    return 'PROVIDER_ERROR'
