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
from fastapi.responses import FileResponse, Response, StreamingResponse, JSONResponse
from agno.os import AgentOS
from agno.db.sqlite import SqliteDb
from agno.scheduler import ScheduleManager
from .store import Store, now, uid
from .service import MarketService
from .analysis_guard import review_analysis, report_view
from .contracts import AskInput, CompareInput, ReportInput, NotifyInput, ReviewInput
from .intelligence import query_agent, make_monitor_workflow, make_report_workflow
from .qa_context import classify_error

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
        if not item.get('segments'):item['segments']=parse_content(Path(item['path']).read_bytes(),item['media'])
        service.store.put('documents',item['source_id']+':'+item['sha256'],item)
    for fact in seed['facts']: service.store.put('facts',fact['id'],fact)
    for event in seed.get('events',[]): service.store.put('events',event.get('id') or hashlib.sha256(json.dumps(event,sort_keys=True).encode()).hexdigest(),event)


def create_app(directory=DATA, *, seed=True, scheduler=True):
    store=Store(directory);service=MarketService(store);service.recover_jobs()
    if seed:initialize(service)
    native_db=SqliteDb(id='london-product',db_file=str(store.root/'agno.sqlite3'))
    service.workflow=make_monitor_workflow(service,native_db)
    service.report_workflow=make_report_workflow(service,native_db)
    service.agent_factory=lambda:query_agent(service,native_db)

    @asynccontextmanager
    async def lifespan(_app):
        if scheduler:
            service.schedule_manager=ScheduleManager(native_db)
            service.sync_schedules()
        yield
        service.pool.shutdown(wait=False,cancel_futures=True)

    base=FastAPI(title='London Office Market Product',lifespan=lifespan)

    @base.middleware('http')
    async def local_boundary(request,call_next):
        host=request.headers.get('host','').split(':')[0]
        origin=request.headers.get('origin')
        if host not in ['127.0.0.1','localhost','testserver']:
            return JSONResponse({'detail':'Loopback host required'},status_code=403)
        if request.method not in ['GET','HEAD','OPTIONS'] and origin and origin not in ['http://localhost:3101','http://127.0.0.1:3101']:
            return JSONResponse({'detail':'Untrusted origin'},status_code=403)
        return await call_next(request)

    @base.exception_handler(KeyError)
    async def missing(_request,exc):return JSONResponse({'detail':'Record not found'},status_code=404)
    @base.exception_handler(ValueError)
    async def invalid(_request,exc):return JSONResponse({'detail':str(exc)[:180]},status_code=422)

    @base.get('/api/market/overview')
    def overview():return service.overview()

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
        return service.submit('refresh',key=idempotency_key)

    @base.post('/api/market/sources/{identity}/refresh',status_code=202)
    def refresh_source(identity:str,idempotency_key:str|None=Header(None)):
        if not store.get('sources',identity):raise KeyError(identity)
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
        source=store.get('sources',doc['source_id']) or {}
        if not source.get('allow_llm',True):raise HTTPException(409,'Source policy prohibits AI processing')
        return service.submit('extract',document_id=identity,key=idempotency_key)

    @base.get('/api/market/events')
    def events(geography:str='',kind:str='',importance:str='',status:str=''):
        items=[e for e in store.all('events') if (status=='superseded' or e.get('status')!='superseded') and (kind=='source_update' or e.get('kind')!='source_update') and all(not v or v=='all' or e.get(k)==v for k,v in dict(geography=geography,kind=kind,importance=importance,status=status).items())]
        return dict(items=items,total=len(items))

    @base.post('/api/market/events/{identity}/ack')
    def acknowledge(identity:str):return store.update('events',identity,dict(status='acknowledged',acknowledged_at=now()))

    @base.get('/api/market/comparisons')
    def comparisons():return dict(items=store.all('comparisons'))

    @base.post('/api/market/compare')
    def compare(data:CompareInput):return service.compare(data.old_id,data.new_id)

    @base.get('/api/market/reports')
    def reports():return dict(items=[dict(id=r['id'],title=('[Superseded] ' if r.get('status')=='superseded' else '')+('[AI interpretation · REVIEW_REQUIRED] ' if r.get('analysis_status')=='REVIEW_REQUIRED' else '')+r['title'],created_at=r['created_at'],period=r['period'],status=r.get('status','current'),
        markdown_url=f"/api/market/reports/{r['id']}?format=markdown",html_url=f"/api/market/reports/{r['id']}?format=html") for r in store.all('reports')])

    @base.post('/api/market/reports')
    def report(data:ReportInput,idempotency_key:str|None=Header(None)):
        if data.include_analysis:return JSONResponse(service.submit('report_analysis',period=data.period,key=idempotency_key),status_code=202)
        return service.generate_report(data.period,key=idempotency_key)

    @base.get('/api/market/reports/{identity}')
    def report_file(identity:str,format:str='html'):
        row=store.get('reports',identity)
        if not row:raise KeyError(identity)
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
        if old['kind'] not in ['refresh','extract']:raise HTTPException(409,'Retry this action from its Ask or Reports page; model calls are never replayed implicitly')
        return service.submit(old['kind'],source_id=old.get('source_id'),document_id=old.get('document_id'),category=old.get('category'),key=idempotency_key,retry_of=identity)

    @base.get('/api/market/settings')
    def settings():return service.settings()

    @base.put('/api/market/settings')
    def save_settings(values:dict):return service.save_settings(values)

    @base.post('/api/market/notifications')
    def notification(data:NotifyInput):return service.notify(data.report_id)

    @base.get('/api/market/notifications')
    def notifications():return dict(items=store.all('notifications'))

    @base.get('/api/market/notifications/configuration')
    def notification_configuration():return service.notification_configuration()

    @base.post('/api/market/scheduled/{category}')
    def scheduled(category:str,idempotency_key:str|None=Header(None)):
        if category not in ['news','market','report-daily','report-weekly']:raise KeyError(category)
        if not service.settings()['monitoring_enabled']:raise HTTPException(409,'Monitoring disabled')
        if category.startswith('report-'):
            period=category.removeprefix('report-'); stamp=now()[:10]
            report=service.generate_report(period,key='scheduled-'+period+'-'+stamp)
            notifications_requested=service.settings()['notifications_enabled']
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
    async def ask(data:AskInput):
        from .routing import route_question
        route = route_question(data.message) if data.mode == 'auto' else dict(mode=data.mode,reason='explicit_selection')
        async def stream():
            def event(payload):return 'data: '+json.dumps(payload,ensure_ascii=False,default=str)+'\n\n'
            started=time.perf_counter();first=None
            row=store.put('jobs',uid(),dict(kind='ask',status='running',stage=route['mode'],route=route,progress=10,started_at=now(),attempts=1))
            if route['mode']=='saved':
                answer,citations=service.saved_answer(data.message)
                for piece in answer.splitlines(keepends=True):
                    if first is None:first=time.perf_counter()
                    yield event(dict(type='token',content=piece))
                metrics=dict(ttft_seconds=first-started if first else None,total_seconds=time.perf_counter()-started,model_requests=0,route=route)
                store.update('jobs',row['id'],dict(status='succeeded',stage='complete',progress=100,finished_at=now(),metrics=metrics))
                yield event(dict(type='done',citations=citations,run_id=None,metrics=metrics));return
            agent=service.agent_factory();run_id=None;answer='';completed=False;tool_calls=[];stage='model';evidence_status=None;retrieved_urls=set();evidence_packs=[]
            try:
                async for chunk in agent.arun(data.message,stream=True,stream_events=True):
                    run_id=getattr(chunk,'run_id',None) or run_id
                    name=str(getattr(chunk,'event',''))
                    if name=='RunError':
                        raise RuntimeError(classify_error(getattr(chunk,'content',None),getattr(chunk,'error_type','') or ''))
                    if name=='RunCompleted':completed=True
                    if name=='ToolCallCompleted':
                        tool=getattr(chunk,'tool',None)
                        tool_calls.append(getattr(tool,'tool_name',None) or getattr(tool,'name',None) or str(tool)[:120])
                        stage='retrieval'
                        if getattr(tool,'tool_call_error',False):raise ValueError('TOOL_ERROR')
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
                if not answer.strip() or not completed:raise ValueError('FINAL_ANSWER_MISSING')
                reviewed=review_analysis(answer,store,evidence_packs=evidence_packs)
                if reviewed['publication_review']['status']!='withheld' and not citations and not any(reviewed['safe_evidence'].values()):
                    raise ValueError('NO_VERIFIED_EVIDENCE' if evidence_status else 'FINAL_ANSWER_MISSING')
                if not citations:
                    citations=list({i['document_id']:dict(document_id=i['document_id'],url=i['url'],title=i['report_title']) for group in reviewed['safe_evidence'].values() for i in group}.values())
                stage='publication_review'
                published_at=time.perf_counter()
                for piece in reviewed['answer'].splitlines(keepends=True):
                    yield event(dict(type='token',content=piece))
                metrics=dict(agent.model.budget_for(run_id).record(),provider_ttft_seconds=first-started if first else None,ttft_seconds=published_at-started,total_seconds=time.perf_counter()-started,route=route)
                store.update('jobs',row['id'],dict(status='succeeded',stage='complete',progress=100,finished_at=now(),run_id=run_id,metrics=metrics,result=dict(reviewed,tool_calls=tool_calls,evidence_packs=evidence_packs),quality_status='REVIEW_REQUIRED'))
                yield event(dict(type='done',citations=citations,run_id=run_id,metrics=metrics,submission_id=row['id'],notice_code=evidence_status,publication_review=reviewed['publication_review']))
            except asyncio.CancelledError:
                budget=agent.model.budget_for(run_id);budget.failed(RuntimeError('CLIENT_CANCELLED'))
                store.update('jobs',row['id'],dict(status='cancelled',stage='cancelled',finished_at=now(),run_id=run_id,metrics=budget.record(),result={'partial_answer':answer}))
                raise
            except Exception as exc:
                code=classify_error(str(exc),type(exc).__name__)
                messages={
                    'TOKEN_BUDGET_EXCEEDED':'上下文估算（context estimate）、实耗或请求上限触及保护。预算仍为输入 60,000 / 输出 8,000 Token，最多 3 次请求，单次输出 1,800；详细预估和实耗见运行记录。',
                    'MODEL_TIMEOUT':'模型请求或本轮运行超时。',
                    'PROVIDER_ERROR':'模型服务异常或用量回执缺失。',
                    'TOOL_ERROR':'数据查询工具执行失败。',
                    'NO_VERIFIED_EVIDENCE':'检索未提供足以支撑带来源最终回答的证据。',
                    'FINAL_ANSWER_MISSING':'未获得带有效来源的完整最终回答，或最后一次请求仍要求调用工具。'}
                message=f"{code}：{messages[code]} 已完成工具调用 {len(tool_calls)} 次；失败阶段：{stage}；最终分析未发布。已停止，不自动重试。"
                metrics=agent.model.budget_for(run_id).record()
                store.update('jobs',row['id'],dict(status='failed',stage=stage,finished_at=now(),run_id=run_id,error=message,error_code=code,metrics=metrics,result=dict(raw_answer=answer,tool_calls=tool_calls,final_answer_generated=bool(answer.strip()) and completed)))
                yield event(dict(type='error',code=code,message=message,run_id=run_id,metrics=metrics,stage=stage,submission_id=row['id'],final_answer_generated=bool(answer.strip()) and completed))
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

    agent_os=AgentOS(id='london-market-product',name='London Office Market',db=native_db,
        agents=[service.agent_factory()],workflows=[service.workflow,service.report_workflow],base_app=base,scheduler=scheduler,
        scheduler_poll_interval=5,scheduler_base_url='http://127.0.0.1:7780',telemetry=False,tracing=True,
        cors_allowed_origins=['http://localhost:3101','http://127.0.0.1:3101'])
    app=agent_os.get_app();app.state.market=service;app.state.agent_os=agent_os
    return app


if __name__=='__main__':
    import uvicorn
    uvicorn.run(create_app(),host='127.0.0.1',port=7780)
