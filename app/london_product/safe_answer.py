"""Read-only publication from retrieved records; never repair or reuse model prose."""
import hashlib
import html
import json
from pathlib import Path
from urllib.parse import urlsplit


def retrieved_packs(tools):
    packs = []
    for tool in tools or []:
        if tool.get('tool_name') != 'search_market_evidence' or tool.get('tool_call_error'):
            continue
        try:
            pack = tool.get('result')
            pack = json.loads(pack) if isinstance(pack, str) else pack
            if isinstance(pack, dict):
                packs.append(pack)
        except (TypeError, ValueError):
            continue
    return packs


def safe_evidence(store, packs):
    from .analysis_guard import event_context
    from .qa_context import verified
    groups = dict(verified_fact=[], publisher_reported_change=[], pending_review=[])
    omitted = []; seen = set(); documents = {}
    for pack in packs or []:
        for key, table in [('facts', 'facts'), ('events', 'events'), ('publisher_reported_changes', 'events')]:
            for candidate in pack.get(key, []):
                if not isinstance(candidate, dict):
                    continue
                identity = candidate.get('id')
                if (table, identity) in seen:
                    continue
                seen.add((table, identity))
                row = store.get(table, identity or '')
                reason = None
                if not row or row.get('status') in ['rejected', 'superseded'] or row.get('human_review_status') == 'rejected':
                    reason = 'missing_rejected_or_superseded'
                # Check every retrieved business field that is present. A stale
                # or forged pack must not select a different fact by ID alone.
                elif any(candidate[k] != row.get(k) for k in ['value','unit','period','geography','definition','status','human_review_status','document_id','evidence','reported_value','reported_change'] if k in candidate):
                    reason = 'retrieved_record_mismatch'
                doc = store.get('documents', row.get('document_id', '')) if row else None
                source = store.get('sources', row.get('source_id', '')) if row else None
                if not doc or not source or source.get('allow_llm') is False:
                    reason = reason or 'source_or_document_unavailable'
                if reason:
                    omitted.append(dict(id=identity, reason=reason)); continue
                did = doc['id']
                if did not in documents:
                    try:
                        documents[did] = hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest() == doc.get('sha256')
                    except (OSError, KeyError):
                        documents[did] = False
                if not documents[did]:
                    omitted.append(dict(id=identity, reason='original_hash_unavailable_or_mismatch')); continue
                evidence = row.get('evidence') or {}
                if table == 'events' and row.get('classification') != 'publisher_reported_change':
                    evidence = event_context(row, store)
                quote = evidence.get('quote', '')
                matches = [s for s in doc.get('segments', []) if quote and quote in s.get('text', '') and
                    (not evidence.get('page') or s.get('page') == evidence['page'])]
                if not matches or evidence.get('context_missing') or len(quote) > 5000:
                    omitted.append(dict(id=identity, reason='quote_or_location_unverified')); continue
                segment = matches[0]
                # Original quotes are rendered verbatim as quotations, never as
                # paraphrased planning/lease status or a computed market trend.
                item = {k: row.get(k) for k in ['id','metric','period','geography','definition','value','unit','status','human_review_status']}
                item.update(quote=quote, document_id=did, document_sha256=doc['sha256'],
                    report_title=doc.get('title'), url=doc.get('url'), published_at=doc.get('published_at'),
                    page=segment.get('page'), locator=segment.get('locator'), retrieved_locator=evidence.get('locator'))
                category = 'pending_review'
                if row.get('classification') == 'publisher_reported_change' and row.get('evidence_validation') == 'exact_quote_in_hash_verified_original' and row.get('document_sha256') == doc['sha256'] and row.get('calculation_performed') is False:
                    category = 'publisher_reported_change'
                elif table == 'facts' and verified(row):
                    category = 'verified_fact'
                groups[category].append(item)
    return groups, omitted


def text(value):
    # Source text is data, not Markdown/HTML instructions or active links.
    value = html.escape(str(value if value is not None else '未披露'), quote=True)
    for char in ['\\', '`', '*', '_', '[', ']', '#', '|']:
        value = value.replace(char, '\\'+char)
    return value.replace('\n', ' ')


def render_groups(groups, omitted):
    """Render the retrieved evidence groups; shared by both publication tiers."""
    lines = []
    headings = [('verified_fact','已核验事实'), ('publisher_reported_change','机构披露变化'), ('pending_review','待审核的原始披露')]
    for category, heading in headings:
        lines.append('## '+heading)
        if not groups[category]:
            lines.append('本次检索没有可在此类别展示的记录。现有已核验数据不足以确认市场趋势。')
        for item in groups[category]:
            lines.append('### '+text(item.get('metric') or '来源原文')+' · '+text(item['period']))
            lines.append('分类：'+category+'；数据状态：'+text(item['status'])+'；人工审核：'+text(item['human_review_status'])+'。')
            if category=='publisher_reported_change':
                lines.append('仅转述机构原文，不是系统计算，不是已批准事实；未反推上期数值。')
            elif category=='pending_review':
                lines.append('待核实：仅展示来源披露，不用于正式变化计算或风险、机会结论。')
            lines.append('地域：'+text(item['geography'])+'；定义：'+text(item['definition'])+'；原记录数值：'+text(item['value'])+'；单位：'+text(item['unit'])+'。')
            lines.append('> '+text(item['quote']))
            url=item.get('url') or ''
            link='<'+url.replace('>','%3E').replace('<','%3C').replace(' ','%20')+'>' if urlsplit(url).scheme in ['http','https'] else 'URL 未核验'
            lines.append('来源：'+text(item['report_title'])+'；发布日期：'+text(item['published_at'])+'；'+link+'  \n'
                +'原文位置：'+text(item['locator'])+'；页码：'+text(item['page'])+'；引用定位：'+text(item['retrieved_locator'])+'  \n'
                +'记录 ID：'+text(item['id'])+'；文档 ID：'+text(item['document_id'])+'；SHA-256：'+text(item['document_sha256']))
    return lines


def render_safe_answer(groups, omitted, codes):
    lines = ['AI draft withheld — 现展示基于证据的安全回答',
        '原始 AI 草稿未通过发布检查，未发布其判断。以下由确定性代码整理本次检索证据；没有新增模型调用，没有批准任何数据。REVIEW_REQUIRED。',
        '拦截原因：'+', '.join(codes)]
    lines += render_groups(groups, omitted)
    lines += ['## 风险与机会 · 证据不足',
        '本回退没有重新生成投资、租赁或开发判断。单个披露值不能证明趋势、因果或租户支付溢价意愿。需要更多已核验、同口径证据才可作判断；不以模型常识补齐。',
        '## 口径与覆盖限制',
        '租金年度分母、空置率方法及季度成交口径未经确认时保持待核实。不同机构或统计时期不拼接为趋势；本回答没有执行数值比较。',
        '预租与洽谈中交易的合并面积不代表已签预租面积。规划受理、审查、撤回指令、拟采纳和正式批准并不等同；事件仅引用原文，不升级状态。',
        '仅覆盖本次实际检索且原件哈希、原文和记录一致的证据，不代表全市场或当前最新季度。未检索、缺失、已拒绝或无法复核的证据不展示。',
        f'无法安全展示的检索记录：{len(omitted)}。原始草稿及拦截原因仍保存在运行记录中。']
    return '\n\n'.join(lines)


def project_run(run, store):
    from .analysis_guard import review_analysis
    if run.get('agent_id') != 'london-market-agent' or run.get('status') != 'COMPLETED' or not isinstance(run.get('content'), str) or not run['content'].strip():
        raise ValueError('FINAL_ANSWER_MISSING: only completed London Market Runs can be published')
    result = review_analysis(run['content'], store, evidence_packs=retrieved_packs(run.get('tools')))
    # Raw content remains in the native Run; do not send it to the presentation layer.
    result.pop('raw_answer', None)
    return dict(result, run_id=run['run_id'], session_id=run.get('session_id'), projection_only=True)
