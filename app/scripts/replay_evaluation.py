"""Re-score unchanged real provider outputs after deterministic parser repair. ZERO model calls."""
import json,hashlib,sys
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from london_data.contracts import materialize
from london_data.documents import parse_document
from london_data.validation import validate
from london_data.extraction import ROOT

label=sys.argv[1]
directory=ROOT/'b1/evidence/evaluations'/label
report=json.loads((directory/'results.json').read_text(encoding='utf-8'))
gold=json.loads((directory/'gold-provisional.json').read_text(encoding='utf-8'))
registry=json.loads((directory/'source-registry.json').read_text(encoding='utf-8'))
out={'method':'Unchanged raw provider responses; deterministic materialization/parser recovery only. No human edit of predicted facts, no new model call, no changed scoring thresholds. Original processing failures remain in results.json.',
     'gold_status':gold['status'],'model_requests_this_replay':0,'raw_hashes':{},'runs':[]}
for row in report['runs']:
    path=ROOT/'b1/evidence/extractions'/(row['execution_id']+'.json');before=path.read_bytes();raw=json.loads(before)
    out['raw_hashes'][row['execution_id']]=hashlib.sha256(before).hexdigest()
    key=row['document'];entry=registry['documents'][key];content=Path(entry['file']).read_bytes()
    segs=parse_document(content,'application/pdf' if entry['file'].endswith('.pdf') else 'text/html')
    item={'document':key,'repeat':row['repeat'],'execution_id':row['execution_id'],'run_id':raw.get('run_id'),'original_processing_status':raw['status'],'details':[],'correct':0,'predicted':0,'expected':3}
    try:
        processed=materialize(raw['raw_output']).model_dump(mode='json');item['predicted']=sum(x['value'] is not None for x in processed['observations'])
        for g in gold['documents'][key]['facts']:
            matches=[o for o in processed['observations'] if o['metric']==g['metric']];errors=[]
            if len(matches)!=1:errors.append('MISSING_OR_DUPLICATE')
            else:
                o=matches[0]
                for k,expected in g.items():
                    if k in ['evidence','annotation_note']:continue
                    got=o.get(k)
                    same=Decimal(str(got))==Decimal(str(expected)) if k in ['value','precision'] and got is not None and expected is not None else got==expected
                    if not same:errors.append(f'{k}: {got} != {expected}')
                checked=validate(o,segs,registry['profile'].get('definitions'),registry['profile'],entry['period'])
                errors += [e for e in checked['validation_errors'] if e not in ['UNKNOWN_RENT_TIME_BASIS','NO_ANNUAL_UNIT_EVIDENCE']]
            item['details'].append({'metric':g['metric'],'correct':not errors,'errors':errors})
            if not errors:item['correct']+=1
        item['precision']=item['correct']/item['predicted'] if item['predicted'] else 0;item['recall']=item['correct']/3
        item['threshold_pass']=item['precision']>=.9 and item['recall']>=.9
    except Exception as e:item.update(error_type=type(e).__name__,threshold_pass=False,precision=0,recall=0)
    assert before==path.read_bytes(),'Replay must never overwrite raw provider evidence'
    out['runs'].append(item)
out['all_thresholds_pass']=all(x['threshold_pass'] for x in out['runs'])
out['formal_acceptance']='BLOCKED_PENDING_RENT_UNIT_AND_HUMAN_GOLD_REVIEW'
(directory/'replay-results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'runs':len(out['runs']),'pass':sum(x['threshold_pass'] for x in out['runs']),'failed':[x for x in out['runs'] if not x['threshold_pass']]},ensure_ascii=False,indent=2))
