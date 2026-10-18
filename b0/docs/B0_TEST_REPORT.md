# B0 测试与验收报告

测试日期：2026-10-17；精确版本见 B0_VERSION_COMPATIBILITY。所有模型输出来自真实已授权 API。没有 Mock 模型、固定回答、生成图片或替代 Runtime。以下 PASS 仅覆盖表中明确验证的行为。

| 测试项 | 状态 | 核心证据（相对 b0/evidence） | 说明 |
|---|---|---|---|
| 官方源码下载与身份 | PASS | `versions/repositories.json`、`package-source-checks.json` | 3 个官方仓库；Agno 标签浅克隆成功；tracked diff 为空 |
| 原版 AgentOS 最小示例启动 | PASS | `api-results/quickstart-api.json`、`logs/quickstart-startup.log` | 独立运行副本仅环境调整；原生 AgentOS 实例 |
| 原版 UI 启动 | PASS | `logs/ui-install.log`、`ui-start-turbo.log`、截图 01 | 原锁文件安装；Next.js 15.5.18；HTTP 200 |
| 前后端连接 | PASS | `cors-before.json`、`cors-after.json`、截图 01 | 默认 CORS 失败先记录；b0 环境配置后发现成功 |
| 真实模型调用 / T01 Agent | PASS | `model-probe.json`、`T01-introduction.json`、`T01-arithmetic.json`、截图 02 | 两指定问题真实返回；模型、响应、Run/Session ID 有凭据 |
| UI 流式交互 | PASS | `ui-tool-stream-new-session.json`、`logs/ui-network-events-new-session.json`、截图 03/05 | HTTP 200 text/event-stream；16 个真实事件；前端显示结果 |
| T02 Tool Calling | PASS（保留一次异常） | `T02-tools.json`、`logs/tool-invocations.jsonl`、截图 05 | 参数 17/25；Python 执行；原生结果 42；完成回答 42。一次多轮 UI 请求的偏题回答保留在另一个 stream 文件 |
| T03 Session 上下文 | PASS | `T03-context.json`、`T03-recall.json`、`T03-session-id.json` | 同 Session 回忆中性标记 |
| T03 刷新/重启持久化 | PASS | 截图 06/07/08、`T08-history-before/after.json`、`T08-restart-checks.json` | UI 展示、API runs 与 SQLite 恢复相符；不是仅缓存空会话 |
| T04 原生 Workflow | PASS（Backend）；Frontend NOT SUPPORTED | `T04-workflow.json`、截图 14 | Draft/Review 顺序完成；上一完整输出进入下一步 user message；Run ID 可追踪 |
| T05 原生 Team | PASS | `T05-team.json`、`ui-team-stream.json`、截图 09/10 | 两名成员真实运行；成员 Run ID 与 Team Run 关联；UI 可执行 |
| T06 Native Skills | PASS（Backend） | `T06-skills.json` | 官方 SKILL.md 经 LocalSkills 注册，真实 get_skill_instructions 调用及指令文本；不把普通函数称 Skill |
| T07 Scheduler 自然触发 | PASS | `T07-scheduler.json`、截图 12、相关日志 | Cron 每分钟；自然 claim；success；Schedule Run/Agent Run；已停用 |
| Scheduler 控制/失败状态 | PASS（预期负面测试） | `T07-scheduler-failure.json` | enable/disable/trigger 成功；不存在 Agent 导致 404/failed，真实失败历史可查；已停用 |
| T08 Run/Tool/Scheduler History | PASS | `T08-history-before/after.json`、后端语义凭据 | Agent、Team、Workflow 和调度历史可查；重启一致；工具调用在 run 和 SSE 可查 |
| Tracing 本地存储/读取 | PASS（限定范围） | T08 trace list/detail | 本地 tracing DB 写入、列表、detail、重启保留；无专用 UI，也未审计全部 span 语义 |
| Memory / Knowledge / Evaluations | SUPPORTED BUT NOT TESTED | 源码、OpenAPI、FUNCTION_CATALOG | 不计入本轮 PASS；未运行长期记忆、内容摄入、检索或评估 |
| UI 组件与产品差距审计 | PASS（审计交付） | `B0_UI_AUDIT.md`、`B0_GAP_ANALYSIS.md` | 由源码路径+浏览器证据支持；不代表业务功能实现 |
| UI lint/typecheck/format | PASS | `logs/ui-lint.log`、`ui-typecheck.log`、`ui-format.log`、`ui-check-exits.tsv` | 无源码更改、未禁用检查；next lint 弃用提示保留 |
| Python 校验 / OpenSpec | PASS | `logs/final-verification.log` | compileall；openspec strict；语义验证脚本，最终复核后填充凭据 |
| 生产 build | PASS（Turbopack）；默认 Webpack BLOCKED | `logs/ui-build-turbo.log`、`ui-build-webpack.log`、`ui-build-processes-before-stop.log` | 官方 `pnpm build --turbopack` 完整构建通过；默认 Webpack 编译停滞约7分钟后定向停止，没有宣称默认路径通过 |

## 代表性真实身份

| 行为 | ID |
|---|---|
| T01 introduction Run | `04d11dfc-ace0-4efb-9882-ec12abb36730` |
| T02 Tools Run | `bdf1196b-0b5b-41fe-bda1-ea72ccb94365` |
| T03 持久化 Session | `489ed5fa-1f60-40dc-9907-14af720ed95e` |
| T04 Workflow Run | `be0df5ce-421c-4f01-8c8c-75fad1685e25` |
| T05 Team Run | `df5bc7cc-b3f1-4d5c-b720-05170239d452` |
| T05 Explainer / Reviewer | `8067e709-46b6-4de6-ae4c-665748e0d375` / `42bbddad-5d1a-4864-a964-1b3a4592a327` |
| T06 Skills Run | `12459751-8f79-4685-ab98-bb817b3fb163` |
| T07 Schedule | `590bff91-bd55-43eb-a0e1-3af266d56a7b` |
| T07 自然 Schedule Run | `b629dd72-c08a-4570-9605-df51d1a91286` |
| T07 实际 Agent Run | `36f9fcd7-dde9-4958-995c-d3b52cd16a06` |

自然调度触发时间戳 `1792228743`、完成 `1792228774`，对应北京时间 2026-10-17 17:19:03 与 17:19:34。不得把 Schedule ID 当作 Agent Run ID。

## 失败、修复与证据边界

额外 harness 负面检验向不存在的 Agent 发出真实 HTTP 请求，得到404并由测试脚本返回exit1；没有模型请求。最终OpenSpec检查曾在错误工作目录找不到change，切换到`D:\deepinsight-lite\b0`后strict验证通过；原始尝试日志与最终校验日志分开保留。

完整 clone TLS 失败、pnpm 11 frozen-lockfile mismatch、缺少 greenlet、Webpack 首页编译停滞、默认 CORS 400，均经过定位并用非业务源码的环境/版本/启动配置解决，详见 ENVIRONMENT_REPORT。初始早于服务就绪的 health 请求失败后重检为 200。

截图 13 是 Workflow detail 查询漏传 session_id 的真实 422；补充选定版本要求的 query 后截图 14 为真实运行记录。负面证据保留，不把失败截图命名成成功证据。

中转模型一次偏题回复保存在 `ui-tool-stream.json` / 截图 04；新 Session 请求在 `ui-tool-stream-new-session.json` / 截图 05 中通过。它证明框架执行/解析路径可用，不能证明供应商所有多轮请求都可靠。

`verified-backend-checks.json` 是后端语义门禁；`browser-acceptance.json` 是浏览器证据索引。截图是真实浏览器捕获；架构图仅是审计可视化，二者不混用。未进行压力测试、生产部署、故障恢复 SLA、业务准确率或 London 数据验证。
