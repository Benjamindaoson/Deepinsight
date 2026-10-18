# DeepInsight Lite B0 最终报告

日期：2026-10-17，Asia/Shanghai。受众：项目负责人。

## 结论

**B0 本地基础运行与原生架构验收通过，已取得未修改官方业务源码的 Agno Agent UI + AgentOS 基线。额外生产构建通过官方 Turbopack 参数完成；默认 Webpack 路径在本机仍有编译停滞限制。此结论不等于生产上线或供应商可靠性验收。**

可以把此版本作为 B 路线下一阶段的执行与聊天底座。保留原生编排能力，后续增加市场数据契约、业务 Skills/Workflows 和产品页面。当前不是 London 市场监测产品，也没有生产部署、业务准确率、数据源接入或 ROI 证明。本轮停止在 B0。

## 冻结身份

| 组件 | 选择 |
|---|---|
| Agent UI | 官方 main 快照 `6dad9593fca6756e1813e4f4b3b2620be6377691` |
| Agno / AgentOS | `agno==2.9.0`，官方 tag SHA `b8894410bc40f94c82377b5e7f2eb59a6528fdac` |
| Python | 最终 Windows 3.12.10，独立 `b0/.venv-win`；WSL 3.12.14 尝试环境保留 |
| UI 工具链 | WSL Node 24.18.0、pnpm 10.34.5；官方锁文件 |
| Runtime / UI | `http://localhost:7777` / `http://localhost:3100` |
| 模型 | 官方 OpenAIChat 适配器；既有授权 relay，服务返回 ID `claude-sonnet-4-6` |
| 存储 / 调度 | 原生 SQLite、AgentOS Scheduler；没有额外调度框架或数据库服务 |

Docker 模板已下载并记录 SHA，但其 main 要求 Agno 3.0.4 / Python 3.14，未运行。只实际验证一组有依据的 UI+Agno 组合，没有无限试错或并装互相冲突版本。

## 已完成的工作和真实证据

- 建立指定 upstream/b0/secrets/app 目录；官方仓库经 git clone 下载，保留 remote、SHA 与状态。
- 原生最小 AgentOS 示例运行副本启动；health/info/config/docs 及组件发现 API 返回 200。
- 原版 UI 冻结安装，使用 `--turbopack --port 3100` 成功启动；修正 **b0 副本**的本地 CORS 环境配置后连接 Runtime。
- Agent 两个指定问题通过；Tools 具备原生调用、Python 函数执行、参数、结果和最终回答证据；UI 捕获到真实 SSE 流。
- Session 上下文、浏览器刷新、后端重启恢复通过；Agent/Team/Workflow/Scheduler 历史及选定 trace 在重启后仍可读取。
- 原生 Sequential Workflow 的两步依次完成，上一步完整输出进入下一步；Team 两个成员各有真实 Run ID；Skills 使用官方 SKILL.md/LocalSkills，模型实际加载指令。
- 原生 Cron 自然触发一次成功，关联 Schedule Run 与 Agent Run；创建/启用/停用/手动触发/预期失败历史可观测。全部测试 Schedule 已停用。
- 完成 UI 源码组件审计、London 产品差距表、架构方向图、复现手册与独立测试脚本审阅。原版 UI 没有 Workflow/Skills/Scheduler 等管理页的缺口被保留。

后端语义门禁：`evidence/api-results/verified-backend-checks.json`。浏览器门禁与截图索引：`browser-acceptance.json`。通过数量是脚本当前生成值，不将截图存在本身当作所有行为通过。源码完整性及 artifact hashes：`evidence/artifact-manifest.json` 与 `versions/repositories-final.json`。

## 典型运行实测

| 测试 | 请求耗时（秒） | 本轮模型请求数 | 报告 Token |
|---|---:|---:|---:|
| Agent 自我介绍 | 32.860 | 1 | 115 |
| Agent 算术（自动用了工具） | 12.203 | 2 | 385 |
| 显式 Tool Calling | 5.578 | 2 | 709 |
| Session 写入 / 回忆 | 5.297 / 2.265 | 1 / 1 | 615 / 637 |
| 两步 Workflow | 58.000 | 2 | 1,670 |
| 双成员 Team（含协调模型） | 34.375 | 4 | 2,365 |
| 原生 Skills | 29.235 | 2 | 846 |
| Scheduler 自然触发 | trigger→完成 31 秒 | 1 | 606 |

数值为一次观测，非均值、p95 或 SLA。模型请求数根据本轮 assistant message metrics 推导，排除旧 Session history，Workflow/Team 包含子执行；Token 是 Agno/服务报告值，不是账单。UI 对话和模型预检等额外调用有各自原始证据，不把上表相加当作完整账单。

Runtime restart-to-health 7.884 秒；UI Ready 20.4 秒、首次首页编译 29.4 秒。空闲进程内存见最终资源凭据；必要应用服务两项。未作负载或多用户容量评估。

## 发生的问题及影响

| 问题 | 结果与边界 |
|---|---|
| 完整 Agno clone TLS 中断 | 同一官方源浅克隆精确标签成功；保留版本证据 |
| pnpm 11 overrides/lockfile 不匹配 | 固定 pnpm 10.34.5 后原锁文件安装成功 |
| WSL NTFS 导入极慢 | 使用项目内独立 Windows Python 3.12 后端；没有覆盖系统环境 |
| SQLAlchemy 缺 greenlet | 安装官方 asyncio extra 后启动成功 |
| 默认 Webpack dev 编译停滞 | 官方 `--turbopack` 参数启动通过；未改源/配置 |
| 默认 CORS 不允许 3100 | b0 环境配置加入本地来源，预检由 400 变 200 |
| 多轮中转模型偏题一次 | 工具执行/结果正确，最终回复偏题；原始 SSE 保留，新会话复核通过；供应商可靠性风险未消失 |
| 开源 UI 缺管理页 | Workflow、Scheduler、Skills、Tracing、评估等后台能力与 UI 支持分别报告 |
| 额外生产 build | `pnpm build --turbopack` 完整成功；默认 Webpack 约7分钟停滞后只停止已核实属于本轮的构建进程；失败/停滞日志保留 |

UI `Images.tsx` 的 fallback innerHTML URL 插值还存在需后续独立验证的潜在注入风险；本轮没做利用验证，也没修改官方源码。API 文档重复 operation ID 警告及 next lint 弃用提示保留在日志，未隐藏。

## 源码、费用与数据边界

三个官方仓库的 **tracked 业务源码没有修改**。仅有 `.codegraph/` 本地未跟踪索引及被官方 gitignore 排除的依赖/构建产物。B0 测试、配置、文档、证据均放在 b0；没有 fork/push/publish，没有访问或操作 A 路线文件，`app/` 没有业务实现。

使用了既有模型服务额度，未购买、充值、部署付费云或开通商业 Control Plane。直连 DeepSeek 余额接口返回 unavailable，旧配置模型 ID 也不在列表，因而没有用它发起推理；改用已有授权 relay。**实际货币扣费无法从该 relay API 确认，记为 NOT AVAILABLE，而不是 0 元。** 密钥未打印，不进入前端/官方仓库；最终扫描只输出命中文件名，不输出密钥。

## B1+ 保留、修改与新增

KEEP：AgentOS 原生 Agent/Tools/Skills/Workflow/Team/Scheduler、聊天流、Session 恢复。

MODIFY：导航、实体可见性、工具执行详情、引用证据、认证与错误体验。是否继续 SQLite 由业务并发/备份要求决定，不能由本轮小规模验证直接推成生产结论。

ADD：London 数据源与指标契约、时间序列、区域映射、历史可比性、事件/阈值、通知回执、报告实体、运行状态页及市场 Dashboard。B0 只提供差距与设计建议，没有实现这些业务模块。

审核通过后才启动 B1；不擅自更换框架或升级 v3。

## 交付状态

**B0：PASS（限定为本地开源基线验收，带上述已知限制）。** 基础运行、原生能力、真实模型、工具、刷新与重启后的 Session 恢复均有证据。后端语义门禁22项、浏览器保存证据门禁6项通过；独立审阅通过限定范围 harness 复核。原版 lint/typecheck/format 退出码均为0；官方 `pnpm build --turbopack` 完整生成静态页面和构建输出。

默认 Webpack build 仍为 BLOCKED，原因尚未缩小到单一根因，不把已观测的慢文件系统提示当作充分因果证明。生产部署未进行；Memory/Knowledge/Evaluations仅审计支持情况，未做端到端测试。所有测试调度已停用；本地服务最终可用性以 `api-results/final-live-check.json` 为准。

必读文档：ENVIRONMENT_REPORT、VERSION_COMPATIBILITY、FUNCTION_CATALOG、UI_AUDIT、GAP_ANALYSIS、TEST_REPORT、RUNBOOK，以及本文；补充 CHECKPOINTS、REVIEW_RECEIPT 和 architecture 产物。所有文件位于 `D:\deepinsight-lite\b0\docs`。
