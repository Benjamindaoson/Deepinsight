# Jev Shadow Mode

后续增量：实际 query/节点分类已独立接入，见 [JEV_QUERY_CLASSIFIER.md](JEV_QUERY_CLASSIFIER.md)。本文描述 Shadow 观察器自身的契约；其 controls_execution=false 不代表主动分类器不存在。

Jev 只观察 `/api/market/ask` 的分类，不决定执行路径。现有 `saved` / `agent`、显式模式、报告、来源核验和发布门禁继续控制产品。原生 `/agents/.../runs` 不经过此观察器。本阶段没有实现 R0–R4、实时研究 Worker 或主动模型选择。

## 接入契约

使用已有 httpx，固定调用 TypeSafe 官方 `POST https://api.typesafe.ai/v1/systemone`。默认锁定 `jev-1.13.0`；请求与返回模型均记录。这里没有使用第三方 Jev 网站或安装路由代理。

官方依据（2026-10-18 查阅）：[API](https://docs.typesafe.ai/api)、[Choice](https://docs.typesafe.ai/primitives/choice)、[模型和版本](https://docs.typesafe.ai/models)。官方接口使用 `state` / `model` / `questions`，响应是 `model` / `answers` / `usage`。

一次调用包含四个独立问题：

| 问题 | 类型 | 记录 |
|---|---|---|
| 任务类别 | Choice | `saved_lookup`、`market_comparison`、`latest_information`、`focused_analysis`、`full_report`、`deep_research`；完整概率及置信度 |
| 是否要求最新资料 | Noul | 0–1 概率；不代表已检查数据库新鲜度 |
| 是否需要多步推理 | Noul | 0–1 概率 |
| 任务复杂度 | Score | 0–3 加权分数及概率 |

置信度低于 0.7 仅标记 `low_confidence`。分类建议与现有二分类规则通过粗粒度映射对照：前两类映射 saved，其余映射 agent；这只是诊断，不能说明比较任务应该永远不调用模型，也不能证明原路由错误。`actual_route` 另外保存显式模式产生的真实执行选择。

## 配置和启动

默认关闭。仅当服务端进程具有 `LONDON_JEV_SHADOW_ENABLED=1` 和专用 `LONDON_JEV_API_KEY` 才会请求外部接口；不会继承 `OPENAI_API_KEY`、`TYPESAFE_API_KEY` 或 Tavily 密钥。不要把密钥放入前端变量、聊天或版本控制。`.env.product.example` 是示例，不会被自动加载；通过安全的进程环境注入专用凭据。

| 变量 | 默认值 | 限制 |
|---|---|---|
| `LONDON_JEV_SHADOW_ENABLED` | `0` | 仅 `1` 启用 |
| `LONDON_JEV_API_KEY` | 空 | 专用 TypeSafe 凭据 |
| `LONDON_JEV_MODEL` | `jev-1.13.0` | Jev 版本号，或显式选择 latest/preview；正式评测建议锁版本 |
| `LONDON_JEV_TIMEOUT_SECONDS` | `2` | 0.05–10 秒；整个 HTTP 调用的墙钟期限 |
| `LONDON_JEV_MAX_PENDING` | `4` | 1–32；含运行中及排队 |
| `LONDON_JEV_MAX_CALLS` | `100` | 1–10000；每进程累计接收上限，失败也占用，不自动重试 |

启动继续使用项目既有命令：

```powershell
cd D:\deepinsight-lite\app
.\.venv\Scripts\python.exe -m london_product.runtime
```

正式 API 为 `http://127.0.0.1:7780`。配置在创建 app 时读取；更改环境后需要受控重启。本次验证使用隔离实例，不替换现有产品进程。

## 隔离、隐私和可观测性

每个 app 有一个专用后台线程；接收请求只入队，不等待 Jev。真实 HTTP 在独立、可终止的 Python 子进程内执行，父进程按墙钟期限结束卡住的请求，包含解释器启动时间（另有进程终止清理开销）。这样即使 DNS 解析阻塞，也不会无限占用观察器线程。子进程仅加载 HTTP 适配器，不启动业务应用、数据库或调度器；问题和凭据经私有 stdin 管道传递，不写到命令参数。

队列满、达到调用上限、关闭或缺配置时跳过。关闭时取消未执行队列；正在进行的 HTTP 调用继续至期限。进程崩溃可能丢失观察，日志也可能写入失败；这不是持久任务队列。子进程有启动开销，应在真实评测中计入观察耗时；它不阻塞主请求等待。

启用会将当前问题全文发送给 TypeSafe 并产生该服务用量，不发送历史会话、PDF 或数据库内容。磁盘回执只存问题 SHA-256 和字符数，不存原问题、凭据、HTTP 响应体或异常文本。SHA-256 是关联标识，不是匿名化保证。目录是运行时数据根下的 `routing-shadow/observations.jsonl`（正式运行通常位于 `app/data/product/`，已被忽略）。保留和清理遵循该机器的数据管理策略。

独立状态接口：

```text
GET /api/market/routing/shadow
```

返回 `state`、`controls_execution=false`、模型、策略指纹、accepted/completed/cancelled、in_flight、容量/预算丢弃、写入失败和结果分类计数。不返回密钥或原问题。未配置为 `configuration_missing`，关闭为 `disabled`，错误配置为 `invalid_configuration`。计数在进程重启后重置；回执跨重启追加。它不修改业务审核状态。

## 离线统计

```powershell
cd D:\deepinsight-lite
app\.venv\Scripts\python.exe app\scripts\jev-shadow-summary.py --help
app\.venv\Scripts\python.exe app\scripts\jev-shadow-summary.py --receipts app\data\product\routing-shadow\observations.jsonl
```

可选 `--labels <本地JSON>`，格式为 `{ "submission-id": "focused_analysis" }`；标签应由人独立标注。可用 `--output <summary.json>` 保存汇总。工具不联网、不启动模型、不改路由，拒绝覆盖输入文件。

统计包括成功/失败数、成功观察调用的 P50/P95（nearest-rank，含本地 HTTP/解析，不含排队）、粗粒度规则分歧和低置信度数。每条回执另含排队、接收和调用耗时。无标签时 `accuracy=null`；有标签时准确率只针对成功且已标注的交集，不代表总体覆盖率。损坏行单独计数。请求覆盖率和成本上限还需结合运行中状态计数；仅用成功回执不能宣称零失败、延迟改善或成本节省。

## 验证与启用边界

2026-10-18 的实现验收：后端完整回归 **308 passed**，其中本功能专项 **31 passed**。另在隔离后端 `127.0.0.1:7794` 执行真实 HTTP 健康、状态及 Saved 问答，均为 200，SSE 以 done 正常结束，答案模型请求为 0。还用离线 HTTP 替身验证真实子进程模块及 stdin/stdout 成功路径，无外部调用。专项包含关闭/缺配置、概率异常、HTTP 失败、硬期限、队列满、调用上限、取消、写入失败、显式/自动 saved 和 agent 路径、发布门禁、统计与损坏回执。独立审查发现的 DNS 超时边界和整数溢出均已修复并复审。

验证记录位于仓库 `docs/delivery/jev-shadow-20261018/VERIFICATION.md`；MockTransport 耗时不代表真实 Jev 性能。现有 7780 产品实例没有被本轮重启，源代码变更需在下次受控启动时加载。

测试使用专用 MockTransport 和隔离临时数据库，不以伪造回执冒充真实 Jev 结果。真实 Jev 分类准确率、实际服务 P50/P95 和生产吞吐量必须在专用凭据配置后另测。单次供应商宣传延迟不属于本项目结果。

回滚：关闭 `LONDON_JEV_SHADOW_ENABLED` 并受控重启。无需数据库迁移或前端发布。不要根据 Shadow 结果自动启用主动路由。
