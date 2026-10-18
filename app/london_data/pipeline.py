"""Seven native Agno Workflow steps; no substitute execution engine."""
import hashlib
import html
import json
import uuid
import time
from pathlib import Path
from agno.db.sqlite import SqliteDb
from agno.workflow import Workflow,Step
from agno.workflow.types import StepInput,StepOutput
from agno.run import RunContext
from .documents import fetch,parse_document
from .extraction import ROOT,DATA,extract,config_version
from .store import Repository,now
from .validation import validate
from .comparison import compare
from .tools import compare_saved_observations


def registry():return json.loads((ROOT/'b1/data/source-registry.json').read_text(encoding='utf-8'))
def repository():return Repository(DATA/'market.db')
def state(si):
    value=si.previous_step_content or si.input
    if isinstance(value,str):value=json.loads(value)
    if not isinstance(value,dict):raise ValueError('Workflow input must be a JSON object')
    return dict(value)


def export_result(data,directory=None):
    directory=Path(directory or ROOT/'b1/outputs'/str(uuid.uuid4()));directory.mkdir(parents=True,exist_ok=True)
    jp=directory/'result.json';mp=directory/'result.md'
    jp.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    lines=['# London office market — saved evidence','',
           'Historical quarterly data, not a real-time quote. Changes use disclosed rounded values.','',
           '| Metric / geography | Period | Value | Unit | Status | Evidence |',
           '|---|---|---:|---|---|---|']
    details=[]
    for o in data.get('observations',[]):
        e=o['evidence'];loc='page '+str(e['page']) if e.get('page') else e['segment_id']
        lines.append(f"| {o['metric']} / {o['geography']} | {o['period']} | {o['value']} | {o['unit']} | {o['status']} | {loc}; observation {o['id']} |")
        details.append(f"- {o['id']}: definition {o['definition']}; grade {o['grade']}; basis {o['basis']}; method {o['method']}; disclosed increment {o['precision']}; run {o.get('run_id')}; quote: {e['quote']}")
    lines+=['','## Fact evidence','']+details
    lines+=['','## Comparisons','']
    for c in data.get('comparisons',[]):
        display=c.get('display',{});absolute=display.get('absolute_change',c['absolute_change']);relative=display.get('relative_change_pct',c['relative_change_pct'])
        lines += [f"- {c['old']['metric']} {c['old']['period']} → {c['new']['period']}: {c['status']}; absolute={absolute if absolute is not None else 'N/A'} {c['change_unit'] or ''}; relative={str(relative)+'%' if relative is not None else 'N/A'}; reasons={c['reasons']}; comparison={c.get('id')}",f"  Inputs: {c['old']['id']} → {c['new']['id']}; formulas {c['formulas']}; display {c['display_precision']}; conversion {c.get('unit_conversion')}"]
    lines+=['','## Provenance','']
    lines.append(f"Workflow Run ID: {data.get('workflow_run_id')}; extraction Run ID: {data.get('extraction_run_id')}; execution: {data.get('execution_id')}")
    lines.append('Human gold review: pending_review; reviewer: project owner. Business acceptance: BLOCKED.')
    for d in data.get('documents',[]):
        lines.append(f"- {d['id']}: {d['url']}; SHA-256 {d['sha256']}; published={d['published_at']}; collected={d['collected_at']}; snapshot={d['path']}")
    lines+=['','## Source anomalies','', 'BNP Q2 2026 reports 26% take-up growth, whereas disclosed 2.5m → 3.0m computes to 20%. These are preserved separately; the calculation does not reproduce the publisher claim. The 8.4% vacancy figures are rounded; a stated 2bps decline cannot be recovered from those rounded endpoints.']
    # Escape document-derived markup; retain Markdown syntax and plain source URLs.
    mp.write_text('\n'.join(html.escape(x,quote=False) for x in lines),encoding='utf-8')
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [jp,mp]}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return {'json':str(jp),'markdown':str(mp),'manifest':str(directory/'manifest.json')}


def fetch_step(step_input:StepInput,run_context:RunContext=None)->StepOutput:
    s=state(step_input);s['document_started_epoch']=time.time();r=registry();entry=r['documents'][s['document_key']];profile=r['profile']
    s['workflow_run_id']=run_context.run_id if run_context else None
    content,media,url=fetch(entry['url'],set(r['allowed_hosts']),r['allowed_prefixes'])
    repo=repository();repo.put('sources',profile['source_id'],profile)
    d=repo.snapshot(profile['source_id'],url,content,media,entry['published_at'],[])
    s.update(document=d,profile=profile,entry=entry,execution_id=str(uuid.uuid4()))
    return StepOutput(content=s)


def parse_step(step_input:StepInput)->StepOutput:
    s=state(step_input);d=s['document'];segments=parse_document(Path(d['path']).read_bytes(),d['media'])
    d['segments']=segments;repository().update('documents',d['id'],d)
    s['document']=d;return StepOutput(content=s)


def extract_step(step_input:StepInput)->StepOutput:
    s=state(step_input);repo=repository();d=s['document'];version=config_version(s['profile'])
    prior=repo.successful(d['id'],version)
    if prior:
        s.update(attempt=prior,cached=True);return StepOutput(content=s)
    attempt=repo.attempt(d['id'],version,s['execution_id']);s['attempt']=attempt
    attempt['workflow_run_id']=s.get('workflow_run_id');repo.update('attempts',attempt['id'],attempt)
    try:
        output,record=extract(d,s['profile'],s['execution_id'],s['document_started_epoch'])
        metrics=[o.get('metric') for o in output.get('observations',[])]
        if len(metrics)!=3 or set(metrics)!={'rent','vacancy','takeup'}:raise ValueError('MISSING_OR_DUPLICATE_TARGET_METRICS')
        attempt.update(run_id=record['run_id'],raw_output=record['raw_output'],derived_output=output,budget=record['budget'],raw_evidence_path=str(ROOT/'b1/evidence/extractions'/(s['execution_id']+'.json')))
        repo.update('attempts',attempt['id'],attempt);s.update(output=output,cached=False)
        return StepOutput(content=s)
    except Exception as e:
        attempt.update(status='failed',error_type=type(e).__name__,finished_at=now())
        raw=ROOT/'b1/evidence/extractions'/(s['execution_id']+'.json')
        if raw.exists():attempt['budget']=json.loads(raw.read_text(encoding='utf-8')).get('budget')
        repo.update('attempts',attempt['id'],attempt);raise


def validate_step(step_input:StepInput)->StepOutput:
    s=state(step_input)
    if not s.get('cached'):
        d=s['document'];s['facts']=[validate(dict(f,document_id=d['id'],attempt_id=s['attempt']['id']),d['segments'],s['profile'].get('definitions'),s['profile'],s['entry']['period']) for f in s['output']['observations']]
    return StepOutput(content=s)


def persist_step(step_input:StepInput)->StepOutput:
    s=state(step_input)
    if time.time()-s['document_started_epoch']>480:
        if not s.get('cached'):repository().update('attempts',s['attempt']['id'],dict(s['attempt'],status='failed',finished_at=now(),error_type='DOCUMENT_DEADLINE_BEFORE_PERSIST'))
        raise ValueError('DOCUMENT_DEADLINE_BEFORE_PERSIST')
    if not s.get('cached'):repository().persist(s['attempt'],s['facts'])
    return StepOutput(content=s)


def compare_step(step_input:StepInput)->StepOutput:
    s=state(step_input);repo=repository();obs=[o for o in repo.observations(include_all=True) if o['status']!='superseded'];out=[]
    # Only requested main period pair. Attempts/holdout evaluations do not silently become production facts.
    for metric in ['rent','vacancy','takeup']:
        old=next((o for o in obs if o['metric']==metric and o['period']=='2026Q1'),None)
        new=next((o for o in obs if o['metric']==metric and o['period']=='2026Q2'),None)
        if old and new:out.append(repo.save_comparison(compare_saved_observations.entrypoint(old['id'],new['id'])))
    s['comparison_ids']=[x['id'] for x in out];return StepOutput(content=s)


def export_step(step_input:StepInput)->StepOutput:
    s=state(step_input);repo=repository()
    result=dict(observations=[o for o in repo.observations(include_all=True) if o['status']!='superseded'],comparisons=repo.current_comparisons(),historical_comparisons=repo.all('comparisons'),documents=repo.all('documents'),execution_id=s['execution_id'],workflow_run_id=s.get('workflow_run_id'),extraction_run_id=s['attempt']['run_id'],cached=s.get('cached',False),human_review_status='pending_review',final_reviewer='project owner (user)',business_acceptance='BLOCKED')
    result['files']=export_result(result)
    return StepOutput(content=result)


def make_workflow(db=None):
    return Workflow(id='london-foundation',name='London Market Data Foundation',
                    db=db or SqliteDb(id='b1-runtime',db_file=str(DATA/'agno.db')),
                    steps=[Step(name=n,executor=f,max_retries=0,on_error='fail') for n,f in [('Fetch',fetch_step),('Parse',parse_step),('Extract',extract_step),('Validate',validate_step),('Persist',persist_step),('Compare',compare_step),('Export',export_step)]],
                    store_events=True,telemetry=False)
