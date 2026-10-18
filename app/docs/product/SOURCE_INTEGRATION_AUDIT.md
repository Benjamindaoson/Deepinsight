# London Office Market 数据源、模型与工具接入审计

核查时间：2026-10-18，约08:10–08:13（Asia/Shanghai）。范围仅 D:\deepinsight-lite 当前 app/london_product；不包含历史B0/B1测试次数、Radar项目或Codex自身的开发工具。本轮只读检查源码、配置白名单字段、业务/原生SQLite及本地OpenAPI，未调用模型或刷新外部来源。只新增审计文档及JSON收据。

**结论：当前接入是局部可追溯，尚未全面、精准覆盖题目。13是登记条目数，不是13个成功的指标API，更不代表13个来源均经过LLM自动抽取。** 前次交付的技术链路PASS不能解释为数据覆盖、准确性和持续更新全部通过。

## 实际数据路径

1. Python httpx 从来源白名单的公开网页、PDF、CSV、JSON或RSS地址下载，保存字节、哈希、时间及来源；HTML/PDF等在本地解析。它不靠模型自身知识获取市场数字。
2. 三条宏观序列有确定性适配器：BoE IUDBEDR Bank Rate（CSV）、ONS L55O CPIH（JSON）、ONS LF24就业率（JSON）。就业是英国16–64岁季调三个月滚动率，并非伦敦办公室就业。当前适配器主要保存最后一条序列记录，没有自动回填完整宏观历史。
3. 研究报告自动采集与LLM抽取是分开的操作：refresh保存文件，不自动对新研究报告启动Extract。Extract为显式受控任务，提示最多8条事实，选最多8段、12KB上下文，不能声称全文所有指标都覆盖。
4. 32条有效候选中，21条来自既有研究报告资格初标，3条来自宏观资格材料，8条来自本轮成功LLM抽取。现版本成功LLM抽取仅验证了BNP Q1一份文档；首轮失败保留。
5. 问答工具search_market_evidence检索本地保存记录，名字中的search不是联网搜索。查询按关键词排序，事实约11KB、事实加事件约14KB上下文；没有向量库、外部搜索或每次重读全部PDF。
6. 当前新闻/公告分类由Python关键词规则执行，并非逐篇LLM语义核验。默认日报/周报是确定性模板；显式选择AI分析时才额外调用模型。

依据：[sources.py](../../london_product/sources.py:30)、[采集HTTP](../../london_product/sources.py:121)、[查询工具](../../london_product/intelligence.py:78)、[显式抽取](../../london_product/intelligence.py:124)、[事件规则](../../london_product/service.py:360)、[宏观适配](../../london_product/service.py:388)。

## 来源逐项状态

以下状态来自已保存的最近真实尝试，本轮未重试外网。快照数量包含HTML列表、文章及内容版本，不等于独立研究报告数。

| 登记条目 | 实际方式 | 最近状态 | 本地快照 | 有效指标候选 |
|---|---|---|---:|---:|
| BNP Paribas Real Estate | 固定Q2网页及公开PDF；复用Q1/Q2原件 | healthy | 6 | 22（含8条LLM候选） |
| JLL | 市场网页及已存Q2 PDF | healthy | 2 | 5 |
| Savills | 已保存Q2 PDF；当前配置PDF链接刷新失败 | failed，历史原件可用 | 1 | 2 |
| CBRE | 配置的Q2报告网页 | HTTP错误 | 0 | 0 |
| Knight Frank | 已登记研究网页，当前产品禁用AI与自动采集 | policy_restricted | 0 | 0 |
| Bank of England | 官方数据库CSV导出，IUDBEDR | healthy | 1 | 1 |
| ONS CPIH | 官方公开JSON，L55O | healthy | 1 | 1 |
| ONS Employment | 官方公开JSON，LF24 | healthy | 1 | 1 |
| Planning London Datahub | 数据集说明网页，未接成规划记录API | HTTP403 | 0 | 0 |
| GPE | HTML新闻列表及文章 | healthy | 8 | 0（事件另存） |
| British Land | HTML新闻列表及文章 | healthy | 5 | 0（事件另存） |
| City of London | HTML新闻列表及文章 | healthy | 4 | 0（事件另存） |
| BBC Business | RSS XML | ConnectTimeout | 0 | 0 |

总计13登记条目、8最近healthy、4failed、1restricted；9条来源有本地内容（包括Savills历史原件）。29快照对应18个不同URL，仅4份PDF：BNP Q1/Q2、JLL Q2、Savills Q2。独立交叉检查29/29原件哈希匹配。实际URL、来源状态、数据计数见[source-integration-audit-20261018.json](../../data/product/evidence/source-integration-audit-20261018.json)。

## 当前模型和调用计数

- 配置中转base_url：`https://api.jingziai.club/v1`。
- 请求模型标识：`claude-sonnet-4-6`。
- 客户端：Agno OpenAIChat兼容协议，经`chat.completions.create`请求；预计路径`/v1/chat/completions`。客户端名称不意味着模型是OpenAI模型。
- 配置读取自既有secrets/model.json，本轮仅输出base_url/model，未输出或修改密钥。只能核实请求标识及保存响应，不能独立认证中转实际底层模型或收费口径。
- 当前产品累计16次provider请求：抽取4次（2个尝试）、问答8次（4个运行）、AI报告分析4次（2个运行）。包含失败尝试。一个失败流式运行最终用量不完整；费用回执N/A。
- 两次分析调用的服务商返回输出量超过请求的单次max_tokens，完整异常见provider-usage-review-delivery.json。此项继续REVIEW_REQUIRED。

依据：[模型构造](../../london_product/intelligence.py:66)、[配置读取](../../london_data/extraction.py:127)、[实际调用账本](../../data/product/evidence/model-call-ledger.json)。

## 工具与API数量口径

| 数量口径 | 结果 | 解释 |
|---|---:|---|
| 自定义Agent业务工具 | 2 | search_market_evidence、compare_market_facts |
| Agno原生Skills辅助工具 | 3 | get_skill_instructions、get_skill_reference、get_skill_script |
| 查询Agent可用工具合计 | 5 | 2业务工具+3Skills辅助工具；不是5个外部数据接口 |
| 本地业务Skills目录 | 3 | Extract、Compare、Event Monitor；Skill不是一个外部API |
| 原生记录中实际工具调用 | 9 | 按tool_call_id去重：search_market_evidence 7次、get_skill_instructions 2次 |
| 模型实际触发compare_market_facts | 0 | 确定性比较通过业务API/UI另有真实执行，不能算模型工具调用 |
| 外部宏观数据接口/序列地址 | 3 | BoE CSV+ONS JSON×2；其中BoE是下载导出接口 |
| 外部模型API服务 | 1 | jingziai.club OpenAI兼容中转，累计16请求 |
| 外部新闻搜索API | 0 | 未集成Tavily/Serp/Google/Bing等联网搜索 |
| 已配置外部通知渠道 | 0 | 本机loopback测试不算外部发送渠道 |
| 产品自定义本地REST操作 | 26 | 23个路径，按HTTP方法计数 |
| 本地完整OpenAPI操作 | 145 | 110路径，含119个Agno原生操作；不是145个外部API |

网络实现另有特定本机合成DNS情况下使用的Cloudflare DoH公共解析辅助服务；它不是市场数据来源。其他九个来源条目主要是普通HTML/PDF入口，一个是RSS。**当前没有覆盖所有下载、重定向和DNS辅助请求的统一传输账本，因此不能可靠给出外部采集HTTP请求总次数。29快照不等于29次请求。**

## 题目指标覆盖

| 要求 | 当前有效候选/内容 | 判断 |
|---|---|---|
| Prime/Grade A Rent | 6条rent | 部分；六条规范化租金均为空，年度单位未确认，不能正式比较；prime不等于完整Grade A租金序列 |
| Vacancy/Availability | 8条vacancy，0条独立availability | 部分；定义、分母、物业范围未完整核实，vacancy不能自动替代availability |
| Quarterly Take-up | 9条takeup | 部分；有两季主报告数据与子市场候选，但不是所有地域/来源连续季度都完整 |
| 新建、翻新、预租、未来供应 | supply 3、prelet_share 1、公告文本 | 部分；没有完整项目级时间序列及新建/翻新/预租分项台账 |
| City/West End | 有候选 | 部分；尚无批准后的同口径变化序列 |
| Canary Wharf | 有租金；take-up/vacancy为Canary Wharf & Docklands合并口径 | 部分；不能把合并地域默认为纯Canary Wharf |
| Midtown/Fringe | Midtown 2条，Fringe 0条 | 不完整 |
| 利率、就业、宏观 | Bank Rate、CPIH、英国就业率各1条 | 三条已存；不等于伦敦地区办公就业或完整宏观历史 |
| Flight-to-quality | Grade A share 2条及文本 | 部分间接证据，无独立主题监测验收 |
| ESG | 原件中有可持续办公/装修内容 | 部分文本；未形成精准主题分类 |
| Hybrid Working | 尚无已验证结构化主题记录 | 未完成 |
| 租赁、搬迁、规划、新闻 | 6条待审公告事件 | 部分；无广泛新闻搜索，Planning记录API未通，搬迁未可靠单列 |

治理上32条候选全部待审（13needs_review、19pending_review），31条method未知/null，两条模型租金period为空。没有正式人工approved事实。这是可追溯候选库，不是经过全面准确性验收的正式市场库。

## 影响“全面精准”的工程缺口

1. 固定季度地址和每轮最多两个文章链接，没有完整分页/游标和下一季度报告发现保证。
2. 定时refresh不自动对新研究报告运行Extract；新PDF下载成功不等于关键指标自动更新。
3. 事件使用首个匹配关键词决定类别/重要性。British Land装修与可持续办公文章当前被归为lease；标签未通过语义核验。
4. ESG/Hybrid/Fringe、规划结构化记录、伦敦就业、完整项目级未来供应尚缺。
5. ProductFact允许inflation_rate，而确定性适配和库中用inflation_cpih；数据契约命名仍需统一。初标记录也不能冒充全部具备原生抽取Run ID的自动结果。
6. 没有完整外部HTTP请求级计数；模型工具调用计数与模型请求计数已从原生记录/账本区分。
7. 原G0未放行、原四报告原始评测AC26仍FAIL；当前一次成功抽取不能替代跨来源评测。AI报告已有语义问题仍待审核。

后续优先级应为：先修实际来源入口/新季度发现和请求级记录，再建立“新报告→受预算约束的抽取→校验→待审”的自动更新链，补齐缺失指标和事件分类，最后用跨来源标注集验证覆盖与准确性。此文仅审计；本轮没有修改这些实现或重新发起付费模型验证。

交叉审阅：[SOURCE_COVERAGE_CROSSCHECK.md](SOURCE_COVERAGE_CROSSCHECK.md)。机器收据：[source-integration-audit-20261018.json](../../data/product/evidence/source-integration-audit-20261018.json)。
