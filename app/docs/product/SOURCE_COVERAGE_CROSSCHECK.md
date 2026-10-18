# 数据源与指标覆盖独立复核

核查时间：2026-10-18。范围：`D:\deepinsight-lite` 当前产品代码、本机 SQLite 与已保存原件。只读核查，无外网请求、无模型调用、无采集刷新；仅新增本报告。原始数据库以 SQLite URI `mode=ro` 打开，没有通过产品初始化函数读取。

## 结论

**尚未全面、精准覆盖题目要求。** 已登记 13 个来源入口，其中 8 个当前健康、4 个失败、1 个政策禁用。9 个来源拥有已保存快照（包括当前获取失败但已有历史 PDF 的 Savills）。产品库有 29 个文档版本、18 个不同 URL、32 条有效候选指标、6 条有效文章事件。29 个快照不是 29 份独立研究报告；其中仅 4 个 PDF，分别为 BNP Q1/Q2、JLL Q2、Savills Q2。

32 条候选中，21 条来自原件对照预置初标、2 条来自初期宏观资格核验、1 条来自就业资格核验、8 条来自本轮真实 LLM 抽取。实际成功抽取只覆盖 BNP Q1 这一份 PDF；另有同一报告的早期失败抽取。**人工批准 0 条，可正式比较 0 条**。候选状态为 19 条 `pending_review`、13 条 `needs_review`；32 条均有引用，31 条 method 为 unknown/null，2 条时期为空，6 条租金规范化值为空。

这是有真实来源、原始保存、抽取和查询能力的受限产品；不能将“登记入口”“HTTP 成功”“有候选记录”混称为“全面接入且验证完成”。

## 数据是怎样来的

1. 报告和公告：Python `httpx.AsyncClient` 对固定官方公开 URL 执行 GET，保存原始内容。PDF 用 PyMuPDF 按页取文字，HTML 用正文解析器；不是让模型自己上网找数据。代码：[sources.py:121](D:/deepinsight-lite/app/london_product/sources.py:121)、[sources.py:290](D:/deepinsight-lite/app/london_product/sources.py:290)。
2. 宏观：BoE CSV 下载端点、ONS CPIH JSON 数据端点、ONS Employment JSON 数据端点，确定性读取官方序列，无需 LLM。代码：[service.py:388](D:/deepinsight-lite/app/london_product/service.py:388)。这是 **3 个结构化外部数据端点**；不能把所有网页 URL 都说成官方 API。
3. RSS：BBC Business RSS 有适配器和配置，但当前连接超时，产品库没有实际 RSS 快照。不能声称 RSS 新闻已成功覆盖。
4. 原有资料：启动时从本地 B1/G0 原件和初标导入候选，逐条核验引用确实存在，并保存 hash。代码：[seed.py:22](D:/deepinsight-lite/app/london_product/seed.py:22)、[seed.py:41](D:/deepinsight-lite/app/london_product/seed.py:41)、[runtime.py:24](D:/deepinsight-lite/app/london_product/runtime.py:24)。原件核验不等于最终人工批准。
5. LLM：只有显式 Extract 任务才对已保存报告调用原生 Agno Structured Output。当前最多 8 条事实、最多 8 段、有字节预算。代码：[intelligence.py:124](D:/deepinsight-lite/app/london_product/intelligence.py:124)、[intelligence.py:140](D:/deepinsight-lite/app/london_product/intelligence.py:140)。
6. 定时 refresh 当前只做获取、解析、保存、规则事件提取与三个宏观适配器；**新研究报告不会在 refresh 中自动进入 LLM Extract**。代码：[service.py:312](D:/deepinsight-lite/app/london_product/service.py:312)。因此自动刷新来源与自动更新全部市场指标之间仍有断点。

## 来源逐项核对

数值来自 `app/data/product/market.sqlite3` 的 `sources/documents/facts/events` 表，facts 排除 superseded，events 排除 superseded 和 source_update；来源配置：[sources.py:30](D:/deepinsight-lite/app/london_product/sources.py:30)。

| 来源入口 | 当前获取方式与状态 | 本地快照 | 有效指标 | 有效事件 | 真实边界 |
|---|---|---:|---:|---:|---|
| BNP Paribas | HTML 入口 + PDF，healthy | 6：2 PDF、4 HTML版本 | 22 | 0 | 两季度原件；8条真正LLM候选均来自Q1，其余为初标；静态Q2 URL不等于自动发现未来季度 |
| JLL | HTML入口，已有Q2 PDF，healthy | 2 | 5 | 0 | Q2候选预置，未执行本轮LLM抽取；没有完整两季度系列 |
| Savills | 公开PDF，当前 HTTPStatusError | 1 PDF | 2 | 0 | 复用历史保存原件；当前健康失败必须保留 |
| CBRE | HTML研究页，HTTPStatusError | 0 | 0 | 0 | 仅登记，未成功接入数据 |
| Knight Frank | 官方研究页，policy_restricted | 0 | 0 | 0 | 产品获取与LLM均禁用；历史B1原件不计作产品入库 |
| Bank of England | IUDBEDR CSV，healthy | 1 CSV | 1 | 0 | UK政策利率，不是伦敦专属指标；目前事实库只保存最新观察值 |
| ONS CPIH | L55O/MM23 JSON，healthy | 1 JSON | 1 | 0 | UK CPIH同比；非伦敦办公成本指数 |
| ONS Employment | LF24/LMS JSON，healthy | 1 JSON | 1 | 0 | UK16–64岁季调就业率，2026 MAY-JUL三个月平均；不能解释成6月单月 |
| Planning London Datahub | 数据集介绍网页，HTTP403 | 0 | 0 | 0 | 不是已接通规划记录API；没有规划批量记录 |
| GPE | 官网新闻列表及文章HTML，healthy | 8 HTML版本 | 0 | 2 | 业主文章事件；不是结构化租赁全量交易库 |
| British Land | 官网新闻列表及文章HTML，healthy | 5 HTML版本 | 0 | 2 | 一则季度更新、一则装修/搬迁文章；存在分类准确性问题 |
| City of London | 官网新闻列表及文章HTML，healthy | 4 HTML版本 | 0 | 2 | 审批及City Plan公告，不等同整个伦敦规划数据库 |
| BBC Business | RSS，ConnectTimeout | 0 | 0 | 0 | 未取得可用实时新闻样本 |

所有 29 个文档路径本轮均存在，逐个 SHA-256 复算 **29/29 一致**。这证明本地原件未变化，不独立证明发布内容正确或所有指标完整。原件路径在数据库 `documents.path`，另有 [SOURCE_REGISTRY.json](D:/deepinsight-lite/app/data/product/evidence/SOURCE_REGISTRY.json)。

## 对题目指标的实际覆盖

| 题目要求 | 当前候选及地域 | 判断 |
|---|---|---|
| Prime / Grade A rent | rent 6条：City、West End、Canary Wharf；均未确认年度分母，规范化值全空；模型两条租金时期为空 | PARTIAL；不能做正式季度变化；Prime不能等价Grade A平均租金 |
| Vacancy / Availability | vacancy 8条；availability 0条；Central London、West End、Midtown、Canary Wharf & Docklands | PARTIAL；不同来源定义不完整，不可把availability与vacancy互换 |
| Quarterly take-up | 9条候选；BNP两季度核心原件存在，含不同抽取版本；City、West End、Midtown、合并Docklands等 | PARTIAL；候选非去重正式统计；季度与H1保持区别，未批准比较 |
| 新建/翻新/未来供应 | supply 3条，主要为可用存量；Silk Street审批和业主文章补充个案 | PARTIAL；没有新建/翻新/完工/未来供应的完整结构化分类或连续季度序列 |
| 预租 | prelet_share 1条（JLL80%，实际是pre-let OR under offer）；prelet数量指标0条；GPE文章有个案 | PARTIAL；不可把80%或4300 sqft合计直接解释成纯预租 |
| City | 2条City+2条source-defined City；指标只有rent/takeup | PARTIAL；无City独立vacancy候选 |
| West End | 7条，rent/takeup/vacancy/supply | PARTIAL；来源、时期、单位不齐，未形成正式连续同口径系列 |
| Canary Wharf | 单独地理只有1条rent；另有Canary Wharf & Docklands合并地域的vacancy/takeup | PARTIAL；合并地域不得当作Canary Wharf单独值 |
| Midtown / Fringe | Midtown2条（takeup/vacancy），Fringe0条 | PARTIAL / Fringe缺失 |
| 利率/就业/其他宏观 | 各1条UK BankRate、UK就业率、CPIH | PARTIAL；三序列最新值有真实机器数据，未存完整历史事实，不是伦敦就业指标 |
| Flight-to-quality | grade_a_share 2条，及一次抽取输出4条themes文本 | PARTIAL；是主题依据，未建设可检索主题事实/趋势序列 |
| ESG | British Land20Triton正文含可持续与脱碳内容，但当前事件kind=lease | PARTIAL；主题内容存在，精准分类未完成 |
| Hybrid Working | 无已入库独立主题/事件样本 | 未验证覆盖 |
| 重大租赁/企业搬迁 | GPE/BritishLand有限事件，自动分类全部首关键词匹配 | PARTIAL；现有事件没有relocation类型，不能声称企业搬迁已准确识别 |
| 规划审批/政策 | SilkStreet审批、CityPlan2040文章 | PARTIAL；2个公告样本，不是PlanningDatahub全量接入 |
| 新闻搜索/广泛行业新闻 | 未接搜索API；RSS当前失败 | 未实现搜索覆盖 / RSS BLOCKED |

32条按metric计数：rent6、vacancy8、takeup9、supply3、prelet_share1、grade_a_share2、interest_rate1、inflation_cpih1、employment1。没有availability/prelet独立数值记录。

## 精准性和持续监测的具体缺口

- 自动事件使用按顺序的关键词首匹配，不是LLM语义分类；一篇非RSS文章最多生成一个事件，地域默认London。British Land《More than a fit out: 20 Triton Street》包含自身搬迁、可持续和装修内容，却保存为 `lease`。代码：[service.py:378](D:/deepinsight-lite/app/london_product/service.py:378)。该事件ID `fcb0e058-85fe-4977-8ed5-c6255e799070`，证据文档ID `870fb5d9-0bad-4387-bcb2-60ab774ca68c`。不能据事件数量宣称分类精确。
- 每个列表最多发现2条链接，没有历史翻页/游标追赶；若刷新间隔内发布超过2条符合文章，可能漏采。代码：[sources.py:173](D:/deepinsight-lite/app/london_product/sources.py:173)、[sources.py:182](D:/deepinsight-lite/app/london_product/sources.py:182)。BNP/CBRE/Savills入口含固定2026Q2地址，尚无普适新季度发现流程。
- 新文档自动获取后并未自动执行市场结构化抽取；当前成功LLM抽取只有BNP Q1、8条事实。宏观适配器只提取最后一条观察值（BoE rows[-1]、ONS months[-1]），所以虽然原始下载包含历史，产品事实库并没有完整宏观历史。代码：[service.py:393](D:/deepinsight-lite/app/london_product/service.py:393)、[service.py:400](D:/deepinsight-lite/app/london_product/service.py:400)。
- ProductExtraction允许 `inflation_rate`，确定性适配器实际写入 `inflation_cpih`，存在指标命名未统一。证据：[contracts.py:8](D:/deepinsight-lite/app/london_product/contracts.py:8)、[service.py:404](D:/deepinsight-lite/app/london_product/service.py:404)。当前CPIH值仍可查询，但不应把契约覆盖说成完全一致。
- XLSX、RSS/Atom解析器有代码及工程测试，但本轮真实快照不存在XLSX或RSS；这两类只能称支持解析，不能称真实来源端到端成功。

## 可复核取证点

- 权威本机数据库：[market.sqlite3](D:/deepinsight-lite/app/data/product/market.sqlite3)。只读SQL模板：`SELECT payload FROM sources`、`SELECT payload FROM documents`、`SELECT payload FROM facts`、`SELECT payload FROM events`、`SELECT payload FROM extractions`。
- BNP Q1原件：[doc-bnp-8255a921c15294718433.pdf](D:/deepinsight-lite/app/data/product/originals/doc-bnp-8255a921c15294718433.pdf)，SHA `8255a921c15294718433e5a893e6616593ab730904de4be452ba74d0c27bde7c`。
- BNP Q2原件：[doc-bnp-3dd8de05ccb26ce235df.pdf](D:/deepinsight-lite/app/data/product/originals/doc-bnp-3dd8de05ccb26ce235df.pdf)，SHA `3dd8de05ccb26ce235dfc8f9cf96d47bb2f760196d56cfcc94b0dc2a2a2016cd`。
- 唯一成功产品抽取：extraction ID `29513215-da9e-41b1-97f1-e7fb01d9bcda`，Agent Run `2c7b503a-120a-4959-9053-d547be3df898`，Workflow Run `3e09d973-4511-4762-a241-e5385a2e4e10`；[real-extraction-v2.json](D:/deepinsight-lite/app/data/product/evidence/real-extraction-v2.json)。
- 原始六条金标准候选：[GOLDEN_FACTS.json](D:/deepinsight-lite/b1/g0-review/2026-10-17/GOLDEN_FACTS.json)。人审清单：[B1_HUMAN_REVIEW_CHECKLIST.md](D:/deepinsight-lite/app/docs/product/B1_HUMAN_REVIEW_CHECKLIST.md)。
- 宏观原件：[boe.csv](D:/deepinsight-lite/app/data/product/source-qualification/boe.csv)、[ons.json](D:/deepinsight-lite/app/data/product/source-qualification/ons.json)、[ons-employment.json](D:/deepinsight-lite/app/data/product/source-qualification/ons-employment.json)。

本报告是当前状态审计，不新增来源、不批准候选、不更改历史验收，也未用模型回答填补缺失指标。
