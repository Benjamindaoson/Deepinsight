"""Evidence validation catches malformed, unsupported and ambiguous candidates."""
import re
import calendar
from decimal import Decimal, InvalidOperation
from .contracts import Observation


def normalize(text):return re.sub(r'\s+',' ',str(text)).strip().casefold()


def evidence_binding(data):
    """Bind the selected numeric lexeme to its local subject and unit, fail closed.

    A long quote merely containing a keyword is insufficient: an earlier amount
    of the same quantity, a different nearest geography, or a cumulative prefix
    makes that assignment ambiguous. Explicit contrary quarters are refused.
    """
    q=normalize(data['evidence']['quote']);metric=data['metric'];value=data['value']
    periods={y+'Q'+n for n,y in re.findall(r'\bq([1-4])\s*(20\d{2})\b',q)}
    periods.update(y+'Q'+n for y,n in re.findall(r'\b(20\d{2})\s*q([1-4])\b',q))
    if periods and periods!={data['period']}:return ['EVIDENCE_PERIOD_MISMATCH']
    subjects={'rent':r'prime\s+(?:(?:office|city)\s+)?rents?', 'vacancy':r'vacan(?:cy|cies)', 'takeup':r'take[ -]?up'}
    number=r'(?:c\.\s*)?(\d[\d,]*(?:\.\d+)?)\s*(million|thousand|m|k)?\b'
    unit={'rent':r'(?:per\s+)?sq\s*\.?\s*(?:ft|feet)|psf', 'vacancy':r'%', 'takeup':r'(?:sq\s*\.?\s*(?:ft|feet|m)|square\s+(?:feet|metres?))'}[metric]
    matches=[]
    for m in re.finditer(number,q):
        scale=Decimal({'m':1000000,'million':1000000,'k':1000,'thousand':1000}.get(m[2] or '',1))
        if value is None or Decimal(m[1].replace(',',''))*scale!=Decimal(value):continue
        anchors=list(re.finditer(subjects[metric],q[:m.start()]))
        if not anchors:continue
        anchor=anchors[-1];between=q[anchor.end():m.start()]
        if metric=='takeup' and re.search(r'\b(?:ytd|year.to.date|h[12]|cumulative)\s*$',q[max(0,anchor.start()-24):anchor.start()]):continue
        if len(between)>180 or re.search(r';|\b(?:ytd|year.to.date|h[12]|cumulative)\b',between):continue
        # An earlier amount of this quantity binds the subject first. A later
        # YTD/other-region amount cannot borrow that same subject.
        if re.search(number+r'\s*(?:'+unit+r')',between):continue
        tail=q[m.end():m.end()+32]
        if metric=='rent':
            if not (q[max(0,m.start()-1):m.start()]=='£' or re.match(r'\s*(?:'+unit+r')',tail)):continue
        elif not re.match(r'\s*(?:'+unit+r')',tail):continue
        geos=list(re.finditer(r'central london|west end|\bcity\b|docklands|midtown|southbank',q[anchor.start():m.start()]))
        if geos and normalize(data['geography'])!=geos[-1][0]:continue
        matches.append(m.start())
    return [] if len(matches)==1 else ['AMBIGUOUS_METRIC_VALUE_UNIT_BINDING']


def validate(candidate,segments,definitions=None,profile=None,expected_period=None):
    try:data=Observation.model_validate(candidate).model_dump(mode='json')
    except Exception as e:return dict(candidate if isinstance(candidate,dict) else {'raw_type':type(candidate).__name__},status='rejected',validation_errors=['SCHEMA:'+type(e).__name__])
    errors=[];ev=data['evidence'];seg=next((s for s in segments if s['segment_id']==ev['segment_id']),None)
    if seg is None or not ev['quote'] or normalize(ev['quote']) not in normalize(seg['text']):errors.append('EVIDENCE_NOT_FOUND')
    if data['value'] is None:errors.append('MISSING_VALUE')
    else:
        if Decimal(data['value'])<0 or (data['metric']=='vacancy' and Decimal(data['value'])>100):errors.append('VALUE_RANGE')
        nums=[];disclosures=[]
        for m in re.finditer(r'(?<![\w.])(?:c\.\s*)?(\d[\d,]*(?:\.\d+)?)\s*([mM]|million|[kK]|thousand)?\b',ev['quote']):
            try:
                scale=Decimal({'m':1000000,'million':1000000,'k':1000,'thousand':1000}.get((m[2] or '').lower(),1))
                literal=Decimal(m[1].replace(',',''));scaled=literal*scale;nums.append(scaled)
                if scaled==Decimal(data['value']):
                    disclosures.append(Decimal(10)**literal.as_tuple().exponent*scale)
                    data['reported_number_literal']=m[0].strip()
                    data['reported_number']=str(literal)
                    data['reported_multiplier']=str(scale)
            except InvalidOperation:pass
        if Decimal(data['value']) not in nums:errors.append('VALUE_NOT_IN_QUOTE')
        try:
            if not disclosures or Decimal(data['precision']) not in disclosures:errors.append('DISCLOSURE_PRECISION_MISMATCH')
        except InvalidOperation:errors.append('INVALID_PRECISION')
    if normalize(data['geography']) not in normalize(ev['quote']):
        # HTML overall-market bullets may inherit an explicit publication title.
        # Never apply that context to a quoted submarket or a Grade A subset.
        inherited=(data['geography']=='Central London' and seg and 'central london office market' in normalize(seg.get('scope_text',''))
                   and not re.search(r'\bCity\b|West End|Docklands|Midtown|Southbank|Grade[- ]?A',ev['quote'],re.I))
        if inherited:data['evidence']['context_quote']=seg['scope_text'];data['evidence']['context_basis']='publisher-report-title'
        else:errors.append('GEOGRAPHY_NOT_IN_QUOTE')
    if data['metric']=='rent':
        if data['unit'] not in ('GBP/sqft/year','GBP/sqm/year'):errors.append('UNKNOWN_RENT_TIME_BASIS')
        if not re.search(r'per annum|per year|/year|p\.a\.',ev['quote'],re.I):
            # An explicit qualified publisher definition is required; no implicit UK annual default.
            if not definitions or not definitions.get('annual_rent_definition'):errors.append('NO_ANNUAL_UNIT_EVIDENCE')
        if not re.search(r'prime',ev['quote'],re.I):errors.append('RENT_TYPE_NOT_IN_QUOTE')
    if data['metric']=='vacancy' and ('%' not in ev['quote'] or 'vacan' not in normalize(ev['quote'])):errors.append('VACANCY_UNIT_OR_DEFINITION')
    if data['metric']=='takeup' and (data['basis']!='quarter' or data['unit'] not in ('sqft','sqm')):errors.append('NOT_QUARTER_TAKEUP')
    errors.extend(evidence_binding(data))
    if any(data.get(k) in ('',None,'unknown') for k in ['period','geography','definition','method','basis','grade']):errors.append('UNKNOWN_COMPARABILITY_KEY')
    if not re.fullmatch(r'\d{4}Q[1-4]',data['period']):errors.append('UNKNOWN_PERIOD')
    if profile:
        expected=dict(source_id=profile['source_id'],series=profile['series'],**profile.get('metrics',{}).get(data['metric'],{}))
        for key,value in expected.items():
            if data.get(key)!=value:errors.append('PROFILE_MISMATCH_'+key.upper())
    if expected_period and data['period']!=expected_period:errors.append('DOCUMENT_PERIOD_MISMATCH')
    if re.fullmatch(r'\d{4}Q[1-4]',data['period']):
        y=int(data['period'][:4]);m=(int(data['period'][-1])-1)*3+1
        data['period_start']=f'{y:04d}-{m:02d}-01';data['period_end']=f'{y:04d}-{m+2:02d}-{calendar.monthrange(y,m+2)[1]}'
    data.update(status='validated' if not errors else 'needs_review',validation_errors=errors)
    data['validation_version']='evidence-binding-v2'
    data['normalized_value']=data['value'];data['normalized_unit']=data['unit']
    if seg is not None:
        data['evidence'].update(page=seg.get('page'),offset=normalize(seg['text']).find(normalize(ev['quote'])))
    if definitions:data['definition_provenance']=definitions
    return data
