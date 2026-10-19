# Jev Query 分类器与节点判断

Jev 已接入实际业务路径。`/ask` 的 auto 请求会按分类选择现有本地数据或分析执行；`/chat` 使用的原生 AgentOS run 会先执行分类 Hook，再把意图和能力边界传给证据工具。Shadow 观察仍可独立使用。

## 一次 query 如何执行

1. 用户显式选择 saved/agent：尊重该选择，不为选路调用 Jev。
2. 明确的本地查询或比较：规则直接走 saved，不调用 Jev。例如 `Show City rent`、`Compare City and Canary Wharf vacancy Q2 2026`。
3. 解释、研究、最新资料或意图不清的 auto 请求：调用 Jev 的四个 typed questions，复用官方 HTTP 适配器、严格响应校验和可终止子进程。
4. Python 应用分类策略，Jev 本身不执行工具、不写市场事实、不授予审核权限。
5. 已有数据、计算、报告和发布门禁继续执行。

| Jev 意图 | auto 请求执行策略 |
|---|---|
| saved_lookup | saved |
| market_comparison | saved；用户同时要求解释/分析时保持 agent |
| focused_analysis / full_report | 现有 agent 分析 |
| latest_information | 现有 saved 数据；明确 `LIVE_RESEARCH_UNAVAILABLE`，不自动抓取来源 |
| deep_research | 现有受限分析；明确 `DEEP_RESEARCH_WORKER_UNAVAILABLE`，不冒充深度研究 Worker |

用户明确要求解释、风险分析或报告时，分类器不能静默降级为纯数据查询。置信度低于 0.7、超时、响应无效或无可用容量时，记录原因并按原有路径回退。分类新鲜度概率只是意图信号，不是数据新鲜度证明。

## 两个实际入口

**市场 `/api/market/ask`**：auto 模式会用分类结果决定执行路径。SSE 先发送 routing 进度，再执行已有报告/问答；路由写入任务和最终 metrics。`model_requests` 是原有答案模型计数，`classifier_requests` 单独标记分类尝试，不能把两者混作总调用数。每次决策有 `decision_id`，可对应独立回执。已经主动尝试过 Jev 时，不再为同一请求重复做 Shadow 调用。

**原生 `/agents/london-market-agent/runs`**：运行前执行 `classify_query_node`。分类绑定到当前 run ID，检索工具结果中的 `query_routing` 提供紧凑指导；旧 run 的决策不会继承给新 run。此入口仍执行原生 Agent 模型循环，saved 意图在这里是检索指导，不能声称原生聊天已实现零模型快路径。市场 ask 的现有决策通过服务端 ContextVar 复用，不接受浏览器提交的路由覆盖。

## 专用配置

默认 `LONDON_JEV_ROUTING_ENABLED=1`，即业务节点启用。没有密钥时，状态为 `configuration_missing`，不能声称 Jev 正在真实分类。配置以下二者之一后，受控重启后端即可使用，不需要再改业务代码：

- 服务端环境变量 `LONDON_JEV_API_KEY`。
- 项目忽略目录 `D:\deepinsight-lite\secrets\jev.json`。字段参考 `app/config.jev.example.json`；至少填写 `api_key`，`enabled` 默认为 true。文件存在时其中字段覆盖对应环境配置，空 api_key 也会覆盖环境值。

不会继承 OPENAI_API_KEY、TYPESAFE_API_KEY、Tavily 凭据或现有中转密钥。固定调用 [TypeSafe 官方 API](https://docs.typesafe.ai/api) 的 `https://api.typesafe.ai/v1/systemone`，不支持在配置文件中改写 endpoint。当前默认模型为 `jev-1.13.0`，详见 [官方模型文档](https://docs.typesafe.ai/models)。

支持 model、timeout_seconds（0.05–10 秒）、max_pending（1–32）、max_calls（每进程 1–10000）及 confidence_threshold（0–1）。默认 2 秒、4 个并发、100 次接收上限。次数包含失败尝试；没有自动重试。父进程期限包括子进程启动，另有终止清理开销。`LONDON_JEV_ROUTING_ENABLED=0` 优先于配置文件，将 auto 路由恢复为原来的 `route_question` 规则。

当前用户明确表示暂时没有凭据。因此本次交付验证的是接入、策略、失败隔离与运行中节点；真实服务分类质量和延迟尚未实测。

## 状态与诊断

```text
GET  /api/market/routing
POST /api/market/routing/classify
```

诊断请求：`{"message":"Explain City risks","mode":"auto"}`。它只返回分类与执行决策，不调用答案模型，不新增业务 jobs/facts/reports/events；配置了凭据时，诊断本身会消耗一次分类额度并发送当前问题。不要把诊断请求当成免费静态查询。

状态包括 node_integrated、enabled、state、controls_auto_execution、accepted、in_flight、结果计数及回执队列/丢弃/写入失败。`controls_auto_execution=true` 只在配置 ready 时出现；该字段不等于质量门槛已经通过。

运行时数据根目录下 `routing/decisions.jsonl` 保存独立决策回执：问题 SHA-256、长度、decision_id、分类/回退状态、模型和用量、最终模式及限制。不保存问题全文和密钥。启用时当前问题全文会发给 TypeSafe；不发送市场数据库或会话历史。哈希是关联标识，不是匿名化保证。

回执使用 128 项上限的后台队列；磁盘慢或失败不阻塞请求循环。队列满会增加 receipt_dropped，写入错误增加 write_failures，关机/崩溃可能丢失未落盘回执。分类执行池也有独立容量限制，满时立即回退。

## 本地运行与验收

继续使用既有命令：在 `D:\deepinsight-lite\app` 运行 `.\.venv\Scripts\python.exe -m london_product.runtime`；后端 `http://127.0.0.1:7780`，前端使用现有页面。本次不需要前端构建或数据库迁移。

专项测试在 app 执行 `.\.venv\Scripts\python.exe -m pytest -q tests/test_query_router.py tests/test_jev_shadow.py`。完整结果与正式后端加载状态见仓库 `docs/delivery/jev-query-classifier-20261018/VERIFICATION.md`。

2026-10-18 本轮工程验收：Jev 专项 55 项通过；最新完整后端回归 344 项通过，日志与源码版本边界见验证记录。正式 7780 后端已经受控重启，并实测新节点状态与分类诊断返回 200；当前无专用密钥，明确为 configuration_missing。真实 Jev 的准确率、延迟与用量没有被离线测试替代。
