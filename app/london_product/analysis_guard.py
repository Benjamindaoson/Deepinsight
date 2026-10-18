"""Conservative publication checks, not semantic approval or a fact correction engine.

Raw model answers remain immutable audit material. Flagged drafts are withheld in
full: removing a sentence alone could leave its unsupported causal conclusions.
The small rule set deliberately also flags some correctly qualified statements;
only human review can authorize those. Deterministic comparisons remain separate.
"""
import hashlib
import html
import re

VERSION = 'publication-guard-v5-directional'
HEADING = '## Optional AI interpretation — REVIEW_REQUIRED'

# Hard codes mean the draft makes a claim we cannot let through in any form.
HARD_CODES = {'LEASE_STATUS_QUANTITY', 'UNVERIFIED_PLANNING_STATUS', 'MODEL_SOURCE_COUNT',
              'NO_VERIFIABLE_RETRIEVED_EVIDENCE'}
# Soft codes are acceptable only when a deterministic series for the *same*
# metric exists, so a reader can check the stated direction against data.
SOFT_CODES = {'UNVERIFIED_MARKET_TREND', 'UNVERIFIED_INDICATOR_TREND', 'NO_VERIFIED_FACTS'}

PROSE_METRICS = {
    'rent': ('rent', '租金'),
    'vacancy': ('vacancy', '空置'),
    'availability': ('availability', '可用率'),
    'takeup': ('take-up', 'take up', 'takeup', '吸纳', '成交'),
    'supply': ('supply', '供应'),
    'prelet': ('pre-let', 'prelet', '预租'),
    'interest_rate': ('interest rate', 'bank rate', '利率'),
    'employment': ('employment', '就业'),
    'inflation_rate': ('inflation', '通胀', 'cpih', 'cpi '),
}


def prose_metrics(prose):
    lowered = prose.lower()
    return {metric for metric, words in PROSE_METRICS.items() if any(word in lowered for word in words)}


DIRECTIONAL_BANNER = ('## 倾向性判断（AI 生成 · 未经人工复核）',
    '以下为模型基于本次检索证据给出的**倾向性判断**，不是已确认的市场变化，不得作为决策依据。'
    '确定性计算与完整证据见本回答后续部分。')


def source_inventory(store):
    documents = store.all('documents')
    facts = [f for f in store.all('facts') if f.get('status') != 'superseded']
    events = [e for e in store.all('events') if e.get('status') != 'superseded' and e.get('kind') != 'source_update']
    return dict(registered_source_entries=len(store.all('sources')),
        entries_with_saved_documents=len({d['source_id'] for d in documents if d.get('source_id')}),
        saved_document_snapshots=len(documents),
        distinct_saved_urls=len({d['url'] for d in documents if d.get('url')}),
        active_fact_event_source_entries=len({x['source_id'] for x in facts+events if x.get('source_id')}))


def event_context(event, store):
    """Return an exact contiguous excerpt including preceding transaction qualifiers."""
    doc = store.get('documents', event.get('document_id', '')) or {}
    quote = (event.get('evidence') or {}).get('quote') or event.get('summary', '')
    for segment in doc.get('segments', []):
        text = segment.get('text', '')
        at = text.find(quote) if quote else -1
        if at < 0:
            continue
        # Previous sentence is crucial for 'The transactions total ...'. Never
        # invent a quantity split between pre-let and under-offer floors.
        prefix = text[:at].rstrip()
        previous = re.search(r'[^.!?。]+[.!?。]?$', prefix)
        start = previous.start() if previous else at
        excerpt = text[start:at+len(quote)].strip()
        return dict(quote=excerpt, locator=segment.get('locator'), page=segment.get('page'),
            document_id=doc.get('id'), document_sha256=doc.get('sha256'),
            url=doc.get('url'), published_at=doc.get('published_at'), status=event.get('status', 'needs_review'))
    return dict(quote=quote, locator=(event.get('evidence') or {}).get('locator'),
        document_id=doc.get('id'), document_sha256=doc.get('sha256'), url=doc.get('url'),
        published_at=doc.get('published_at'), status='needs_review', context_missing=True)


def review_analysis(raw, store, evidence_packs=None):
    raw = str(raw or '')
    # Strip URLs before pattern checks: years/slugs must not count as quantities.
    prose = re.sub(r'https?://\S+', '', raw).replace('**', '')
    codes = []
    if re.search(r'pre[\s‐‑–-]?let|under[\s-]+offer|预租|洽谈', prose, re.I) and re.search(r'\d[\d,.]*\s*(?:sq\s*ft|sq\.?\s*m|sqm|square|平方|%|per\s*cent)', prose, re.I):
        codes.append('LEASE_STATUS_QUANTITY')
    if re.search(r'supply|availability|供应|供给|可供', prose, re.I) and re.search(r'contract|declin|decreas|tighten|shrink|fell|fallen|increas|grew|growth|扩张|收缩|下降|降低|降至|减少|上升|增长|收紧', prose, re.I):
        codes.append('UNVERIFIED_MARKET_TREND')
    if re.search(r'rent|租金|空置率|vacancy|take.up|成交', prose, re.I) and re.search(r'rose|risen|increas|growth|grew|fell|declin|stable|上涨|上升|增长|下降|稳定|改善', prose, re.I):
        codes.append('UNVERIFIED_INDICATOR_TREND')
    if re.search(r'planning|city plan|规划', prose, re.I) and re.search(r'approved|adopted|permission granted|批准|获批|已采纳|确定性', prose, re.I):
        codes.append('UNVERIFIED_PLANNING_STATUS')
    if re.search(r'source\s+count|\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:(?:unique|distinct|saved|different)\s+)*(?:sources?|publishers?|urls?)\b|来源数量|来源总数|[\d一二三四五六七八九十]+\s*(?:个|家|条)?\s*(?:来源|机构)', prose, re.I):
        codes.append('MODEL_SOURCE_COUNT')
    inventory = source_inventory(store)
    from .safe_answer import safe_evidence, render_safe_answer, render_groups
    from . import directional
    groups, omitted = safe_evidence(store, evidence_packs)
    # A completed native response with no verifiable retrieved evidence must
    # still answer honestly, without promoting ungrounded prose.
    if evidence_packs is not None and not any(groups.values()):
        codes.append('NO_VERIFIABLE_RETRIEVED_EVIDENCE')
    elif evidence_packs is not None and not groups['verified_fact']:
        codes.append('NO_VERIFIED_FACTS')
    hard = [c for c in codes if c in HARD_CODES]
    soft = [c for c in codes if c in SOFT_CODES]
    assessment = directional.assess(store)
    directional_block = directional.render(assessment)
    mentioned = prose_metrics(prose)
    corroborating = [s for s in assessment.get('series', []) if s.get('metric') in mentioned]
    lines = []
    if hard:
        # Unpublishable claim: keep the deterministic evidence fallback, but no
        # longer present "no data" when a computed direction exists.
        status = 'withheld'
        lines += [render_safe_answer(groups, omitted, codes)]
        if directional_block:
            lines += ['', directional_block]
    elif soft and corroborating:
        # Middle tier: publish the draft, explicitly provisional, next to the
        # deterministic computation a reader can check. Requires a same-metric
        # candidate pair, so a claim about a metric with no series is withheld.
        status = 'directional_published'
        lines += [DIRECTIONAL_BANNER[0], DIRECTIONAL_BANNER[1], raw]
        lines += ['', '### 发布检查说明',
                  '草稿包含未经人工复核的趋势表述（' + ', '.join(soft) + '），因此仅以“倾向性判断”发布，未被认定为已确认事实。'
                  '可核验部分仅为与草稿指标一致的确定性序列：' + ', '.join(sorted({s['metric'] for s in corroborating})) + '。'
                  '本回答没有批准任何数据，状态仍为 REVIEW_REQUIRED。']
        if directional_block:
            lines += ['', directional_block]
        lines += [''] + render_groups(groups, omitted)
    elif soft:
        status = 'withheld'
        lines += [render_safe_answer(groups, omitted, codes + ['NO_COMPARABLE_CANDIDATE_PAIR'])]
        if directional_block:
            lines += ['', directional_block]
    else:
        status = 'limited_checks_passed'
        lines += [raw, 'Publication checks: limited_checks_passed; this is not semantic or human approval. REVIEW_REQUIRED.']
        if directional_block:
            lines += ['', directional_block]
    lines += ['', '### Saved evidence inventory (computed; not the number of citations in this answer)',
        f"- Registered source entries: {inventory['registered_source_entries']}",
        f"- Entries with saved documents: {inventory['entries_with_saved_documents']}",
        f"- Saved document snapshots: {inventory['saved_document_snapshots']}",
        f"- Distinct saved URLs: {inventory['distinct_saved_urls']}",
        f"- Source entries contributing active facts/events: {inventory['active_fact_event_source_entries']}"]
    return dict(answer='\n\n'.join(lines), raw_answer=raw,
        raw_sha256=hashlib.sha256(raw.encode()).hexdigest(), quality_status='REVIEW_REQUIRED',
        answer_origin=('deterministic_evidence_fallback' if status == 'withheld'
                       else 'ai_directional_unreviewed' if status == 'directional_published'
                       else 'ai_limited_checks'),
        safe_evidence=groups, omitted_evidence=omitted,
        directional=assessment,
        publication_review=dict(version=VERSION, status=status,
            codes=codes, hard_codes=hard, soft_codes=soft,
            fallback_published=status == 'withheld', directional_published=status == 'directional_published',
            semantic_approval=False, human_review_complete=False), source_inventory=inventory)


def reviewed_result(result, store):
    return dict(result, **review_analysis(result.get('raw_answer', result.get('answer', '')), store, result.get('evidence_packs')))


def report_view(row, store, format):
    """Project an old report safely on read; never rewrite stored reports or Runs."""
    markdown = row['markdown']
    if HEADING not in markdown:
        return row[format]
    before, original = markdown.split(HEADING, 1)
    job = store.get('jobs', row.get('analysis_id') or '') or {}
    result = job.get('result') or {}
    raw = result.get('raw_answer', result.get('answer'))
    if raw is None:
        raw = original.split('Native analysis Run:', 1)[0].strip()
    reviewed = review_analysis(raw, store, result.get('evidence_packs'))
    run_line = 'Native analysis Run:'+original.split('Native analysis Run:', 1)[1] if 'Native analysis Run:' in original else 'Native analysis Run: unavailable'
    markdown = before+HEADING+'\n\n'+reviewed['answer']+'\n\n'+run_line+'\n\nRaw analysis SHA-256: '+reviewed['raw_sha256']
    if format == 'markdown':
        return markdown
    return '<!doctype html><html lang="en"><meta charset="utf-8"><title>London market reviewed report</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>London market reviewed report</h1><pre>'+html.escape(markdown)+'</pre></html>'
