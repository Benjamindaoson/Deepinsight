"""Build the complete human/machine registry. Verification comes from receipts only."""
import json
from datetime import datetime, timezone
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'app/docs/product'
FIELDS = ['raw_value', 'raw_unit', 'geography', 'statistical_period', 'definition', 'published_at',
          'collected_at', 'source_url', 'original_sha256', 'page_or_locator', 'normalization_basis']
RESEARCH = ['jll', 'savills', 'cbre']
sources = {
    'jll': ('JLL Central London Office Market Dynamics', 'https://www.jll.com/en-uk/insights/market-dynamics/central-london-office', 'web_report'),
    'savills': ('Savills Central London Office Market Watch', 'https://www.savills.com/research_articles/255800/393427-0', 'web_report'),
    'cbre': ('CBRE UK public research', 'https://www.cbre.co.uk/', 'web_report'),
    'planning-london': ('Planning London Datahub', 'https://www.london.gov.uk/programmes-strategies/planning/digital-planning/planning-london-datahub', 'official_api'),
    'planning-uk': ('Planning Data API documentation', 'https://www.planning.data.gov.uk/docs', 'official_api'),
    'nomis-london': ('Nomis BRES London workplace jobs', 'https://www.nomisweb.co.uk/api/v01/dataset/NM_189_1.data.csv?geography=2013265927&industry=37748736&employment_status=4&measure=1&measures=20100&time=latest,previous&select=date,geography_name,industry_name,employment_status_name,obs_value', 'official_api'),
    'boe': ('Bank of England Bank Rate', 'https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2025&Dateto=now&SeriesCodes=IUDBEDR&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N', 'official_api'),
    'ons': ('ONS CPIH annual inflation', 'https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/l55o/mm23/data', 'official_api'),
    'ons-employment': ('ONS employment rate', 'https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/timeseries/lf24/lms/data', 'official_api'),
    'gpe': ('GPE official announcements', 'https://www.gpe.co.uk/news-media/news/', 'web_report'),
    'britishland': ('British Land announcements', 'https://www.britishland.com/news/', 'web_report'),
    'epc-nondomestic': ('Government non-domestic EPC', 'https://api.get-energy-performance-data.communities.gov.uk/api/non-domestic/search', 'official_api'),
    'bbc-rss': ('BBC Business RSS', 'https://feeds.bbci.co.uk/news/business/rss.xml', 'web_report'),
}
definitions = [
 ('D01','prime_rent','Prime office rents',RESEARCH,'GBP/area; annual only with source text','Do not infer annual denominator; preserve raw and derived fields separately.'),
 ('D01','grade_a_rent','Grade A office rents',RESEARCH,'GBP/area; separately published Grade A rent','Prime rent and Grade A share are not substitutes.'),
 ('D02','vacancy','Vacancy rates',RESEARCH,'percent; overall versus Grade A explicit','No rate from available area without source denominator.'),
 ('D02','availability','Availability rates / available space',RESEARCH,'percent OR sqft/sqm, separate definitions','Availability, vacancy and available floor area must remain distinct.'),
 ('D03','takeup','Leasing take-up',RESEARCH,'sqft/sqm; quarter/YTD/year explicit','No quarterly flow from YTD; YoY only as disclosed or compatible calculation.'),
 ('D03','leasing_activity','Leasing activity',RESEARCH+['gpe','britishland'],'deal count/area OR individual event','Public announcements are incomplete; under offer is not signed or pre-let.'),
 ('D04','development','New developments',['planning-london','planning-uk','gpe','britishland'],'application status/date and disclosed floor area','Approved is not started/completed. Borough is not exact submarket.'),
 ('D04','refurbishment','Refurbishments',['planning-london','planning-uk','gpe','britishland'],'project classification with exact supporting text','Keyword hit alone is insufficient; retain unknown project type.'),
 ('D04','prelet','Pre-lets',RESEARCH+['gpe','britishland'],'tenant/project/pre-let area/date/delivery when disclosed','No inferred pre-let split/share from combined under-offer total or total area.'),
 ('D05','city','City',RESEARCH+['planning-london'],'rent/vacancy/availability/take-up/supply/events','Publisher City boundary/method must be preserved.'),
 ('D05','west_end','West End',RESEARCH+['planning-london'],'rent/vacancy/availability/take-up/supply/events','Westminster borough is not West End boundary.'),
 ('D05','canary_wharf','Canary Wharf',RESEARCH+['planning-london'],'rent/vacancy/availability/take-up/supply/events','Docklands/Tower Hamlets is not interchangeable with Canary Wharf.'),
 ('D05','midtown_fringe','Midtown / Fringe',RESEARCH+['planning-london'],'rent/vacancy/availability/take-up/supply/events','Retain Midtown and Fringe separately when the source separates them.'),
 ('D06','interest_rate','Interest rates',['boe'],'Bank Rate percent/date; UK','Macro context is not direct London office demand evidence.'),
 ('D06','economy','Economy',['ons'],'CPIH annual percent/month; UK; GDP remains separate gap','Inflation is a limited macro proxy, not a GDP implementation.'),
 ('D06','employment','Employment',['nomis-london','ons-employment'],'annual London workplace jobs; UK employment rate separately','Jobs differ from employed residents, office workers and leasing demand.'),
 ('D07','flight_to_quality','Flight-to-quality',RESEARCH+['gpe','britishland'],'qualitative attributable statement; Grade A share separately','High Grade A share does not prove rental premium or willingness to pay.'),
 ('D07','esg','ESG',RESEARCH+['epc-nondomestic','gpe','britishland'],'property EPC / qualitative market demand separately','EPC token/license required; building certificate is not market-wide ESG demand.'),
 ('D07','hybrid_working','Hybrid working',RESEARCH+['bbc-rss'],'qualitative evidence with publication date','No fabricated occupancy or causal demand estimate.'),
 ('D07','market_news','Market news',['bbc-rss','gpe','britishland']+RESEARCH,'dated attributable relevant London CRE event','General business news requires relevance filtering; not a complete deal database.'),
]
rows=[]
for i,(domain,key,name,candidates,unit,rule) in enumerate(definitions,1):
    rows.append(dict(id=f'M{i:02}',domain=domain,key=key,name=name,status='not_tested',
        priority=['free_official_api_or_open_data','authoritative_web_report','evidence_bound_model','explicit_gap'],
        target_fields=FIELDS,units_and_definition=unit,guardrail=rule,candidates=candidates,
        geography=['City','West End','Canary Wharf','Midtown / Fringe'] if domain not in ['D06'] else ['UK','London'],
        historical_coverage='not_verified_in_this_run',frequency='publisher_defined; not yet verified',
        verification=[],missing_fields=FIELDS,api_key_required=False,paid_subscription_required='not established',
        limitation='A candidate URL is not an implemented or verified metric. Research reports may require license; no free market time-series API assumed.',
        integration='Existing london_product.sources/service/structured_sources; no replacement framework'))
registry=dict(schema_version=1,generated_at=datetime.now(timezone.utc).isoformat(),
    scope='Seven previously confirmed assessment domains; attached request truncated after D05; user confirmed continuation.',
    status_enum=['api_verified','open_data_verified','web_monitor_verified','report_parsing_verified','model_assisted_verified','partial','blocked','unavailable','not_tested'],
    verification_policy='This registry is initially not_tested. Update only from this delivery run evidence; saved historical originals alone do not prove current website access.',
    source_candidates={k:dict(name=n,url=u,kind=t,status='not_tested') for k,(n,u,t) in sources.items()},metrics=rows)
DEST.mkdir(parents=True,exist_ok=True)
(DEST/'DATA_SOURCE_REGISTRY.yaml').write_text(yaml.safe_dump(registry,allow_unicode=True,sort_keys=False),encoding='utf-8')
lines=['# 数据指标与来源登记表','',f"生成时间：{registry['generated_at']}",'',
 '范围：七个已确认领域、20 个登记项。D05 四个子市场各自登记；宏观与需求指标延续前次题目范围。',
 '状态以 YAML 的枚举为准；初次登记全部 not_tested，随后仅依据本轮原始请求与解析回执更新。免费 API → 公开报告 → 有证据模型辅助 → 明确缺口。',
 '', '| 编号 | 领域 | 指标 | 当前状态 | 单位与定义 | 候选来源 | 强制边界 |','|---|---|---|---|---|---|---|']
for r in rows:lines.append('| '+' | '.join([r['id'],r['domain'],r['name'],r['status'],r['units_and_definition'],', '.join(r['candidates']),r['guardrail']])+' |')
lines+=['','## 全部候选来源','']
for key,s in registry['source_candidates'].items():lines.append(f"- {key}: [{s['name']}]({s['url']})；{s['kind']}；not_tested。")
lines+=['','每项记录要求：'+', '.join(FIELDS)+'。',
 '成功状态必须有原始文件 SHA-256、请求时间、字段断言、源 URL、统计期和位置；缺日期必须保留未知。没有查完候选源的指标不会写成 unavailable。',
 '原始事实、归一化结果和派生变化必须分别保存。人工审核文字不能补造年度租金依据。公开规划记录不是完整供应库，新闻不是完整成交库。']
(DEST/'DATA_SOURCE_REGISTRY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Registered',len(rows),'metrics across',len({r['domain'] for r in rows}),'domains before implementation.')
