"""Bounded deterministic projections on existing immutable originals.

Only literal publisher statements are projected. These are pending-review
observations, never verified causal conclusions or automatic approval.
"""
import csv
import hashlib
import io
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from .normalization import derive

VERSION='indicator-projection-v4-historical-vacancy'


def _quote(original, cleaned):
    pattern=r'\s+'.join(re.escape(x) for x in cleaned.split())
    found=re.search(pattern,original)
    return found.group() if found else None


def _save(store,doc,source,segment,metric,value,unit,period,geo,definition,quote,**extra):
    if not quote or quote not in segment['text']:raise ValueError('PROJECTION_QUOTE_MISSING')
    evidence=dict(quote=quote,page=segment.get('page'),locator=segment['locator'])
    row=dict(metric=metric,value=value,unit=unit,period=period,geography=geo,definition=definition,
             grade='not_applicable',method='publisher_literal_disclosure',basis='unknown',currency=None,
             source_id=source['id'],publisher=source.get('name'),series=definition,document_id=doc['id'],
             published_at=doc.get('published_at'),collected_at=doc.get('collected_at'),
             status='pending_review',human_review_status='pending_review',extraction_version=VERSION,
             evidence=evidence)
    row.update(extra)
    row.update(derive(row))
    if unit=='source_unit_not_stated':
        row.update(normalized_value=None,normalized_unit=None,
                   normalization_notes=row['normalization_notes']+['SOURCE_UNIT_NOT_STATED'])
    if row['normalization_notes']:row['status']='needs_review'
    identity='indicator:'+hashlib.sha256(json.dumps([VERSION,doc['sha256'],source['id'],segment['locator'],metric,value,unit,period,geo,definition],ensure_ascii=False).encode()).hexdigest()
    return store.put('facts',identity,row)


def project_macro(store,doc,source,content):
    """Bounded latest 24 monthly observations or last 366 Bank Rate observations.

    Revisions supersede the old candidate; no human approval is inherited.
    Every quote is an actual saved parser segment, not reconstructed CSV.
    """
    sid=source['id']; series=[]
    if sid=='boe':
        rows=list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))
        for i,row in enumerate(rows):
            if row.get('IUDBEDR') and row.get('DATE'):
                period=datetime.strptime(row['DATE'],'%d %b %Y').date().isoformat()
                series.append((i,period,row['IUDBEDR'],'interest_rate','percent','Official Bank Rate; IUDBEDR','date'))
        series=series[-366:]
    elif sid in ['ons','ons-employment','ons-gva']:
        payload=json.loads(content); desc=payload['description']
        expected={'ons':'L55O','ons-employment':'LF24','ons-gva':'ECYX'}[sid]
        if desc.get('cdid')!=expected:raise ValueError('ONS_SERIES_MISMATCH')
        if sid!='ons-gva' and desc.get('unit')!='%':raise ValueError('ONS_UNIT_MISMATCH')
        if sid=='ons-gva' and ('Gross Value Added' not in desc.get('title','') or 'period on period growth' not in desc.get('title','')):raise ValueError('ONS_GVA_DEFINITION_MISMATCH')
        if desc.get('releaseDate') and not doc.get('published_at'):
            doc=store.update('documents',doc['id'],dict(published_at=desc['releaseDate']))
        for i,row in list(enumerate(payload.get('months',[])))[-24:]:
            value=row.get('value')
            if value in [None,'','..','-']:continue
            if sid=='ons-employment':
                period=row.get('label','')
                if not re.fullmatch(r'\d{4} [A-Z]{3}-[A-Z]{3}',period):raise ValueError('ONS_ROLLING_PERIOD_MISSING')
            else:period=datetime.strptime(row['date'],'%Y %b').strftime('%Y-%m')
            metric={'ons':'inflation_cpih','ons-employment':'employment','ons-gva':'gva_growth'}[sid]
            unit='source_unit_not_stated' if sid=='ons-gva' and not desc.get('unit') else 'percent'
            series.append((i,period,value,metric,unit,desc['title']+'; '+expected,
                           {'ons':'annual_rate_month','ons-employment':'rolling_three_month_average','ons-gva':'monthly_growth'}[sid]))
    else:return 0
    count=0
    segments={s['locator']:s for s in doc['segments']}
    for index,period,raw,metric,unit,definition,basis in series:
        try:value=str(Decimal(raw))
        except InvalidOperation:continue
        locator=f'csv:row:{index+2}' if sid=='boe' else f'json:/months/{index}'
        segment=segments.get(locator)
        if not segment:raise ValueError('MACRO_SEGMENT_MISSING')
        prior=[f for f in store.all('facts') if f.get('source_id')==sid and f.get('metric')==metric and f.get('period')==period and f.get('status')!='superseded']
        if any(Decimal(str(f['value']))==Decimal(value) for f in prior):continue
        row=_save(store,doc,source,segment,metric,value,unit,period,'United Kingdom',definition,segment['text'],basis=basis)
        for old in prior:store.update('facts',old['id'],dict(status='superseded',superseded_by=row['id']))
        count+=1
    return count


THEMES={
 'flight_to_quality':r'flight[- ]to[- ]quality|demand for (?:premium|best-in-class|Grade A)|occupiers? continu\w* to prioritise high-quality',
 'esg':r'BREEAM|sustainab\w*|energy efficien\w*|\bEPC\b',
 'hybrid_working':r'hybrid work\w*|working from home|homeworking',
 'refurbishment':r'refurbish\w*',
 'prelet':r'pre[- ]?let\w*',
 'development':r'under construction|development pipeline|new[- ]build|new developments?',
 'leasing_activity':r'\bleas(?:e|ed|es|ing)\b|\blettings?\b|\btransactions?\b',
}


def project_document(store,doc,source):
    if source['id'] not in ['jll','bnp','savills-html','savills','cbre','ons-hybrid','gpe','britishland','citylondon','bbc-rss']:return 0
    count=0
    for segment in doc['segments']:
        original=segment['text'];text=' '.join(original.split())
        quarter=re.search(r'\bQ([1-4])\s+(20\d{2})\b',text)
        period=quarter[2]+'Q'+quarter[1] if quarter else 'unknown'
        geo='London (source context; exact submarket unknown)'
        heading=re.search(r'LEASING BY SUBMARKET:\s*(THE CITY|WEST END|MIDTOWN|SOUTHBANK|CANARY WHARF\s*&\s*DOCKLANDS)',text,re.I)
        if heading:geo={'THE CITY':'City','WEST END':'West End','MIDTOWN':'Midtown','SOUTHBANK':'Southbank','CANARY WHARF & DOCKLANDS':'Canary Wharf & Docklands'}[' '.join(heading[1].upper().split())]
        elif original.lstrip().startswith('City\n'):geo='City'
        elif 'Central London' in text[:300]:geo='Central London'
        if source['id']=='ons-hybrid':geo='Great Britain (London subgroup where explicitly stated)';period='2022-09 to 2023-01'
        # Source-specific numeric grammar; all quantities are stated, never inferred.
        if source['id'] in ['jll','bnp','savills-html','savills','cbre'] and quarter:
            area=r'(?P<value>[\d,]+(?:\.\d+)?)\s*(?P<scale>million|m)?\s*sq\.?\s*(?:ft|feet)\.?'
            patterns=[
                ('takeup',r'(?:Take-up reached|office take-up (?:totalled|reached)|City take-up totalled|take-up (?:totalling|reaching))\s+(?:approximately\s+)?'+area,'Reported leasing take-up','quarterly_flow'),
                ('availability',r'(?:Supply (?:contracted for a third consecutive quarter to|fell for (?:a|the) third consecutive quarter[^.]*? to)|Available (?:office )?supply[^.]*? to|Central London supply stood at)\s*'+area,'Available office area; not vacancy rate','available_area'),
                ('supply',r'(?:Space under construction (?:fell to|rose[^.]*? to)|Under construction)\s*'+area,'Office space under construction','under_construction'),
                ('supply',r'completions totalled\s*'+area,'Reported completed office area','completions'),
                ('vacancy',r'(?:vacancy rate (?:at|of)|vacancy (?:stood at|reducing to|reduced to|reaching)|Vacancy rate)\s*(?P<value>\d+(?:\.\d+)?)%','Overall vacancy rate; source methodology','stock_rate'),
            ]
            for metric,pattern,definition,basis in patterns:
                # BNP overview pages contain multiple named markets. A page
                # heading cannot bind an unqualified numeric match to one area.
                if source['id']=='bnp' and not heading:continue
                match=re.search(pattern,text,re.I)
                if not match:continue
                quote=_quote(original,match.group());unit='percent' if metric=='vacancy' else 'million sq ft' if match.groupdict().get('scale') in ['m','million'] else 'sqft'
                row=_save(store,doc,source,segment,metric,match['value'].replace(',',''),unit,period,geo,definition,quote,basis=basis)
                count+=1
            share=re.search(r'U/C preleased\s+(?P<value>\d+(?:\.\d+)?)%',text,re.I)
            if share and source['id']=='jll':
                _save(store,doc,source,segment,'prelet_share',share['value'],'percent',period,geo,
                      'Publisher U/C preleased share; no area inferred',_quote(original,share.group()),basis='under_construction_preleased_share')
                count+=1
            if source['id']=='jll':
                named=re.search(r'The West End was most active for the first time since Q[1-4] 20\d{2} at\s+'+area,text,re.I)
                if named:
                    _save(store,doc,source,segment,'takeup',named['value'].replace(',',''),
                        'million sq ft' if named.groupdict().get('scale') in ['million','m'] else 'sqft',period,'West End',
                        'Reported quarterly take-up; named West End narrative',_quote(original,named.group()),basis='quarterly_flow')
                    count+=1
            # Named rent regions in the quote override page grouping only when explicit.
            rent_patterns=[
                (r'(?P<geo>City|West End) average Grade A rent[^£]{0,35}£(?P<value>[\d.]+) per sq\.?\s*ft', 'Grade A'),
                (r'(?:Prime (?P<geo>City|West End) rents|Prime rents[^£]{0,20}in the (?P<geo2>West End|City))[^£]{0,25}£(?P<value>[\d.]+) per sq\.?\s*ft','Prime'),
                (r'(?P<geo>West End|City) (?:prime rents rose[^£]{0,40}|rents rose[^£]{0,20})£(?P<value>[\d.]+) per sq\.?\s*ft','Prime'),
            ]
            for pattern,grade in rent_patterns:
                for match in re.finditer(pattern,text,re.I):
                    region=match.groupdict().get('geo') or match.groupdict().get('geo2')
                    region='West End' if region.lower()=='west end' else 'City'
                    _save(store,doc,source,segment,'rent',match['value'],'GBP/sqft',period,region,
                          grade+' office rent; original time denominator retained',_quote(original,match.group()),
                          grade=grade,currency='GBP',basis='quoted_rent')
                    count+=1
            if source['id']=='bnp' and heading:
                # PDF line breaks can split "take-up". Bind matches to the
                # explicit submarket heading and retain exact original quotes.
                literal_patterns=[
                    ('takeup',r'take-\s*up reaching\s+(?:approximately\s+)?'+area,'Reported quarterly take-up; narrative value','quarterly_flow'),
                    ('availability',r'(?:available office space\s+reducing|Available supply\s+reduced|Office supply across the West End remained broadly stable during Q[1-4], increasing marginally by [\d.]+% quarter-on-quarter)\s+to\s+'+area,'Available office area; not development pipeline','available_area'),
                    ('vacancy',r'(?:overall vacancy has continued to improve, falling to|vacancy has continued to fall, reaching|Overall vacancy held at a low|vacancy, which reduced to)\s+(?P<value>\d+(?:\.\d+)?)%','Overall vacancy; submarket narrative','stock_rate'),
                    ('rent',r'Prime rents (?:increased to (?:a new record high of )?|across Canary Wharf remained stable during the quarter at )£(?P<value>\d+(?:\.\d+)?)\s+psf(?:\s+(?:(?:per annum|per year)(?!\w)|p\.?a\.?(?![\w.])))?','Prime rent; retain disclosed time denominator','quoted_rent'),
                ]
                for metric,pattern,definition,basis in literal_patterns:
                    match=re.search(pattern,text,re.I)
                    if not match:continue
                    unit='GBP/sqft' if metric=='rent' else 'percent' if metric=='vacancy' else 'million sq ft' if match.groupdict().get('scale') in ['m','million'] else 'sqft'
                    region='Canary Wharf' if metric=='rent' and 'across Canary Wharf' in match.group() else geo
                    _save(store,doc,source,segment,metric,match['value'].replace(',',''),unit,period,region,
                          definition,_quote(original,match.group()),basis=basis,
                          grade='Prime' if metric=='rent' else 'not_applicable',currency='GBP' if metric=='rent' else None)
                    count+=1
                if geo=='Canary Wharf & Docklands':
                    card=re.search(r'(?P<value>\d+(?:\.\d+)?)k\s*sq\s*ft\s+Q[1-4]\s+CANARY WHARF\s*&\s*DOCKLANDS\s+TAKE-UP',text,re.I)
                    if card:
                        _save(store,doc,source,segment,'takeup',str(Decimal(card['value'])*1000),'sqft',period,geo,
                              'Combined submarket headline take-up card; retain separately from narrative',
                              _quote(original,card.group()),basis='quarterly_flow_headline')
                        count+=1
        for key,pattern in THEMES.items():
            match=re.search(pattern,original,re.I)
            if not match:continue
            # Keep a bounded exact substring, explicitly a candidate classification.
            start=max(0,match.start()-180);end=min(len(original),match.end()+300)
            quote=original[start:end]
            identity='theme:'+hashlib.sha256((source['id']+doc['sha256']+segment['locator']+key).encode()).hexdigest()
            store.put('events',identity,dict(kind='demand' if key in ['flight_to_quality','esg','hybrid_working'] else key,
                title=key.replace('_',' ')+' · '+geo,summary=quote,indicator_keys=[key,'market_news'],
                geography=geo,period=period,status='pending_review',human_review_status='pending_review',importance='normal',
                source_id=source['id'],document_id=doc['id'],url=doc['url'],published_at=doc.get('published_at'),
                evidence=dict(quote=quote,page=segment.get('page'),locator=segment['locator']),
                classification_method='literal-theme-candidate-v1; exact text, not semantic confirmation',
                limitations='Qualitative source excerpt; not a complete transaction/project database or quantified demand measure.'))
            count+=1
    return count
