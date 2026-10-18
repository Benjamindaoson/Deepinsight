"""Deterministic, fail-closed decimal quarter comparisons."""
import re
from decimal import Decimal, localcontext,ROUND_HALF_UP

SQM_TO_SQFT = Decimal('10.7639104167097')
KEYS = ['source_id','series','metric','geography','definition','basis','grade','method','currency']


def quarter(p):
    m=re.fullmatch(r'(\d{4})Q([1-4])',str(p))
    return int(m[1])*4+int(m[2])-1 if m else None


def compare(old: dict, new: dict) -> dict:
    reasons=[]
    result=dict(status='not_comparable',reasons=reasons,warnings=[],absolute_change=None,
                relative_change_pct=None,change_unit=None,old=old,new=new,
                formulas={'absolute':'new - old','relative_pct':'(new - old) / old * 100'},
                calculation_version='decimal-v1',display_precision='0.01; ROUND_HALF_UP',
                unit_conversion={'sqm_to_sqft':str(SQM_TO_SQFT)},
                precision_note='Computed from disclosed rounded values; not an independently estimated market growth rate.')
    for key in KEYS:
        # currency is deliberately null for dimensionless percent and area quantities.
        if key!='currency' and (old.get(key) in (None,'','unknown') or new.get(key) in (None,'','unknown')):
            reasons.append('UNKNOWN_'+key.upper())
        elif old.get(key)!=new.get(key):reasons.append('MISMATCH_'+key.upper())
    if old.get('status')!='validated' or new.get('status')!='validated':reasons.append('NOT_VALIDATED')
    a,b=quarter(old.get('period')),quarter(new.get('period'))
    if a is None or b is None or b-a!=1:reasons.append('NON_CONSECUTIVE_QUARTERS')
    if old.get('value') is None or new.get('value') is None:reasons.append('MISSING_VALUE')
    units={'rent':{'GBP/sqft/year':Decimal(1),'GBP/sqm/year':1/SQM_TO_SQFT},
           'vacancy':{'percent':Decimal(1)},'takeup':{'sqft':Decimal(1),'sqm':SQM_TO_SQFT}}
    allowed=units.get(old.get('metric'),{})
    if old.get('unit') not in allowed or new.get('unit') not in allowed:reasons.append('UNKNOWN_UNIT_BASIS')
    if old.get('metric')=='takeup' and (old.get('basis')!='quarter' or new.get('basis')!='quarter'):
        reasons.append('NOT_QUARTER_FLOW')
    if reasons:return result
    with localcontext() as ctx:
        ctx.prec=34
        x=Decimal(str(old['value']))*allowed[old['unit']]
        y=Decimal(str(new['value']))*allowed[new['unit']]
        delta=y-x
        result.update(status='comparable',absolute_change=str(delta),
                      normalized_old=str(x),normalized_new=str(y),
                      change_unit='pp' if old['metric']=='vacancy' else ('sqft' if old['metric']=='takeup' else 'GBP/sqft/year'))
        if old['metric']!='vacancy':
            if x==0:result['warnings'].append('ZERO_BASE')
            else:result['relative_change_pct']=str(delta/x*100)
        result['display']={k:(str(Decimal(result[k]).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) if result.get(k) is not None else None) for k in ['absolute_change','relative_change_pct']}
    return result
