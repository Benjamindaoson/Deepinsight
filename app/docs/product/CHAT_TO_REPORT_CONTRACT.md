# Chat-to-Report：接口、状态与发布验收

本契约面向后端、前端和验收维护者。聊天是入口，持久化的 ReportArtifact 是交付物。`success` 只表示本次确定性证据覆盖满足请求，不能解释为市场判断、语义审核或投资建议通过。

## 交付形式

| 类型 | 触发示例 | 交付 |
|---|---|---|
| `fact_answer` | 最新 City prime rent | 简答、原值原单位、地区、统计期间、审核状态和原文证据 |
| `topic_analysis` | 分析 Canary Wharf vacancy / availability | 范围、指标、可比图表、事实发现、数据缺口和解释限制 |
| `market_report` | Q2 2026 London office market report | 执行摘要、指标、区域比较、图表、发现、风险机会、展望、限制、来源 |

地区和期间通过显式 `parent_report_id` 或原生会话状态继承。用户明确指定的新地区、指标或季度只覆盖对应条件。Q1 等季度简写使用父报告年份。`latest` 指最新已保存期间，不能声称这是最新公布或当前季度。

## 数据结构

后端定义：`london_product/report_contracts.py`，版本 `1.0`。`ReportArtifact.model_json_schema()` 可导出完整 JSON Schema。前端对应 `src/lib/report-artifact.ts`。

必备字段包括 `report_id / title / report_type / generated_at / query / scope / geographies / observation_period / executive_summary / market_snapshot / regional_comparison / calculations / charts / key_findings / risks / opportunities / outlook / data_gaps / limitations / sources / evidence / generation_status / publication_review / ai_analysis / acquisition`。

### Claim–Evidence publication contract

模型 Finding 的 `claims` 使用 `Claim` 类型。观察须绑定 metric、value/unit 对、geography、observation_period、definition、method、evidence_ids 和 locator；变化另外绑定 old_id/new_id、old_observation_period 和 direction，并匹配现有确定性计算。数值不能从另一指标、另一地区或另一单位的记录借用。

发布器使用完整句式编译：正文必须与绑定字段生成的支持句式一致，或整句通过兼容解析。正确前缀、单个正确数字、有来源 ID、JSON 合法均不足以授权剩余文字。未知主张返回 `CLAIM_SUPPORT_UNKNOWN`，不会被当作“语义验证通过”。目前支持来源观察、确定性变化、原文归属陈述及不夹带事实的研究动作；任意自由因果解释仍需后续独立语义核验能力。

`state_assertion` 是独立状态谓词，由系统按本报告地区、指标、期间和当前存储状态求值。来源可读取、已人工审核、满足报告元数据准入及独立语义审核是不同状态。年度分母失败不会更改原始人工审核字段；未审记录可支持准确的“记录仍待审核”说明，不能支持已确认市场数值。审批、覆盖、缺失与语义核验状态不能由模型自行宣布。

`ai_analysis.original_payload` 和 `validation_audit` 保留未发布原文、证据 ID、状态检查及拒绝原因，用于审计。聊天、HTML 和 Markdown 的可见结论只来自通过当前校验的 Finding，不渲染该审计原文。每次重开报告重新核验旧模型 Finding；证据指纹变化会撤回全部结论类别（包括 outlook）和图表，原始数据库记录仍保留用于审计。

数值记录包含 fact ID、原值原单位、归一值归一单位、原始定义、期间和审核状态。发现、计算和图表点均关联 evidence IDs。证据保存文档 ID、URL、公布与采集日期、统计期间、原文、实际页码/定位和原始文件 SHA-256。没有公布日期或页码时保留空值。

沿用现有 SQLite `reports` 表的 JSON payload，无数据库迁移。旧 daily/weekly 报告继续使用原有导出接口。生成时间和市场统计期间始终是独立字段。

## HTTP 接口

### `POST /api/market/ask`

```json
{
  "message": "Prepare Q2 2026 London office market report comparing City and West End",
  "mode": "saved",
  "parent_report_id": null,
  "refresh_sources": false
}
```

- `message`：1–4000 字符。
- `mode`：`saved / auto / agent`，默认 `saved`。saved 不调用模型；auto 沿用当前意图路由；agent 使用现有受限 Agno Agent。
- `parent_report_id`：可选，必须是已有结构化报告。不存在返回 422。
- `refresh_sources`：默认 false。true 时先提交现有 refresh Job，等待其终态，再读取保存的事实。不新增调度器，不绕过源启用、源政策或事实审核。采集成功不代表提取或人工批准完成。
- 返回 SSE。前端停止会取消当前连接，不自动重发模型请求。失败前已保存的确定性报告仍能在 Reports 重开。
- 该 ask 接口没有“重试即可重放收费 Run”的语义；不要把浏览器产生的 Idempotency-Key 当作原生收费调用去重保证。

### SSE 事件

| `type` | 字段 | 前端行为 |
|---|---|---|
| `progress` | `stage / message / submission_id? / job_id?` | 显示 evidence、acquisition、validation、analysis 或 publication_review 状态 |
| `report` | `report_id / report` | 直接渲染结构化报告；相同 ID 的后续事件替换较早视图 |
| `token` | `content` | 兼容已有文本消费者；有 report 时报告组件为主要交付 |
| `done` | `citations / run_id / submission_id / metrics / report_id` | 唯一成功执行终止回执，不代表事实或语义批准 |
| `error` | `code / message / stage? / submission_id? / run_id? / report_id?` | 显示明确失败；保留已收到的报告，不伪造 done，不自动重试 |

SSE 支持跨字节 UTF-8、CRLF 和末尾事件。没有 done 的连接终止是未确认完成。report 事件可早于模型完成，避免模型失败导致确定性证据丢失。

### `GET /api/market/reports`

保持 `{items: [...]}`。结构化记录增加 `report_type` 和 `generation_status`。读取时重新检查证据，列表不会继续把失效报告显示为成功。旧报告的 cadence period 和状态保留原含义。

### `GET /api/market/reports/{id}?format=json|markdown|html`

- `json` 返回重新验证后的 ReportArtifact；旧非结构化报告没有 JSON artifact，返回 422。
- `markdown / html` 从同一个投影导出。HTML 转义来源文本且执行现有 CSP。
- GET 不触发模型、采集、再生成或事实状态修改。
- 重新检查原始文件哈希、引用原文与页码、文档绑定、当前源政策、事实完整指纹及人工审核状态。变更后清空可发布发现/计算/图表，返回 `insufficient_evidence` 和 `EVIDENCE_CHANGED`。冻结引文仅供审计。

## 原生聊天契约

复用 `search_market_evidence`，其结果增加 `report_id / report_summary / analysis_contract?`。原生 tool result 本身进入现有 Agno 会话，因此恢复历史时同样能读取报告。报告指针只能来自成功的检索工具，不能从模型正文猜测。

工具返回仍受原有 10KB 上限约束；需要压缩时删除整个可选事件或事实，不截断原文和限定词。完整报告不受该工具摘要裁剪影响，仍保存在 reports 中。父范围储存在当前会话状态，独立会话不共享范围。

原生 post hook 校验模型解释结构并保存待审草稿。RunCompleted 的只读 publication 投影只发布确定性报告状态，不把原始模型 JSON 展示成已确认结论。最终内容或失败状态到达时，报告卡片重新读取；历史恢复也读取同一接口。

## 状态与失败处理

| 状态 | 条件 | 可展示内容 |
|---|---|---|
| `success` | 请求的确定性数据覆盖满足要求，所请求比较/历史通过门禁 | 可追溯事实与程序计算，仍无语义批准 |
| `partial` | 已有有效事实，但部分指标、比较、历史或模型解释未完成 | 已通过部分及明确缺口 |
| `insufficient_evidence` | 没有本期合格事实，或原始证据/审核状态失效 | 候选记录、审计引文、缺口，不能给确认趋势 |
| `failed` | 无法构建有效 artifact | Jobs 记录失败阶段；前端显示错误，不能标生成成功 |

`ai_analysis.status` 独立表示 `pending / review_required / withheld / schema_invalid / failed`。符合结构不代表解释获得证据支持；所有自由模型解释保留为未发布草稿，不能进入执行摘要、已确认发现、正式风险或机会。当前没有自动语义批准器，不把正则检查冒充语义验证。

模型异常、预算超限、取消、结构错误或证据不足都不触发隐式收费重试。保留已生成的确定性报告，并将 AI 阶段明确标为未完成、失败或拦截。原生失败 Run 的状态通过现有会话记录投影到报告读取结果。

## 图表发布门禁

- 趋势图：审核通过、原文哈希/数值有效、来源系列/地区/定义/单位/grade/method/basis 一致且季度连续；缺季度断线。计算复用 `london_data.comparison.compare` 和 Decimal。
- 区域图：同期间、来源系列、指标定义、单位与方法相容，至少两个不同地区；冲突重复不选值、不平均。来源自定义地区保留原名，仅作候选，不等同于请求地区。
- 供应图：必须有明确的来源分组、互斥标记及不同类别；规划、已完工、可租与预租面积不直接相加。
- 时间线：必须有实际 event_date/date、有效日历日期和原文证据。发布日期不冒充事件发生日期；重复日期/URL/原文去重。
- 每图有标题、单位、地区、期间、可展开数据和来源；没有足够数据就展示原因。加载/空/错误分别显示，不生成虚构系列。

## 发布验收门槛

工程门槛：后端全套测试通过，前端测试、typecheck、lint 和 build 实际执行；浏览器验证聊天生成、报告展开、证据展开、Reports 重开、继承范围、空数据及失败状态。

证据门槛：用真实数据验证缺口行为；合成 fixture 仅验证比较和图表算法，不作为真实市场覆盖证据。必须单独验收真实模型、外部采集和人工语义审核，不能由工程测试替代。

发布前复核：不泄露密钥、不新增依赖和并行框架、不删除旧 Reports、不修改原始事实审核状态、不把历史报告声称为实时报告。任何核心外部门槛未执行时，验收总状态只能是 PARTIAL。
