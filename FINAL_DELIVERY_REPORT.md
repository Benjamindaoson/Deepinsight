## 官方结构化 API 与快速问答路由交付 — 2026-10-18

**本轮完成五路公开官方 API 的真实接入、并行采集、原文存档和按问题路由。整体产品仍为 PARTIAL：本地已存数据问答达到两秒目标，复杂 AI 分析未达到两秒，且未经人工审核的市场指标仍不能作为正式趋势。**

- 新接入 Planning London Datahub 的 City of London、Westminster、Tower Hamlets、Camden 四个只读申请查询，以及 Nomis BRES 伦敦工作地就业 CSV。一次真实 Agno Workflow 刷新中五路均成功，保存四份规划响应和一份 Nomis CSV，原始 SHA-256 逐份重算一致；形成 14 条待审核规划候选事件、两条待审核就业观测。Run ID `a7b5f661-8682-4399-a7c4-6baadd25d51d`，任务 `a9c6aec4-5e1b-46ef-98d6-0645506a6d79`。本轮 14 路来源成功或未变化，CBRE 与 Savills 为 HTTP 403，任务据实标记 `partial`。
- 政府非住宅 EPC API 已登记为可选来源；因缺少 `LONDON_EPC_TOKEN`，状态 `configuration_missing`，未发请求，也未将楼宇证书数据冒充写字楼市场 ESG 趋势。现有 BNP/JLL/BoE/ONS、业主公告、RSS、Tavily 候选发现、Agno Scheduler 与 Apprise 保持原有路径。Knight Frank 的限制继续生效。
- `/api/market/ask` 的 Auto 模式把明确的指标、地域和证据查阅路由到本地确定性查询；风险、机会、原因和趋势解读继续交给原生 Agent 与发布门禁。采集任务使用四路并发并在后台执行，普通问答不等待外部 API。真实浏览器查询“查看伦敦就业数据”显示两期数值、工作地口径、原始 URL、CSV 行号和 `pending_review`，模型请求数为零。
- 30 次本机回环已存查询：完成耗时 p50 88.15 ms、p95 138.5 ms，零模型请求；这是本地已存问答测量，不是所有问题的两秒 SLA。历史真实 Native Agent 分析约 21.5 秒，本轮未新增付费模型调用或语义验收。后台真实刷新约 27 秒，但不阻塞已存数据查询。
- 修复证据包变量覆盖导致的工具错误；恢复租金年度单位与模型草稿的审核门禁：`GBP/sqft` 没有明确每年分母时保持未知且不年度化；未证实趋势草稿继续拦截并给出安全证据回答，不因存在其他候选序列而放行。已存事实及人工审核状态未改写，数据库目前无人工批准事实。
- 完整后端回归 **230 passed**（原始输出见验收目录 `BACKEND_REGRESSION.txt`）；前端 **25 passed**，TypeScript 通过，ESLint 在构建镜像为零错误、一条既有 `<img>` 性能警告。OpenSpec 严格校验与前端构建预检通过；生产构建在本轮前端改动后通过。后端 `/health`、概览接口返回 200，产品 UI 在 `http://127.0.0.1:3101/ask` 实际完成快速问答。一次分离启动的后端进程曾无异常堆栈退出；前台运行后恢复，长期启动稳定性仍需观察，不能宣称已经通过生产可靠性验收。

详细来源、性能样本、哈希、浏览器结果和限制见 [本轮验收报告](app/data/product/evidence/structured-signals-routing-20261018/ACCEPTANCE_REPORT.md)。运行入口：双击 `app/Start-London-Market.cmd`；停止：`app/Stop-London-Market.cmd`；命令行后端为 `& app/scripts/product-start.ps1` / `& app/scripts/product-stop.ps1`。人工审核租金、空置率方法和季度比较、EPC 凭证及外部通知目的地仍是单独门禁，不能写成 PASS。

---

## Tavily live activation — 2026-10-18

New dedicated key configured in local ignored storage; API ready in running backend. Project MCP registered and real initialize/tools-list passed. One real product search: 1 provider credit, 8.088s, one JLL URL, verified original hash, pending_review retained. Existing news Workflow completed in 33.511s with PARTIAL due Planning HTTP403. Same-key replay 46.86ms, no extra search. Four schedule IDs and facts/review states preserved. 211 offline tests passed; zero LLM requests and zero external recipient notifications. Details: [Tavily activation acceptance](app/data/product/evidence/tavily-live-setup-20261018/ACCEPTANCE_REPORT.md). MCP current-session hot loading and exhaustive news coverage are not claimed. Notifications remain unconfigured.

# 真实数据使用补充 — 2026-10-18

通过现有生产接口真实刷新 GPE、British Land、City of London 和 Bank of England。初次四项网络失败，公开 DNS 检查后各通过已有重试入口恢复一次，四项均成功；失败与恢复记录均保留。九份原文引用（含五篇文章和央行 CSV）逐份哈希校验通过，相同内容复用旧快照。

已在产品生成实际周报：[打开报告](http://127.0.0.1:3101/reports?report=fbd939d0-424f-413e-a523-bbdec6f97210)；报告 Run `d0fb31c8-660c-4340-92a1-19e6807b9a2f`。这是确定性证据周报，非本轮 AI 分析成功声明。人工审核状态和比较门禁保留。无代码改动、Mock、付费模型请求、Tavily 请求或外部发送。

证据：`app/data/product/evidence/live-data-20261018/REAL_DATA_RESULT.md`、`original-evidence.json`、`jobs.json`、`recovery-results.json`。Tavily 与外部通知仍需本地新凭证及授权。

---

# News discovery and notification integration — 2026-10-18

**Implementation and local verification PASS; real Tavily and external recipient delivery remain BLOCKED. Overall product remains PARTIAL.**

This round reused MarketService, native Agno Workflow/Scheduler, existing jobs/documents/events/reports and Apprise. No new monitoring engine, scheduler or database. Tavily is an optional candidate-URL adapter, disabled by default, requiring a NEW dedicated `LONDON_TAVILY_API_KEY`; the inherited generic key is ignored. Search snippets never become facts. Originals retain hashes and evidence; extracted events remain pending review.

- Baseline 192 tests passed; final **208 passed in 34.93s**. Full offline-fixture chain + real localhost HTTP Apprise delivery passed; repeat search/event/send were deduplicated.
- Real GPE listing and two article originals acquired in **8.3s**, hashes verified. Monitoring Run `69af2d31-2132-4727-847d-f8da8df4fc2e`; known-event versions retained. Three incompatible comparisons still rejected.
- Real weekly report and HTML/Markdown export succeeded: report `ced8fb96-b6c4-418f-af2b-a30cca3dc148`, native Run `8a7eca13-aeae-4e25-8730-dc184154e14a`. Browser Job Status and report body verified, including pending labels and citations.
- All four business schedules retain identical IDs, enabled states and cron expressions after restart. The existing fifth, disabled historical probe is preserved.
- All 33 existing facts and 41 original hashes unchanged. No original record deleted. New snapshots/report appended; two existing events received normal content-version metadata.
- Apprise configuration exceptions are now caught; an exception after dispatch records `delivery_unknown` and blocks unsafe resend. New read-only preflight and explicit-send CLI reuse the same notification path.
- Real Tavily calls **0**; paid LLM calls **0**; external notification sends **0**. Current dedicated key and destination both missing. Localhost acceptance is not external recipient delivery. Prior AI semantic-quality limits are unchanged.

Product: http://127.0.0.1:3101 . [Actual weekly report](http://127.0.0.1:3101/reports?report=ced8fb96-b6c4-418f-af2b-a30cca3dc148).

Full evidence: [News and notification acceptance](app/data/product/evidence/news-discovery-notifications-20261018/ACCEPTANCE_REPORT.md). Updated operational authority: `app/docs/product/B1_RUNBOOK.md`. New config is owner-only server environment, never chat/frontend. Start/stop remain `app/Start-London-Market.cmd` / `app/Stop-London-Market.cmd`; backend-specific verified commands are `app/scripts/product-start.ps1` / `product-stop.ps1`.

---

# DeepInsight Lite — 修复后单次真实问答验收（2026-10-18）

**技术执行 PASS；AI 语义分析未通过；安全回答回退 PASS。此次用户交互链路通过，整体产品仍 PARTIAL。**

本次按新授权只提交了一次“最近一个季度伦敦写字楼市场有哪些变化、风险和机会？”，未改业务代码，未重试。真实 Native Agent 完成检索、模型生成、发布检查，并向页面返回非空且有来源的安全回答。

| 维度 | 实际结果 |
|---|---|
| 模型 / 中转 | claude-sonnet-4-6 / https://api.jingziai.club/v1 |
| 网页提交 / 模型请求 / 工具 | 1 / 2 / 1次search_market_evidence |
| 实际Token（服务商回执） | 累计输入2394、输出1356；单次输出58/1298；全部在现有限额内 |
| 时间 | Native浏览器流21.540秒；含发布检查21.646秒；精确用户可见正文TTFT未测得 |
| 费用 | N/A，无法核实，不代表免费 |
| Run ID | d075bf6b-9e43-4c01-b944-9f4babc66764，COMPLETED |
| AI草稿 | 非空；存在Tower of London误写为“塔桥”和部分来源引用缺失，不判语义通过 |
| 最终页面 | 1条机构披露变化、8条待审披露；9条来源/数值/原文/状态核查通过；0批准 |
| 保护 | 未超预算、无账本错误、无重复模型请求；原件/事实/审核状态/历史Run和原账本一致 |

**已知限制**：规划事件因检索包默认pending_review与保存字段null不一致而保守省略；机构变化卡片通用数值行显示未披露，但原文正确显示2.6 million sq.ft.和15%。本轮只记录，不改代码、不放宽门禁。

完整证据：[本次真实验收报告](app/data/product/evidence/post-fallback-live-20261018/AI_QA_ACCEPTANCE_REPORT.md)。运行入口仍为 http://127.0.0.1:3101 ，当前构建身份仍为 `bfbfd31e01cb87d6c0b9715afe26396cf77e87495821c7ffbbfa6bd68691cb1f`。
其他业务模块本轮未重新全量验收，不新增PASS声明。本轮已停止，不继续开发或追加模型测试。

---

# 历史记录：离线安全回答回退补充（2026-10-18）

**本轮离线修复 PASS；产品整体仍 PARTIAL。未进行新真实模型问答，历史真实验收失败不改写。**

- 已实现确定性安全回退：AI 草稿拦截后，基于本次实际检索且原件、原文、记录可核对的证据生成非空回答；区分已核验事实、机构披露变化、待审核披露和证据不足。
- 原生聊天及历史恢复统一使用只读发布投影，保留 Agno Session/Run 和原始草稿。界面明确标记回退；有限自动检查不等于语义或人工审核。
- 同一历史草稿离线回放保留 11 条待审核披露、0 条升级批准；3 条证据无法复核而省略，记录原因。租金趋势、规划过度表述和未支持的风险机会不发布。
- **192 项后端测试通过（37.87s），25 项前端测试通过**；生产构建、TypeScript、Lint 通过，保留既有图片性能警告。
- 实际浏览器已验证旧会话恢复、非空安全回答、来源/页码/状态展示及刷新恢复。只读，无新网页问答提交；模型请求 0、输入/输出 0。
- 数据库事实/审核状态、原始文档、原生会话 Run、指定历史证据和模型账本的前后校验全部一致。预算、模型服务、原生调度、上游源码保持原样。
- 前端构建身份：`bfbfd31e01cb87d6c0b9715afe26396cf77e87495821c7ffbbfa6bd68691cb1f`（100 源文件）。实际运行 http://127.0.0.1:3101 。

完整证据、修改文件、已执行命令及限制：[离线回退验收](app/data/product/evidence/safe-answer-fallback-20261018/REPAIR_ACCEPTANCE_REPORT.md)。
启动仍使用 `app/scripts/product-start.ps1` 和 WSL `app/scripts/product-ui-start.sh`；停止使用对应 stop 脚本。
**下一次真实模型问答需单独授权。本轮停止，不用离线结果冒充真实模型通过。**

---

# 历史记录：受控问答修复与验收（2026-10-18）

**产品总状态仍为 PARTIAL，不能宣布全部业务闭环完成。真实采集、机构披露变化、事件、原生调度及报告已有运行证据；本轮唯一的真实 Native Agent 问答失败。失败后没有重试。**

完整本轮证据：[AI_QA_ACCEPTANCE_REPORT](app/data/product/evidence/provider-receipts-20261018/AI_QA_ACCEPTANCE_REPORT.md)。本节为最新结果，下方保留上一轮记录，未覆盖历史失败证据。

## 本轮实际修复

- 问答模型新增Run独立持久化账本：保存格式化请求体（无密钥/headers）、全上下文估算、原始provider用量、解析后用量及明确超限原因。缺失用量为null，超限后禁止后续请求。
- 精简最终回答提示，完整指标与证据仍由原工具面板显示。未改变模型、端点、总预算、单次1800输出上限或事实审核门禁。
- 页面区分provider实际超限、缺回执和本地预算拒绝；历史会话恢复保留Run ERROR，避免刷新后把失败草稿显示为完成回答。
- 实测暴露本轮新增持久化缺陷：逐Token原子替换遇Windows共享冲突会中断流。已用真实Windows文件句柄复现并离线修复：减少逐Token写盘，仅本地替换最多5次尝试，总等待不超过300ms；持续失败返回AUDIT_STORAGE_ERROR并停止后续请求。**修复后没有再次真实调用模型。**

## 唯一真实问答 — FAIL

- 问题：最近一个季度伦敦写字楼市场有哪些变化、风险和机会？
- 提交：`provider-receipts-20261018-1792293506531`。
- Run：`bc3d6a09-34db-47b5-9771-2a4cb5f449d1`；Session：`05a18e1b-3c5c-4117-99b7-9a19fcb84942`。
- 配置及回包模型：`claude-sonnet-4-6`；端点：`https://api.jingziai.club/v1`。
- 1次网页提交、2次模型请求、1次search_market_evidence；8条候选事实、1普通事件、1机构披露变化，无重复检索。
- 请求1：实际输入37、输出60。请求2：实际Token未知。输入预估分别6415、14111，不能写成实际用量。费用N/A。
- 浏览器请求耗时19.701734秒；原生Run19.597153秒。用户可见正文精确TTFT=N/A；原生4.178578秒对应首轮模型响应，不能当最终分析首Token。
- 第二次流式输出期间账本替换报WinError5；Run ERROR，没有RunCompleted或完整回答。具体占用者未独立确认；同类Windows共享冲突已复现。
- 保留最多3请求、累计输入60000/输出8000、max_tokens1800、SDK/Agent重试0；由于缺第二次回执，累计实际用量是否合规无法核实。失败后0额外Native POST。

## 最新测试与业务门槛

| 项目 | 状态 | 证据与限制 |
|---|---|---|
| 后端全回归 | PASS离线/本地 | **176 passed in 31.48s**；含SDK MockTransport及真实Windows文件锁；不等于真实模型通过 |
| 问答当时的前端集成构建 | PASS，有既有警告 | 20测试、类型、生产构建通过；当时99文件身份匹配；manifest `ea7e30c08592236a2f77625f84af8d60e59be913464ae112d44962156e00af03`；后续UX源码已变化，见下方说明 |
| 完整AI回答 | FAIL | 一次真实提交失败；修复后未再次调用模型 |
| 事实/原件保护 | PASS | 33个存储事实记录整体哈希不变、原件哈希不变、0批准 |
| 重启恢复 | PASS已查路径 | 32条有效事实、7事件、13报告可读；本次失败Run恢复仍ERROR；不是仅凭HTTP200认定完整验收 |
| 真实市场变化 | 复用已运行案例 | JLL 2026Q2成交260万sq.ft.、环比15%；publisher_reported_change、pending_review；原Run `2a9592cf-3286-4c96-818d-204615b1c1e0`；非系统计算 |
| 正式两期数值比较 | BLOCKED | 方法、单位及人工审核门禁保留，未擅自批准 |
| 采集/事件/定时日报/网页周报 | 已有实际证据 | 下文market-closure-20261018记录保留；本轮没有重复调查或重新触发全量业务 |
| 新鲜Extract调用 | 本轮未执行 | 历史真实Run及缓存/离线回放不能冒充本轮新抽取 |
| 外部通知/公网部署 | 未执行/配置缺失 | 未外发、购买或部署 |
| 全覆盖/长期无人值守 | PARTIAL | 部分来源受限，人审和正式历史序列未通过，无长期SLA证据 |

本轮文件：`app/london_product/intelligence.py`、`app/tests/test_usage_receipts.py`、`app/openspec/changes/provider-usage-receipts/proposal.md`；前端 `chat-errors.ts`、`ux-errors.test.mjs`、`useSessionLoader.tsx`、`types/os.ts`、`MessageItem.tsx`。并行UX会话在同目录的其他改动已保留，不能全部归为本轮实现。构建锁及源码身份校验曾拒绝冲突发布，最后复用核验一致的集成构建。用户授权后已发送协调消息。依赖、密钥、官方源码与Radar未修改；根目录无Git，Commit=N/A，交付身份另存文件哈希。

## 运行入口

**http://127.0.0.1:3101**，AgentOS **http://127.0.0.1:7780**。双击 `app/Start-London-Market.cmd` / `app/Stop-London-Market.cmd`。后端已启动到最终离线修复版。本轮问答使用上述已核验前端构建；证据保存后已向并行UX会话释放前端。该会话报告继续修复会话日期、上下文身份和深色文字，其最新源码领先于本次问答构建，最终发布以该会话后续构建证据为准，不将旧manifest冒充当前源码一致性。本轮实际执行：

```powershell
# D:\deepinsight-lite
& .\app\scripts\product-stop.ps1
& .\app\scripts\product-start.ps1
# 在 app/ 工作目录执行
.\.venv\Scripts\python.exe -m pytest -q
# 前端使用现有独立WSL依赖，不重新安装
wsl.exe bash /mnt/d/deepinsight-lite/app/scripts/product-ui-stop.sh
wsl.exe bash /mnt/d/deepinsight-lite/app/frontend/build-product.sh --build
Start-Process wsl.exe -ArgumentList @('bash','/mnt/d/deepinsight-lite/app/scripts/product-ui-start.sh') -WindowStyle Hidden
```

本轮停止，不追加真实模型测试。后端修复与本地回归通过，真实AI业务验收仍失败，二者严格分开。

---

# 历史：上一轮市场监测闭环交付（2026-10-18）

**当前总状态：PARTIAL。真实采集、机构披露变化、来源证据、原生定时日报及周报路径已实际运行；本轮唯一一次 Native Agent 问答以用量门禁错误结束，因此不能宣布全部核心业务验收完成。已停止真实模型测试，没有第二次提交。**

本节为最新结果；下方历史报告保留，不把历史成功、Mock 回放或旧测试计数冒充本轮结果。项目仍为 `D:\deepinsight-lite`，Agno 2.9.0，既有前端布局及依赖保持。官方两个源码仓库 tracked diff 均为空；A 路线未操作。

## 本轮代码与产品变化

- 在现有监测 Workflow 中增加独立 `publisher_reported_change`：只识别 JLL Central London PDF 明确的季度 take-up 变化句，校验原始文件哈希及实际 PDF 页面的精确引用。保留人工待审，禁止反推前期数值或冒充系统计算。
- 机构披露变化进入事件列表、紧凑 Evidence Pack、聊天证据展开面板及日报/周报；页面保留原设计，仅增加分类、原文、页码、哈希、时期和审核状态展示。
- 继续使用已有校准估算器、全请求上下文计数、Run 内检索去重和第三次请求强制回答保护；没有提高预算。补齐 availability、prelet、inflation_rate 的主题映射，排除人工拒绝事件。
- Extract 不再把错误顶层 schema 或全部引用无效的结果缓存为成功；保存安全错误码、失败阶段和拒绝原因。已有成功缓存身份不变。
- Scheduler 全部来源失败返回503，部分成功返回207；显式幂等 key 防重放，失败任务重试保留 news/market 原范围。报告成功与通知失败分开表达，通知失败不再被整体 succeeded 掩盖。
- 报告指标表增加定义、原文和定位，防止 `prelet_share` 简写掩盖“预租或洽谈中”的合并口径。拒绝事件不会绕过专门分类区重新进入普通事件区。旧报告和原始响应保留。

## 真实市场变化案例 — PASS（机构披露路径）

JLL `jll 2026q2`，Central London，2026Q2，报告第1页原文：

> Take-up reached 2.6 million sq.ft. in Q2 2026 — up 15% quarter-on-quarter

这是**机构披露的260万平方英尺及环比增长15%**，不是系统从两个已批准季度事实算出的增长率。比较时期标签为2026Q1；前期数值未推算；发布时间未披露仍为空。

- 分类：`publisher_reported_change`；审核：`pending_review`；`calculation_performed=false`。
- 事件 ID：`2a62cfa3-b500-43fa-9e7d-d7b6fd55a0ff`。
- 文档 ID：`doc-jll-e2eaadc6049e717d5ebc`。
- 原件：`app/data/product/originals/doc-jll-e2eaadc6049e717d5ebc.pdf`。
- SHA-256：`e2eaadc6049e717d5ebc1375630fae9424b6ba9f463e2040fea00343316a6cc9`。
- 定位：`pdf:page:1:chars:94-167`。
- URL：https://www.jll.com/content/dam/jllcom/en/uk/documents/reports/research-reports/26-insights-central-london-office-q2-2026.pdf
- 实际监测 Workflow Run：`2a9592cf-3286-4c96-818d-204615b1c1e0`。

BNP Q1/Q2 take-up 的正式比较仍返回 `not_comparable`：UNKNOWN_METHOD、NOT_VALIDATED、HUMAN_REVIEW_PENDING；没有发布系统涨幅。真实 HTTP 比较耗时约71.4ms。证据：`market-change-case.json`、`strict-comparison.json`、`browser-change.png`。

## 实际运行与验收

全部本轮证据：`app/data/product/evidence/market-closure-20261018/`。

| 项目 | 状态 | 实际结果及证据 |
|---|---|---|
| 前后端运行 | PASS | 3101前端生产构建；7780 AgentOS；本轮重启后数据/报告仍可读 |
| 自动化回归 | PASS | 修改前145项；最终 **166 passed in 38.03s**；`baseline-tests.txt`、`regression-tests-final.txt` |
| 前端构建/类型/Lint/测试 | PASS，有警告 | **9/9**；生产构建成功；既有img性能与Node模块类型警告保留；`frontend-build.txt` |
| 真实采集与保存 | PASS，本轮限定来源 | GPE来源及两篇文章成功保存，0来源失败；原生Workflow真实执行；`monitor/gpe-real-refresh.json`及monitor说明 |
| HTML/PDF/CSV/JSON解析 | PASS工程回归；非本轮全来源实测 | 166项回归含现有解析、宏观接口、异常/持久化测试；没有重复调查或声称每个来源本轮都成功 |
| Extract修复 | PASS离线及真实缓存；新模型抽取未执行 | 真实BNP原文+既有响应Mock回放8条事实；成功缓存两次0模型0写入；历史真实Run `2c7b503a-120a-4959-9053-d547be3df898`；见extract子目录 |
| 真实变化案例 | PASS机构披露路径 | JLL明确季度变化，实际PDF精确匹配、哈希及Run关联；非正式数值比较 |
| 定时日报 | PASS本轮单次 | 原生poller实际触发；ScheduleRun `7833a514-2131-4905-b44f-57a4c8905318`；日报Workflow `e4e51bd4-9184-44a5-b634-cf05d2c349a7` |
| 日报/周报/导出 | PASS | 日报`0711cb24-b77c-489f-b7e7-f1784dd724bb`；API周报`36b65b3c-8bc2-4dcd-8e66-cc84f12a4057`；网页点击生成周报`2772fbc3-7dbd-471a-a094-198572a6f9dd`；HTML/Markdown实际读取 |
| 幂等与保护 | PASS | 重复日报同report/run；事件身份去重；33个原事实版本未变、32个检查时已有原件哈希未变、0新增批准；`final-integrity.json` |
| 浏览器业务路径 | PASS已检查路径 | 机构变化筛选/证据、BNP比较拒绝、周报生成阅读、Monitoring/Job Status；截图及DOM已保存 |
| 本轮真实AI最终回答 | **FAIL** | 1网页提交、2模型请求、1检索；Run以PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED结束；无RunCompleted、无重试 |
| AI原始草稿语义 | REVIEW_REQUIRED | 引用匹配工具证据，机构变化和假设有区分，80%保持预租或洽谈合并；不等于完整语义通过或成功回答 |
| 外部通知 | configuration_missing | 实际尝试返回缺配置、attempts0；既有本地回环传输测试通过不等于外部送达；本轮无外发 |
| 持续运行可靠性 | PARTIAL | 实际单次原生调度通过，不宣称长期无人值守SLA；部分来源不可达/受限仍显示真实状态 |

原生通用HTTP调度的ScheduleRun不含业务Workflow Run ID；本轮通过业务Job和原生Workflow Session关联，未补造字段。207表示HTTP层成功但业务partial，不能解读为所有来源/通知成功。4个产品计划保留，未重复注册。

## 唯一一次真实问答 — FAIL，已停止

问题：最近一个季度伦敦写字楼市场有哪些变化、风险和机会？

- 端点：`https://api.jingziai.club/v1`；实际配置标识：`claude-sonnet-4-6`。
- 提交：`market-closure-20261018-1792291906184`；Native Run：`a76d97d4-3e35-4977-ae7f-70d02a9a5f89`。
- 真实检索：8条候选指标、1条普通事件、1条机构披露变化；没有重复检索。
- 原生耗时37.228秒；浏览器请求完成37.338秒；provider首响应约7.413秒（不是分析正文首token）。
- 请求1原生用量记录：输入37、输出103；**请求2及累计精确Token未知**。第二次实际用量检查抛错早于原生完成事件/用量持久化；不能把请求1的140 Token写成整次用量，也不能据此确认累计限额通过。
- 失败原因：`PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED`。与此前输入预估过大不同，这是provider用量检查拒绝；缺少第二次回执无法精确判断是单次输出还是累计门槛及超限幅度。
- 原保护：3请求/60000输入/8000输出/max_tokens1800；零自动重试和fallback。费用N/A，不代表免费。
- 原始流已保存，包含未完成验收的草稿；页面显示失败。没有第二次真实提交，没有将草稿包装成完成答案。

详细见本轮 `AI_QA_ACCEPTANCE_REPORT.md`、`model-call-ledger.json`、`native-stream.txt`、`native-run.json`、`raw-streamed-draft.md`、`browser-failure.png`。下一次必要修复应先让provider用量及门禁决策在抛异常前持久化，再核对中转的max_tokens/usage语义；本轮未继续付费测试，未提高预算。

## 覆盖与仍未通过的门槛

已保存数据支持租金、空置率、take-up、供应/预租合并比例、部分City/West End/Canary Wharf/Midtown及英国利率/通胀/就业查询。事件来自已有业主与政府资料。**登记13条来源不等于13家机构全面接入**；CBRE、Savills当前下载失败，Planning Datahub403、BBC RSS超时，Knight Frank许可受限停用。ESG、hybrid working、Fringe独立覆盖及全市场连续历史仍未形成完整、已审核事实序列。

正式金标准/人审仍待完成；原G0及B1 AC原结果不被本轮改写。没有因新机构披露路径批准旧数据、改原件、修改金标准。公网部署未执行。外部通知配置缺失作为明确边界，不冒充已发。新鲜Extract模型调用本轮未执行，不能用离线回放替代。

## 本轮文件与可复现运行

业务改动：`app/london_product/publisher_changes.py`（新增）、`service.py`、`qa_context.py`、`intelligence.py`、`runtime.py`。新增测试：`test_publisher_changes.py`、`test_extract_closure.py`、`test_monitor_closure.py`；新增验证脚本：`verify-market-closure.py`、`verify-extract-cache.py`、`verify-monitor-closure.py`。

前端仅证据显示增量：`chat-evidence.ts`、`ToolEvidence.tsx`、`MessageItem.tsx`、`market-api.ts`、`MarketApp.tsx`、`chat-evidence.test.mjs`。OpenSpec：`app/openspec/changes/market-monitor-closure/proposal.md`。依赖未新增或升级。根目录无Git仓库，Commit=N/A。

用户入口：**http://127.0.0.1:3101**。双击 `app/Start-London-Market.cmd` 启动，`app/Stop-London-Market.cmd` 停止。以下命令本轮实际执行过：

```powershell
# D:\deepinsight-lite
& .\app\scripts\product-stop.ps1
& .\app\scripts\product-start.ps1
wsl.exe bash /mnt/d/deepinsight-lite/app/scripts/product-ui-stop.sh
wsl.exe bash /mnt/d/deepinsight-lite/app/frontend/build-product.sh --build
Start-Process wsl.exe -ArgumentList @('bash','/mnt/d/deepinsight-lite/app/scripts/product-ui-start.sh') -WindowStyle Hidden

# D:\deepinsight-lite\app，独立环境
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -X utf8 scripts/verify-market-closure.py
.\.venv\Scripts\python.exe -X utf8 scripts/verify-extract-cache.py
# 下项会真实抓取GPE并临时触发一次现有日报计划，不是只读测试
.\.venv\Scripts\python.exe -X utf8 scripts/verify-monitor-closure.py
```

缓存市场查询20次本地顺序HTTP样本P95约125.3ms；不视为生产SLA。前端构建源身份：`31ab030739bd694a0615f84d4e2020973399816ab358c16ec97962c26a92ff88`。本轮不做PPT，不开展新来源普查，保留产品运行供检查，停止开发与真实模型验收。

---

# 历史：DeepInsight Lite — 最后一轮针对性修复交付

交付日期：2026-10-18。工作区：`D:\deepinsight-lite`。

**本轮必要修复已实现，并通过 127 项回归及真实浏览器验证。产品总体业务验收仍为 PARTIAL：事实人工审核、G0 来源口径、正式正向历史比较和 AI 语义审核没有因此自动通过。** 本轮停止于下列修复，不重写架构，不新增数据源调查，不制作 PPT。

## 本轮实际修复

| 问题 | 根因与修复 | 实际验证 | 状态 |
|---|---|---|---|
| 预租与洽谈中面积混淆 | GPE 原文先说明一层 pre-let、另一层 under offer，再给出 transactions 合计超过 4,300 sqft；短摘要丢失前句。查询工具和新报告现在带连续原文上下文。涉及预租/洽谈数量的模型草稿进入发布门禁，不把合计面积重标为已签约预租面积。 | 两份真实已保存回答回放、英文/中文变体、原文连续摘录、真实报告界面 | PASS：已知错误发布防护；语义审核仍待审 |
| 跨机构供应趋势推断 | 旧回答把 BNP Q1 22.8m 与 JLL Q2 21.6m 连成“供应收缩”。现在拦截带供应趋势判断的模型草稿，不依靠提示词或引用存在就认定正确。正式数值比较继续由原来的严格 Python 工具处理。 | v2 真输出回放、跨机构与中文负例；真实 BNP 比较拒绝 | PASS：已知错误发布防护 |
| 来源数量错误 | 旧模型称“5 unique URLs”，括号列举又不一致。模型自行报来源数量的草稿被拦截；来源登记数、已有文档的来源条目数、快照数、去重 URL 数、事实/事件贡献来源条目数由 Python 分别统计。 | 实际数据库与构造去重边界测试 | PASS |
| 缓存/历史报告绕过修复 | 新分析、成功缓存读取、传入分析生成报告、旧报告 HTML/Markdown 读取均经过门禁。历史报告以读取视图呈现安全结果，原报告数据库行和原始模型输出不被覆盖。通知正文也使用同一报告视图。 | 缓存零模型测试、旧报告双格式 HTTP 和浏览器验证、原记录逐行比对 | PASS |
| 流式先展示错误、最后才审核 | 业务 Ask 接口先接收原始模型输出，完成基础及发布检查后再发送内容；未完成的运行不会泄漏部分错误文本。 | 成功/未完成两类合成流传输测试；原始回答独立保存；provider TTFT 与用户可见 TTFT 分开记录 | PASS：传输回归；本轮未发新模型请求 |

门禁是保守的有限规则，可能把已经正确限定的预租数量或供应描述一起拦下。命中时整份 AI 草稿 withheld，避免仅删除一句后遗留相同假设的风险/机会结论。没有声称这是通用语义事实核查；未命中仍为 `REVIEW_REQUIRED`，不会升级为 PASS。原生 `/chat` 会话和 AgentOS 原始 Run 保留为未批准模型输出，本轮业务发布门禁覆盖 Reports 与 `/api/market/ask`，不宣称重写了原生流式端点。

## 真实历史比较演示

复用本地 BNP Q1/Q2 2026 PDF；没有新增抓取或采购。两期原文均在第 3 页，六条核心事实全部重新执行了本地 PDF 原文匹配及哈希检查。

| 字段 | 2026 Q1 | 2026 Q2 |
|---|---|---|
| 事实 ID | BNP-2026Q1-TAKEUP | BNP-2026Q2-TAKEUP |
| 机构/系列 | BNP Paribas Real Estate / UK Central London Office Market Update | 同系列 |
| 地域 | Central London (BNP source-defined office market) | 相同源定义地域 |
| 指标 | 单季度 take-up；deals over 1,000 sq ft | 单季度 take-up；非 H1 累计 |
| 原始披露值 | 2.5m sq ft in Q1 2026 | 3.0m sq ft in Q2 2026 |
| 规范化输入 | 2,500,000 sqft | 3,000,000 sqft |
| 披露增量 | 100,000 sqft；不是精确未舍入值 | 100,000 sqft；不是精确未舍入值 |
| 方法/人工审核 | unknown / pending_review | unknown / pending_review |

**实际 API 和网页返回：`not_comparable`。** 原因：`UNKNOWN_METHOD`、`NOT_VALIDATED`、`HUMAN_REVIEW_PENDING`。`absolute_change`、`relative_change_pct`、`change_unit` 均为空。没有展示涨幅、没有把标签一致当成统计方法资格通过。Q2 原文叙述百分比的既有争议也保留在原标注中。

当前 32 条有效候选事实的人工批准数为 0，因此没有通过全部现行资格门禁的真实正向比较对。本轮按用户允许的“不合格则明确不可比”路径完成演示；“展示已批准的真实增长结果”仍 BLOCKED。

原件：

- [BNP Q1 PDF](b1/g0-review/2026-10-17/raw/bnp-q1-2026.pdf)，SHA-256 `8255a921c15294718433e5a893e6616593ab730904de4be452ba74d0c27bde7c`。
- [BNP Q2 PDF](b1/g0-review/2026-10-17/raw/bnp-q2-2026.pdf)，SHA-256 `3dd8de05ccb26ce235dfc8f9cf96d47bb2f760196d56cfcc94b0dc2a2a2016cd`。
- [实际比较回执](app/data/product/evidence/final-repair-20261018/real-comparison.json)、[六条事实原文核验](app/data/product/evidence/final-repair-20261018/six-core-facts-local-verification.json)。

## 实际测试与证据

证据目录：`app/data/product/evidence/final-repair-20261018/`。

| 验证 | 真实结果 | 证据 |
|---|---|---|
| 先失败再修复 | 第一组 12 项回归修复前全部失败，包含旧报告仍发布错误文本的断言；修复后通过 | `pytest-red.txt` |
| 完整自动化回归 | **127 passed in 21.13s，0 失败**；本轮新增 15 项，当前工作区另有 112 项既有测试。本轮未修改/删除既有测试文件；先前 106 项通过记录原样保留 | `pytest-green.txt`、`pytest.xml`；历史 `../python-tests-final.txt` |
| 真模型错误回放 | v1/v2 原始回答进入新门禁均 withheld；原文及 SHA 保留 | `real-output-replay.json`、`v1-safe-publication.md`、`v2-safe-publication.md` |
| 真实 HTTP 报告读取 | 两份旧 AI 报告 × HTML/Markdown，均成功读取且不再发布已知错误段落 | `real-report-http.json`、对应 ID 的导出文件 |
| 真实浏览器 | Reports 旧分析门禁、Changes & Events 两期选择/拒绝、Saved Ask 两期值及引用、新周报生成/阅读、重启刷新后新报告仍可读 | `browser-*-dom.txt`、`browser-report.png`、`browser-comparison.png`、`browser-saved-ask.png` |
| 原生 Workflow | 网页生成新无模型周报成功；Run `3d6d1c14-3ddb-45eb-8ef6-b5531cbb56f1` | `browser-generated-report.json`、`repair-runtime-jobs.json` |
| 重启持久化 | 后端停止并重启；新周报仍存在，原事实及待审核状态一致，原始文件哈希一致 | `verification-after-restart.txt`、`browser-after-restart-dom.txt` |
| 保护边界 | 修复前 33 个事实版本、29 文档、14 事件版本、2 抽取记录、8 报告原记录全部不变；29 文档文件哈希一致；304 个受保护文件一致 | `before-records.json`、`integrity.json` |
| 运行环境 | Python 3.12.10 / Agno 2.9.0；官方 UI HEAD `6dad9593fca6756e1813e4f4b3b2620be6377691`；两个 upstream 仓库 tracked diff 为空 | `delivery-receipt.json` |

网页新周报 ID：`d2fbb243-5b20-4ec3-b485-13af0a6d9763`；32 条事实、6 个有效事件。导出为 `browser-generated-report.md` / `.html`。原生 Workflow 没有模型调用。浏览器 saved 查询后端耗时约 15.7ms；这是单次已保存查询测量，不是 P95 或 AI 首 token 延迟。

浏览器初次导航遇到已有 UI 服务连接拒绝。使用现有 `product-launch.ps1 -NoBrowser` 恢复服务，随后在新标签完成上述真实验证；没有改前端源码、构建产物或网络安全设置。新标签验证时控制台 error 列表为空。

**本轮新模型请求 0 次、新模型 Token 0、新模型费用 0；没有新抓取、搜索 API 或外部通知。** 回放与合成 SSE 测试不冒充新模型能力实测。原先真实模型回答仍可从已存 Run 和原始证据检查，不能因新发布门禁生效就称模型已不再犯错。

## 仍未通过的业务门槛

| 门槛 | 当前状态 | 本轮处理 |
|---|---|---|
| 六条核心事实正式金标准 | BLOCKED / pending_review | 原文与哈希可复核，用户人工签收未发生 |
| BNP 租金年度分母与空置率方法资格 | BLOCKED | 未推定年租单位、未补未知方法、未换源 |
| 正式真实正向历史比较 | BLOCKED | 实际演示拒绝，不生成变化数字 |
| AI 语义审核 | PARTIAL / REVIEW_REQUIRED | 已知错误不会在业务发布路径继续直接展示；有限规则不保证所有语言/新错误都被发现；原生聊天输出仍属未批准草稿 |
| 原 B1 全部 AC / 原始留出评测 | 未改变历史状态 | 旧记录仍 24 PASS / 5 BLOCKED / 1 FAIL；AC-26 原始评测 FAIL；本轮没有重跑或改写原 30 项验收 |
| 数据覆盖 | PARTIAL | 13 登记条目、9 条目有保存文档、29 快照、18 去重 URL、9 条目贡献有效事实/事件；这些不是 13 家已全面接入的独立机构 |
| 外部通知 | 未配置，非本轮阻塞项 | 未发送；历史回环传输验证不等同外部邮件/消息成功 |
| 公网部署 | 未执行，非本轮阻塞项 | 继续本地 Windows + WSL；不声称公网生产验收 |

继续使用 [人工复核清单](app/docs/product/B1_HUMAN_REVIEW_CHECKLIST.md)；[历史 AC 承接表](app/docs/product/LEGACY_AC_STATUS.md) 只解释旧记录，未重写。

## 修改文件与运行方式

业务修改仅涉及 `app/london_product/analysis_guard.py`（新增）、`service.py`、`intelligence.py`、`runtime.py`。新增 `app/tests/test_analysis_publication.py`、`app/scripts/verify-final-repair.py`；更新既有 OpenSpec 任务、`app/README.md` 和本报告。未新增依赖、未改数据库 schema、未改前端或框架版本。根目录无 Git 元数据，Commit 为 N/A；以 `changed-file-hashes.json` 提供本轮文件身份。

用户入口：**[London Office Market](http://127.0.0.1:3101)**。后端：`http://127.0.0.1:7780`。交付时两者已启动。

双击 [Start-London-Market.cmd](app/Start-London-Market.cmd) 启动、[Stop-London-Market.cmd](app/Stop-London-Market.cmd) 停止。维护命令均从 `D:\deepinsight-lite` 执行：

```powershell
# 本轮实际执行并验证的启动命令
& .\app\scripts\product-launch.ps1 -NoBrowser

# 后端停止与重启：本轮实际执行两次
& .\app\scripts\product-stop.ps1
& .\app\scripts\product-start.ps1

# 本轮实际执行的完整测试与运行验证
Set-Location D:\deepinsight-lite\app
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe scripts/verify-final-repair.py
```

完整停止可双击 Stop CMD，或先执行后端 stop，再执行已有 `wsl.exe bash /mnt/d/deepinsight-lite/app/scripts/product-ui-stop.sh`。本轮保留 UI 运行供用户检查，没有为重复测试而停止它。前端没有修改，未重新构建；本轮验证的是已有生产 UI 与修复后端的真实交互。

本轮针对性修复交付结束。保留上述业务门槛与限制，不自动进入下一轮开发或新数据源调查。

## 2026-10-18 补充：问答检索上下文与预算错误提示

按用户后续限定授权，仅修改 `app/london_product/intelligence.py` 的首次强制检索/后续自动回答、Run 内检索去重及完整返回体 10,000 字节限制；在 `runtime.py` 保留允许列出的预算错误码与可理解的页面错误消息。没有增加模型预算、修改事实发布门禁或批准事实。新增五项 Python 回归与一项前端流测试，完整结果为 **132 Python 测试通过、4 前端流测试通过、TypeScript 检查通过**。

唯一一次修复后网页 Native Agent 问答使用 `claude-sonnet-4-6`（`https://api.jingziai.club/v1`），共 **2 次模型请求、1 次证据检索、输入 6,101 / 输出 1,718 Token、26.085 秒**，费用 **N/A**。工具返回 9,789 字节，未再次触发预算错误；但原始草稿触发 `UNVERIFIED_MARKET_TREND`，页面显示 **AI draft withheld — REVIEW_REQUIRED**。生成草稿不等于获得可发布答案，事实语义验收仍未通过，已停止且未重试。

原始草稿仍有未经批准的租金趋势判断、规划通过状态表述过度等问题，详见 [限定修复验收报告](app/data/product/evidence/qa-context-repair-20261018/REPAIR_ACCEPTANCE_REPORT.md)。报告附真实运行、工具返回、原始草稿、页面截图、用量和全部回归证据。原 facts/documents/events 及事实门禁代码哈希不变，原 G0/B1 门槛不变。网页仍为 http://127.0.0.1:3101/ask ，本轮实际执行后端 stop/start 加载修复，未改变启动方式。
