"""Attach this delivery's receipts to the previously complete registry."""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime,timezone
import yaml
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(sys.argv[1]).resolve()
DEST=ROOT/'app/docs/product'
registry=yaml.safe_load((DEST/'DATA_SOURCE_REGISTRY.yaml').read_text(encoding='utf-8'))
receipt=json.loads((OUT/'public-sources.json').read_text(encoding='utf-8'))
checks={r['source_id']:r for r in receipt['results']}
registry['source_candidates'].setdefault('bnp',dict(name='BNP Paribas Real Estate saved Q1/Q2 reports',url='https://www.realestate.bnpparibas.co.uk/insights/central-london-office-market-update-q2-2026',kind='web_report',status='partial',limitation='Existing hash-bound PDF originals; no fresh BNP request in this run.'))
with sqlite3.connect((OUT/'isolated/market.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    records={t:[json.loads(r[0]) for r in db.execute('SELECT payload FROM '+t)] for t in ['facts','documents','events']}
documents={d['id']:d for d in records['documents']}
verification=[]
for identity in ['seed-jll-2026Q2-takeup','seed-jll-2026Q2-vacancy','seed-jll-2026Q2-supply']:
    f=next(f for f in records['facts'] if f['id']==identity)
    d=documents[f['document_id']];q=f['evidence']['quote'];page=f['evidence'].get('page')
    original_ok=hashlib.sha256(Path(d['path']).read_bytes()).hexdigest()==d['sha256']
    quote_ok=any(q in s['text'] and s.get('page')==page for s in d['segments'])
    assert original_ok and quote_ok
    verification.append(dict(id=identity,metric=f['metric'],value=f['value'],unit=f['unit'],period=f['period'],geography=f['geography'],
        quote=q,page=page,url=d['url'],original_sha256=d['sha256'],original_hash_valid=original_ok,quote_in_page=quote_ok,
        published_at=d.get('published_at'),limitation='Exact source replay; publication date and full methodology undisclosed. Pending human review.'))
(OUT/'three-fact-source-checks.json').write_text(json.dumps(dict(at=datetime.now(timezone.utc).isoformat(),facts=verification),ensure_ascii=False,indent=2),encoding='utf-8')
for key,s in registry['source_candidates'].items():
    mapped='planning-api-city' if key=='planning-london' else key
    c=checks.get(mapped)
    if c:
        s.update(status='partial' if c['status']=='acquired' else 'blocked',request_receipt=str((OUT/'public-sources.json').relative_to(ROOT)),
                 http_result=c.get('result',{}).get('sources'),failure=c.get('error') or c.get('reason'),verified_at=c['at'])
        if c['status']=='acquired' and key in ['boe','ons','ons-employment','nomis-london']:s['status']='api_verified'
        if c['status']=='acquired' and key=='jll':s.update(status='report_parsing_verified',verified_target_fields=['quarterly_take_up','overall_vacancy','available_supply'],fact_receipt=str((OUT/'three-fact-source-checks.json').relative_to(ROOT)))
    if key=='planning-uk':s.update(status='partial',limitation='Official documentation exists; planning-application dataset reports no providers. Not a verified London office feed.',investigation_url='https://www.planning.data.gov.uk/dataset/planning-application')
metric_map={'prime_rent':['rent'],'grade_a_rent':[],'vacancy':['vacancy'],'availability':['availability','supply'],
    'takeup':['takeup'],'leasing_activity':[],'prelet':['prelet','prelet_share'],'interest_rate':['interest_rate'],
    'economy':['inflation_cpih'],'employment':['employment']}
geo_map={'city':['City'],'west_end':['West End'],'canary_wharf':['Canary Wharf'],'midtown_fringe':['Midtown','Fringe']}
for m in registry['metrics']:
    key=m['key']; facts=[];events=[]
    if key not in ['interest_rate','economy','employment','esg','market_news'] and 'bnp' not in m['candidates']:m['candidates'].append('bnp')
    active=[f for f in records['facts'] if f.get('status') not in ['superseded','rejected']]
    if key in geo_map:facts=[f for f in active if any(f.get('geography','').startswith(g) for g in geo_map[key])]
    elif key in metric_map:facts=[f for f in active if f.get('metric') in metric_map[key]]
    else:events=[e for e in records['events'] if e.get('kind') not in ['source_update'] and e.get('status') not in ['superseded','rejected']]
    m['status']='partial'
    m['verification']=[dict(receipt=str((OUT/'public-sources.json').relative_to(ROOT)),at=receipt['at'],kind='current_free_acquisition'),
                       dict(saved_fact_ids=[f['id'] for f in facts],saved_event_candidates=len(events),kind='saved_source_coverage_not_automatic_approval')]
    m['missing_fields']=['full_methodology','complete_submarket_history']
    m['historical_coverage']=sorted({f.get('period') or 'unknown' for f in facts}) or 'No verified structured target series'
    m['limitation']={
      'prime_rent':'Real raw rents exist; no annual normalization without explicit source annual wording. Legacy approved labels do not resolve it. No free official prime rent API identified in investigated candidates.',
      'grade_a_rent':'No separate Grade A rent record. Grade A share and Prime rents deliberately excluded. JLL/Savills/CBRE candidates investigated; two configured report URLs blocked 403. No verified free API.',
      'vacancy':'Real JLL/BNP numeric disclosures; overall/Grade A/source-defined geography stay separate. Methodology and publication dates incomplete; review pending.',
      'availability':'Saved supply observations describe available area. They are not automatically availability rates or future development pipeline; rate unavailable in saved facts.',
      'takeup':'Real JLL quarterly narrative differs from YTD card; exact quote/page/hash checked. No complete transaction database; some dates/methods unknown.',
      'leasing_activity':'Official owner events available; under-offer/signed/pre-let preserved in original text. Candidate event discovery is not a complete deal-count series.',
      'development':'Current official Planning London JSON returns application descriptions/status/reference/last_updated. Some records are office candidates; neither approval nor last_updated proves completion or publication date.',
      'refurbishment':'Official planning and owner text acquired; no verified complete refurbishment project field/series. Keyword classification remains a candidate.',
      'prelet':'JLL combined pre-let OR under-offer share is not pure pre-let. Owner announcements may disclose individual cases; no project-wide pre-let area/share inferred.',
      'city':'Saved source-defined City rent/vacancy/take-up plus official City applications. Annual rent, methods and exact boundaries still limit comparison.',
      'west_end':'Saved rents/vacancy/take-up; Westminster API acquired but no qualifying office candidates in this five-record sample. Borough not substituted for West End.',
      'canary_wharf':'Limited raw rent/vacancy and Docklands-qualified observations. Tower Hamlets planning candidates do not establish Canary Wharf-wide measures.',
      'midtown_fringe':'Midtown raw rent/vacancy present; Fringe numeric coverage absent. Camden sample has no qualifying office candidates; do not merge scopes.',
      'interest_rate':'Current BoE official CSV IUDBEDR field parsed into saved percent/date fact. Publication timestamp not supplied by endpoint; UK macro only.',
      'economy':'Current ONS L55O CPIH percent/month parsed. This is inflation context; GDP has official candidate download but is not yet integrated.',
      'employment':'Current Nomis London BRES API fields/schema and two annual workplace-job rows verified; UK ONS rolling employment separate. Not office employment or occupier demand.',
      'flight_to_quality':'Some Grade A share and qualitative report text exist. No direct willingness-to-pay or causal flight-to-quality metric.',
      'esg':'EPC blocked: bearer token absent; no request sent. Qualitative reports do not establish office-market ESG demand or complete certification coverage.',
      'hybrid_working':'Candidate research/news paths exist; this run did not verify a specific London hybrid-working series or fresh attributable demand conclusion.',
      'market_news':'Fresh owner/RSS acquisition and stored attributed event text; date/geo/relevance vary. Search is already implemented but not paid-tested in this run.'}[key]
    if key in ['grade_a_rent','hybrid_working']:m['missing_fields']=['verified_target_value','definition','statistical_period','exact_submarket']
    if key in ['grade_a_rent','hybrid_working']:m['status']='not_tested'
    if key=='esg':m.update(status='blocked',api_key_required=True,missing_fields=['EPC token','verified_property_records','market_demand_evidence'])
    if key in ['interest_rate','employment']:m['status']='api_verified'
    if key=='economy':m['status']='partial'
    m['verified_submetrics']=['IUDBEDR Bank Rate'] if key=='interest_rate' else ['BRES workplace jobs; ONS rolling rate separately'] if key=='employment' else []
registry['last_verified_at']=receipt['at']
registry['verification_policy']='Current receipt validates acquisition separately from metric coverage. api_verified applies only to named verified_submetrics, never the entire London office domain.'
for ext in ['md','yaml']:
    before=OUT/('registry-initial.'+ext)
    if not before.exists():before.write_bytes((DEST/('DATA_SOURCE_REGISTRY.'+ext)).read_bytes())
(DEST/'DATA_SOURCE_REGISTRY.yaml').write_text(yaml.safe_dump(registry,allow_unicode=True,sort_keys=False),encoding='utf-8')
lines=['# 数据指标与来源登记表','',f"本轮核验：{receipt['at']}",'',
 '20 项登记、7 个题目领域。状态反映目标字段；其中 api_verified 仅覆盖明确列出的子指标，不代表整个业务领域通过。',
 '优先顺序：免费官方 API/开放文件 → 权威网页/报告 → 有证据模型辅助 → 明确缺口。本轮付费模型/搜索调用为 0。',
 '', '| 编号 | 领域 / 指标 | 状态 | 实际结果与缺口 |','|---|---|---|---|']
for m in registry['metrics']:lines.append(f"| {m['id']} | {m['domain']} {m['name']} | {m['status']} | {m['limitation']} |")
lines+=['','## 当前获取回执','', '| Source | Current acquisition | Detail |','|---|---|---|']
for key,c in checks.items():lines.append(f"| {key} | {c['status']} | {c.get('error') or c.get('reason') or str(c.get('result',{}).get('sources',[]))} |")
lines+=['','## 候选来源完整清单','']
for key,s in registry['source_candidates'].items():lines.append(f"- [{s['name']}]({s['url']})：{s['status']}。")
lines+=['','## 可复核证据','',f"- 采集与结构化回执：`{(OUT/'public-sources.json').relative_to(ROOT)}`。",f"- 三个 JLL 事实逐条回原件：`{(OUT/'three-fact-source-checks.json').relative_to(ROOT)}`。",' - YAML 包含全部目标字段、单位定义、区域、历史期、候选来源、缺失字段与凭据/费用边界。',
 ' - 公开市场租金/空置/成交的免费官方时间序列 API 在本次候选调查中未找到可用字段；这不等同于已证明所有免费 API 都不存在。',
 ' - [Planning Data 文档](https://www.planning.data.gov.uk/docs)与[planning-application 数据集](https://www.planning.data.gov.uk/dataset/planning-application)已调查；不能因为通用 API 存在就声称取得伦敦写字楼项目。',
 ' - [ONS GDP 下载页](https://www.ons.gov.uk/economy/grossdomesticproductgdp/datasets/gdpmonthlyestimateuktimeseriesdataset/current)是后续候选；未实施和核验，不能用 CPIH 冒充 GDP。',
 ' - 所有 raw 租金、历史事实与原文保留；不接受行业惯例年度化，不推算 Grade A rent、空置率分母、纯 pre-let 比例或完整交易数量。']
(DEST/'DATA_SOURCE_REGISTRY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({s:sum(m['status']==s for m in registry['metrics']) for s in registry['status_enum']}))
