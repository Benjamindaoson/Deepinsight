"""Loopback product API composed with the frozen native AgentOS runtime."""
import json
import os
import time
import hashlib
import asyncio
import html
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse, JSONResponse
from agno.os import AgentOS
from agno.db.sqlite import SqliteDb
from agno.scheduler import ScheduleManager
from .store import Store, now, uid
from .service import MarketService
from .analysis_guard import review_analysis, report_view
from .contracts import AskInput, CompareInput, ReportInput, NotifyInput, ReviewInput
from .intelligence import (query_agent, make_monitor_workflow, make_report_workflow,
                           make_saved_query_workflow, run_saved_query_workflow)
from .qa_context import classify_error, error_message

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT/'app/data/product'


def initialize(service):
    from .seed import seed_records
    from .sources import parse_content
    seed=seed_records(ROOT)
    for source in seed['sources']: service.store.put('sources',source['id'],source)
    # Retire only the known failed legacy landing URL. Historical snapshots
    # remain in place; the official structured API has separate source IDs.
    legacy = service.store.get('sources', 'planning')
    if legacy and legacy.get('url') == 'https://data.london.gov.uk/dataset/planning-london-datahub' and legacy.get('enabled'):
        service.store.update('sources', legacy['id'], dict(enabled=False,
            policy_note='Legacy catalog landing URL retired after HTTP 403; official Planning London Datahub API sources are active.'))
    epc = service.store.get('sources', 'epc-nondomestic')
    epc_default = next(source for source in seed['sources'] if source['id'] == 'epc-nondomestic')
    if epc and epc.get('enabled') != epc_default['enabled']:
        service.store.update('sources', epc['id'], dict(enabled=epc_default['enabled'],
            health=epc_default['health']))
    for document in seed['documents']:
        item=dict(document)
        identity_key = item['source_id']+':'+item['sha256']
        existing = service.store.get('documents', identity_key)
        if not existing:
            # Use existing ID if available, otherwise generate new one
            existing_by_id = service.store.get('documents', item.get('id'))
            if existing_by_id:
                # Record already exists with this ID, skip
                continue
            if not item.get('segments'):item['segments']=parse_content(Path(item['path']).read_bytes(),item['media'])
            service.store.put('documents', identity_key, item)
    for fact in seed['facts']:
        existing = service.store.get('facts', fact['id'])
        if not existing:
            service.store.put('facts', fact['id'], fact)
    for event in seed.get('events',[]):
        event_id = event.get('id') or hashlib.sha256(json.dumps(event,sort_keys=True).encode()).hexdigest()
        existing = service.store.get('events', event_id)
        if not existing:
            service.store.put('events', event_id, event)


def create_app(directory=DATA, *, seed=True, scheduler=True, frontend_port=3101,
               offline=False, api_port=7780, extra_frontend_port=None):
    if not isinstance(frontend_port,int) or not 1024 <= frontend_port <= 65535:
        raise ValueError('Invalid loopback frontend port')
    if type(api_port) is not int or not 1024 <= api_port <= 65535:raise ValueError('Invalid loopback API port')
    allowed_origins=[f'http://localhost:{frontend_port}',f'http://127.0.0.1:{frontend_port}']
    if extra_frontend_port is not None:
        if type(extra_frontend_port) is not int or not 1024 <= extra_frontend_port <= 65535:raise ValueError('Invalid extra frontend port')
        allowed_origins.extend([f'http://localhost:{extra_frontend_port}',f'http://127.0.0.1:{extra_frontend_port}'])
    store=Store(directory);service=MarketService(store);service.recover_jobs()
    from .jev_shadow import JevShadowObserver, ShadowConfig
    offline_shadow = ShadowConfig(enabled=False)
    shadow=JevShadowObserver(store.root, offline_shadow if offline else None)
    from .query_router import QueryRouter, QUERY_ROUTE
    router=QueryRouter(store.root, config=offline_shadow if offline else None)
    service.query_router=router
    if seed:initialize(service)
    native_db=SqliteDb(id='london-product',db_file=str(store.root/'agno.sqlite3'))
    service.workflow=make_monitor_workflow(service,native_db)
    service.report_workflow=make_report_workflow(service,native_db)
    service.query_workflow=make_saved_query_workflow(service,native_db)
    # Credential-free mode must not even construct a provider-backed Agent.
    # Its UI ask route is forced through the deterministic saved-evidence path
    # below, while the live application retains the existing factory.
    service.agent_factory=None if offline else lambda:query_agent(service,native_db)
    from .research import ResearchWorker, ResearchInput
    research=ResearchWorker(service,native_db)

    @asynccontextmanager
    async def lifespan(_app):
        if scheduler:
            service.schedule_manager=ScheduleManager(native_db)
            service.sync_schedules()
        try:
            yield
        finally:
            shadow.close()
            router.close()
            service.pool.shutdown(wait=False,cancel_futures=True)

    base=FastAPI(title='London Office Market Product',lifespan=lifespan)
    from .offline_api import (
        DISCLAIMER, offline_health_payload, register_offline_endpoints,
        skill_names_for_message,
    )
    register_offline_endpoints(base, service)
    from .model_connections import register_connections, Connections, owner, ACTIVE_CONNECTION, ACTIVE_ATTACHMENTS
    from .attachments import register_attachments, attachment_context
    register_connections(base, store)
    register_attachments(base, store)

    @base.get('/api/market/release')
    def release_identity():
        from .release_identity import runtime_identity
        result=runtime_identity(service,offline)
        result['workflow_ids']=[service.workflow.id,service.report_workflow.id,
            service.query_workflow.id,research.workflow.id]
        return result

    def health_payload():
        result=offline_health_payload(service)
        if not offline:
            result.update(mode='live',model_execution_available=True,model_call_verified=False,
                disclaimer='Saved source evidence with optional real model execution. Connection availability is not a verified model response or market conclusion.')
        else:result.update(model_execution_available=False,model_call_verified=False)
        return result

    @base.middleware('http')
    async def local_boundary(request,call_next):
        host=request.headers.get('host','').split(':')[0]
        origin=request.headers.get('origin')
        if host not in ['127.0.0.1','localhost','testserver']:
            return JSONResponse({'detail':'Loopback host required'},status_code=403)
        # AgentOS owns /health; serve truthful product execution metadata at
        # the boundary rather than letting its generic route erase the mode.
        if request.method=='GET' and request.url.path=='/health':
            return JSONResponse(health_payload())
        if request.method not in ['GET','HEAD','OPTIONS'] and origin and origin not in allowed_origins:
            return JSONResponse({'detail':'Untrusted origin'},status_code=403)
        return await call_next(request)

    @base.exception_handler(KeyError)
    async def missing(_request,exc):
        return JSONResponse({'detail':'Record not found','sources':[],
            'disclaimer':DISCLAIMER},status_code=404)
    @base.exception_handler(ValueError)
    async def invalid(_request,exc):
        from .safe_answer import english_text
        return JSONResponse({'detail':english_text(str(exc))[:180],'sources':[],
            'disclaimer':DISCLAIMER},status_code=422)
    @base.exception_handler(RequestValidationError)
    async def invalid_request(_request,exc):
        errors=[{k:v for k,v in e.items() if k not in ['ctx','input']} for e in exc.errors()]
        return JSONResponse({'detail':errors,'sources':[],
            'disclaimer':DISCLAIMER},status_code=422)

    @base.get('/api/market/overview')
    def overview():return service.overview()

    @base.get('/api/market/routing/shadow')
    def routing_shadow_status():return shadow.status()

    @base.get('/api/market/routing')
    def query_routing_status():return router.status()

    from .contracts import ClassifyInput
    @base.post('/api/market/routing/classify')
    async def classify_query(data:ClassifyInput):
        if offline:
            return JSONResponse(dict(detail='OFFLINE_EXTERNAL_IO_DISABLED',sources=[],
                disclaimer=DISCLAIMER),status_code=409)
        return await router.classify(data.message,data.mode,allow_research=True)

    @base.get('/api/market/coverage')
    def coverage():
        from .indicators import coverage as current_coverage
        return current_coverage(store)

    @base.get('/api/market/sessions/{session_id}/runs/{run_id}/publication')
    def publication(session_id:str, run_id:str):
        from agno.db.base import SessionType
        from .safe_answer import project_run
        session=native_db.get_session(session_id,session_type=SessionType.AGENT,deserialize=False)
        if not session:raise HTTPException(404,'Run not found')
        run=next((r for r in session.get('runs',[]) if r.get('run_id')==run_id),None)
        if not run:raise HTTPException(404,'Run not found')
        return project_run(run,store)

    @base.get('/api/market/facts')
    def facts(geography:str='',metric:str='',period:str='',status:str='',source_id:str='',limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0)):
        return service.facts(geography=geography,metric=metric,period=period,status=status,source_id=source_id,limit=limit,offset=offset)

    @base.get('/api/market/search')
    def search_evidence(q:str=Query(...,min_length=1,max_length=300),record_type:str|None=None,
                        source_id:str|None=None,geography:str|None=None,period:str|None=None,
                        metric:str|None=None,review_status:str|None=None,limit:int=Query(20,ge=1,le=50)):
        items=store.search_evidence(q,record_type=record_type,source_id=source_id,
            geography=geography,period=period,metric=metric,review_status=review_status,limit=limit)
        return dict(items=items,total=len(items),model_requests=0,index='sqlite_fts5_v3')

    @base.get('/api/market/performance')
    def performance(kind:str|None=None,route:str|None=None):
        from .phase_trace import summarize
        return summarize(store.root,kind=kind,route=route)

    @base.get('/api/market/facts/{identity}/evidence')
    def evidence(identity:str):return service.evidence(identity)

    @base.get('/api/market/reviews')
    def reviews(status:str='pending'):
        queue=service.review_queue(status)
        return dict(queue=queue, decisions=store.all('reviews')[:200],
                    counts=queue['counts'])

    @base.post('/api/market/facts/{identity}/review')
    def review_fact(identity:str, data:ReviewInput):
        return service.review_fact(identity, data.decision, data.reviewer, data.note)

    @base.get('/api/market/directional')
    def directional_assessment():
        from . import directional
        return directional.assess(store)

    @base.get('/api/market/sources')
    def sources():return dict(items=store.all('sources'))

    @base.patch('/api/market/sources/{identity}')
    def source_settings(identity:str,values:dict):
        source=store.get('sources',identity)
        if not source:raise KeyError(identity)
        if set(values)!= {'enabled'} or not isinstance(values['enabled'],bool):raise ValueError('Only enabled boolean is editable')
        if values['enabled'] and source.get('allow_llm') is False:raise ValueError('Source policy restriction: requires review before enabling')
        return store.update('sources',identity,values)

    @base.post('/api/market/refresh',status_code=202)
    def refresh(idempotency_key:str|None=Header(None)):
        if offline:
            return JSONResponse(dict(detail='OFFLINE_EXTERNAL_IO_DISABLED',sources=[],
                disclaimer=DISCLAIMER),status_code=409)
        return service.submit('refresh',key=idempotency_key)

    @base.post('/api/market/sources/{identity}/refresh',status_code=202)
    def refresh_source(identity:str,idempotency_key:str|None=Header(None)):
        if not store.get('sources',identity):raise KeyError(identity)
        if offline:
            return JSONResponse(dict(detail='OFFLINE_EXTERNAL_IO_DISABLED',sources=[],
                disclaimer=DISCLAIMER),status_code=409)
        return service.submit('refresh',source_id=identity,key=idempotency_key)

    @base.get('/api/market/documents')
    def documents():return dict(items=[{k:v for k,v in d.items() if k not in ['segments','path']} for d in store.all('documents')])

    @base.get('/api/market/documents/{identity}/file')
    def document_file(identity:str):
        document=store.get('documents',identity)
        if not document:raise KeyError(identity)
        path=Path(document['path']).resolve()
        if not path.is_relative_to(store.root) or not path.is_file():raise HTTPException(404,'Stored original unavailable')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=document['sha256']:raise HTTPException(409,'Original hash mismatch')
        return FileResponse(path,media_type=document['media'],filename=document['sha256']+('.pdf' if 'pdf' in document['media'] else '.txt'))

    @base.post('/api/market/documents/{identity}/extract',status_code=202)
    def extract(identity:str,idempotency_key:str|None=Header(None)):
        doc=store.get('documents',identity)
        if not doc:raise KeyError(identity)
        if offline:
            return JSONResponse(dict(detail='OFFLINE_EXTERNAL_IO_DISABLED',sources=[],
                disclaimer=DISCLAIMER),status_code=409)
        source=store.get('sources',doc['source_id']) or {}
        if not source.get('allow_llm',True):raise HTTPException(409,'Source policy prohibits AI processing')
        return service.submit('extract',document_id=identity,key=idempotency_key)

    @base.get('/api/market/events')
    def events(geography:str='',kind:str='',importance:str='',status:str=''):
        items=[e for e in store.all('events') if (status=='superseded' or e.get('status')!='superseded') and (kind=='source_update' or e.get('kind')!='source_update') and all(not v or v=='all' or e.get(k)==v for k,v in dict(geography=geography,kind=kind,importance=importance,status=status).items())]
        from .structured_sources import current_event
        return dict(items=[current_event(e) for e in items],total=len(items))

    @base.post('/api/market/events/{identity}/ack')
    def acknowledge(identity:str):return store.update('events',identity,dict(status='acknowledged',acknowledged_at=now()))

    @base.get('/api/market/comparisons')
    def comparisons():return dict(items=store.all('comparisons'))

    @base.post('/api/market/compare')
    def compare(data:CompareInput):
        result,run_id=run_saved_query_workflow(service,'compare',old_id=data.old_id,new_id=data.new_id)
        return dict(result,run_id=run_id,execution_path='agno_workflow')

    @base.get('/api/market/reports')
    def reports():
        from .chat_report import read_report
        items=[]
        for r in store.all('reports'):
            status=read_report(store,r['id'])['generation_status'] if r.get('artifact') else r.get('generation_status')
            items.append(dict(id=r['id'],title=('[Superseded] ' if r.get('status')=='superseded' else '')+('[AI interpretation · REVIEW_REQUIRED] ' if r.get('analysis_status')=='REVIEW_REQUIRED' else '')+r['title'],created_at=r['created_at'],period=r['period'],status=r.get('status','current'),
                report_type=r.get('report_type'),generation_status=status,
                markdown_url=f"/api/market/reports/{r['id']}?format=markdown",html_url=f"/api/market/reports/{r['id']}?format=html"))
        return dict(items=items)

    @base.post('/api/market/reports')
    def report(data:ReportInput,idempotency_key:str|None=Header(None)):
        if data.include_analysis and data.geography:
            raise ValueError('Scoped reports currently support saved evidence only; AI scope requires separate validation')
        if data.include_analysis:
            if offline:
                return JSONResponse(dict(detail='OFFLINE_EXTERNAL_IO_DISABLED',sources=[],
                    disclaimer=DISCLAIMER),status_code=409)
            return JSONResponse(service.submit('report_analysis',period=data.period,key=idempotency_key),status_code=202)
        return service.generate_report(data.period,key=idempotency_key,geography=data.geography)

    @base.get('/api/market/reports/{identity}')
    def report_file(identity:str,format:str='html',download:bool=False):
        row=store.get('reports',identity)
        if not row:raise KeyError(identity)
        if format=='json':
            if row.get('artifact'):
                from .chat_report import read_report
                payload=read_report(store,identity)
            else:payload=row
            from urllib.parse import quote
            headers={'Content-Disposition':f'attachment; filename="report-{quote(identity,safe="")}.json"'} if download else {}
            return JSONResponse(payload,headers=headers)
        if row.get('artifact'):
            from .chat_report import read_report, render_markdown, render_html
            artifact=read_report(store,identity)
            if format=='json':return artifact
            if format not in ['html','markdown']:raise ValueError('Unsupported report format')
            markdown=render_markdown(artifact)
            from urllib.parse import quote
            export_headers={'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'"}
            if download or format=='markdown':
                suffix='html' if format=='html' else 'md'
                export_headers['Content-Disposition']=f'attachment; filename="report-{quote(identity,safe="")}.{suffix}"'
            return Response(render_html(artifact) if format=='html' else markdown,
                media_type='text/html' if format=='html' else 'text/markdown',
                headers=export_headers)
        if format not in ['html','markdown']:raise ValueError('Unsupported report format')
        body=report_view(row,store,format)
        if row.get('quality_issues') or row.get('known_quality_issues'):
            issues='DRAFT QUALITY REVIEW: '+'; '.join(row.get('quality_issues') or row.get('known_quality_issues'))
            body=('# '+issues+'\n\n'+body) if format=='markdown' else body.replace('<h1>','<p>'+html.escape(issues)+'</p><h1>',1)
        if row.get('status')=='superseded':
            notice='SUPERSEDED REPORT: '+row.get('revision_reason','A later report corrects known quality issues; retain this version for audit only.')
            body=('# '+notice+'\n\n'+body) if format=='markdown' else body.replace('<h1>','<p>'+html.escape(notice)+'</p><h1>',1)
        return Response(body,media_type='text/html' if format=='html' else 'text/markdown',headers={'Content-Disposition':f'attachment; filename="london-{identity}.{"html" if format=="html" else "md"}"','Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'"})

    @base.get('/api/market/jobs')
    def jobs():return dict(items=store.all('jobs')[:200])

    @base.post('/api/market/research/jobs',status_code=202)
    def research_job(data:ResearchInput,idempotency_key:str|None=Header(None)):
        return research.submit(data,key=idempotency_key)

    @base.get('/api/market/jobs/{identity}')
    def job(identity:str):
        value=store.get('jobs',identity)
        if not value:raise KeyError(identity)
        return value

    @base.post('/api/market/jobs/{identity}/retry',status_code=202)
    def retry(identity:str,idempotency_key:str|None=Header(None)):
        old=store.get('jobs',identity)
        if not old:raise KeyError(identity)
        if old['status'] not in ['failed','interrupted','partial']:raise HTTPException(409,'Only failed/interrupted/partial jobs may be retried')
        if old['kind']=='research':
            if not idempotency_key:raise ValueError('Research retry requires a fresh Idempotency-Key')
            return research.submit(ResearchInput(question=old['question'],refresh_sources=old['refresh_sources'],
                source_id=old.get('source_id')),key=idempotency_key,retry_of=identity)
        if old['kind'] not in ['refresh','extract']:raise HTTPException(409,'Retry this action from its Ask or Reports page; model calls are never replayed implicitly')
        if offline:
            return JSONResponse(dict(detail='OFFLINE_EXTERNAL_IO_DISABLED',sources=[],
                disclaimer=DISCLAIMER),status_code=409)
        return service.submit(old['kind'],source_id=old.get('source_id'),document_id=old.get('document_id'),category=old.get('category'),key=idempotency_key,retry_of=identity)

    @base.get('/api/market/settings')
    def settings():return service.settings()

    @base.put('/api/market/settings')
    def save_settings(values:dict):return service.save_settings(values)

    @base.post('/api/market/notifications')
    def notification(data:NotifyInput):
        if offline:
            return JSONResponse(dict(detail='OFFLINE_EXTERNAL_IO_DISABLED',sources=[],
                disclaimer=DISCLAIMER),status_code=409)
        return service.notify(data.report_id)

    @base.get('/api/market/notifications')
    def notifications():return dict(items=store.all('notifications'))

    @base.get('/api/market/notifications/configuration')
    def notification_configuration():return service.notification_configuration()

    @base.post('/api/market/scheduled/{category}')
    def scheduled(category:str,idempotency_key:str|None=Header(None)):
        if category not in ['news','market','report-daily','report-weekly']:raise KeyError(category)
        if offline and category in ['news','market']:
            return JSONResponse(dict(detail='OFFLINE_EXTERNAL_IO_DISABLED',sources=[],
                disclaimer=DISCLAIMER),status_code=409)
        if not service.settings()['monitoring_enabled']:raise HTTPException(409,'Monitoring disabled')
        if category.startswith('report-'):
            period=category.removeprefix('report-'); stamp=now()[:10]
            report=service.generate_report(period,key='scheduled-'+period+'-'+stamp)
            notifications_requested=(not offline) and service.settings()['notifications_enabled']
            delivery=service.notify(report['id']) if notifications_requested else {'status':'disabled'}
            partial=notifications_requested and delivery.get('status')!='sent'
            return JSONResponse(dict(report_id=report['id'],report_status='succeeded',notification=delivery,
                status='partial' if partial else 'succeeded',run_id=report.get('workflow_run_id')),
                status_code=207 if partial else 200)
        # The native scheduler serializes scheduled occurrences. An explicit key
        # additionally protects operator/API replay without coalescing retries.
        identity='scheduled:'+category+':'+idempotency_key if idempotency_key else uid()
        with service._lock:
            row=store.get('jobs',identity)
            if row:
                code=503 if row['status'] in ['failed','interrupted'] else (207 if row['status']=='partial' else (202 if row['status'] in ['queued','running'] else 200))
                return JSONResponse(dict(row,deduplicated=True),status_code=code)
            row=store.put('jobs',identity,dict(kind='refresh',category=category,status='queued',stage='scheduled',progress=0,attempts=1,started_at=now(),source_id=None,document_id=None))
        service._run_job(row)
        result=store.get('jobs',row['id'])
        # Agno's generic endpoint executor checks HTTP status, not the JSON
        # business status. Never record an all-source failure as HTTP success.
        code=503 if result['status']=='failed' else (207 if result['status']=='partial' else 200)
        return JSONResponse(result,status_code=code)

    @base.post('/api/market/ask')
    async def ask(data:AskInput,request:Request,idempotency_key:str|None=Header(None)):
        personal=None;uploads=[]
        if data.connection_id or data.attachment_ids:
            browser=owner(request)
            if data.connection_id:
                if offline:raise ValueError('Personal model calls are disabled in offline mode.')
                personal=Connections(store).select(browser,data.connection_id,data.model,data.thinking)
            uploads=attachment_context(store,browser,data.attachment_ids)
        elif data.model or data.thinking!='standard':raise ValueError('Select a personal model connection first.')
        if uploads and not personal:raise ValueError('Select a personal model connection to use attachments in chat.')
        if not data.session_id:data.session_id=uid()
        if data.parent_report_id and not store.get('reports',data.parent_report_id):
            raise ValueError('PARENT_REPORT_NOT_FOUND')
        request_state=dict(job_id=None,run_id=None,workflow_run_ids=[])

        async def saved_workflow(kind, **fields):
            result,identity=await asyncio.to_thread(run_saved_query_workflow,service,kind,**fields)
            request_state['workflow_run_ids'].append(identity)
            store.update('jobs',request_state['job_id'],dict(workflow_run_ids=list(request_state['workflow_run_ids'])))
            return result,identity

        async def stream():
            def event(payload):return 'data: '+json.dumps(payload,ensure_ascii=False,default=str)+'\n\n'
            started=time.perf_counter();first=None
            from .phase_trace import PhaseTrace
            trace=PhaseTrace(store.root,'ask',data.message)
            yield event(dict(type='progress',stage='routing',session_id=data.session_id,message='Classifying the request and selecting available capabilities.'))
            focused,focused_run_id=await saved_workflow('focused',question=data.message,
                parent_report_id=data.parent_report_id,session_id=data.session_id,requested_mode=data.mode)
            if not data.parent_report_id and focused.get('report_id'):data.parent_report_id=focused['report_id']
            forced_analysis=data.mode=='agent' and focused['operation'] in [
                'data_question','follow_up','evidence_audit','clarification','future_uncertainty']
            if focused['handled'] and not forced_analysis:
                focused_outcome=focused.get('outcome') or ('INSUFFICIENT_EVIDENCE' if str(focused.get('status','')).lower() in ['insufficient_evidence','context_required','blocked'] else 'ANSWERED')
                row=store.update('jobs',request_state['job_id'],dict(status='partial' if focused_outcome=='INSUFFICIENT_EVIDENCE' else 'succeeded',stage=focused['operation'],
                    progress=100,finished_at=now(),result=focused,run_id=focused_run_id))
                yield event(dict(type='token',content=focused['answer']))
                metrics=dict(model_requests=0,total_seconds=time.perf_counter()-started,
                    route=dict(mode='saved',intent=focused['operation'],classifier='operational_rules'))
                if not offline:
                    shadow.submit(data.message,metrics['route'],data.mode,row['id'])
                trace.route='saved';trace.mark('routing');trace.finish('succeeded',model_requests=0)
                yield event(dict(type='done',outcome=focused_outcome,operation=focused['operation'],report_id=focused.get('report_id'),
                    run_id=focused_run_id,execution_path='agno_workflow',
                    citations=focused.get('sources',[]),metrics=metrics,submission_id=row['id'],
                    skill_calls=[dict(skill='verification',datasource='saved_snapshots')],
                    as_of=offline_health_payload(service)['data_asof'],disclaimer=DISCLAIMER))
                return
            if offline:
                route=dict(intent='saved_lookup',mode='saved',classifier='offline_policy',
                    classification_status='deterministic',confidence=1.0,jev_attempted=False,
                    reason='Credential-free runtime uses saved evidence only.',
                    limitations=['Provider-backed analysis, external research and source refresh are disabled in mock mode.'])
            else:
                route=await router.classify(data.message,data.mode,allow_research=True)
            trace.route=route['mode'];trace.mark('routing')
            row=store.update('jobs',request_state['job_id'],dict(status='running',stage=route['mode'],route=route,progress=10))
            if not offline and route['mode']!='research' and not route.get('jev_attempted'):
                shadow.submit(data.message, route, data.mode, row['id'])
            if route.get('limitations') and route['mode']!='research':
                yield event(dict(type='progress',stage='capability_limits',message='Only saved evidence and existing analysis are available. Latest coverage must be checked; no deep-research worker is configured.'))
            if route['mode']=='research':
                yield event(dict(type='progress',stage='research',submission_id=row['id'],
                    message='Starting a background workflow over saved evidence. Progress and the report will appear in Job Status.'))
                try:
                    research_job=research.submit(ResearchInput(question=data.message,refresh_sources=False),
                        key=idempotency_key or row['id'])
                except Exception as exc:
                    store.update('jobs',row['id'],dict(status='failed',stage='research',
                        error=type(exc).__name__,finished_at=now()))
                    trace.finish('failed',model_requests=0)
                    yield event(dict(type='error',code='RESEARCH_START_FAILED',
                        message='Background research could not start. Inspect Job Status; no model analysis was generated.'))
                    return
                answer=('Background saved-evidence research started. Open Job Status for progress and the report. '
                    'Findings retain their source and review status; no model analysis has been generated.')
                yield event(dict(type='token',content=answer))
                metrics=dict(ttft_seconds=time.perf_counter()-started,total_seconds=time.perf_counter()-started,
                    model_requests=0,classifier_requests=0,route=route)
                trace.mark('evidence');trace.mark('publication')
                metrics['phases_ms']=trace.finish('succeeded',model_requests=0)['phases_ms']
                store.update('jobs',row['id'],dict(status='succeeded',stage='complete',progress=100,
                    finished_at=now(),result={'research_job_id':research_job['id']},metrics=metrics))
                yield event(dict(type='done',citations=[],run_id=None,metrics=metrics,
                    research_job_id=research_job['id'],submission_id=row['id']))
                return
            from .chat_report import ACTIVE_REPORT
            yield event(dict(type='progress',stage='evidence',submission_id=row['id'],message='Checking saved sources, scope and evidence.'))
            acquisition=None
            if data.refresh_sources and offline:
                acquisition=dict(mode='offline_disabled',status='not_run',
                    notice='External source refresh is disabled in credential-free mock mode.')
                yield event(dict(type='progress',stage='acquisition',message=acquisition['notice']))
            elif data.refresh_sources:
                # Reuse the original collection workflow and its policy gates.
                refresh_job=service.submit('refresh')
                while store.get('jobs',refresh_job['id'])['status'] in ['queued','running']:
                    yield event(dict(type='progress',stage='acquisition',job_id=refresh_job['id'],message='Refreshing enabled sources through existing Jobs.'))
                    await asyncio.sleep(1)
                refreshed=store.get('jobs',refresh_job['id'])
                acquisition=dict(mode='existing_refresh_job',job_id=refreshed['id'],status=refreshed['status'],notice='Source failures remain visible in Jobs; extraction/review is not implied.')
            trace.mark('acquisition')
            report_workflow_run_id=None
            try:
                yield event(dict(type='progress',stage='validation',message='Verifying original hashes, quotes, review state and comparability.'))
                if focused['operation']=='new_report':
                    from .chat_report import read_report
                    research_job=research.submit(ResearchInput(question=data.message,refresh_sources=False),key=row['id'])
                    for _ in range(120):
                        current=store.get('jobs',research_job['id'])
                        if current['status'] not in ['queued','running']:break
                        yield event(dict(type='progress',stage='research',job_id=current['id'],message='Running the existing research workflow; evidence and coverage checks are in progress.'))
                        await asyncio.sleep(.25)
                    else:raise ValueError('RESEARCH_STILL_RUNNING: inspect Job Status')
                    if not (current.get('result') or {}).get('report_id'):raise ValueError('RESEARCH_REPORT_UNAVAILABLE')
                    artifact=read_report(store,current['result']['report_id'])
                    acquisition=dict(artifact.get('acquisition') or {},research_job_id=current['id'],research_status=current['status'])
                    artifact['acquisition']=acquisition
                    store.update('reports',artifact['report_id'],dict(artifact=artifact))
                else:
                    result,report_workflow_run_id=await saved_workflow('report_context',question=data.message,
                        parent_report_id=data.parent_report_id,key=row['id'],acquisition=acquisition,
                        analysis_context=dict(submission_id=row['id']) if route['mode']=='agent' else None)
                    artifact=store.get('reports',result['report_id'])['artifact']
                if data.session_id:
                    pointer=store.put('settings','conversation:'+data.session_id,dict(report_id=artifact['report_id']))
                    store.update('settings',pointer['id'],dict(report_id=artifact['report_id']))
                trace.mark('evidence')
            except Exception as exc:
                store.update('jobs',row['id'],dict(status='failed',stage='report_build',error=type(exc).__name__,finished_at=now()))
                trace.finish('failed',model_requests=0)
                yield event(dict(type='error',code='REPORT_BUILD_FAILED',message='Report construction failed. Inspect Jobs; no report was published.'))
                return
            yield event(dict(type='report',report=artifact,report_id=artifact['report_id']))
            store.update('jobs',row['id'],dict(result={'report_id':artifact['report_id']}))
            if route['mode']=='saved':
                from .chat_report import render_markdown
                answer=render_markdown(artifact)
                citations=[dict(fact_id=e['fact_id'],document_id=e['document_id'],url=e['url'],title=e['report_title']) for e in artifact['evidence']]
                for piece in answer.splitlines(keepends=True):
                    if first is None:first=time.perf_counter()
                    yield event(dict(type='token',content=piece))
                metrics=dict(ttft_seconds=first-started if first else None,total_seconds=time.perf_counter()-started,model_requests=0,classifier_requests=int(route.get('jev_attempted',False)),route=route)
                trace.mark('publication');receipt=trace.finish('succeeded',model_requests=0)
                metrics['phases_ms']=receipt['phases_ms']
                store.update('jobs',row['id'],dict(status='partial' if artifact['generation_status']!='success' else 'succeeded',
                    quality_status=artifact['generation_status'],stage='complete',progress=100,finished_at=now(),metrics=metrics,
                    run_id=report_workflow_run_id))
                yield event(dict(type='done',citations=citations,run_id=report_workflow_run_id,
                    execution_path='agno_workflow',workflow_run_ids=[focused_run_id,report_workflow_run_id],metrics=metrics,
                    report_id=artifact['report_id'],submission_id=row['id'],
                    skill_calls=[dict(skill=name,datasource='saved_snapshots')
                                 for name in skill_names_for_message(data.message)],
                    as_of=offline_health_payload(service)['data_asof'],disclaimer=DISCLAIMER));return
            yield event(dict(type='progress',stage='analysis',message='Preparing model interpretation; the saved report remains available.'))
            agent=service.agent_factory();run_id=None;answer='';completed=False;tool_calls=[];stage='model';evidence_status=None;retrieved_urls=set();evidence_packs=[]
            route_context=QUERY_ROUTE.set(route)
            report_context=ACTIVE_REPORT.set(artifact['report_id'])
            try:
                # ACTIVE_REPORT and the evidence tool own deterministic scope.
                # Persist the user's exact question for saved-chat consistency.
                scoped_message=data.message
                async for chunk in agent.arun(scoped_message,session_id=data.session_id,stream=True,stream_events=True):
                    run_id=getattr(chunk,'run_id',None) or run_id
                    request_state['run_id']=run_id
                    name=str(getattr(chunk,'event',''))
                    if name=='RunError':
                        raise RuntimeError(classify_error(getattr(chunk,'content',None),getattr(chunk,'error_type','') or ''))
                    if name=='RunCompleted':completed=True
                    if name=='ToolCallCompleted':
                        tool=getattr(chunk,'tool',None)
                        tool_calls.append(getattr(tool,'tool_name',None) or getattr(tool,'name',None) or str(tool)[:120])
                        stage='skills' if getattr(tool,'tool_name',None)=='load_market_skills' else 'retrieval'
                        if getattr(tool,'tool_call_error',False):raise ValueError('TOOL_ERROR')
                        if getattr(tool,'tool_name',None)=='load_market_skills':
                            loaded=json.loads(getattr(tool,'result','{}'))
                            store.update('jobs',row['id'],dict(skill_execution=dict(
                                requested_skills=loaded.get('requested_skills',[]),
                                policy_added_skills=loaded.get('policy_added_skills',[]),
                                audit_id=loaded.get('audit_id'),projection_sha256=loaded.get('projection_sha256'))))
                            yield event(dict(type='progress',stage='skills_loaded',message='Loaded model-selected Skill instructions and verification policy from canonical files.'))
                        if getattr(tool,'tool_name',None)=='search_market_evidence':
                            pack=json.loads(getattr(tool,'result','{}'))
                            evidence_packs.append(pack)
                            evidence_status=pack.get('notice_code') or evidence_status
                            retrieved_urls.update(d['url'] for d in pack.get('documents',{}).values() if d.get('url'))
                            retrieved_urls.update(e.get('transaction_context',{}).get('url') for e in pack.get('events',[]) if e.get('transaction_context',{}).get('url'))
                        stage='final_answer'
                    content=getattr(chunk,'content',None)
                    if content and name in ['RunContent','RunContentEvent'] and isinstance(content,str):
                        if first is None:first=time.perf_counter()
                        answer+=content
                citations=[];seen=set()
                for doc in store.all('documents'):
                    if doc['url'] in answer and doc['url'] not in seen and (not retrieved_urls or doc['url'] in retrieved_urls):
                        seen.add(doc['url']);citations.append(dict(document_id=doc['id'],url=doc['url'],title=doc.get('title')))
                if tool_calls!=['load_market_skills','search_market_evidence'] or not (store.get('jobs',row['id']).get('skill_execution') or {}).get('audit_id'):
                    raise ValueError('SKILL_EXECUTION_INCOMPLETE')
                if not answer.strip() or not completed:raise ValueError('FINAL_ANSWER_MISSING')
                trace.mark('model')
                yield event(dict(type='progress',stage='publication_review',message='Checking the model draft before delivery.'))
                if artifact:
                    from .chat_report import attach_analysis
                    artifact=attach_analysis(store,artifact['report_id'],answer,run_id=run_id)
                    yield event(dict(type='report',report=artifact,report_id=artifact['report_id']))
                reviewed=review_analysis(answer,store,evidence_packs=evidence_packs)
                trace.mark('verification')
                if reviewed['publication_review']['status']!='withheld' and not citations and not any(reviewed['safe_evidence'].values()):
                    raise ValueError('NO_VERIFIED_EVIDENCE' if evidence_status else 'FINAL_ANSWER_MISSING')
                if not citations:
                    citations=list({i['document_id']:dict(document_id=i['document_id'],url=i['url'],title=i['report_title']) for group in reviewed['safe_evidence'].values() for i in group}.values())
                from .safe_answer import project_report_result
                project_report_result(reviewed, artifact)
                stage='publication_review'
                published_at=time.perf_counter()
                for piece in reviewed['answer'].splitlines(keepends=True):
                    yield event(dict(type='token',content=piece))
                metrics=dict(agent.model.budget_for(run_id).record(),provider_ttft_seconds=first-started if first else None,ttft_seconds=published_at-started,total_seconds=time.perf_counter()-started,classifier_requests=int(route.get('jev_attempted',False)),route=route)
                trace.mark('publication');receipt=trace.finish('succeeded',model_requests=metrics.get('requests',metrics.get('model_requests',0)))
                metrics['phases_ms']=receipt['phases_ms']
                outcome=reviewed.get('outcome','PARTIALLY_ANSWERED')
                store.update('jobs',row['id'],dict(status='succeeded' if outcome=='ANSWERED' else 'partial',stage='complete',progress=100,finished_at=now(),run_id=run_id,metrics=metrics,result=dict(reviewed,tool_calls=tool_calls,evidence_packs=evidence_packs,report_id=artifact['report_id']),quality_status=outcome))
                yield event(dict(type='done',outcome=outcome,citations=citations,run_id=run_id,metrics=metrics,submission_id=row['id'],notice_code=evidence_status,publication_review=reviewed['publication_review'],report_id=artifact['report_id'],workflow_run_ids=list(request_state['workflow_run_ids']),execution_path='agno_agent_and_workflow'))
            except asyncio.CancelledError:
                from .chat_report import attach_analysis
                attach_analysis(store,artifact['report_id'],error='CLIENT_CANCELLED',run_id=run_id)
                budget=agent.model.budget_for(run_id);budget.failed(RuntimeError('CLIENT_CANCELLED'))
                store.update('jobs',row['id'],dict(status='cancelled',stage='cancelled',finished_at=now(),run_id=run_id,metrics=budget.record(),result={'partial_answer':answer,'report_id':artifact['report_id']}))
                trace.finish('cancelled',model_requests=budget.record().get('requests',0))
                raise
            except Exception as exc:
                from .chat_report import attach_analysis
                artifact=attach_analysis(store,artifact['report_id'],error='MODEL_EXECUTION_FAILED',run_id=run_id)
                yield event(dict(type='report',report=artifact,report_id=artifact['report_id']))
                code=classify_error(str(exc),type(exc).__name__)
                message=error_message(code)
                metrics=agent.model.budget_for(run_id).record()
                store.update('jobs',row['id'],dict(status='failed',stage=stage,finished_at=now(),run_id=run_id,error=message,error_code=code,metrics=metrics,result=dict(raw_answer=answer,tool_calls=tool_calls,report_id=artifact['report_id'],final_answer_generated=bool(answer.strip()) and completed)))
                trace.finish('failed',model_requests=metrics.get('requests',0))
                yield event(dict(type='error',code=code,message=message,run_id=run_id,metrics=metrics,stage=stage,submission_id=row['id'],report_id=artifact['report_id'],final_answer_generated=bool(answer.strip()) and completed))
            finally:
                ACTIVE_REPORT.reset(report_context)
                QUERY_ROUTE.reset(route_context)
        async def guarded_stream():
            # Own one persisted job before routing or any generator work. The
            # outer boundary covers failures in report building, publication,
            # exception handling and cleanup as well as provider streaming.
            row=store.put('jobs',uid(),dict(kind='ask',status='running',stage='routing',
                progress=0,started_at=now(),attempts=1,request_id=uid(),session_id=data.session_id))
            request_state['job_id']=row['id']
            connection_context=ACTIVE_CONNECTION.set(personal)
            attachments_context=ACTIVE_ATTACHMENTS.set(tuple(uploads))
            try:
                async for payload in stream():yield payload
            except asyncio.CancelledError:
                store.update('jobs',row['id'],dict(status='cancelled',stage='cancelled',finished_at=now(),
                    run_id=request_state['run_id'],error_code='CLIENT_CANCELLED',error='The request was cancelled.'))
                raise
            except Exception as exc:
                code=classify_error(str(exc),type(exc).__name__)
                message=error_message(code)
                store.update('jobs',row['id'],dict(status='failed',finished_at=now(),
                    run_id=request_state['run_id'],error_code=code,error=message,
                    diagnostic=dict(exception_type=type(exc).__name__,request_id=row['request_id'])))
                yield 'data: '+json.dumps(dict(type='error',code=code,message=message,
                    submission_id=row['id'],request_id=row['request_id'],run_id=request_state['run_id'],
                    outcome='PROVIDER_ERROR',retryable=code not in ['MODEL_AUTHENTICATION_FAILED','PROVIDER_QUOTA_EXHAUSTED','TOKEN_ESTIMATOR_UNCALIBRATED']))+'\n\n'
            finally:
                ACTIVE_ATTACHMENTS.reset(attachments_context)
                ACTIVE_CONNECTION.reset(connection_context)
                current=store.get('jobs',row['id'])
                if current and current['status'] in ['running','queued']:
                    store.update('jobs',row['id'],dict(status='failed',finished_at=now(),
                        error_code='FINAL_ANSWER_MISSING',error=error_message('FINAL_ANSWER_MISSING')))
        return StreamingResponse(guarded_stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

    @base.post('/api/market/conversation')
    def conversation(data:AskInput):
        parent=data.parent_report_id
        if not parent and data.session_id:
            from agno.db.base import SessionType
            session=native_db.get_session(data.session_id,session_type=SessionType.AGENT,deserialize=False)
            state=(session or {}).get('session_data',{}).get('session_state',{}) or {}
            parent=state.get('_market_report_id')
        result,run_id=run_saved_query_workflow(service,'focused',question=data.message,
            parent_report_id=parent,session_id=data.session_id,requested_mode=data.mode)
        return dict(result,workflow_run_id=run_id,execution_path='agno_workflow')

    if offline:
        # Expose only the saved-evidence product surface. AgentOS would mount
        # provider-oriented routes and override /health even with agents=[].
        base.add_middleware(CORSMiddleware,allow_origins=allowed_origins,
            allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
        base.state.market=service
        base.state.jev_shadow=shadow
        base.state.query_router=router
        return base

    agent_os=AgentOS(id='london-market-product',name='London Office Market',db=native_db,
        agents=[service.agent_factory()],workflows=[service.workflow,service.report_workflow,
            service.query_workflow,research.workflow],base_app=base,scheduler=scheduler,
        scheduler_poll_interval=5,scheduler_base_url=f'http://127.0.0.1:{api_port}',telemetry=False,tracing=True,
        cors_allowed_origins=allowed_origins)
    app=agent_os.get_app();app.state.market=service;app.state.agent_os=agent_os
    # AgentOS installs CORS without cookies; put the local browser-owned API
    # boundary outside it so preflight and responses retain credential support.
    app.add_middleware(CORSMiddleware,allow_origins=allowed_origins,
        allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
    app.state.jev_shadow=shadow
    app.state.query_router=router
    return app


if __name__=='__main__':
    import uvicorn
    uvicorn.run(create_app(),host='127.0.0.1',port=7780)
