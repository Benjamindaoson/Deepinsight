"""Read native history + domain state for actual restart equality checks."""
import json,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from london_data.pipeline import repository
from london_data.extraction import ROOT
import httpx

label=sys.argv[1];repo=repository();sessions=[]
with sqlite3.connect(str(ROOT/'b1/data/agno.db')) as c:
    for id,type,runs in c.execute('SELECT session_id,session_type,runs FROM agno_sessions'):
        parsed=runs or '[]'
        while isinstance(parsed,str):parsed=json.loads(parsed)
        if isinstance(parsed,dict):parsed=list(parsed.values())
        for run in parsed:
            sessions.append({'session_id':id,'session_type':type,'run_id':run.get('run_id'),'status':run.get('status'),'input':run.get('input'),'metrics':run.get('metrics'),'tools':run.get('tools'), 'content':run.get('content') if type=='agent' and id=='18b4d166-7af5-455d-b388-5633f457dedf' else None})
content={'observations':repo.all('observations'),'comparisons':repo.all('comparisons'),'documents':repo.all('documents'),'native_runs':sessions}
session=httpx.get('http://127.0.0.1:7778/sessions/18b4d166-7af5-455d-b388-5633f457dedf',params={'type':'agent','db_id':'b1-runtime'})
content['browser_session_status']=session.status_code;content['browser_session']=session.json()
out=ROOT/'b1/evidence/api'/('state-'+label+'.json');out.write_text(json.dumps(content,ensure_ascii=False,indent=2,default=str),encoding='utf8')
print(json.dumps({'path':str(out),'observations':len(content['observations']),'comparisons':len(content['comparisons']),'native_runs':len(sessions),'session_status':session.status_code}))
