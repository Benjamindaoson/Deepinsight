"""Read-only publication from retrieved records; never repair or reuse model prose."""
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


def english_text(value):
    """Presentation only: retain original Unicode source data in storage."""
    value=str(value if value is not None else 'Not supplied')
    return re.sub(r'[\u3400-\u9fff\uf900-\ufaff]+', '[Non-English text; inspect original]', value)


def join_blocks(lines):
    """Keep Markdown table rows adjacent while separating prose paragraphs."""
    result='';previous=''
    for line in lines:
        result+=('' if not result else '\n' if line.startswith('|') and previous.startswith('|') else '\n\n')+line
        previous=line
    return result


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
                if table == 'facts' and row:
                    from .normalization import current_fact
                    row = current_fact(row)
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
                    source_document_sha256=doc.get('source_document_sha256') or doc['sha256'],
                    receipt_sha256=doc.get('receipt_sha256'), provenance_kind=doc.get('provenance_kind'),
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
    value = html.escape(english_text(value), quote=True)
    for char in ['\\', '`', '*', '_', '[', ']', '#', '|']:
        value = value.replace(char, '\\'+char)
    return value.replace('\n', ' ')


def render_groups(groups, omitted):
    """Only retrieved, currently traceable records; approval remains separate."""
    headings={'verified_fact':'Verified facts','publisher_reported_change':'Publisher-reported changes','pending_review':'Pending-review disclosures'}
    lines=[]
    for category,heading in headings.items():
        lines.append('## '+heading)
        if not groups[category]:lines.append('No eligible record was retrieved in this category.')
        for item in groups[category]:
            lines += ['Category: '+category,'### '+text(item.get('metric') or 'Source disclosure')+' / '+text(item.get('period')),
                'Area: '+text(item.get('geography'))+'; value: '+text(item.get('value'))+' '+text(item.get('unit')),
                'Review: '+text(item.get('human_review_status'))+'; record status: '+text(item.get('status')),
                'Definition: '+text(item.get('definition')), '> '+text(item.get('quote')),
                'Source: '+text(item.get('report_title'))+' | Published: '+text(item.get('published_at'))+' | '+str(item.get('url') or 'URL unavailable'),
                'Location: '+text(item.get('locator'))+' | Page: '+text(item.get('page'))+' | Evidence ID: '+text(item.get('id')),
                'Source document SHA-256: '+text(item.get('source_document_sha256'))]
            if item.get('receipt_sha256'):
                lines.append('Offline receipt SHA-256: '+text(item.get('receipt_sha256'))
                    +' | Publisher bytes are not redistributed; local integrity covers the receipt.')
            if category!='verified_fact':lines.append('This disclosure is not an approved market fact; it is not a system calculation or independent verification.')
    return lines


def render_safe_answer(groups, omitted, codes):
    lines=['Model draft withheld: insufficient evidence or failed claim verification.',
        'A model draft was generated, but its conclusions were not published. The records below are selected by deterministic checks; no additional model call or fact approval was made.',
        'Failure reasons: '+', '.join(codes)]
    lines += render_groups(groups,omitted)
    lines += ['Next step: inspect the cited original and resolve the listed review or comparability gaps before requesting another analysis.',
        'No investment judgment is released. Unknown rent denominators, combined geographies and incompatible periods remain unresolved.',
        f'{len(omitted)} retrieved record(s) could not be safely displayed. The draft and rejection reasons remain in the run audit record.']
    return '\n\n'.join(lines)


def project_report_result(result, report):
    """Describe the revalidated artifact, without releasing the raw model draft."""
    ai = report.get('ai_analysis') or {}
    accepted = len(ai.get('accepted') or [])
    published = (ai.get('status') == 'published' and accepted > 0
        and report.get('generation_status') in ['success', 'partial']
        and (report.get('publication_review') or {}).get('status') == 'evidence_checked')
    result['raw_draft_review'] = dict(result['publication_review'])
    lines=[]
    if published:
        lines=['## Evidence-grounded model findings']
        for finding in ai['accepted']:
            lines.append('- '+english_text(finding['text']))
            for evidence in report.get('evidence',[]):
                if evidence['id'] in finding.get('evidence_ids',[]):
                    lines.append('  Source: '+str(evidence.get('report_title'))+' | period '+str(evidence.get('period'))
                        +' | published '+str(evidence.get('published_at') or 'unknown')+' | '+str(evidence.get('locator'))
                        +' | '+str(evidence.get('url')))
        lines.append('These model-selected findings passed limited record-level checks. They do not establish causality or constitute investment advice.')
    else:
        lines=['## Evidence limitations', 'No model interpretation passed the publication checks for this request. The draft was withheld.']
    if report.get('market_snapshot'):
        lines += ['## Available source disclosures',
            '| Area | Metric | Period | Disclosed value | Review |','|---|---|---|---|---|']
        for row in report['market_snapshot'][:8]:
            lines.append('| '+' | '.join(english_text(row.get(k)) for k in ['geography','metric','period','value'])+' '+english_text(row.get('unit'))+' | '+english_text(row.get('review_status'))+' |')
        for evidence in report['evidence'][:8]:
            lines.append('Source: '+english_text(evidence.get('report_title'))+' | published '+str(evidence.get('published_at') or 'unknown')
                +' | '+english_text(evidence.get('locator'))+' | '+str(evidence.get('url')))
        lines.append('Pending observations are attributed source disclosures, not approved market conclusions. Unknown rent time denominators cannot support annual comparisons.')
    if report.get('data_gaps'):
        lines += ['## Missing evidence']+[f"- {english_text(g.get('geography'))} / {english_text(g.get('metric'))}: {english_text(g.get('reason'))}" for g in report['data_gaps'][:8]]
    lines += [english_text(x) for x in report.get('limitations',[])[:3]]
    lines.append('Next step: review the cited original definitions and obtain matching evidence for the missing period or measure. No missing quantity or forecast has been invented.')
    result['answer']=join_blocks(lines)
    result['outcome']='ANSWERED' if published and report['generation_status']=='success' else 'PARTIALLY_ANSWERED' if published or report.get('market_snapshot') else 'INSUFFICIENT_EVIDENCE'
    result['answer_origin'] = 'ai_limited_checks' if published else 'deterministic_evidence_fallback'
    result['publication_review'] = dict(status='limited_checks_passed' if published else 'withheld',
        semantic_approval=False, codes=[] if published else result['publication_review'].get('codes', []),
        scope='revalidated_report_findings')
    result['report_id'] = report['report_id']
    return result


def project_run(run, store):
    from .analysis_guard import review_analysis
    if run.get('agent_id') != 'london-market-agent' or run.get('status') != 'COMPLETED' or not isinstance(run.get('content'), str) or not run['content'].strip():
        raise ValueError('FINAL_ANSWER_MISSING: only completed London Market Runs can be published')
    packs=retrieved_packs(run.get('tools'))
    result = review_analysis(run['content'], store, evidence_packs=packs)
    report_id=next((p.get('report_id') for p in packs if p.get('report_id')),None)
    if report_id:
        from .chat_report import read_report
        report=read_report(store,report_id)
        # Free-form model JSON is an unpublished draft even when a lexical
        # checker misses its claim. Only the deterministic artifact is released.
        project_report_result(result, report)
    else:
        # Legacy runs have no typed report to verify. Render only current
        # source records; unknown model prose is never an affirmative answer.
        groups,omitted=safe_evidence(store,packs)
        result['answer']='\n\n'.join(render_groups(groups,omitted))
        result['answer_origin']='deterministic_evidence_fallback'
        result['publication_review'].update(status='withheld',semantic_approval=False)
    # Raw content remains in the native Run; do not send it to the presentation layer.
    result.pop('raw_answer', None)
    return dict(result, run_id=run['run_id'], session_id=run.get('session_id'), projection_only=True)
