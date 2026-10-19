"""Business operations; saved reads/calculations never invoke a model."""
import asyncio
import hashlib
import html
import json
import os
import re
import threading
import time
from decimal import Decimal,InvalidOperation
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from jinja2 import Environment, BaseLoader, select_autoescape
from .store import now, uid
from .analysis_guard import reviewed_result, event_context, report_view
from london_data.comparison import compare as strict_compare

DEFAULTS = dict(news_interval_hours=6, market_interval_hours=168, notifications_enabled=False,monitor_analysis_enabled=False,
                geographies=['Central London','City', 'West End', 'Canary Wharf', 'Midtown / Fringe'],
                metrics=['rent', 'vacancy', 'takeup', 'supply', 'interest_rate', 'employment'], monitoring_enabled=True,
                rent_threshold_pct=5.0, takeup_threshold_pct=10.0, vacancy_threshold_pp=0.5)


def _run_analysis_agent(agent, prompt):
    """Native query agents have async hooks; preserve scoped context across loops."""
    if not callable(getattr(agent,'arun',None)):
        return agent.run(prompt)  # Explicit synchronous adapters, including offline fixtures.
    async def execute():return await agent.arun(prompt)
    try:asyncio.get_running_loop()
    except RuntimeError:return asyncio.run(execute())
    # A synchronous service can also be called by an async host. Never nest an
    # event loop, and carry ACTIVE_REPORT and run-scoped budget contexts with it.
    from contextvars import copy_context
    context=copy_context()
    with ThreadPoolExecutor(max_workers=1,thread_name_prefix='market-analysis') as pool:
        return pool.submit(context.run,lambda:asyncio.run(execute())).result()


class MarketService:
    def __init__(self, store):
        self.store = store; self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='market-job')
        self._cache = {}; self._lock = threading.RLock(); self.schedule_manager = None
        self.workflow = None; self.agent_factory = None
        self.report_workflow=None
        self.extraction_locks={}
        self.analysis_lock=threading.Lock()
        self.notification_locks={}

    def settings(self):
        from .discovery import configuration
        data = self.store.get('settings', 'product')
        result = dict(DEFAULTS, **(data.get('values', {}) if data else {}))
        result.update(news_discovery=configuration(),notification_configured=bool(os.environ.get('LONDON_NOTIFICATION_URL')),
                      schedules=[s.to_dict() for s in self.schedule_manager.list() if s.name.startswith('london-')] if self.schedule_manager else [])
        return result

    def save_settings(self, values):
        allowed = set(DEFAULTS)
        if set(values) - allowed: raise ValueError('Unknown configuration field')
        for key in ['news_interval_hours', 'market_interval_hours']:
            if key in values and (isinstance(values[key], bool) or values[key] not in [1,2,3,4,6,8,12,24,168]):
                raise ValueError(key + ' supports 1,2,3,4,6,8,12,24 or 168 hours')
        for key in ['rent_threshold_pct','takeup_threshold_pct','vacancy_threshold_pp']:
            if key in values and (isinstance(values[key], bool) or not isinstance(values[key], (int,float)) or not 0 < values[key] <= 1000):
                raise ValueError('Threshold must be > 0 and <= 1000')
        for key in ['geographies', 'metrics']:
            if key in values and (not isinstance(values[key], list) or len(values[key]) > 30 or any(not isinstance(x, str) or len(x) > 100 for x in values[key])):
                raise ValueError('Invalid ' + key)
        for key in ['monitoring_enabled', 'notifications_enabled','monitor_analysis_enabled']:
            if key in values and not isinstance(values[key], bool): raise ValueError('Boolean required')
        prior = self.store.put('settings', 'product', dict(values=dict(DEFAULTS)))
        self.store.update('settings', prior['id'], dict(values=dict(prior['values'], **values)))
        if self.schedule_manager: self.sync_schedules()
        self.invalidate(); return self.settings()

    def sync_schedules(self):
        config = self.settings()
        for category, hours in [('news', config['news_interval_hours']), ('market', config['market_interval_hours'])]:
            cron = f'0 */{hours} * * *' if hours < 24 else ('0 7 * * *' if hours == 24 else '0 7 * * 1')
            schedule = self.schedule_manager.create(name='london-' + category, cron=cron,
                endpoint='/api/market/scheduled/' + category, payload={}, timeout_seconds=180, max_retries=1,
                retry_delay_seconds=60, if_exists='update')
            if config['monitoring_enabled']: self.schedule_manager.enable(schedule.id)
            else: self.schedule_manager.disable(schedule.id)
        for period, cron in [('daily','0 8 * * *'),('weekly','0 8 * * 1')]:
            schedule=self.schedule_manager.create(name='london-report-'+period,cron=cron,
                endpoint='/api/market/scheduled/report-'+period,payload={},timeout_seconds=60,max_retries=0,if_exists='update')
            if config['monitoring_enabled']:self.schedule_manager.enable(schedule.id)
            else:self.schedule_manager.disable(schedule.id)

    def recover_jobs(self):
        for job in self.store.all('jobs'):
            if job['status'] in ('running', 'queued'):
                self.store.update('jobs', job['id'], dict(status='interrupted', error='Service stopped before completion; retry available', finished_at=now()))
        for attempt in self.store.all('extractions'):
            if attempt.get('status')=='running':self.store.update('extractions',attempt['id'],dict(status='interrupted',finished_at=now()))
        for attempt in self.store.all('notifications'):
            if attempt.get('status')=='sending':self.store.update('notifications',attempt['id'],dict(status='delivery_unknown',error='Service stopped during delivery; inspect channel before resending',finished_at=now()))
        for event in self.store.all('events'):
            if event.get('kind')!='metric_change' or event.get('analysis_status')!='running':continue
            attempt=next((j for j in self.store.all('jobs') if j.get('kind')=='analysis'
                and j.get('report_id')==event.get('report_id')),None)
            self.store.update('events',event['id'],dict(analysis_status='interrupted',analysis_id=(attempt or {}).get('id'),
                notification_status='analysis_not_publishable'))

    def invalidate(self):
        with self._lock: self._cache.clear()

    def facts(self, **filters):
        limit = min(max(int(filters.pop('limit', 100)), 1), 500); offset = max(int(filters.pop('offset', 0)), 0)
        key = json.dumps([filters, limit, offset], sort_keys=True)
        with self._lock:
            cached = self._cache.get(key)
            if cached and time.monotonic() - cached[0] < 30: return dict(cached[1], cache_hit=True)
        def matches(f,k,v):
            if not v or v=='all':return True
            actual=str(f.get(k,''))
            if actual==str(v):return True
            # Search grouping only; source geography stays intact for strict comparisons.
            return k=='geography' and v in ['City','West End','Canary Wharf'] and actual.startswith(str(v)+' (')
        from .normalization import current_fact
        items = [current_fact(f) for f in self.store.all('facts') if f.get('status') != 'superseded']
        items = [f for f in items if all(matches(f,k,v) for k,v in filters.items())]
        data = dict(items=items[offset:offset+limit], total=len(items), updated_at=now(), cache_hit=False)
        with self._lock: self._cache[key] = (time.monotonic(), data)
        return data

    def overview(self):
        facts = self.facts(limit=500)['items']; events = [e for e in self.store.all('events') if e.get('kind')!='source_update' and e.get('status')!='superseded']
        import re
        def recent(f):
            period=f.get('normalized_period') or f.get('period') or ''
            q=re.fullmatch(r'(\d{4})Q([1-4])',period)
            return int(q[1])*4+int(q[2]) if q else -1
        groups={metric:sorted([f for f in facts if f.get('metric')==metric],key=recent,reverse=True) for metric in ['rent','vacancy','takeup']}
        # Interleave the latest core measures before secondary observations;
        # importing an older report must not displace the current market view.
        featured=[rows[i] for i in range(max([len(v) for v in groups.values()]+[0])) for rows in groups.values() if i<len(rows)]
        facts=featured+[f for f in facts if f.get('metric') not in groups]
        from . import directional
        from .structured_sources import current_event
        return dict(updated_at=now(), facts=facts, events=[current_event(e) for e in events[:12]], sources=self.store.all('sources'),
                    comparisons=self.store.all('comparisons')[:20], jobs=self.store.all('jobs')[:6],
                    directional=directional.assess(self.store),
                    counts=dict(facts=len(facts), events=len(events), documents=len(self.store.all('documents')),
                                reports=len(self.store.all('reports')),
                                validated=sum(f.get('status')=='validated' for f in facts),
                                needs_review=sum(f.get('status') != 'validated' for f in facts),
                                pending_human_review=sum(f.get('human_review_status')!='approved' for f in facts)))

    def evidence(self, fact_id):
        fact = self.store.get('facts', fact_id)
        if not fact: raise KeyError(fact_id)
        from .normalization import current_fact
        fact=current_fact(fact)
        doc = self.store.get('documents', fact['document_id'])
        return dict(fact=fact, document={k:doc.get(k) for k in ['id','title','url','published_at','collected_at','sha256','media']},
                    evidence=fact.get('evidence', {}), download_url='/api/market/documents/' + doc['id'] + '/file',
                    reviews=[r for r in self.store.all('reviews') if r.get('fact_id') == fact['id']],
                    approval=dict(eligible=self.review_eligibility(fact)['eligible'],
                                  blockers=self.review_eligibility(fact)['blockers']))

    def review_eligibility(self, fact):
        """What a human must resolve before this observation can be approved."""
        blockers = []
        if fact.get('status') in ['rejected', 'superseded']:
            blockers.append('RECORD_REJECTED_OR_SUPERSEDED')
        if fact.get('metric') == 'rent':
            from .normalization import derive
            if derive(fact)['annualization'] != 'explicit':
                blockers.append('RENT_ANNUAL_BASIS_UNRESOLVED')
        if fact.get('status') == 'needs_review':
            blockers.append('VALIDATION_FLAGS_PRESENT')
        if not (fact.get('evidence') or {}).get('quote'):
            blockers.append('NO_SOURCE_QUOTE')
        if not fact.get('document_id') or not self.store.get('documents', fact['document_id']):
            blockers.append('ORIGINAL_DOCUMENT_MISSING')
        # A reviewer note cannot supply a missing time denominator.
        soft = {'VALIDATION_FLAGS_PRESENT'}
        return dict(eligible=not [b for b in blockers if b not in soft],
                    blockers=blockers, requires_note=bool(blockers),
                    note_required_for=[b for b in blockers if b in soft])

    def rederive_facts(self):
        """Recompute derived fields for saved facts after a normalization change.

        Deterministic and idempotent: reads the stored raw value/unit, never the
        network or a model, and never touches human review decisions except to
        keep an approved fact validated.
        """
        from .normalization import derive
        changed = []
        for fact in self.store.all('facts'):
            if fact.get('status') in ['rejected', 'superseded']:
                continue
            patch = derive(fact)
            keys = ['normalized_value', 'normalized_unit', 'normalized_period',
                    'normalized_precision', 'annualization', 'annualization_assumption',
                    'normalization_notes', 'normalization_version']
            if not any(fact.get(k) != patch.get(k) for k in keys):
                continue
            numeric_ok = fact.get('value') is None or fact.get('precision') != 'unknown'
            annual_ok = fact.get('metric') != 'rent' or patch['annualization'] == 'explicit'
            complete = all(fact.get(k) not in [None, '', 'unknown']
                           for k in ['value', 'unit', 'geography', 'period', 'definition', 'basis', 'grade', 'method'])
            patch['status'] = ('validated' if fact.get('human_review_status') == 'approved' and annual_ok
                               else 'pending_review' if numeric_ok and annual_ok and complete
                               else 'needs_review')
            self.store.update('facts', fact['id'], patch)
            changed.append(fact['id'])
        self.invalidate()
        return dict(changed=len(changed), facts=len(self.store.all('facts')), ids=changed)

    def review_fact(self, identity, decision, reviewer, note=''):
        """Human decision on one saved observation. Every decision is audited."""
        if decision not in ['approve', 'reject', 'reopen']:
            raise ValueError('Unsupported review decision')
        fact = self.store.get('facts', identity)
        if not fact: raise KeyError(identity)
        eligibility = self.review_eligibility(fact)
        if decision == 'approve':
            hard = [b for b in eligibility['blockers'] if b != 'VALIDATION_FLAGS_PRESENT']
            if hard: raise ValueError('Cannot approve: ' + ', '.join(hard))
            if eligibility['requires_note'] and not note.strip():
                raise ValueError('A note is required to approve a flagged observation: ' + ', '.join(eligibility['blockers']))
            changes = dict(status='validated', human_review_status='approved', reviewed_by=reviewer,
                           reviewed_at=now(), review_note=note, eligibility_blockers=eligibility['blockers'])
        elif decision == 'reject':
            if not note.strip(): raise ValueError('A rejection reason is required')
            changes = dict(status='rejected', human_review_status='rejected', reviewed_by=reviewer,
                           reviewed_at=now(), review_note=note)
        else:
            changes = dict(status='pending_review', human_review_status='pending_review',
                           reviewed_by=reviewer, reviewed_at=now(), review_note=note)
        snapshot = hashlib.sha256(json.dumps(fact, sort_keys=True, default=str).encode()).hexdigest()
        record = self.store.put('reviews', uid(), dict(
            fact_id=fact['id'], decision=decision, reviewer=reviewer, note=note, at=now(),
            prior_status=fact.get('status'), prior_review_status=fact.get('human_review_status'),
            fact_snapshot_sha256=snapshot, annualization=fact.get('annualization'),
            blockers=eligibility['blockers']))
        updated = self.store.update('facts', fact['id'], changes)
        self.invalidate()
        return dict(fact=updated, review=record)

    def review_queue(self, status='pending'):
        from .normalization import current_fact
        facts = [current_fact(f) for f in self.store.all('facts') if f.get('status') != 'superseded']
        if status == 'pending':
            facts = [f for f in facts if f.get('human_review_status') not in ['approved', 'rejected']]
        elif status == 'approved':
            facts = [f for f in facts if f.get('human_review_status') == 'approved']
        elif status == 'rejected':
            facts = [f for f in facts if f.get('human_review_status') == 'rejected']
        rows = []
        for f in facts:
            e = self.review_eligibility(f)
            rows.append(dict(f, approval=dict(eligible=e['eligible'], blockers=e['blockers'], requires_note=e['requires_note'])))
        rows.sort(key=lambda f: (not f['approval']['eligible'], f.get('period') or ''))
        return dict(items=rows, total=len(rows),
                    counts=dict(pending=sum(1 for f in rows if f.get('human_review_status') not in ['approved','rejected']),
                                approved=sum(1 for f in rows if f.get('human_review_status') == 'approved'),
                                rejected=sum(1 for f in rows if f.get('human_review_status') == 'rejected')))

    def compare(self, old_id, new_id):
        a, b = [self.store.get('facts', i) for i in [old_id, new_id]]
        if not a or not b: raise KeyError('Fact not found')
        from .normalization import current_fact
        a,b=current_fact(a),current_fact(b)
        def inputs(f):
            return dict(f,value=f.get('normalized_value') if f.get('normalization_version') else f.get('value'),
                unit=f.get('normalized_unit') if f.get('normalization_version') else f.get('unit'),
                period=f.get('normalized_period') if f.get('normalization_version') else f.get('period'))
        result = strict_compare(inputs(a),inputs(b))
        result['raw_input_ids']=[a['id'],b['id']]
        if any(f.get('human_review_status', 'pending_review') != 'approved' for f in [a, b]):
            result.update(status='not_comparable', absolute_change=None, relative_change_pct=None, change_unit=None)
            result['reasons'].append('HUMAN_REVIEW_PENDING')
            result.pop('display', None)
        from .safe_answer import safe_evidence
        groups,_=safe_evidence(self.store,[dict(facts=[dict(id=a['id']),dict(id=b['id'])])])
        verified_ids={f['id'] for f in groups['verified_fact']}
        if {a['id'],b['id']}-verified_ids:
            result.update(status='not_comparable',absolute_change=None,relative_change_pct=None,change_unit=None)
            result['reasons'].append('EVIDENCE_NOT_VERIFIED')
            result.pop('display',None)
        key = hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()
        return self.store.put('comparisons', key, result)

    def monitor_changes(self, run_id=None, detection_context='scheduled_refresh'):
        """Threshold events on approved, comparable consecutive quarters.

        detection_context: 'scheduled_refresh' for live scheduled runs, or
        'historical_replay' when re-processing saved historical snapshots. A
        replay is always labelled; it is never presented as a new market move.
        """
        from .publisher_changes import discover_reported_changes
        reported = discover_reported_changes(self.store, run_id)
        # Do not reuse the UI's short-lived read cache for signal authority.
        from .normalization import current_fact
        facts=[];invalid_inputs=[]
        for f in self.store.all('facts'):
            if f.get('status') in ['superseded','rejected']:continue
            try:facts.append(current_fact(f))
            except (InvalidOperation,ValueError,TypeError):
                invalid_inputs.append(dict(status='invalid_observation',fact_ids=[f['id']],reason='NORMALIZATION_FAILED'))
        config=self.settings(); alerts=[]; refused=len(invalid_inputs);decisions=list(invalid_inputs)
        invalid_numeric_ids=set()
        for fact in facts:
            if fact.get('metric') not in ['rent','vacancy','takeup']:
                continue
            value=fact.get('normalized_value') if fact.get('normalization_version') else fact.get('value')
            try:
                number=Decimal(str(value))
                valid=number.is_finite() and number>=0 and (fact['metric']!='vacancy' or number<=100)
            except (InvalidOperation,TypeError,ValueError):
                valid=False
            if not valid:
                invalid_numeric_ids.add(fact['id'])
                decisions.append(dict(status='invalid_observation',fact_ids=[fact['id']],
                    reason='Invalid numeric observation; directional monitoring withheld.'))
                refused+=1
        from .safe_answer import safe_evidence
        grounded,_=safe_evidence(self.store,[dict(facts=facts)])
        eligible_ids={f['id'] for f in grounded['verified_fact']}-invalid_numeric_ids
        previous=[e for e in self.store.all('events') if e.get('kind')=='metric_change' and e.get('status')!='superseded']
        preferred_ids={i for e in previous for i in [e.get('old_id'),e.get('new_id')]}
        for event in previous:
            if event.get('old_id') not in eligible_ids or event.get('new_id') not in eligible_ids:
                self.store.update('events',event['id'],dict(status='superseded',signal_status='retracted',
                    superseded_reason='comparison_not_comparable',superseded_at=now()))
        groups={}
        for f in facts:
            if f['id'] not in eligible_ids:continue
            if f.get('metric') not in ['rent','vacancy','takeup'] or f.get('metric') not in config['metrics']:continue
            area=f.get('geography') or ''
            if not any(area==g or area.startswith(g+' (') or (g=='Midtown / Fringe' and area in ['Midtown','Fringe']) for g in config['geographies']):continue
            key=tuple(str(f.get(k)) for k in ['source_id','series','metric','geography','definition','basis','grade','method','currency'])
            key+=(str(f.get('normalized_unit') if f.get('normalization_version') else f.get('unit')),)
            groups.setdefault(key,[]).append(f)
        conflicting_ids=set()
        for rows in groups.values():
            periods={}
            for f in rows:
                p=(f.get('normalized_period') if f.get('normalization_version') else f.get('period')) or ''
                periods.setdefault(p,[]).append(f)
            rows=[]
            for p,candidates in sorted(periods.items()):
                try:
                    values={Decimal(str(f.get('normalized_value') if f.get('normalization_version') else f.get('value'))) for f in candidates}
                    valid=all(v.is_finite() and v>=0 and (candidates[0]['metric']!='vacancy' or v<=100) for v in values)
                except (InvalidOperation,TypeError,ValueError):values=set();valid=False
                if not valid or len(values)!=1:
                    conflicting_ids.update(f['id'] for f in candidates)
                    decisions.append(dict(status='conflicting_observations' if valid else 'invalid_observation',period=p,fact_ids=[f['id'] for f in candidates],
                        reason='Approved same-period values disagree; directional monitoring withheld.' if valid else 'Invalid numeric observation; directional monitoring withheld.'))
                    refused+=1;continue
                # Keep an existing eligible representative so an identical
                # disclosure does not produce a new event or notification.
                rows.append(min(candidates,key=lambda f:(f['id'] not in preferred_ids,f['id'])))
            for old,new in zip(rows,rows[1:]):
                result=self.compare(old['id'],new['id'])
                decision=dict(old_id=old['id'],new_id=new['id'],comparison_id=result['id'],status=result['status'])
                decisions.append(decision)
                signal_identity=hashlib.sha256(('metric_change:'+old['id']+':'+new['id']).encode()).hexdigest()
                def active_events():
                    return [event for event in self.store.all('events')
                        if event.get('kind')=='metric_change' and event.get('status')!='superseded'
                        and event.get('old_id')==old['id'] and event.get('new_id')==new['id']]
                def retire(reason):
                    for event in active_events():
                        self.store.update('events',event['id'],dict(status='superseded',
                            signal_status='retracted',superseded_reason=reason,superseded_at=now()))
                if result['status']!='comparable':
                    retire('comparison_not_comparable');refused+=1;continue
                metric=new['metric']; threshold=config['vacancy_threshold_pp' if metric=='vacancy' else metric+'_threshold_pct']
                value=result['absolute_change'] if metric=='vacancy' else result.get('relative_change_pct')
                decision.update(value=value,threshold=threshold,change_unit='pp' if metric=='vacancy' else 'percent')
                if value is None or abs(Decimal(value))<Decimal(str(threshold)):
                    decision['status']='below_threshold'
                    retire('threshold_not_met');continue
                decision['status']='threshold_met'
                for previous in active_events():
                    if previous.get('comparison_id')!=result['id']:
                        self.store.update('events',previous['id'],dict(status='superseded',
                            signal_status='retracted',superseded_reason='comparison_revised',superseded_at=now()))
                existing=next((event for event in active_events() if event.get('comparison_id')==result['id']),None)
                prior=self.store.get('events','threshold:'+result['id'])
                identity='threshold:'+result['id'] if not prior else 'threshold:'+result['id']+':'+uid()
                unit='pp' if metric=='vacancy' else '%'
                reason=(f"System-computed change: {metric} moved {value}{unit} from {old.get('period')} to {new.get('period')}, "
                    f"meeting the configured {threshold}{unit} threshold. Both observations have recorded approval, are hash-verified and "
                    f"share one source definition ({new.get('definition') or 'definition on record'}). Comparison record {result['id']}; "
                    f"periods are statistical quarters, not detection dates.")
                if detection_context=='historical_replay':
                    reason+=' HISTORICAL REPLAY: detected by re-processing saved snapshots; not a new market discovery.'
                event=existing or self.store.put('events',identity,dict(kind='metric_change',importance='high',status='new',
                    signal_identity=signal_identity,signal_status='active',review_status='approved',
                    title=f"{new['geography']} {metric}: {value} {unit} change",
                    summary='Deterministic threshold on reviewed, compatible consecutive quarters.',geography=new['geography'],
                    source_id=new['source_id'],document_id=new.get('document_id'),period=new['period'],
                    comparison_id=result['id'],old_id=old['id'],new_id=new['id'],threshold=threshold,metric=metric,
                    importance_reason=reason,detection_context=detection_context,
                    value=value,change_unit='pp' if metric=='vacancy' else 'percent',evidence=new.get('evidence',{})))
                alerts.append(event['id'])
        # A deleted, superseded or regrouped input can disappear from the pairs
        # above entirely. Reconcile all previously active signals as well.
        for event in self.store.all('events'):
            if event.get('kind')=='metric_change' and event.get('status')!='superseded' and event['id'] not in alerts:
                self.store.update('events',event['id'],dict(status='superseded',signal_status='retracted',
                    superseded_reason='approved_same_period_conflict' if {event.get('old_id'),event.get('new_id')}&conflicting_ids else 'input_no_longer_current_pair',superseded_at=now()))
        self.invalidate();return dict(alerts=len(alerts),event_ids=alerts,not_comparable=refused,
            decisions=decisions,excluded_unreviewed_or_ungrounded=len(facts)+len(invalid_inputs)-len(eligible_ids),
            publisher_reported_changes=[e['id'] for e in reported])

    def monitor_intelligence(self, monitor_result, run_id=None, detection_context='scheduled_refresh'):
        """Close the loop: threshold event → scoped report → optional notification.

        Every artefact is linked by ID (event → report → notification) and every
        step is idempotent: the event identity derives from the comparison, the
        report key from the event, and notification dedupe from the report.
        Model interpretation is explicit opt-in, uses the existing bounded
        Agent, and must pass the same report publication gate before sending.
        """
        outcomes=[]
        for event_id in monitor_result.get('event_ids',[]):
            event=self.store.get('events',event_id)
            if not event or event.get('kind')!='metric_change' or event.get('status')=='superseded':continue
            if event.get('report_id'):
                outcomes.append(dict(event_id=event_id,report_id=event['report_id'],notification_id=event.get('notification_id'),deduplicated=True))
                continue
            from .chat_report import build_report
            metric=event.get('metric') or 'vacancy'
            query=f"Analyse the {event['geography']} {metric} change in {event['period']} versus the previous quarter."
            if metric=='takeup':
                query+=' Include vacancy as an evidence cross-check for conditional risks and opportunities.'
            report=build_report(self,query,key='monitor:'+event_id,acquisition=dict(
                mode='scheduled_monitoring',network_requests=0,detection_context=detection_context,
                notice='Triggered by a monitoring threshold event on saved approved snapshots; no live retrieval was performed.'
                    +(' Historical replay: conclusions describe saved historical periods, not new discoveries.' if detection_context=='historical_replay' else '')))
            # Claim the event/report link before optional inference. Interrupted
            # or failed inference must never be replayed by scheduler retries.
            self.store.update('events',event_id,dict(report_id=report['report_id'],
                analysis_status='running' if self.settings()['monitor_analysis_enabled'] else 'not_requested',run_id=run_id))
            analysis=None
            if self.settings()['monitor_analysis_enabled']:
                analysis=self.report_analysis(report_id=report['report_id'])
            analysis_status=(analysis or {}).get('analysis_status','not_requested')
            notification=None
            if self.settings()['notifications_enabled'] and (analysis is None or analysis_status=='published'):
                notification=self.notify(report['report_id'])
            self.store.update('events',event_id,dict(report_id=report['report_id'],analysis='model_interpretation' if analysis else 'deterministic_report',
                analysis_status=analysis_status,analysis_id=(analysis or {}).get('analysis_id'),
                run_id=run_id,notification_id=(notification or {}).get('id'),
                notification_status=(notification or {}).get('status') or ('analysis_not_publishable' if analysis is not None and analysis_status!='published' else None)))
            outcomes.append(dict(event_id=event_id,report_id=report['report_id'],generation_status=report['generation_status'],
                analysis_status=analysis_status,analysis_id=(analysis or {}).get('analysis_id'),
                notification_id=(notification or {}).get('id'),notification_status=(notification or {}).get('status')
                    or ('analysis_not_publishable' if analysis is not None and analysis_status!='published' else None),deduplicated=False))
        return outcomes

    def _scoped_report_analysis(self,report_id):
        """Existing analysis entry point, bound to one saved report and receipt."""
        from .chat_report import ACTIVE_REPORT,read_report,attach_analysis
        from .qa_context import classify_error
        with self.analysis_lock:
            report=read_report(self.store,report_id)
            identity='scoped-analysis:'+report_id
            prior=self.store.get('jobs',identity)
            if prior:
                receipt=dict(prior.get('result') or {})
                current=(report.get('ai_analysis') or {}).get('status')
                withheld=report['publication_review']['status']=='withheld' or current=='withheld'
                result=dict(receipt,analysis_id=prior['id'],analysis_status='withheld' if withheld else current or receipt.get('analysis_status',prior['status']),
                    execution_receipt=receipt,cached=True)
                if withheld:result['error_code']=next(iter(report['publication_review'].get('codes',[])),'PUBLICATION_REVALIDATION_FAILED')
                return result
            row=self.store.put('jobs',identity,dict(kind='analysis',report_id=report_id,status='running',stage='prerequisites',
                progress=10,started_at=now(),attempts=1))
            eligible=[e['id'] for e in report['evidence'] if e.get('review_status')=='approved']
            if not eligible or report['publication_review']['status']=='withheld':
                attach_analysis(self.store,report_id,error='NO_VERIFIED_EVIDENCE')
                result=dict(report_id=report_id,analysis_id=row['id'],analysis_status='blocked',error_code='NO_VERIFIED_EVIDENCE',metrics=dict(requests=0),cached=False)
                self.store.update('jobs',row['id'],dict(status='blocked',stage='prerequisites',finished_at=now(),error_code='NO_VERIFIED_EVIDENCE',metrics=result['metrics'],result=result))
                return result
            agent=None;run=None;token=ACTIVE_REPORT.set(report_id)
            try:
                agent=self.agent_factory()
                self.store.update('jobs',row['id'],dict(stage='native_agent'))
                run=_run_analysis_agent(agent,report['query']+'\nReturn only the ReportInterpretation JSON for the existing report; do not change scope or review state.')
                if str(getattr(run.status,'value',run.status))!='COMPLETED' or not str(run.content or '').strip():raise ValueError('FINAL_ANSWER_MISSING')
                artifact=attach_analysis(self.store,report_id,run.content,run_id=run.run_id)
                metrics=agent.model.budget_for(run.run_id).record()
                status=artifact['ai_analysis']['status']
                result=dict(report_id=report_id,analysis_id=row['id'],analysis_status=status,run_id=run.run_id,metrics=metrics,cached=False)
                self.store.update('jobs',row['id'],dict(status='succeeded' if status=='published' else 'partial',stage='publication_review',
                    progress=100,finished_at=now(),run_id=run.run_id,metrics=metrics,result=result,quality_status='REVIEW_REQUIRED'))
                return result
            except Exception as exc:
                code=classify_error(str(exc),type(exc).__name__)
                attach_analysis(self.store,report_id,error=code,run_id=getattr(run,'run_id',None))
                metrics=agent.model.budget.record() if agent else dict(requests=0)
                result=dict(report_id=report_id,analysis_id=row['id'],analysis_status='failed',error_code=code,metrics=metrics,cached=False)
                self.store.update('jobs',row['id'],dict(status='failed',stage='native_agent',finished_at=now(),error_code=code,
                    error=code,exception_type=type(exc).__name__,failure_stage='agent_execution',
                    metrics=metrics,result=result,quality_status='REVIEW_REQUIRED'))
                return result
            finally:ACTIVE_REPORT.reset(token)

    def report_analysis(self,report_id=None):
        """Explicit optional analysis, cached on the saved evidence identity."""
        if report_id is not None:return self._scoped_report_analysis(report_id)
        with self.analysis_lock:
            if not self.facts(limit=1)['items']:raise ValueError('NO_SAVED_EVIDENCE')
            fingerprint=hashlib.sha256(json.dumps(dict(facts=self.facts(limit=500)['items'],events=self.store.all('events'),prompt_version='report-analysis-v2'),sort_keys=True,default=str).encode()).hexdigest()
            identity='analysis:'+fingerprint
            prior=next((j for j in self.store.all('jobs') if j.get('kind')=='analysis' and j.get('fingerprint')==fingerprint and j.get('status')=='succeeded'),None) or self.store.get('jobs',identity)
            if prior and prior['status']=='succeeded':return dict(reviewed_result(prior['result'],self.store),cached=True)
            row=self.store.put('jobs',identity if not prior else identity+':'+uid(),dict(kind='analysis',fingerprint=fingerprint,status='running',stage='native_agent',progress=10,started_at=now(),attempts=1))
            agent=self.agent_factory()
            run=None
            try:
                run=_run_analysis_agent(agent,'Retrieve saved London office market evidence. Write at most 550 words. Include: reported core observations with periods; one leasing/supply event; two conditional risk/opportunity hypotheses; review limitations. Cite exact saved URLs and periods for each factual claim. All source observations remain pending. Do not calculate changes. Do not give source counts. Do not claim a geography or metric is absent from the database: retrieval is a bounded subset and saved_geographies/saved_metrics describes broader coverage. Vacancy overall is not the same as Grade A. Do not explain why publishers differ without direct methodology evidence. No investment recommendations. Separate reported fact, tentative interpretation and unconfirmed method. Use saved evidence only.')
                answer=str(run.content or '')
                if str(getattr(run.status,'value',run.status))!='COMPLETED' or not answer.strip():raise ValueError('NATIVE_ANALYSIS_INCOMPLETE')
                if not any(d['url'] in answer for d in self.store.all('documents')):raise ValueError('ANALYSIS_MISSING_SAVED_CITATIONS')
                result=reviewed_result(dict(answer=answer,run_id=run.run_id,quality_status='REVIEW_REQUIRED',analysis_id=row['id'],cached=False),self.store)
                self.store.update('jobs',row['id'],dict(status='succeeded',stage='complete',progress=100,finished_at=now(),run_id=run.run_id,metrics=agent.model.budget_for(run.run_id).record(),result=result,quality_status='REVIEW_REQUIRED'))
                return result
            except Exception as exc:
                self.store.update('jobs',row['id'],dict(status='failed',stage='failed',finished_at=now(),error=type(exc).__name__,run_id=getattr(run,'run_id',None),metrics=agent.model.budget.record(),result={'raw_answer':str(getattr(run,'content','') or '')},quality_status='REVIEW_REQUIRED'))
                raise

    def report(self, period, key=None, analysis=None, geography=None):
        if period not in ['daily', 'weekly']: raise ValueError('Unsupported report period')
        if key:
            prior=self.store.get('reports','report:'+key)
            if prior and prior.get('status')=='superseded':
                key=key+':revision-1';prior=self.store.get('reports','report:'+key)
            if prior:
                if prior['period']!=period or prior.get('geography')!=geography:raise ValueError('Report idempotency key used for another scope or period')
                return dict(prior,markdown_url=f"/api/market/reports/{prior['id']}?format=markdown",html_url=f"/api/market/reports/{prior['id']}?format=html")
        facts = [f for f in self.facts(limit=500)['items'] if f.get('status')!='rejected' and f.get('human_review_status')!='rejected']; events = [e for e in self.store.all('events')
            if e.get('kind') not in ['source_update','publisher_reported_change']
            and e.get('status') not in ['superseded','rejected'] and e.get('human_review_status')!='rejected'][:30]
        def in_scope(row):
            area=row.get('geography') or ''
            return not geography or area==geography or area.startswith(geography+' (') or (geography=='Midtown / Fringe' and area in ['Midtown','Fringe'])
        facts=[f for f in facts if in_scope(f)]
        events=[e for e in events if in_scope(e)]
        sources = self.store.all('sources'); stamp = now()
        from datetime import datetime,timezone,timedelta
        window_days=1 if period=='daily' else 7
        window_start=(datetime.fromisoformat(stamp)-timedelta(days=window_days)).isoformat()
        def recent_event(e):
            from .structured_sources import current_event
            e=current_event(e)
            try:
                date=datetime.fromisoformat((e.get('published_at') or '').replace('Z','+00:00'))
                if date.tzinfo is None:date=date.replace(tzinfo=timezone.utc)
                return datetime.fromisoformat(window_start) <= date <= datetime.fromisoformat(stamp)
            except (ValueError,TypeError):return False
        recent=[e for e in events if recent_event(e)]
        lines = [f'# London office market — {period} brief', '', f'Generated {stamp}. Historical source periods remain labelled. Human review: pending_review / needs_review.',
                 f'Scope: {geography or "All saved areas"}. News window: {window_start} to {stamp} ({window_days} days); {len(recent)} dated events in window. Other observations below are historical background, not new daily/weekly market changes.',
                 '', '## Market facts', '', '| Metric / area | Period | Value / unit | Status | Definition and evidence | Source |', '|---|---|---|---|---|---|']
        for f in facts:
            safe = lambda x: str(x if x is not None else 'Unknown').replace('|','\\|').replace('\n',' ')
            doc = self.store.get('documents', f.get('document_id','')) or {}
            lines.append('| ' + ' | '.join(map(safe, [f.get('metric','')+' / '+f.get('geography',''), f.get('period'),
                str(f.get('value'))+' '+str(f.get('unit')), f.get('status'),
                str(f.get('definition') or 'Definition unknown')+'; '+str(f.get('evidence',{}).get('quote') or '')+'; '+str(f.get('evidence',{}).get('locator') or 'Locator unknown'),
                doc.get('url', f.get('source_id'))])) + ' |')
        if not facts:lines+=['','No saved market facts. This is an empty-source status report, not a market conclusion.']
        from . import directional
        assessment = directional.assess(self.store)
        if geography:
            assessment=dict(assessment,series=[s for s in assessment.get('series',[]) if in_scope(s)],summary='Scoped candidate series; original source boundaries and periods retained.')
        block = directional.render(assessment)
        if block: lines += ['', block]
        from .publisher_changes import saved_reported_changes
        lines += ['', '## Publisher-reported changes — attributed, not independently approved']
        for change in saved_reported_changes(self.store):
            if not in_scope(change):continue
            lines += ['', '### '+change['title'],
                'Classification: publisher_reported_change; not a system-calculated change. Human review: '+change['human_review_status'],
                '> '+change['evidence']['quote'],
                f"Period: {change['period']} versus {change['comparison_period']}; definition: {change['definition']}",
                f"Source: {change['url']}; published: {change.get('published_at') or 'not disclosed'}; locator: {change['evidence']['locator']}; record: {change['id']}; document SHA-256: {change['document_sha256']}",
                change['limitation']]
        lines += ['', '## Important events — source dates retained; historical background when outside window']
        for e in events:
            context=event_context(e,self.store)
            lines += ['', '### '+e['title'], context['quote'], e.get('url',''), 'Evidence status: '+e.get('status','pending_review'), 'Evidence locator: '+str(context.get('locator'))]
        lines += ['', '## Risks and opportunities',
                  '- Evidence gap: unknown units and unreviewed methods block formal changes. Review source evidence before decisions.',
                  '- Supply and leasing events describe reported activity, not proven causal drivers. No investment recommendation is inferred.',
                  '', '## Source health']
        lines += ['- '+s.get('name',s['id'])+': '+s.get('health','not_checked')+'; last success '+str(s.get('last_success')) for s in sources]
        if analysis:
            analysis=reviewed_result(analysis,self.store)
            lines+=['','## Optional AI interpretation — REVIEW_REQUIRED','This generated analysis is separate from source facts and has not received semantic or human approval.',analysis['answer'], 'Native analysis Run: '+analysis['run_id']]
        markdown = '\n'.join(lines)
        env = Environment(loader=BaseLoader(), autoescape=select_autoescape(default=True))
        rendered = env.from_string('<!doctype html><html lang="en"><meta charset="utf-8"><title>{{title}}</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px;line-height:1.6}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>{{title}}</h1><pre>{{body}}</pre></html>').render(title='London office market '+period+' brief',body=markdown)
        row = self.store.put('reports', 'report:'+key if key else uid(), dict(title='London office market '+period+' brief', period=period, markdown=markdown, html=rendered,
            geography=geography,window_days=window_days,window_start=window_start,window_end=stamp,recent_event_ids=[e['id'] for e in recent],
            analysis_status='REVIEW_REQUIRED' if analysis else ('deterministic_evidence_summary' if facts else 'no_data'),analysis_id=analysis.get('analysis_id') if analysis else None,analysis_cached=analysis.get('cached') if analysis else None, fact_ids=[f['id'] for f in facts], event_ids=[e['id'] for e in events],
            directional_status=assessment.get('status'), directional_series=len(assessment.get('series',[]))))
        return dict(row, markdown_url=f"/api/market/reports/{row['id']}?format=markdown", html_url=f"/api/market/reports/{row['id']}?format=html")

    def generate_report(self,period,key=None,geography=None):
        if not self.report_workflow:return self.report(period,key,geography=geography)
        with self._lock:
            identity='report:'+(key or uid());prior=self.store.get('jobs',identity)
            if prior:
                if prior.get('period')!=period or prior.get('geography')!=geography:raise ValueError('Report idempotency key used for another scope or period')
                if prior.get('status')=='running':raise ValueError('Report already running')
                if prior.get('status')=='succeeded':return self.report(period,key,geography=geography)
                raise ValueError('Prior report failed or was interrupted; use a fresh idempotency key for explicit retry')
            job=self.store.put('jobs',identity,dict(kind='report',status='running',stage='evidence_summary',progress=10,started_at=now(),attempts=1,period=period,geography=geography))
        try:
            run=self.report_workflow.run(dict(period=period,key=key,job_id=job['id'],geography=geography))
            if str(getattr(run.status,'value',run.status))!='COMPLETED' or not isinstance(run.content,dict):raise RuntimeError('REPORT_WORKFLOW_FAILED')
            report=run.content
            self.store.update('reports',report['id'],dict(workflow_run_id=run.run_id))
            self.store.update('jobs',job['id'],dict(status='succeeded',stage='complete',progress=100,finished_at=now(),run_id=run.run_id,result={'report_id':report['id']},model_requests=0))
            return dict(report,workflow_run_id=run.run_id)
        except Exception as exc:
            self.store.update('jobs',job['id'],dict(status='failed',stage='failed',finished_at=now(),error=type(exc).__name__))
            raise

    def notify(self, report_id):
        with self._lock:lock=self.notification_locks.setdefault(report_id,threading.Lock())
        with lock:return self._notify(report_id)

    def notification_configuration(self):
        """Validate local transport syntax only. Never connect or disclose a URL."""
        url=os.environ.get('LONDON_NOTIFICATION_URL')
        result=dict(status='configuration_missing',configured=bool(url),destinations=0,
                    connection_tested=False,external_delivery_verified=False)
        if not url:return result
        try:
            import apprise
            transport=apprise.Apprise()
            valid=transport.add(url)
            return dict(result,status='configured' if valid else 'configuration_invalid',destinations=len(transport))
        except Exception as exc:
            return dict(result,status='configuration_invalid',error=type(exc).__name__)

    def _notify(self,report_id):
        report = self.store.get('reports', report_id)
        if not report: raise KeyError('Report not found')
        url = os.environ.get('LONDON_NOTIFICATION_URL')
        base = dict(report_id=report_id, started_at=now(), attempts=0)
        if not url: return self.store.put('notifications', uid(), dict(base,status='configuration_missing',error='Set server-side LONDON_NOTIFICATION_URL; nothing sent'))
        if not self.settings()['notifications_enabled']:
            return self.store.put('notifications', uid(), dict(base,status='disabled',error='Notifications disabled; nothing sent'))
        if report.get('artifact'):
            from .chat_report import read_report,render_notification
            current=read_report(self.store,report_id)
            ai=current.get('ai_analysis')
            if current['publication_review']['status']=='withheld' or (ai and ai.get('status')!='published'):
                code=next(iter(current['publication_review'].get('codes',[])),'ANALYSIS_NOT_PUBLISHABLE')
                return self.store.put('notifications',uid(),dict(base,status='publication_withheld',error=code,finished_at=now()))
            try:body=render_notification(current)
            except ValueError as exc:
                return self.store.put('notifications',uid(),dict(base,status='payload_withheld',error=str(exc),finished_at=now()))
        else:
            body=report_view(report,self.store,'markdown')
            if len(body.encode('utf-8'))>12000:
                return self.store.put('notifications',uid(),dict(base,status='payload_withheld',error='NOTIFICATION_EVIDENCE_ENVELOPE_EXCEEDED',finished_at=now()))
        prior = next((a for a in self.store.all('notifications') if a['report_id']==report_id and a['status']=='sent'), None)
        if prior: return dict(prior,deduplicated=True)
        uncertain=next((a for a in self.store.all('notifications') if a['report_id']==report_id and a['status']=='delivery_unknown'),None)
        if uncertain:return uncertain
        import apprise
        number=1+max([n.get('attempts',0) for n in self.store.all('notifications') if n.get('report_id')==report_id]+[0])
        row=self.store.put('notifications',uid(),dict(base,status='sending',attempts=number))
        dispatched=False
        try:
            transport=apprise.Apprise(); valid=transport.add(url)
            dispatched=bool(valid)
            sent=bool(valid and transport.notify(body=body,title=report['title']))
            return self.store.update('notifications',row['id'],dict(status='sent' if sent else 'failed',finished_at=now(),
                receipt_kind='apprise_transport_acceptance' if sent else None,recipient_delivery_confirmed=False,
                error=None if sent else 'Transport rejected or delivery failed'))
        except Exception as exc:
            return self.store.update('notifications',row['id'],dict(status='delivery_unknown' if dispatched else 'failed',finished_at=now(),error=type(exc).__name__))

    def submit(self, kind, *, source_id=None, document_id=None, period=None, category=None, key=None, retry_of=None):
        identity = kind+':'+(key or uid())
        with self._lock:
            prior = self.store.get('jobs', identity)
            if prior:
                if prior.get('source_id')!=source_id or prior.get('document_id')!=document_id or prior.get('period')!=period or prior.get('category')!=category:
                    raise ValueError('Idempotency key already used with a different resource')
                return prior
            if kind=='extract':
                running=next((j for j in self.store.all('jobs') if j.get('kind')=='extract' and j.get('document_id')==document_id and j.get('status') in ['queued','running']),None)
                if running:return running
            job = self.store.put('jobs',identity,dict(kind=kind,status='queued',stage='queued',progress=0,attempts=1,
                source_id=source_id,document_id=document_id,period=period,category=category,retry_of=retry_of,started_at=now(),finished_at=None,error=None,result=None))
            self.pool.submit(self._run_job,job)
        return job

    def _run_job(self, job):
        self.store.update('jobs',job['id'],dict(status='running',stage='workflow',progress=5))
        try:
            if self.workflow:
                workflow=self.report_workflow if job['kind']=='report_analysis' else self.workflow
                run = workflow.run({'job_id':job['id'],'kind':job['kind'],'source_id':job.get('source_id'),'document_id':job.get('document_id'),'category':job.get('category'),'period':job.get('period'),'include_analysis':job['kind']=='report_analysis','key':'job:'+job['id']})
                result = run.content
                run_id = run.run_id
                self.store.update('jobs',job['id'],dict(run_id=run_id,native_status=str(run.status)))
                if str(getattr(run.status,'value',run.status))!='COMPLETED' or not isinstance(result,dict):
                    raise RuntimeError('NATIVE_WORKFLOW_FAILED: inspect native Run '+str(run_id))
                if job['kind']=='report_analysis':
                    self.store.update('reports',result['id'],dict(workflow_run_id=run_id))
                    result=dict(report_id=result['id'],analysis_id=result.get('analysis_id'),analysis_cached=result.get('analysis_cached'),quality_status='REVIEW_REQUIRED')
            else:
                result = asyncio.run(self.refresh(job));run_id=None
            partial=isinstance(result,dict) and result.get('failures',0)>0
            failed=partial and result.get('successes',0)==0
            self.store.update('jobs',job['id'],dict(status='failed' if failed else ('partial' if partial else 'succeeded'),stage='complete',progress=100,finished_at=now(),result=result,run_id=run_id,error='All selected sources failed' if failed else None))
        except Exception as exc:
            self.store.update('jobs',job['id'],dict(status='failed',stage='failed',error=type(exc).__name__+': '+str(exc)[:180],finished_at=now()))
        self.invalidate()

    async def refresh(self, job):
        from .sources import fetch_source, parse_content, discover_article_sources, document_metadata
        from .structured_sources import segments as structured_segments, planning_events, nomis_employment
        sources = [s for s in self.store.all('sources') if s.get('enabled') and (not job.get('source_id') or s['id']==job['source_id'])]
        if job.get('category')=='news': sources=[s for s in sources if s.get('category') in ['news','owner','planning']]
        if job.get('category')=='market': sources=[s for s in sources if s.get('category') not in ['news','owner']]
        semaphore=asyncio.Semaphore(4); results=[]
        async def one(source):
            async with semaphore:
                started=time.perf_counter()
                try:
                    response=await fetch_source(source,etag=source.get('etag'),last_modified=source.get('last_modified'))
                    if response['status_code']==304:
                        if not source.get('last_article_failures'):
                            from .indicator_ingestion import project_document, project_macro
                            macro_replayed=False
                            for saved in self.store.all('documents'):
                                if saved['source_id']==source['id']:
                                    project_document(self.store,saved,source)
                                    if source['id'] in ['boe','ons','ons-employment','ons-gva'] and not macro_replayed and saved['url']==source['url']:
                                        project_macro(self.store,saved,source,Path(saved['path']).read_bytes())
                                        macro_replayed=True
                            self.store.update('sources',source['id'],dict(health='healthy',last_success=now(),last_error=None));return dict(source_id=source['id'],status='unchanged')
                        saved=next((d for d in self.store.all('documents') if d['source_id']==source['id'] and d['url']==source['url']),None)
                        if not saved:raise ValueError('CONDITIONAL_RECOVERY_SNAPSHOT_MISSING')
                        response=dict(response,content=Path(saved['path']).read_bytes(),media=saved['media'],url=saved['url'],etag=source.get('etag'),last_modified=source.get('last_modified'))
                    structured = source['id'].startswith('planning-api-') or source['id']=='epc-nondomestic'
                    segments=structured_segments(source,response['content']) if structured else parse_content(response['content'],response['media'])
                    doc=self.store.snapshot(source,response['url'],response['content'],response['media'],segments,
                        title=source.get('name'),published_at=response.get('published_at') or document_metadata(response['content'],response['media']).get('published_at'),etag=response.get('etag'),last_modified=response.get('last_modified'))
                    self.store.update('sources',source['id'],dict(health='healthy',last_success=now(),last_error=None,etag=response.get('etag'),last_modified=response.get('last_modified')))
                    articles=[]; structured_records=0
                    from .indicator_ingestion import project_document, project_macro
                    structured_records+=project_document(self.store,doc,source)
                    if source['id'].startswith('planning-api-'):
                        structured_records=planning_events(self.store,doc,source,response['content'])
                    elif source['id']=='nomis-london':
                        structured_records=nomis_employment(self.store,doc,source,response['content'])
                    if source.get('category') in ['news','owner','planning','research'] and not source['id'].startswith('planning-api-'):
                        if source.get('category')!='research':self.events_from_document(doc,source)
                        for article in discover_article_sources(response['content'],response['url']):
                            try:
                                child=await fetch_source(dict(source,url=article['url']))
                                child_doc=self.store.snapshot(source,child['url'],child['content'],child['media'],parse_content(child['content'],child['media']),title=article['title'],published_at=article.get('published_at') or document_metadata(child['content'],child['media']).get('published_at'))
                                structured_records+=project_document(self.store,child_doc,source)
                                if source.get('category')!='research':self.events_from_document(child_doc,source)
                                articles.append(dict(url=article['url'],status='saved',document_id=child_doc['id']))
                            except Exception as exc:articles.append(dict(url=article['url'],status='failed',error=type(exc).__name__))
                    if source['id'] in ['boe','ons','ons-employment','ons-gva']:structured_records+=project_macro(self.store,doc,source,response['content'])
                    child_failures=sum(a['status']=='failed' for a in articles)
                    self.store.update('sources',source['id'],dict(last_article_failures=child_failures,listing_health='healthy',health='partial' if child_failures else 'healthy',last_error='ARTICLE_FETCH_PARTIAL' if child_failures else None))
                    return dict(source_id=source['id'],status='saved',document_id=doc['id'],articles=articles,
                                structured_records=structured_records,seconds=round(time.perf_counter()-started,3))
                except Exception as exc:
                    code=getattr(getattr(exc,'response',None),'status_code',None)
                    error=type(exc).__name__+(f' (HTTP {code})' if code else '')
                    self.store.update('sources',source['id'],dict(health='failed',last_error=error,last_attempt=now()))
                    return dict(source_id=source['id'],status='failed',error=error,status_code=code,seconds=round(time.perf_counter()-started,3))
                finally:
                    results.append(source['id'])
                    if job.get('job_id') or job.get('id'):
                        self.store.update('jobs',job.get('job_id') or job['id'],dict(progress=10+int(80*len(results)/max(1,len(sources))),stage='fetch_parse_persist'))
        # Search discovery and registered-source reads are independent. Launch
        # together; neither is part of the foreground question path.
        discovery_task=None
        if job.get('category')=='news' and not job.get('source_id'):
            from .discovery import refresh_candidates
            discovery_task=asyncio.create_task(refresh_candidates(self))
        results=await asyncio.gather(*(one(s) for s in sources))
        # Discovery extends this native Workflow's news acquisition step only.
        # Individual-source retries and market refreshes never spend search credits.
        discovery=dict(status='not_requested',requests=0,candidates=[],successes=0,failures=0)
        if discovery_task: discovery=await discovery_task
        article_failures=sum(a['status']=='failed' for r in results for a in r.get('articles',[]))
        self.invalidate()
        return dict(sources=results,discovery=discovery,successes=sum(r['status']!='failed' for r in results)+discovery.get('successes',0),failures=sum(r['status']=='failed' for r in results)+article_failures+discovery.get('failures',0),article_failures=article_failures)

    def events_from_document(self, doc, source):
        from urllib.parse import urlsplit
        if any(e.get('document_id')==doc['id'] for e in self.store.all('events')):return
        prior=next((e for e in self.store.all('events') if e.get('url')==doc['url'] and e.get('kind')!='source_update' and e.get('status')!='superseded'),None)
        if prior:
            versions=list(dict.fromkeys(prior.get('content_versions',[prior.get('document_id')])+[doc['id']]))
            self.store.update('events',prior['id'],dict(content_versions=versions,latest_document_id=doc['id'],last_seen=now(),content_change_status='needs_review'))
            return
        # A listing is a collection change, not a verified market event.
        if urlsplit(doc['url']).path.rstrip('/')==urlsplit(source['url']).path.rstrip('/') and source.get('category')!='news':
            self.store.put('events','listing:'+doc['id'],dict(title=source.get('name','Source')+' listing changed',summary='New collection snapshot; article acquisition is recorded separately.',kind='source_update',importance='low',status='needs_review',source_id=source['id'],document_id=doc['id'],url=doc['url'],evidence={}))
            return
        segments=doc['segments']
        for segment in segments[:60]:
            text=segment.get('text','').strip()
            if len(text)<45:continue
            lowered=text.lower()
            if source.get('category')=='news' and not ('london' in lowered and any(w in lowered for w in ['office','lease','property','planning'])) and 'bank of england' not in lowered:continue
            kinds=[('planning',r'\b(planning|consent|approval)\b'),('lease',r'\b(leases?|leased|lettings?|pre[- ]?lets?)\b'),('relocation',r'\b(relocat\w*|headquarters)\b'),('supply',r'\b(develop\w*|refurbish\w*|completions?)\b'),('policy',r'\b(policy|interest rates?|inflation)\b'),('demand',r'\b(hybrid|esg|quality)\b')]
            kind=next((k for k,pattern in kinds if re.search(pattern,lowered)),None)
            if not kind:continue
            identity=hashlib.sha256((source['id']+text).encode()).hexdigest()
            title=segment.get('title') or doc.get('title') or text[:140]
            self.store.put('events',identity,dict(title=title,summary=text[:1000],kind=kind,importance='high' if kind in ['planning','lease','relocation'] else 'normal',
                status='pending_review',geography='London',source_id=source['id'],document_id=doc['id'],url=segment.get('url') or doc['url'],published_at=segment.get('published_at') or doc.get('published_at'),
                evidence=dict(quote=text[:1000],page=segment.get('page'),locator=segment.get('locator',segment.get('segment_id'))),classification_method='keyword-v1; reported text, not semantic verification'))
            if source.get('category')!='news':break

    def macro_from_document(self,doc,source,content):
        """Publisher-specific machine-readable series; no inferred market units."""
        import csv,io
        from datetime import datetime
        if source['id']=='boe':
            rows=[r for r in csv.DictReader(io.StringIO(content.decode('utf-8-sig'))) if r.get('IUDBEDR')]
            row=rows[-1];value=str(Decimal(row['IUDBEDR']));period=datetime.strptime(row['DATE'],'%d %b %Y').date().isoformat()
            metric='interest_rate';definition='Official Bank Rate, series IUDBEDR';quote=row['DATE']+','+row['IUDBEDR'];locator='CSV row '+str(len(rows)+1)
        else:
            payload=json.loads(content);description=payload['description']
            expected='LF24' if source['id']=='ons-employment' else 'L55O'
            if description.get('cdid')!=expected or description.get('unit')!='%':raise ValueError('Unexpected ONS series schema')
            row=payload['months'][-1];value=str(Decimal(row['value']))
            if source['id']=='ons-employment':
                if not row.get('label') or not re.fullmatch(r'\d{4} [A-Z]{3}-[A-Z]{3}',row['label']):raise ValueError('Employment rolling period missing')
                period=row['label'];metric='employment'
            else:period=datetime.strptime(row['date'],'%Y %b').strftime('%Y-%m');metric='inflation_cpih'
            definition=description['title']+'; '+description.get('keyNote','');quote=json.dumps(row,ensure_ascii=False);locator='JSON months[-1]'
            if not doc.get('published_at') and description.get('releaseDate'):
                doc=self.store.update('documents',doc['id'],dict(published_at=description['releaseDate']))
        if any(f.get('document_id')==doc['id'] and f.get('metric')==metric and f.get('period')==period and Decimal(str(f.get('value')))==Decimal(value) for f in self.store.all('facts')):return
        self.store.put('facts','macro:'+source['id']+':'+doc['sha256']+':'+period,dict(metric=metric,value=value,raw_value=value,normalized_value=value,unit='percent',
            precision=str(Decimal('1').scaleb(Decimal(value).as_tuple().exponent)),geography='United Kingdom',period=period,raw_period=row.get('date',period),definition=definition,grade='not_applicable',method='publisher_machine_series',basis='date' if source['id']=='boe' else ('rolling_three_month_average' if metric=='employment' else 'annual_rate_month'),currency=None,
            source_id=source['id'],publisher=source['name'],series=definition,document_id=doc['id'],status='pending_review',human_review_status='pending_review',
            published_at=doc.get('published_at'),collected_at=doc['collected_at'],extraction_version='deterministic-macro-v1',evidence=dict(quote=quote,page=None,locator=locator)))

    def saved_answer(self, message):
        facts=[f for f in self.facts(limit=500)['items'] if f.get('status')!='rejected' and f.get('human_review_status')!='rejected']; events=[e for e in self.store.all('events') if e.get('kind')!='source_update' and e.get('status') not in ['superseded','rejected'] and e.get('human_review_status')!='rejected']
        lower=message.lower();geos=[g for g in ['City','West End','Canary Wharf','Midtown'] if g.lower() in lower]
        if geos:facts=[f for f in facts if any(g.lower() in f.get('geography','').lower() for g in geos)]
        metrics={v for k,v in [('rent','rent'),('租金','rent'),('vacancy','vacancy'),('空置','vacancy'),('availability','availability'),('take-up','takeup'),('leasing','takeup'),('成交','takeup'),('interest','interest_rate'),('利率','interest_rate'),('employment','employment'),('就业','employment'),('inflation','inflation_cpih'),('通胀','inflation_cpih'),('bank of england','interest_rate'),('boe','interest_rate'),('base rate','interest_rate'),('bank rate','interest_rate')] if k in lower}
        if metrics:facts=[f for f in facts if f['metric'] in metrics]
        if 'grade a' in lower and 'rent' in lower:facts=[f for f in facts if f.get('grade')=='Grade A']
        elif 'prime' in lower and 'rent' in lower:
            from .indicators import matches
            facts=[f for f in facts if matches(f,'prime_rent')]
        periods=set(re.findall(r'20\d{2}Q[1-4]',message,re.I))
        if periods:facts=[f for f in facts if (f.get('normalized_period') or f.get('period') or '').upper() in {p.upper() for p in periods}]
        if metrics=={'employment'} and ('london' in lower or '伦敦' in lower):
            facts=[f for f in facts if f.get('geography','').startswith('London')]
        wants_events=any(term in lower for term in ('事件','新闻','规划','项目','供应','event','news','planning','supply','notable changes','developments','leasing activity'))
        theme_terms={'hybrid_working':['hybrid','混合办公'],'esg':['esg','sustainab','可持续'],
                     'flight_to_quality':['flight-to-quality','flight to quality','优质化'],'refurbishment':['refurbish','翻新'],'prelet':['pre-let','prelet','预租']}
        themes=[k for k,words in theme_terms.items() if any(w in lower for w in words)]
        if themes:
            wants_events=True
            events=[e for e in events if any(k in e.get('indicator_keys',[]) for k in themes)]
        if wants_events and not metrics: facts=[]
        if wants_events:
            if any(term in lower for term in ('规划','planning')):
                events=[e for e in events if e.get('kind')=='planning']
            if geos:
                events=[e for e in events if any(g.lower() in e.get('geography','').lower() for g in geos)]
            events=events[:10]
        lines=['Saved evidence query · no new model request','Historical periods and review status shown below.','']
        citations=[]
        for f in facts[:24]:
            d=self.store.get('documents',f.get('document_id','')) or {}
            evidence=f.get('evidence') or {}
            location=evidence.get('locator') or (f"pdf:page:{evidence['page']}" if evidence.get('page') else 'not recorded')
            lines.append(f"- {f.get('geography')} · {f.get('metric')} · {f.get('period')}: {f.get('value')} {f.get('unit')} [{f.get('status')}]. Definition: {f.get('definition') or 'not specified'}. Source: {d.get('url',f.get('source_id'))}; location {location}.")
            if d:citations.append(dict(document_id=d['id'],url=d['url'],period=f.get('period')))
        if not facts and not wants_events:lines.append('No matching saved facts. Use Market Data to inspect missing or pending coverage.')
        if len(geos)>1:
            lines.append('A cross-area change is not calculated here: selected observations still require identical definitions, periods, units and approval.')
        from . import directional
        assessment=directional.assess(self.store)
        series=assessment.get('series',[])
        if metrics: series=[s for s in series if s['metric'] in metrics]
        if geos: series=[s for s in series if any(g.lower() in (s['geography'] or '').lower() for g in geos)]
        if series:
            reviewed=sum(1 for s in series if s.get('basis')=='human_approved')
            scoped=dict(assessment,status='available',series=series,
                summary=(f'{len(series)} comparable candidate series; {reviewed} human-reviewed; '
                         f'{len(series)-reviewed} pending review. Arithmetic differences do not establish a confirmed market change.'))
            block=directional.render(scoped)
            if block: lines+=['',block]
        if wants_events:
            lines+=['','Reported events (pending review):']+[f"- {e['title']} [{e.get('human_review_status') or e.get('status')}], {e.get('application_status') or e.get('published_at') or 'date not supplied'} — {e.get('url','')}; {e.get('evidence',{}).get('locator','location not supplied')}" for e in events]
            if not events:lines.append('No matching saved event candidates.')
        lines+=['','Interpretation: no formal change is asserted from unreviewed or incompatible facts. Risks/opportunities require reviewed evidence; unknown annual rent units remain unresolved.']
        return '\n'.join(lines),citations
