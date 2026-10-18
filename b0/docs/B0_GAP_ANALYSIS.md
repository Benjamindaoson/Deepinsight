# B0 London Office Market 产品差距分析

结论：可复用 Agno 原生执行和聊天基础，市场数据、指标体系、报告、告警产品仍需业务设计与实现。这里仅形成 B1+ 审计建议，`app/` 保持空白。复杂度为设计估计（不是已完成工作或工期承诺），取决于数据授权、指标口径和交付边界。

| 功能 | 原版是否支持 | KEEP / MODIFY / ADD | 复杂度 | 建议阶段 |
|---|---|---|---|---|
| 市场数据采集 | SDK 有可扩展 Tools；未验证 London 数据源和授权 | KEEP Tool 接入机制；ADD 数据源 adapter、抓取/快照/失败凭据 | 高 | B1 数据契约 |
| 指标抽取 | Agent/Skills 可执行，但不存在冻结市场 schema/口径 | KEEP Agent/Skills；ADD 来源、单位、期间、区域、证据定位和校验 | 高 | B1 |
| 历史比较 | Session 历史不等于市场时间序列；无领域数据库 | ADD 指标版本、可比口径、修订记录、比较服务 | 高 | B1–B2 |
| 新闻事件监测 | 未配置真实新闻源/去重/实体关联 | ADD 来源范围、事件 schema、去重及监测状态 | 中–高 | B1–B2 |
| Agent 市场分析 | 原生 Agent/Team/Workflow 跑通；市场分析未实现 | KEEP 执行层；ADD 业务 Skill/Workflow、引用与边界 | 中–高 | B1 |
| 定时任务 | 原生 Cron/SQLite poller/历史实测通过；开源 UI 无任务管理 | KEEP Scheduler；ADD 配置、启停、失败处理与运行页 | 中 | B1–B2 |
| 主动通知 | 无本项目通知通道、订阅规则或回执 | ADD 事件阈值、订阅、发送 adapter、幂等与失败记录 | 中–高 | B2 |
| 报告中心 | 聊天 Markdown 可输出文本；没有持久化报告产品 | KEEP Markdown；ADD 报告实体、版本、审批/导出与引用 | 中–高 | B2 |
| 市场 Dashboard | 无市场 KPI 卡、趋势图、区域比较 | ADD 指标查询、图表、时间/区域筛选；MODIFY 导航 | 高 | B2 |
| 自然语言问答 | 基础聊天/工具/Sessions 已实测；市场知识未接入 | KEEP 聊天、SSE、工具、Sessions；ADD 领域数据和来源契约 | 中 | B1 |

## 八个预期页面

| 页面 | 现状 | 可复用 | 需新增/修改 |
|---|---|---|---|
| London Office Market Overview | 不存在 | typography、基础布局 | KPI、数据更新时间、缺失状态、来源入口 |
| Monitoring Configuration | 不存在 | select、dialog、button、textarea | 监测对象/来源/频率、原生 Schedule API 交互 |
| Rent / Vacancy / Take-up Trends | 不存在 | 页面壳、基础状态组件 | 指标口径、时间轴、单位、图表和修订标记 |
| Submarket Comparison | 不存在 | 基础选择组件 | 区域映射、同期间可比表/图、缺失说明 |
| Market Events & Alerts | 不存在 | toast 仅用于即时 UI 反馈 | 事件流、规则、已读/处置、通知回执 |
| Market Intelligence Chat | 基础聊天存在 | ChatArea、SSE、Messages、Tools、Sessions | 领域 Agent、引用证据、业务上下文选择 |
| Report Center | 不存在 | MarkdownRenderer 可用于正文展示 | 报告索引、版本、导出、状态与权限 |
| Task Runs & Monitoring Status | Runtime API/数据库存在，UI 页面缺失 | Scheduler/Run IDs、history、tracing | 运行列表、步骤/工具详情、失败原因、重试/停用控制 |

## 改造优先级

**KEEP**：原生 AgentOS、Agent/Tool/Skill/Workflow/Team/Scheduler、SQLite 轻量验证底座、官方聊天/SSE/Session 恢复。禁止另写通用编排器来替代这些已通过的能力。

**MODIFY**：Sidebar 产品导航、实体可见性、工具参数/结果详情、来源证据展示、认证与错误状态。运行链路和数据库选择需基于 B1 的持久化/并发需求再定，当前 SQLite 验收不代表所有生产负载合适。

**DISABLE**：B1 首版不需要的多媒体/研究演示入口；不要将欢迎页对商业 Control Plane 的外链当作业务导航。是否隐藏应在后续产品范围确认后实施，本轮未隐藏。

**ADD**：市场数据契约、指标实体、时序比较、数据新鲜度/修订、监测配置、事件告警、通知回执、报告中心和 Dashboard。先确定可取得的数据源、更新频率、指标可比性及来源合法使用方式，再开发业务 Skill/Workflow；本报告不声称已接入任何 London 数据源。

下一阶段必须由负责人审核范围后开始。B0 没有自动进入 B1。
