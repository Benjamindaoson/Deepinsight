# B0 版本兼容性报告

## 冻结候选 A

| 组件 | 精确身份 |
|---|---|
| 官方 Agent UI main 快照 | `6dad9593fca6756e1813e4f4b3b2620be6377691` |
| UI 包 / 核心依赖 | agent-ui 0.1.0；Next 15.5.18、React 18.3.1、TypeScript 5.7.3；其余依赖由原版 `pnpm-lock.yaml` 冻结 |
| 官方 Agno | `v2.9.0`，SHA `b8894410bc40f94c82377b5e7f2eb59a6528fdac` |
| 实际安装 Runtime | PyPI `agno==2.9.0`，Windows Python 3.12.10 |
| Node / pnpm | WSL 24.18.0 / 10.34.5 |
| UI / API | `http://localhost:3100` / `http://localhost:7777` |
| 模型适配器 | 官方 `OpenAIChat`，已授权的 OpenAI-compatible relay，服务返回模型 ID `claude-sonnet-4-6` |
| 原生存储 | `SqliteDb(id='b0-sqlite')` |

`repositories.json` 保存三仓库 remote/SHA/status。`package-source-checks.json` 逐项比对 PyPI 安装包与冻结标签的 Agent、AgentOS、Skills、Scheduler、SQLite 核心文件，换行规范化后全部相同。该核查仅覆盖列出的五个文件，不扩张成整包逐字节证明。

## 选择依据与候选上限

最终另对三个官方 checkout 的 **5,389 个 tracked blobs** 做了完整内容核对（UI 87、Agno 5,243、模板 59）。混用 Windows/WSL Git 暴露 13 个仅 CRLF 的 UI checkout 差异，先逐项证明规范化内容相同，再恢复成精确 HEAD blob；恢复凭据在 `checkout-eol-restoration.json`。最终 tracked diff 为0；Windows 对一个相对 symlink 的反斜线表示按链接语义归一化，未改链接目标。换行恢复不属于业务改造，未用于绕过依赖冲突。

[官方 Agent UI README](https://github.com/agno-agi/agent-ui) 明确声明 main 支持 Agno v2.x。最新文档可能使用 v3 API，因此本轮以精确 v2.9.0 源码、实际 OpenAPI、真实请求和浏览器结果为准。

只实际验证了 **一组** 有依据的候选 A。候选 A 已提供全部要求的后端原生能力，未再安装第二套 Agno。Docker 模板 main 仅下载审计：SHA `5d378ee3b6695b3847cac450f254cd8c9b3193e7`，其 `pyproject.toml` 要求 Python `>=3.14,<4`、`agno==3.0.4`，与本轮选定 Python 3.12/v2 基线不同，**未运行该模板，不作为候选 B 兼容性已通过的证据**。

## API 与浏览器实测

- `/health`、`/info`、`/config`、`/docs`、`/agents`、`/teams`、`/workflows`、`/openapi.json` 返回 200。
- UI 的 `src/api/routes.ts` 使用 `/health`、`/agents`、`/teams`、`/sessions` 和 Agent/Team runs 路由；发现接口确实返回列表，匹配 UI 的直接数组解析。
- UI 请求收到 HTTP 200、`text/event-stream`。实际流包含 `RunStarted`、`RunContent`、`ToolCallStarted`、`ToolCallCompleted`、`RunCompleted`，已保存原文。模型响应内容逐步进入官方流解析器和界面。
- Agent、Team 均能发现和执行；Session 刷新及后端重启后恢复。Workflow 后端可注册/执行，开源 UI 没有对应模式/路由，记为 **Frontend NOT SUPPORTED / GAP**。
- Skills 通过 `Skills` / `LocalSkills` 原生加载官方示例；Scheduler 原生 poller 在 SQLite 上自然触发、记录历史并停用。这是本版本实测，未把文档中 PostgreSQL 示例的依赖要求套用到所有数据库。

## 运行副本调整清单

原始官方业务源码零修改。`b0/runtime-demo/official_quickstart.py` 保存官方示例快照；`agno_assist.py` 只调整供应商/模型、密钥读取、绝对 DB 路径、本地绑定/端口、CORS 及关闭可选 Agno telemetry/reload。`model_config.py` 只负责读取本地凭据和构造官方模型适配器。

`b0/smoke-tests/native_runtime.py` 是附件允许的中性验证脚本：原生 AgentOS 中注册工具 Agent、官方样例 Skills Agent、两个原生 Workflow Step、两名 Team 成员、SQLite/tracing/scheduler。不是官方最小示例的“原样复制”，也不声称如此；不包含房地产业务。参考模式和源路径在文件注释中记录。

UI 使用原版安装锁文件、原版源码，启动参数加入 `--turbopack --port 3100`。官方配置、包清单、锁文件、通信模块没有改写。`.codegraph/` 是本地未跟踪索引，应与业务源码修改区分。

## 已知限制

1. 中转服务返回的模型 ID 经 `/models` 核实，底层模型身份不能独立确认。一次多轮 UI 工具请求的工具结果是 42，但最终回复偏离问题；原始流证明该异常已经由后端返回。新会话相同请求通过，异常证据未删除。框架互操作通过不等于供应商可靠性已获得保证。
2. 开源 UI 只有 Agent/Team 模式。Skills/Scheduler/Tracing/Memory/Knowledge/Evaluations 管理界面不能从商业 Control Plane 截图推定已有。
3. Swagger 的 API title/version 展示 `Agno AgentOS 1.0.0` 是 OpenAPI app metadata；实际 SDK 版本由 `/info.agno_version` 和安装锁定记录确认，不将二者混同。
4. 后续必须按 SHA/精确版本重建，禁止直接升级 `latest`。v3 升级需要独立兼容性门禁。
