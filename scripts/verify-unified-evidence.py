"""Read-only reconcile genuine browser receipts with native runs and frozen identity.

Does not submit questions, invoke models, write market data or generate answers.
"""
import hashlib
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from html.parser import HTMLParser

from release_manifest import resolve_release

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/delivery/unified-release-20261019-r1'

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def decode(value):
    for _ in range(3):
        if not isinstance(value,str):break
        try:value=json.loads(value)
        except ValueError:break
    return value

release=resolve_release(ROOT,OUT/'CANDIDATE_POINTER.json')
with urllib.request.urlopen('http://127.0.0.1:7788/api/market/release') as response:identity=json.load(response)
assert identity['managed_release'] and identity['mode']=='live'
assert identity['manifest_sha256']==release['manifest_sha256']
assert Path(identity['source_app']).resolve()==Path(release['backend_app'])
cases={name:read(OUT/(name+'.json')) for name in ['FINAL_A','FINAL_F','FINAL_C']}
calls=[];skills=set();cases_summary=[]
for name,case in cases.items():
    assert case['identity']['manifest_sha256']==release['manifest_sha256'],name
    assert case['job']['status']=='partial' and case['job']['stage']=='complete'
    run=next(r for r in case['native_runs'] if r.get('agent_id'))
    assert run['status']=='COMPLETED' and run['run_id']==case['job']['run_id']
    tools=run['tools']
    assert [t['tool_name'] for t in tools]==['load_market_skills','search_market_evidence']
    assert all(not t.get('tool_call_error') for t in tools)
    load=decode(tools[0]['result']);pack=decode(tools[1]['result']);audit=case['skill_audit']
    assert load['status']==audit['status']=='loaded'
    assert load['audit_id']==audit['audit_id'] and load['projection_sha256']==audit['projection_sha256']
    assert load['requested_skills']==audit['requested_skills']
    assert all(c['status']=='loaded' for c in audit['sdk_calls'])
    assert len(audit['sdk_calls'])==2*len(audit['sources'])
    for source in audit['sources']:
        assert digest(Path(source['source_path']))==source['source_sha256']
        assert digest(Path(source['reference_path']))==source['reference_sha256']
    skills.update(audit['requested_skills'])
    ledger=case['model_ledger']
    assert ledger['requests']==3 and ledger['terminal_error'] is None
    assert ledger['endpoint'].rstrip('/')=='https://api.deepseek.com'
    assert run['metrics']['input_tokens']==ledger['input_tokens']
    assert run['metrics']['output_tokens']==ledger['output_tokens']
    for call in ledger['calls']:
        assert call['status']=='returned' and call['provider_response_id']
        assert call['provider_model']=='deepseek-flash' and call['raw_provider_usage']
        calls.append(dict(test=name,run_id=run['run_id'],number=call['number'],
            timestamp=datetime.fromtimestamp(call['started'],timezone.utc).isoformat(),
            provider='DeepSeek official via Agno OpenAI Chat adapter',endpoint=ledger['endpoint'],
            model=call['provider_model'],status=call['status'],http_status=None,
            http_status_note='Streaming response completed; transport does not persist a numeric status code.',
            provider_response_id=call['provider_response_id'],input_tokens=call['input_tokens'],
            output_tokens=call['output_tokens'],raw_provider_usage=call['raw_provider_usage']))
    workflows=[r for r in case['native_runs'] if r.get('workflow_id')]
    assert len(workflows)==2 and {r['run_id'] for r in workflows}==set(case['job']['workflow_run_ids'])
    assert all(r['status']=='COMPLETED' and all(s['success'] for s in r['step_results']) for r in workflows)
    artifact=case['report']['artifact']
    assert artifact['publication_review']['semantic_approval'] is False
    cases_summary.append(dict(test=name,job_id=case['job']['id'],agent_run_id=run['run_id'],
        report_id=case['report']['id'],session_id=case['job']['session_id'],
        workflow_run_ids=case['job']['workflow_run_ids'],scope=artifact['scope'],
        generation_status=case['report']['generation_status'],publication_review=artifact['publication_review'],
        requests=ledger['requests'],input_tokens=ledger['input_tokens'],output_tokens=ledger['output_tokens'],
        skills=audit['requested_skills']))

a=cases['FINAL_A']['report']['artifact'];f=cases['FINAL_F']['report']['artifact'];c=cases['FINAL_C']['report']['artifact']
assert a['scope']['geographies']==f['scope']['geographies']==['West End']
assert a['scope']['observation_period']==f['scope']['observation_period']=='2026Q2'
assert f['parent_report_id']==a['report_id']
assert cases['FINAL_A']['job']['session_id']==cases['FINAL_F']['job']['session_id']
assert c['scope']['geographies']==['Canary Wharf'] and c['scope']['observation_period']=='2026-10'
assert c['generation_status']=='insufficient_evidence' and not c['evidence']
assert c['publication_review']['ai_status']=='withheld'
agent=next(r for r in cases['FINAL_A']['native_runs'] if r.get('agent_id'))
attachments=decode(agent['tools'][1]['result'])['user_attachments']
assert len(attachments)==1 and attachments[0]['id']=='d217f4b0-8a95-45a7-bcea-1807362c9711'
assert attachments[0]['sha256']=='3dd8de05ccb26ce235dfc8f9cf96d47bb2f760196d56cfcc94b0dc2a2a2016cd'
assert attachments[0]['review_status']=='unreviewed_user_upload' and attachments[0]['segment_count']==13

baseline=read(OUT/'MARKET_BASELINE.json')
with sqlite3.connect((ROOT/'app/data/product/market.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    facts={r[0]:json.loads(r[1]) for r in db.execute('select id,payload from facts')}
    assert set(facts)==set(baseline['facts'])
    for id,fields in baseline['facts'].items():
        assert {key:facts[id].get(key) for key in fields}==fields,id
    assert sorted(r[0] for r in db.execute('select payload from reviews'))==sorted(baseline['reviews'])
    jobs={r[0]:json.loads(r[1]) for r in db.execute('select id,payload from jobs')}
    reports={r[0]:json.loads(r[1]) for r in db.execute('select id,payload from reports')}
with sqlite3.connect((ROOT/'app/data/product/agno.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    runs=[run for row in db.execute('select runs from agno_sessions') for run in decode(row[0])]
for name,id in [('RESEARCH_WORKFLOW','b026bd82-94fc-484c-b61d-e088cac87c69'),('WEEKLY_WORKFLOW','5dec1652-b8a5-4add-8256-522a03b11aed')]:
    job=jobs[id];run=next(r for r in runs if r.get('run_id')==job['run_id'])
    assert run['status']=='COMPLETED' and run.get('workflow_id')
    assert all(step['success'] for step in run['step_results'])
    assert job.get('model_requests',job.get('result',{}).get('model_requests'))==0
    save(name+'.json',dict(identity=identity,job=job,native_run=run,report=reports[job['result']['report_id']]))

exported=read(OUT/'exports/FINAL-A-report.json')
def normalize_export(value):
    # Exports re-check the original evidence at read time and Pydantic expands
    # absent optional claim fields to null. All substantive fields must match.
    if isinstance(value,dict):return {k:normalize_export(v) for k,v in value.items()
        if v is not None and k not in ['checked_at','evidence_integrity_checked_at']}
    if isinstance(value,list):return [normalize_export(v) for v in value]
    return value
assert normalize_export(exported)==normalize_export(a)
html=(OUT/'exports/FINAL-A-report.html').read_text(encoding='utf-8')
markdown=(OUT/'exports/FINAL-A-report.md').read_text(encoding='utf-8')
parser=HTMLParser();parser.feed(html);parser.close()
for value in ['West End','2026Q2','6.7','partial',a['sources'][0]['url']]:
    assert value.casefold() in html.casefold() and value.casefold() in markdown.casefold(),value
assert 'df888608' in html

all_case_paths=[OUT/'BEFORE_SCOPE_FIX.json',OUT/'AFTER_SCOPE_FIX_PRE_COMPARE.json',
    *(OUT/'before-independent-review'/(name+'.json') for name in cases),
    *(OUT/(name+'.json') for name in cases)]
all_calls=[]
for path in all_case_paths:
    old=read(path)
    for call in old['model_ledger']['calls']:
        all_calls.append(dict(evidence=str(path.relative_to(OUT)),run_id=old['job']['run_id'],
            provider_response_id=call['provider_response_id'],status=call['status'],
            input_tokens=call['input_tokens'],output_tokens=call['output_tokens']))
assert len({c['provider_response_id'] for c in all_calls})==len(all_calls)
probe=read(OUT/'PROVIDER_PROBE.json')
all_calls.append(dict(evidence='PROVIDER_PROBE.json',provider_response_id=probe['provider_response_id'],
    status=probe['result'],input_tokens=probe['usage']['prompt_tokens'],output_tokens=probe['usage']['completion_tokens']))
save('MODEL_CALLS.json',dict(final_calls=calls,all_this_task_calls=all_calls,
    final_totals=dict(requests=len(calls),input_tokens=sum(c['input_tokens'] for c in calls),output_tokens=sum(c['output_tokens'] for c in calls)),
    task_totals=dict(requests=len(all_calls),input_tokens=sum(c['input_tokens'] for c in all_calls),output_tokens=sum(c['output_tokens'] for c in all_calls)),
    monetary_cost='N/A: provider response supplies tokens, not an invoice; no price inferred.'))

secrets=[]
for path in (ROOT/'secrets').glob('*.json'):
    try:key=read(path).get('api_key')
    except (ValueError,AttributeError):continue
    if isinstance(key,str) and len(key)>12:secrets.append(key.encode())
scanned=0
for directory,dirs,names in os.walk(OUT,followlinks=False):
    dirs[:]=[d for d in dirs if d not in ['node_modules','__pycache__','cache']]
    for name in names:
        path=Path(directory)/name
        if path.suffix in ['.pyc','.tsbuildinfo']:continue
        if any(secret in path.read_bytes() for secret in secrets):raise AssertionError('Secret exposure: '+str(path.relative_to(OUT)))
        scanned+=1
summary=dict(at=datetime.now(timezone.utc).isoformat(),release=release,identity=identity,
    cases=cases_summary,live_unique_skills=sorted(skills),attachment_verified=True,
    facts_and_reviews_unchanged=True,exports_consistent=True,secret_scan_files=scanned,
    secret_matches=0,checks='PASS',native_saved_query_runs=6,additional_native_workflows=2,
    limitation='Business publication remains partial/insufficient. No Team, external notification delivery or live source refresh claimed.')
save('EVIDENCE_VERIFICATION.json',summary)
print(json.dumps(dict(checks='PASS',manifest=release['manifest_sha256'],live_skills=sorted(skills),
    final_model_calls=len(calls),total_model_calls=len(all_calls),secret_matches=0,files_scanned=scanned)))
