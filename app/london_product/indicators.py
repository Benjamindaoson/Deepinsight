"""Executable assessment registry; coverage is not a publication approval."""
from pathlib import Path
import re
import yaml

REGISTRY = Path(__file__).parents[1] / 'docs/product/DATA_SOURCE_REGISTRY.yaml'


def definitions():
    rows=yaml.safe_load(REGISTRY.read_text(encoding='utf-8'))['metrics']
    if [r['id'] for r in rows] != [f'M{i:02}' for i in range(1,21)]:
        raise ValueError('INDICATOR_REGISTRY_INCOMPLETE')
    return rows


def matches(f, key):
    metric=f.get('metric'); grade=str(f.get('grade','')).lower()
    if key=='prime_rent': return metric=='rent' and (grade.startswith('prime') or bool(re.match(r'^(?:(?:City|West End|Canary Wharf|Midtown)\s+)?Prime(?:\s+office)?(?:\s+rent|$)',f.get('definition',''),re.I)))
    if key=='grade_a_rent': return metric=='rent' and grade=='grade a'
    if key in ['vacancy','availability','takeup','interest_rate','employment']:return metric==key
    if key=='prelet':return metric in ['prelet','prelet_share']
    if key=='development':return metric=='supply' and f.get('basis') in ['under_construction','completions','future_pipeline']
    if key=='economy':return metric in ['inflation_cpih','inflation_rate','gva_growth','gdp']
    if key in ['city','west_end','canary_wharf','midtown_fringe']:
        geo=str(f.get('geography','')).lower()
        return {'city':geo in ['city','city (source-defined)'] or geo.startswith('city of london'),
                'west_end':geo.startswith('west end'), 'canary_wharf':'canary wharf' in geo,
                'midtown_fringe': 'midtown' in geo or 'fringe' in geo}[key]
    return False


def coverage(store):
    from .qa_context import verified
    facts=[f for f in store.all('facts') if f.get('status') not in ['superseded','rejected']]
    events=[e for e in store.all('events') if e.get('status') not in ['superseded','rejected']]
    sources={s['id']:s for s in store.all('sources')}
    docs={d['id']:d for d in store.all('documents')}
    rows=[]
    for definition in definitions():
        key=definition['key']; related=[f for f in facts if matches(f,key)]
        fs=[f for f in related if f.get('document_id') in docs and (f.get('evidence') or {}).get('quote')]
        es=[e for e in events if key in e.get('indicator_keys',[]) and e.get('document_id') in docs and (e.get('evidence') or {}).get('quote')]
        geos=sorted({f.get('geography','unknown') for f in related})
        exact={'city':['City','City (source-defined)'],'west_end':['West End'],
               'canary_wharf':['Canary Wharf'],'midtown_fringe':['Midtown','Fringe']}.get(key)
        approved=[f for f in fs if verified(f)]
        errors=[dict(source_id=i,health=sources[i].get('health'),reason=sources[i].get('last_error') or sources[i].get('policy_note'))
                for i in definition['source_ids'] if i in sources and (sources[i].get('health') in ['failed','configuration_missing','policy_restricted'] or not sources[i].get('enabled',True))]
        rows.append(dict(id=definition['id'],key=key,name=definition['name'],domain=definition['domain'],
            source_ids=definition['source_ids'],fact_ids=[f['id'] for f in fs],event_ids=[e['id'] for e in es],
            exact_geography_fact_ids=[f['id'] for f in fs if not exact or f.get('geography') in exact],
            source_geographies=geos,periods=sorted({f.get('period') or 'unknown' for f in fs}),
            approved_fact_count=len(approved),candidate_fact_count=len(fs)-len(approved),source_errors=errors,
            status='partial' if fs or es else 'blocked' if errors else 'not_tested',
            evidence_type='numeric_and_qualitative' if fs and es else 'numeric' if fs else 'qualitative' if es else 'missing',
            limitations=definition.get('limitation'),missing_fields=definition.get('missing_fields',[])))
    return dict(metrics=rows,total=20,notice='Candidate/source coverage is separate from business correctness, complete submarket coverage and human approval.')
