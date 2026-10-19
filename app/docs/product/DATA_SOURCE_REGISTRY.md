# DeepInsight Lite 数据源与指标登记表

本轮核验时间：2026-10-18T13:16:46.184805+00:00。本轮交付目录：`docs\delivery\poc-20261018-205425`。

20 项均绑定已有采集入口和可查询覆盖接口；这不代表 20 项全部通过。19 项存在数值或定性证据，独立 Grade A 租金受阻。没有任何一项因文件存在、HTTP 200 或模型返回文字而自动通过。

## 执行入口

`MarketService.refresh → sources.fetch_source / parse_content → Store.snapshot → indicator_ingestion / structured_sources`。原生 Workflow / Scheduler 继续复用同一业务链路。`GET /api/market/coverage` 读取本 YAML 的 source_ids 并返回实际记录 ID；前端 Monitor Settings 展示全部 20 项。

## 指标覆盖

|编号|指标|登记状态|数值记录|定性候选|已批准|地域原名|限制|
|---|---|---|---:|---:|---:|---|---|
|M01|Prime office rents|partial|9|0|0|Canary Wharf; City; City (BNP source-defined office submarket); West End|JLL/BNP real raw prime rents are available; annual denominator remains unconfirmed. Source definitions and publisher differences stay separate; no annual rent trend is approved.|
|M02|Grade A office rents|blocked|0|0|0|无独立数值|No independent numeric Grade A rent observation is verified. Savills PDF/HTML and UK/HK alternatives returned 403. BCO alternative PDF was actually fetched and contains historical charts, but its page 2 requires prior written permission for copying/storage/transmission; no automatic ingestion or chart-derived values. Prime rents and Grade A share are excluded.|
|M03|Vacancy rates|partial|11|0|0|Canary Wharf & Docklands; Central London; Central London (BNP source-defined office market); City; Midtown; West End|Numeric overall vacancy exists, but full independent quarterly history for all four requested areas and Grade A vacancy remains incomplete. Combined Canary Wharf & Docklands is not standalone Canary Wharf.|
|M04|Availability rates / available space|partial|4|0|0|Canary Wharf & Docklands; Central London; City; Southbank|Available floor area is projected separately from vacancy rates. No availability rate is inferred from area. Complete source methodology and all submarket histories remain missing.|
|M05|Leasing take-up|partial|16|0|0|Canary Wharf & Docklands; Central London; Central London (BNP source-defined office market); City; Midtown; Southbank; West End|Real quarterly take-up is projected from JLL/BNP; H1, YTD, individual deals and under-offer quantities are not interchangeable. Old and current publisher methodologies differ.|
|M06|Leasing activity|partial|0|25|0|无独立数值|Source-located leasing narrative candidates exist. No complete signed transaction database, complete transaction count, structured tenant/date/status pipeline or exhaustive market coverage is claimed.|
|M07|New developments|partial|3|6|0|Central London; City|Official Planning London API samples and source-reported construction/completion totals exist. Planning samples do not prove construction or completion. JLL City narrative and table construction totals require reconciliation; no complete project pipeline.|
|M08|Refurbishments|partial|0|4|0|无独立数值|Actual refurbishment text is saved as candidate evidence; keyword classification is not confirmed project classification. Structured project status, area and completion date remain incomplete.|
|M09|Pre-lets|partial|3|15|0|Central London; City|JLL explicitly reported U/C preleased shares are saved as percentages. Mixed pre-let/under-offer wording stays combined; no pre-let area, tenant or ratio is inferred from total area.|
|M10|City|partial|10|0|0|City|City source-defined market observations are available. Administrative City of London planning records remain separate in their original geography.|
|M11|West End|partial|10|0|0|West End|West End raw rents, vacancy and take-up exist. Missing annual basis and publisher methodology prevent approved cross-source annual rent comparison.|
|M12|Canary Wharf|partial|5|0|0|Canary Wharf; Canary Wharf & Docklands|A separate reported Canary Wharf rent exists, but vacancy/take-up/availability mostly cover Canary Wharf & Docklands. No split is inferred; full standalone multi-metric comparison is incomplete.|
|M13|Midtown / Fringe|partial|4|0|0|Midtown|Midtown numeric evidence is available. Fringe is not silently merged with Midtown; independent Fringe indicators remain missing.|
|M14|Interest rates|api_verified|366|0|0|United Kingdom|BoE IUDBEDR actual structured download and last 366 observations are available; UK Official Bank Rate, not London rent yield or a different interest series. Publication timestamp may be unknown; effective observation dates are preserved.|
|M15|Economy|partial|48|0|0|United Kingdom|ONS L55O CPIH has a bounded 24-month series. ECYX is monthly GVA growth, not GDP index. Its JSON unit is empty: raw observations retain source_unit_not_stated, no normalized percent assertion. No London GDP series is claimed.|
|M16|Employment|api_verified|26|0|0|London (workplace); United Kingdom|ONS LF24 retains 24 rolling-three-month UK employment-rate observations; Nomis BRES retains actual London workplace jobs for source years. Annual historical jobs are not 2026 real-time office demand.|
|M17|Flight-to-quality|partial|0|2|0|无独立数值|Real report text supports qualitative flight-to-quality candidates. No invented quality index or premium causality; candidates and interpretations remain unreviewed.|
|M18|ESG|partial|0|20|0|无独立数值|Real sustainability/BREEAM report and owner text is retrievable. EPC remains blocked without LONDON_EPC_TOKEN; property certificates do not prove market-wide occupier preferences.|
|M19|Hybrid working|partial|0|4|0|无独立数值|ONS source dated 2023-02-13 covers Sep 2022–Jan 2023; owner text is supplementary qualitative evidence. It is historical evidence, not a 2026 London/submarket hybrid-working series.|
|M20|Market news|partial|0|76|0|无独立数值|Publisher reports, owner articles and RSS provide source-located candidate news. Bounded article discovery and keyword classification are not an exhaustive semantic news/deal database.|

## 来源、凭据及替代调查

官方 API/结构化下载优先；公开报告次之；模型只基于实际保存来源。失败记录与替代调查均保留。EPC 的 bearer token 仅通过服务器环境变量 LONDON_EPC_TOKEN 读取，不写入 YAML 或浏览器。缺少凭据时保持禁用。Knight Frank 已有明确 AI 使用限制，继续禁用。BCO 的权限问题不因 PDF 能下载而消失。

## 证据边界

数字记录数包括待审核的原始值，指标间存在重叠，不可相加作为独立市场事实总量。历史快照与最新采集时间分别保存；同一原文再次获取仍保留原始快照时间，新请求时间见 receipt。年度租金无明确来源依据时 normalized_value 为空；人工备注不能绕过年度门禁。宏观 UK、London workplace、商业子市场保持不同口径。

四轮模型实测：2 轮输出用量超单次上限而失败；2 轮草稿被门禁拦截，安全证据回退成功。模型分析尚未通过业务验收。完整清单字段、来源 URL、失败原因及记录 ID 见同名 YAML。
