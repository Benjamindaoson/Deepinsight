"""Real, independent 4-document x 3-run evaluation. Never edits gold or raw output."""
import argparse
import hashlib
import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from london_data.pipeline import registry
from london_data.documents import parse_document
from london_data.extraction import extract,ROOT,config_version
from london_data.store import Repository
from london_data.validation import validate


def main():
    p=argparse.ArgumentParser();p.add_argument('--execute-real-models',action='store_true',required=True)
    p.add_argument('--label',required=True);args=p.parse_args()
    r=registry();gold=json.loads((ROOT/'b1/data/gold-provisional.json').read_text(encoding='utf-8'))
    out=ROOT/'b1/evidence/evaluations'/args.label
    out.mkdir(parents=True,exist_ok=False)
    report=dict(label=args.label,config_version=config_version(r['profile']),gold_sha256=hashlib.sha256((ROOT/'b1/data/gold-provisional.json').read_bytes()).hexdigest(),gold_review_status=gold['status'],runs=[])
    repo=Repository(out/'evaluation.db')
    for repeat in range(1,4):
        for key,entry in r['documents'].items():
            content=Path(entry['file']).read_bytes();media='application/pdf' if entry['file'].endswith('.pdf') else 'text/html'
            if hashlib.sha256(content).hexdigest()!=gold['documents'][key]['sha256']:raise ValueError('CORPUS_HASH_MISMATCH')
            d=repo.snapshot('bnp',entry['url'],content,media,entry['published_at'],parse_document(content,media))
            execution_id=f'eval-{args.label}-{key}-r{repeat}'
            row=dict(document=key,repeat=repeat,role=entry['role'],execution_id=execution_id,expected=len([g for g in gold['documents'][key]['facts'] if g['value'] is not None]),correct=0,predicted=0,details=[],status='failed')
            try:
                output,record=extract(d,r['profile'],execution_id)
                row.update(run_id=record['run_id'],budget=record['budget'],status='completed')
                obs=output['observations'];row['predicted']=sum(o['value'] is not None for o in obs)
                for g in gold['documents'][key]['facts']:
                    candidates=[o for o in obs if o['metric']==g['metric']]
                    errors=[]
                    if len(candidates)!=1:errors.append('MISSING_OR_DUPLICATE_METRIC')
                    else:
                        o=candidates[0]
                        for field,expected in g.items():
                            if field in ['evidence','annotation_note']:continue
                            got=o.get(field)
                            equal=Decimal(str(got))==Decimal(str(expected)) if field in ['value','precision'] and got is not None and expected is not None else got==expected
                            if not equal:errors.append(f'{field}:expected={expected},actual={got}')
                        checked=validate(o,d['segments'],r['profile'].get('definitions'))
                        # Unknown rent time basis is a known release blocker, not an extraction hallucination.
                        ev_errors=[e for e in checked['validation_errors'] if e not in ['UNKNOWN_RENT_TIME_BASIS','NO_ANNUAL_UNIT_EVIDENCE']]
                        errors+=ev_errors
                    correct=not errors
                    if correct and g['value'] is not None:row['correct']+=1
                    row['details'].append(dict(metric=g['metric'],correct=correct,errors=errors))
                row['precision']=row['correct']/row['predicted'] if row['predicted'] else 0
                row['recall']=row['correct']/row['expected'] if row['expected'] else None
                row['threshold_pass']=row['precision']>=.9 and row['recall'] is not None and row['recall']>=.9
            except Exception as e:row.update(error_type=type(e).__name__,precision=0,recall=0,threshold_pass=False)
            report['runs'].append(row)
            (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(row,ensure_ascii=False),flush=True)
    report['raw_thresholds_pass']=all(x['threshold_pass'] for x in report['runs'])
    report['formal_acceptance']='BLOCKED_PENDING_G0_RENT_UNIT_AND_HUMAN_GOLD_REVIEW'
    (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
