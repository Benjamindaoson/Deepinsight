import argparse,json,sys
from pathlib import Path
from .pipeline import make_workflow,repository,registry
from .extraction import ROOT


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description='B1 London market foundation (real model calls only for ingest)')
    p.add_argument('command',choices=['ingest','query','sources'])
    p.add_argument('--document',default='bnp-q1-2026')
    a=p.parse_args()
    if a.command=='sources':print(json.dumps(registry(),ensure_ascii=False,indent=2));return
    if a.command=='query':print(json.dumps(dict(observations=repository().observations(include_all=True),comparisons=repository().all('comparisons')),ensure_ascii=False,indent=2));return
    run=make_workflow().run({'document_key':a.document})
    result=run.to_dict()
    path=ROOT/'b1/evidence/workflows'/f'{run.run_id}.json';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    for attempt in repository().all('attempts'):
        if isinstance(run.content,dict) and attempt['run_id']==run.content.get('extraction_run_id'):
            attempt['workflow_run_id']=run.run_id;repository().update('attempts',attempt['id'],attempt)
    print(json.dumps(dict(run_id=run.run_id,status=str(run.status),evidence=str(path)),indent=2))
    if getattr(run.status,'name',None)!='completed':raise SystemExit(1)


if __name__=='__main__':main()
