"""Bounded background research over registered sources and saved evidence.

This reuses product Jobs, the existing fetcher, the report contract and Agno
Workflow. It does not run a paid model or promote human-review states.
"""

import asyncio
import hashlib
import json
import threading
import copy
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from agno.workflow import Workflow, Step, StepInput, StepOutput

from .store import now, uid


class ResearchInput(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    refresh_sources: bool = False
    source_id: str | None = None

    @field_validator('question')
    @classmethod
    def meaningful_question(cls,value):
        if not value.strip():raise ValueError('Question cannot be whitespace only')
        return value


def make_research_workflow(service, db, worker):
    def collect(step_input: StepInput) -> StepOutput:
        data = dict(step_input.input)
        job_id = data['job_id']
        service.store.update('jobs', job_id, dict(stage='collect', progress=15))
        def acquire():
            if not data['refresh_sources']:return None
            result = asyncio.run(service.refresh(dict(job_id=job_id, source_id=data['source_id'])))
            return dict(mode='registered_source_refresh', source_id=data['source_id'],result=result, model_requests=0,
                notice='Registered source refresh attempted; failures retain saved evidence and do not establish current coverage.'
                    if result.get('failures') else 'Registered source refresh completed; collection does not approve observations.')
        signature=worker._digest(dict(refresh=data['refresh_sources'],source_id=data['source_id'],
            inputs=worker._snapshot() if data['refresh_sources'] else None))
        acquisition=worker._checkpoint(job_id,'collect',signature,acquire)
        if data['refresh_sources']:
            checkpoint=service.store.get('jobs',job_id)['checkpoints']['collect']
            if (acquisition or {}).get('result',{}).get('failures'):
                worker._save_checkpoint(job_id,'collect',dict(checkpoint,status='failed',error='SOURCE_REFRESH_FAILED'))
            elif not checkpoint.get('reused'):
                post=worker._digest(dict(refresh=True,source_id=data['source_id'],inputs=worker._snapshot()))
                worker._save_checkpoint(job_id,'collect',dict(checkpoint,initial_input_sha256=signature,input_sha256=post))
        return StepOutput(content=dict(data, acquisition=acquisition))

    def retrieve(step_input: StepInput) -> StepOutput:
        data = step_input.previous_step_content
        service.store.update('jobs', data['job_id'], dict(stage='retrieve', progress=55))
        hits=worker._branches(data)
        if worker._adapt(data):
            hits.extend(worker._branches(data,kinds={'followup'}))
        seen = set()
        unique = []
        for hit in hits:
            key = (hit['record_type'],hit['record_id'],hit['locator'])
            if key not in seen:
                seen.add(key)
                unique.append(hit)
        unique.sort(key=lambda hit:(hit['record_type'],hit['record_id'],hit['locator'] or ''))
        return StepOutput(content=dict(data, candidate_hits=[
            {**{key: hit[key] for key in ('record_type', 'record_id', 'locator', 'review_status')},
             'scope_status':'structured_match' if hit['record_type']=='fact' else 'unscoped_document_candidate'}
            for hit in unique]))

    def report(step_input: StepInput) -> StepOutput:
        from .chat_report import build_report

        data = step_input.previous_step_content
        service.store.update('jobs', data['job_id'], dict(stage='validate_report', progress=80))
        dependencies=service.store.get('jobs',data['job_id'])['checkpoints']
        signature=worker._digest(dict(snapshot=worker._snapshot(),candidates=data['candidate_hits'],acquisition=data['acquisition'],
            dependency_statuses={key:dict(status=value['status'],required=value.get('required')) for key,value in dependencies.items() if key!='report'}))
        def generate():
            checkpoints=service.store.get('jobs',data['job_id'])['checkpoints']
            required_failures=[key for key,value in checkpoints.items()
                if key!='report' and value.get('required') and value['status']!='succeeded']
            acquisition=data['acquisition']
            if required_failures:
                acquisition=dict(acquisition or {},mode=(acquisition or {}).get('mode','saved_snapshots'),
                    notice=(acquisition or {}).get('notice','Saved evidence only; required investigation branches did not complete.'),
                    research_required_failures=required_failures)
            artifact=build_report(service,data['question'],key='research:'+data['job_id']+':'+signature,
                acquisition=acquisition)
            return dict(report_id=artifact['report_id'],generation_status=artifact['generation_status'],
                data_gaps=artifact['data_gaps'],conflicts=artifact['conflicts'])
        output=worker._checkpoint(data['job_id'],'report',signature,generate)
        return StepOutput(content=dict(output,candidate_hits=data['candidate_hits'],acquisition=data['acquisition'],model_requests=0))

    return Workflow(id='london-saved-research-workflow',name='London Saved Evidence Research',db=db,
        steps=[Step(name='Collect registered source',executor=collect,max_retries=0,on_error='fail'),
               Step(name='Retrieve temporal evidence',executor=retrieve,max_retries=0,on_error='fail'),
               Step(name='Validate and export report',executor=report,max_retries=0,on_error='fail')],
        store_events=True,telemetry=False)


class ResearchWorker:
    def __init__(self, service, db):
        self.service = service
        self.workflow = make_research_workflow(service, db, self)
        self._lock = threading.RLock()
        self.max_parallel=4
        self.branch_timeout_seconds=10
        self._branch_slots=threading.BoundedSemaphore(4)
        self.max_followup_branches=4

    @staticmethod
    def _digest(value):
        return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()

    def _snapshot(self):
        """Current records and original bytes, not file dates or approval labels alone."""
        store=self.service.store
        docs=[]
        for doc in store.all('documents'):
            try:actual=hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest()
            except (OSError,KeyError):actual='UNAVAILABLE'
            docs.append(dict(doc,actual_sha256=actual))
        return dict(facts=store.all('facts'),events=store.all('events'),documents=docs,
            sources=[{k:s.get(k) for k in ['id','enabled','allow_llm','url','policy_note']}
                for s in store.all('sources')])

    def _save_checkpoint(self,job_id,node_id,value):
        with self._lock:
            job=self.service.store.get('jobs',job_id)
            checkpoints=dict(job.get('checkpoints') or {});checkpoints[node_id]=value
            plan=copy.deepcopy(job['plan'])
            for node in plan['nodes']:
                if node['id']==node_id:node['status']=value['status']
            self.service.store.update('jobs',job_id,dict(checkpoints=checkpoints,plan=plan))

    def _cached(self,job_id,node_id,signature):
        job=self.service.store.get('jobs',job_id);prior=(job.get('checkpoints') or {}).get(node_id)
        if not prior or prior.get('status')!='succeeded' or prior.get('input_sha256')!=signature:return None
        if node_id=='report':
            from .chat_report import read_report
            try:
                report=read_report(self.service.store,prior['output']['report_id'])
                if report['publication_review']['status']=='withheld':return None
            except (KeyError,ValueError):return None
        reused=dict(prior,reused=True,reused_at=now(),source_job_id=prior.get('source_job_id') or job.get('retry_of') or job_id)
        self._save_checkpoint(job_id,node_id,reused)
        return reused

    def _checkpoint(self,job_id,node_id,signature,operation):
        cached=self._cached(job_id,node_id,signature)
        if cached:return cached['output']
        started=time.perf_counter()
        receipt=dict(status='running',input_sha256=signature,reused=False,started_at=now(),started_monotonic=started)
        receipt['required']=next(n['required'] for n in self.service.store.get('jobs',job_id)['plan']['nodes'] if n['id']==node_id)
        self._save_checkpoint(job_id,node_id,receipt)
        try:
            output=operation()
        except Exception as exc:
            self._save_checkpoint(job_id,node_id,dict(receipt,status='failed',error=type(exc).__name__,finished_at=now(),
                finished_monotonic=time.perf_counter(),elapsed_ms=round((time.perf_counter()-started)*1000,3)))
            raise
        self._save_checkpoint(job_id,node_id,dict(receipt,status='succeeded',output=output,finished_at=now(),
            finished_monotonic=time.perf_counter(),elapsed_ms=round((time.perf_counter()-started)*1000,3)))
        return output

    def _adapt(self,data):
        """One bounded local investigation pass, derived from actual missing cells.

        Document leads never fill structured cells or trigger model/source calls.
        Failed retrievals are retried explicitly, not hidden by a fallback search.
        """
        with self._lock:
            job=self.service.store.get('jobs',data['job_id'])
            plan=copy.deepcopy(job['plan']);checkpoints=dict(job.get('checkpoints') or {})
            missing=[n for n in plan['nodes'] if n['kind']=='evidence'
                and checkpoints.get(n['id'],{}).get('status')=='succeeded'
                and not checkpoints[n['id']].get('output')]
            limit=max(0,min(4,self.max_followup_branches));followups=[]
            for node in missing[:limit]:
                period=node.get('period')
                followups.append(dict(id='followup:'+node['id'],kind='followup',required=False,
                    geography=node['geography'],metric=node['metric'],period=period,
                    depends_on=[node['id']],status='pending',reason='missing_structured_observations',
                    query=' '.join(str(v) for v in [node['geography'],node['metric'],period] if v),
                    filters=dict(record_type='document',limit=8),
                    completion='Saved-document leads inspected; leads do not approve or fill structured coverage'))
            selected={n['id'] for n in followups}
            obsolete=[key for key in checkpoints if key.startswith('followup:') and key not in selected]
            for key in obsolete:checkpoints.pop(key)
            plan['nodes']=[n for n in plan['nodes'] if n['kind']!='followup']
            report=next(n for n in plan['nodes'] if n['kind']=='report')
            report['depends_on']=[key for key in report['depends_on'] if not key.startswith('followup:')]+list(n['id'] for n in followups)
            plan['nodes'][-1:-1]=followups
            plan['adaptation']=dict(policy='missing-cell-document-followup-v1',passes=int(bool(followups)),
                limit=limit,missing_cells=len(missing),deferred_cells=max(0,len(missing)-limit),
                superseded_checkpoint_ids=obsolete,model_requests=0,external_requests=0,
                decision='investigate_saved_documents' if followups else 'no_followups_needed')
            self.service.store.update('jobs',job['id'],dict(plan=plan,checkpoints=checkpoints))
            return bool(followups)

    def _branches(self,data,kinds=None):
        from .chat_report import candidate_in_area
        from .normalization import derive
        job_id=data['job_id'];job=self.service.store.get('jobs',job_id);scope=job['plan']['scope']
        snapshot=self._snapshot();tasks=[];outputs=[]
        for node in job['plan']['nodes']:
            if node['kind'] not in (kinds or {'evidence','context'}):continue
            if node['kind']=='evidence':
                target_period=node.get('period',scope['observation_period'])
                filters=dict(record_type='fact',metric=node['metric'],geography=node['geography'],period=target_period,limit=8)
                related=[]
                for fact in snapshot['facts']:
                    try:period=derive(fact)['normalized_period']
                    except Exception:period=fact.get('period')
                    if fact.get('metric')==node['metric'] and candidate_in_area(fact,node['geography']) and (not target_period or period==target_period):related.append(fact)
                documents=[d for d in snapshot['documents'] if d['id'] in {f.get('document_id') for f in related}]
                source_ids={f.get('source_id') for f in related}
                inputs=dict(facts=related,documents=documents,sources=[s for s in snapshot['sources'] if s['id'] in source_ids])
                query=node['metric']
            else:
                query=node.get('query',data['question']);filters=node.get('filters',dict(record_type='document',limit=8))
                inputs=dict(documents=snapshot['documents'],sources=snapshot['sources'])
            signature=self._digest(dict(query=query,filters=filters,inputs=inputs))
            cached=self._cached(job_id,node['id'],signature)
            if cached:outputs.extend(cached['output']);continue
            tasks.append((node,signature,query,filters))
        # Only the coordinator persists results. Timed-out futures cannot commit
        # late output or mutate the plan; evidence branches only perform reads.
        pool=ThreadPoolExecutor(max_workers=max(1,min(4,self.max_parallel)),thread_name_prefix='research-evidence')
        pending={}
        def measured(query,filters,timing):
            if not self._branch_slots.acquire(timeout=self.branch_timeout_seconds):raise TimeoutError('BRANCH_CAPACITY_TIMEOUT')
            try:
                timing.update(started_at=now(),started_monotonic=time.perf_counter())
                try:return self.service.store.search_evidence(query,**filters)
                finally:timing.update(finished_at=now(),finished_monotonic=time.perf_counter())
            finally:self._branch_slots.release()
        try:
            for node,signature,query,filters in tasks:
                started=time.perf_counter()
                receipt=dict(status='running',input_sha256=signature,reused=False,queued_at=now(),queued_monotonic=started,
                    input=dict(query=query,filters=filters),required=node['required'])
                self._save_checkpoint(job_id,node['id'],receipt)
                timing={};future=pool.submit(measured,query,filters,timing)
                pending[future]=(node,receipt,timing)
            while pending:
                done,_=wait(pending,timeout=.01,return_when=FIRST_COMPLETED)
                current=time.perf_counter()
                for future,(node,receipt,timing) in list(pending.items()):
                    timeout=current-timing.get('started_monotonic',receipt['queued_monotonic'])>=self.branch_timeout_seconds
                    if future not in done and not timeout:continue
                    receipt=dict(receipt,**timing)
                    receipt.setdefault('finished_at',now());receipt.setdefault('finished_monotonic',current)
                    receipt['elapsed_ms']=round((receipt['finished_monotonic']-receipt.get('started_monotonic',receipt['queued_monotonic']))*1000,3)
                    finished_late=(timing.get('finished_monotonic',current)-timing.get('started_monotonic',receipt['queued_monotonic']))>self.branch_timeout_seconds
                    if finished_late or (timeout and future not in done):
                        future.cancel();receipt.update(status='failed',error='BRANCH_TIMEOUT')
                    else:
                        try:
                            hits=future.result();receipt.update(status='succeeded',output=hits);outputs.extend(hits)
                        except Exception as exc:receipt.update(status='failed',error=type(exc).__name__)
                    self._save_checkpoint(job_id,node['id'],receipt);del pending[future]
        finally:pool.shutdown(wait=False,cancel_futures=True)
        return outputs

    def submit(self, request: ResearchInput, key=None, retry_of=None):
        source_id = request.source_id
        if request.refresh_sources:
            source = self.service.store.get('sources', source_id or '')
            if not source_id or not source or not source.get('enabled'):
                raise ValueError('Research refresh requires one enabled, registered source_id')
        elif source_id:
            raise ValueError('source_id is only used with refresh_sources')
        fingerprint = hashlib.sha256(json.dumps(request.model_dump(),sort_keys=True).encode()).hexdigest()
        identity = 'research:'+(key or uid())
        with self._lock:
            prior = self.service.store.get('jobs', identity)
            if prior:
                if prior.get('fingerprint') != fingerprint:
                    raise ValueError('Research idempotency key used for another question or source')
                return prior
            from .chat_report import resolve_scope
            scope=resolve_scope(request.question)
            periods=scope.get('requested_periods') or [scope['observation_period']]
            nodes=[dict(id='collect',kind='collection',required=bool(request.refresh_sources),depends_on=[],status='pending',
                completion='Registered source refresh completed, or explicitly saved-only')]
            for metric in scope['metrics']:
                for geo in scope['geographies']:
                    for period in periods:
                        identity_suffix=':'+period if len(periods)>1 else ''
                        nodes.append(dict(id='evidence:'+geo+':'+metric+identity_suffix,kind='evidence',geography=geo,metric=metric,
                            period=period,required=True,depends_on=['collect'],status='pending',
                            completion='Bounded retrieval for this area, metric and period; report eligibility checked separately'))
            nodes.append(dict(id='context:documents',kind='context',required=False,depends_on=['collect'],status='pending',
                completion='Optional raw-document leads; never substitute for qualified observations'))
            nodes.append(dict(id='report',kind='report',required=True,depends_on=[n['id'] for n in nodes if n['kind'] in ['evidence','context']],
                status='pending',completion='Current evidence/review/comparability verification and saved report'))
            checkpoints={}
            retired=[]
            if retry_of:
                parent=self.service.store.get('jobs',retry_of)
                if not parent or parent.get('kind')!='research' or parent.get('fingerprint')!=fingerprint:
                    raise ValueError('Research checkpoint parent does not match request')
                if parent.get('status') not in ['failed','interrupted','partial']:raise ValueError('Research parent is not retryable')
                checkpoints=copy.deepcopy(parent.get('checkpoints') or {})
                current_nodes={node['id'] for node in nodes}
                retired=[node_id for node_id in checkpoints if node_id not in current_nodes and not node_id.startswith('followup:')]
                for node_id in retired:checkpoints.pop(node_id)
                for value in checkpoints.values():value['source_job_id']=value.get('source_job_id') or retry_of
            job = self.service.store.put('jobs', identity, dict(kind='research',status='queued',stage='queued',
                progress=0,attempts=1,question=request.question,question_sha256=hashlib.sha256(request.question.encode()).hexdigest(),
                fingerprint=fingerprint,refresh_sources=request.refresh_sources,source_id=source_id,
                retry_of=retry_of,started_at=now(),finished_at=None,error=None,result=None,checkpoints=checkpoints,
                plan=dict(version=2,scope=scope,concurrency_limit=max(1,min(4,self.max_parallel)),branch_timeout_seconds=self.branch_timeout_seconds,
                    nodes=nodes,decision='execute',next_checks=[],retired_checkpoint_ids=retired,
                    coverage_requirements=[dict(geography=n['geography'],metric=n['metric'],period=n['period']) for n in nodes if n['kind']=='evidence'])))
            self.service.pool.submit(self._run, job)
            return job

    def _run(self, job):
        run_id=uid()
        session_id='research:'+job['id']
        self.service.store.update('jobs', job['id'], dict(status='running',stage='workflow',progress=5,run_id=run_id,
            workflow_session_id=session_id,native_status='RUNNING'))
        try:
            run = self.workflow.run(dict(job_id=job['id'],question=job['question'],
                refresh_sources=job['refresh_sources'],source_id=job.get('source_id')),run_id=run_id,session_id=session_id)
            self.service.store.update('jobs',job['id'],dict(run_id=run.run_id,
                native_status=str(getattr(run.status,'value',run.status))))
            if str(getattr(run.status,'value',run.status)) != 'COMPLETED' or not isinstance(run.content,dict):
                raise RuntimeError('RESEARCH_WORKFLOW_FAILED')
            result = run.content
            acquisition = result.get('acquisition') or {}
            source_results = acquisition.get('result') or {}
            failures = source_results.get('failures',0) if isinstance(source_results,dict) else 0
            latest=self.service.store.get('jobs',job['id']);plan=latest['plan']
            branch_failures=[dict(node_id=key,error=value.get('error')) for key,value in latest['checkpoints'].items() if value['status']!='succeeded']
            partial=bool(failures or branch_failures or result.get('data_gaps') or result.get('conflicts') or result.get('generation_status')!='success')
            status = 'partial' if partial else 'succeeded'
            plan.update(decision='partial_delivery' if partial else 'complete',
                next_checks=list(result.get('data_gaps') or [])+list(result.get('conflicts') or [])+branch_failures,
                conflicts=result.get('conflicts') or [],branch_failures=branch_failures)
            self.service.store.update('jobs', job['id'], dict(status=status,stage='complete',progress=100,
                finished_at=now(),run_id=run.run_id,result=result,model_requests=0,plan=plan))
        except Exception as exc:
            latest=self.service.store.get('jobs',job['id']);plan=latest['plan']
            plan.update(decision='stop_failed',next_checks=[dict(stage=latest.get('stage'),error=type(exc).__name__)])
            self.service.store.update('jobs', job['id'], dict(status='failed',stage='failed',
                finished_at=now(),error=type(exc).__name__+': '+str(exc)[:180],model_requests=0,plan=plan,native_status='ERROR'))
