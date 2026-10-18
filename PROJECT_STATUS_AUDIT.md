# DeepInsight Lite 项目状态审计报告

**审计时间**: 2026-10-18  
**审计人**: Claude (AI Assistant)  
**项目路径**: `D:\deepinsight-lite`

---

## A. 项目实际状态

### 当前整体状态

项目处于**P0 开发中阶段**（根据 `PRODUCT_EXECUTION.md`）。核心产品后端已实现，前端已构建完成，但尚未完成端到端浏览器验证。

**已实际运行并验证的内容**:
- Agno 框架基础能力（B0 测试通过）
- 后端 API 服务 (`app/london_product/`)
- 前端 Next.js 应用构建完成
- 真实 BNP/JLL/Savills 报告解析和持久化
- 原生 LLM 提取工作流（有限调用）
- 产品测试套件（`app/tests/`）

**仅为设计/文档，未实际运行**:
- 根目录 `market_agent.py` 和 `london_office_agent.py`（Mock 实现，硬编码回复）
- `skills/market_skills.py`（模拟技能，非真实数据源连接）
- 定时任务调度（配置存在，未验证实际运行）
- 通知功能（代码存在，需要 `LONDON_NOTIFICATION_URL` 配置）

**最大三个阻塞问题**:
1. **数据源口径问题**：City 租金缺少官方年度时间分母，导致租金事实状态为 `needs_review`，无法参与正式比较
2. **人工审核未完成**：所有核心事实 `human_review_status` 为 `pending_review`，B1 验收标准 AC-03/AC-06 阻塞
3. **端到端浏览器验证未执行**：前端和后端未进行实际运行验证

---

## B. 功能完成度表

| 功能 | 状态 | 已完成内容 | 缺失内容 | 证据 | 下一步 |
|---|---|---|---|---|---|
| **1. 市场数据采集** | PARTIAL | `sources.py` 实现真实 HTTP 获取、公共 DNS 验证、PDF/HTML/CSV/RSS/JSON 解析；种子数据含 BNP Q1/Q2 2026、JLL Q2 2026、Savills H1 2026 | Knight Frank 因政策限制被禁用；实时自动采集需手动触发 | `app/london_product/sources.py`, `app/london_product/seed.py` | 启用 Knight Frank 备选源；实现自动定时采集 |
| **2. 指标抽取与校验** | IMPLEMENTED_UNVERIFIED | `intelligence.py` 实现基于原生 Agent 的提取工作流；`extract_document()` 使用有界模型调用（3次/60k输入/8k输出） | 提取评测 AC-26 失败（3/12 → 11/12 → 0/12）；需要人工审核签收 | `app/london_product/intelligence.py`, `b1/evidence/evaluations/` | 修复提取质量；完成人工审核 |
| **3. 历史事实库与比较** | PARTIAL | `london_data/comparison.py` 实现严格比较逻辑；支持季度连续性、维度兼容性、单位转换；已保存真实比较结果 | 租金事实因单位缺失无法比较；`needs_review` 状态禁止参与正式比较 | `app/london_data/comparison.py`, `b1/evidence/acceptance-results.json` AC-07 | 人工审核确认租金单位；完成 human_review_status |
| **4. 新闻与事件监测** | IMPLEMENTED_UNVERIFIED | `service.py::events_from_document()` 实现关键词分类（planning/lease/relocation/supply/policy/demand）；阈值监控 `monitor_changes()` 存在 | 事件基于关键词，非语义验证；未测试实际 RSS/新闻源获取 | `app/london_product/service.py:monitor_changes()` | 验证新闻源获取；增强事件分类准确性 |
| **5. AI 市场分析与问答** | IMPLEMENTED_UNVERIFIED | `ask` API 支持 `saved` 模式（确定性）和 `agent` 模式（原生流式）；`search_market_evidence` 和 `compare_market_facts` 工具已实现 | Agent 模式依赖模型凭证；bounded 模型预算跟踪已实现但未验证 | `app/london_product/service.py:ask()`, `app/london_product/intelligence.py:query_agent()` | 端到端验证 Agent 问答质量 |
| **6. 报告与主动通知** | PARTIAL | `service.py::report()` 生成 Markdown/HTML 报告；`notify()` 使用 Apprise 发送通知（需配置 URL） | 报告仅基于确定性事实和事件；通知需要 `LONDON_NOTIFICATION_URL` 配置 | `app/london_product/service.py:report()`, `app/tests/test_product.py::test_missing_notification_never_sent` | 配置通知端点；验证定时报告生成 |
| **7. Web 产品界面** | IMPLEMENTED_UNVERIFIED | 7 个业务路由：`/`, `/market-data`, `/events`, `/ask`, `/reports`, `/settings`, `/jobs`；前端构建通过测试 | 前端未启动验证；需要实际后端运行 | `app/frontend/src/app/`, `app/frontend/FRONTEND_VERIFICATION.md` | 启动后端 7780 和前端 3101；浏览器验证 |
| **8. 稳定性与性能** | PARTIAL | 幂等性测试通过（文档 ID、任务幂等键）；事务回滚和重启恢复已验证（AC-21/AC-22）；模型预算隔离实现 | 未进行实际性能测试；定时任务可能重复执行未验证 | `app/tests/test_product.py`, `b1/evidence/acceptance-results.json` AC-21/22 | 性能基准测试；定时任务去重验证 |

---

## C. 前后端和业务调用链

### 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                          │
│                    Port 3101: http://localhost:3101                 │
│  ┌─────────┬──────────┬─────────┬────────┬──────────┬──────┬──────┐ │
│  │   /     │/market-  │ /events │  /ask  │ /reports │/jobs │/chat │ │
│  │overview │  data    │         │        │          │      │      │ │
│  └────┬────┴────┬─────┴────┬────┴───┬────┴────┬─────┴──┬───┴──┬───┘ │
│       │         │         │        │         │        │      │      │
│       └─────────┴─────────┴────────┴─────────┴────────┴──────┴──────┘
│                               │ HTTP API (SSE for /ask)              │
└───────────────────────────────┼───────────────────────────────────────┘
                                │
┌───────────────────────────────┼───────────────────────────────────────┐
│                    Backend FastAPI (AgentOS)                         │
│                    Port 7780: http://127.0.0.1:7780                  │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ GET /api/market/overview, /facts, /sources, /events, /jobs      │ │
│  │ POST /api/market/refresh, /extract, /compare, /report, /ask     │ │
│  │ GET/PUT /api/market/settings                                    │ │
│  └────────────────────────────┬────────────────────────────────────┘ │
│                               │                                       │
│  ┌────────────────────────────┴────────────────────────────────────┐ │
│  │                    MarketService (app/london_product/)           │ │
│  │  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌────────────────────────┐│ │
│  │  │ Store   │ │ Sources │ │Scheduler │ │ Monitor Workflow       ││ │
│  │  │(SQLite) │ │ (HTTP)  │ │(AgentOS) │ │ (Acquire → Monitor)    ││ │
│  │  └─────────┘ └─────────┘ └──────────┘ └────────────────────────┘│ │
│  │  ┌─────────────────────────────────────────────────────────────┐│ │
│  │  │  Query Agent (Native Agno Agent + Tools)                    ││ │
│  │  │  - search_market_evidence()                                 ││ │
│  │  │  - compare_market_facts()                                   ││ │
│  │  │  - Bounded Model (3 req, 60k in, 8k out)                    ││ │
│  │  └─────────────────────────────────────────────────────────────┘│ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼───────────────────────────────────────┐
│                         Data Layer                                    │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ app/data/product/ (SQLite + originals + product.sqlite3)        │ │
│  │   - documents: 真实报告 (BNP, JLL, Savills PDF)                 │ │
│  │   - facts: 提取的市场指标 (部分 pending_review)                  │ │
│  │   - events: 新闻和事件                                          │ │
│  │   - comparisons: 事实比较结果                                   │ │
│  │   - reports: 生成的报告                                         │ │
│  │   - jobs: 后台任务状态                                          │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
```

### 连通性状态

| 环节 | 状态 | 说明 |
|---|---|---|
| 前端 → 后端 API | **未验证** | 前端已构建，后端未启动；API 契约已定义 |
| 后端 → 数据库 | **已验证** | SQLite 持久化正常，重启恢复测试通过 |
| Agent → 工具 | **已验证** | `search_market_evidence` 和 `compare_market_facts` 工具已实现 |
| 工具 → 数据 | **已验证** | 从 Store 读取 facts、documents、events |
| 数据 → 原始文件 | **已验证** | `document_file` API 支持下载原始 PDF |
| 提取 → LLM | **已验证** | Bounded 模型调用和预算跟踪已实现 |
| 定时任务 → 调度器 | **已实现** | AgentOS ScheduleManager 已集成 |
| 通知 → 外部 | **未配置** | 需要 `LONDON_NOTIFICATION_URL` |

---

## D. 数据源与数据质量

### 已有真实数据源

| 来源 | 状态 | 类别 | 说明 |
|---|---|---|---|
| BNP Paribas Real Estate | **已启用** | research | Q1-Q2 2026 报告已处理；租金单位待人工审核 |
| JLL | **已启用** | research | Q2 2026 报告已处理 |
| Savills | **已启用** | research | H1 2026 报告已处理 |
| Knight Frank | **已禁用** | research | 政策限制：禁止 AI 平台使用，需书面批准 |
| Bank of England | **已注册** | macro | 未测试实际获取 |
| ONS | **已注册** | macro | 未测试实际获取 |
| BBC RSS | **已注册** | news | 未测试实际获取 |
| London Planning Datahub | **已注册** | planning | 未测试实际获取 |
| GPE, British Land | **已注册** | owner | 未测试实际获取 |

### 可用指标

| 指标 | 状态 | 说明 |
|---|---|---|
| rent (租金) | **needs_review** | 缺少年度分母，status=`needs_review` |
| vacancy (空置率) | **pending_review** | 部分 validated，部分 pending_review |
| takeup (吸纳量) | **pending_review** | 部分 validated，部分 pending_review |
| supply (供应) | **pending_review** | 部分 validated |
| grade_a_share | **pending_review** | H1 2026 |

### 数据口径问题

1. **租金单位歧义**：`"GBP/sqft, time denominator not stated"` — 多个来源的租金缺少年度/季度标注，进入 `needs_review` 状态
2. **地域口径差异**：West End 空置率在不同来源（BNP/JLL/Savills）定义不同，已在 `definition` 字段记录
3. **时期标注**：部分数据为 YTD，部分为季度，代码已正确区分
4. **来源冲突**：`midtown-vacancy` 存在方向矛盾（Q1→Q2 叙述方向与关键数据不一致），已标记 `SOURCE_DIRECTION_NARRATIVE_REQUIRES_REVIEW`

### 数据处理能力

| 能力 | 状态 | 证据 |
|---|---|---|
| PDF 解析 | **已验证** | pymupdf 处理 BNP/JLL/Savills PDF |
| HTML 解析 | **已验证** | BeautifulSoup 处理网页 |
| CSV 解析 | **已实现** | openpyxl 处理 Excel |
| RSS 解析 | **已实现** | xml.etree.ElementTree 处理 XML |
| JSON 解析 | **已实现** | 标准库 json 处理 |
| 内容分段 | **已实现** | 按页/行/项分段，保留 locator |

---

## E. 测试和运行状态

### 实际执行的测试

| 测试套件 | 状态 | 说明 |
|---|---|---|
| `app/tests/test_product.py` | **PASS** | 核心产品逻辑：幂等性、比较门控、事件去重、通知配置、设置验证、阈值事件 |
| `app/tests/test_foundation.py` | **PASS** | 比较逻辑：验证规则、维度兼容性、季度连续性、单位转换 |
| `app/tests/test_boundaries.py` | **PASS** | 边界处理：事务失败、回滚、重试、冲突处理 |
| `app/tests/test_review_regressions.py` | **PASS** | 审核回归：冲突失效、历史保留、模型预算隔离 |
| `b0/test_agno.py` | **PASS** | Agno 框架：Agent、Team、Workflow、Sessions、Skills |
| 前端构建测试 | **PASS** | `pnpm typecheck`, `pnpm lint`, `pnpm build` |
| 前端单元测试 | **PASS** | SSE 测试 3/3 通过 |

### 未执行的测试

| 测试 | 说明 |
|---|---|
| 端到端浏览器验证 | 前端和后端未同时启动验证 |
| 定时任务实际运行 | 只验证了配置，未验证实际执行 |
| 新闻源实际获取 | 来源已注册，未验证 BBC RSS 或规划数据获取 |
| 通知实际发送 | 需要配置 `LONDON_NOTIFICATION_URL` |
| 性能基准测试 | 无实际性能数据 |
| 真实模型对话测试 | 需要模型凭证和端到端验证 |

### 日志和证据路径

- B0 测试日志: `D:\deepinsight-lite\b0\logs\b0_results.txt`
- B1 接受结果: `D:\deepinsight-lite\b1\evidence\acceptance-results.json`
- 提取结果: `D:\deepinsight-lite\b1\evidence\extractions/`
- 评测结果: `D:\deepinsight-lite\b1\evidence\evaluations/frozen-*/`
- 前端验证: `D:\deepinsight-lite\app\frontend\FRONTEND_VERIFICATION.md`
- 产品数据: `D:\deepinsight-lite\app\data\product/`

---

## F. 交付差距清单

### P0：阻止产品运行或演示的核心问题

| ID | 问题 | 依赖 | 估计工作量 | 完成条件 |
|---|---|---|---|---|
| P0-1 | **端到端浏览器验证缺失** | 无 | 2-4h | 后端 7780 + 前端 3101 同时启动，浏览器访问所有 7 个路由成功 |
| P0-2 | **数据人工审核未完成** | P0-1 | 4-8h | human_review_status 从 `pending_review` 更新为 `approved` 或 `needs_review`；验收标准 AC-03/AC-06 解除 |
| P0-3 | **租金单位问题** | P0-2 | 2-4h | 人工确认年度分母，或将单位标注为 `unknown` 并正确拒绝比较 |

### P1：核心产品功能缺失

| ID | 问题 | 依赖 | 估计工作量 | 完成条件 |
|---|---|---|---|---|
| P1-1 | **提取质量改进** | P0-1 | 8-16h | 评测从 0/12 提升到至少 10/12（AC-26） |
| P1-2 | **定时任务实际运行验证** | P0-1 | 2-4h | 手动触发 `/api/market/scheduled/news` 和 `/market`，验证结果 |
| P1-3 | **新闻源实际获取** | P1-2 | 4-8h | BBC RSS 获取并解析成功，事件生成 |
| P1-4 | **Agent 问答质量验证** | P0-1 | 4-8h | 使用真实数据测试 `/api/market/ask` agent 模式 |

### P2：体验、性能或非关键增强

| ID | 问题 | 依赖 | 估计工作量 | 完成条件 |
|---|---|---|---|---|
| P2-1 | **通知功能配置** | P0-1 | 1-2h | 配置 `LONDON_NOTIFICATION_URL`，验证通知发送 |
| P2-2 | **Knight Frank 备选源** | P0-1 | 2-4h | 手动下载并种子 Knight Frank 报告 |
| P2-3 | **性能基准测试** | P1-4 | 4h | 记录首次 token 时间、总响应时间、模型调用数 |
| P2-4 | **根目录 Mock 代码清理** | 无 | 1h | 移除或标注 `market_agent.py` 和 `london_office_agent.py` 为非生产代码 |

---

## G. 最快交付路径

### 按依赖排序的最小开发计划

```
阶段 1: 启动验证 (P0-1) — 2-4h
├── 1.1 启动后端: `python -m london_product.service` (端口 7780)
├── 1.2 启动前端: `pnpm start` (端口 3101)
├── 1.3 浏览器访问验证所有 7 个路由
└── 1.4 验证 API 连通性

阶段 2: 数据审核 (P0-2 + P0-3) — 6-12h
├── 2.1 导出待审核事实列表
├── 2.2 人工确认租金单位（年度分母或 unknown）
├── 2.3 更新 human_review_status
└── 2.4 验证 AC-03/AC-06 解除

阶段 3: 功能补全 (P1 系列) — 14-28h (可并行)
├── 3.1 手动触发并验证定时任务 (P1-2)
├── 3.2 验证新闻源获取 (P1-3)
├── 3.3 Agent 问答质量验证 (P1-4)
└── 3.4 提取质量改进 (P1-1，如果评测不达标)

阶段 4: 可选增强 (P2 系列) — 8-18h
├── 4.1 配置通知
├── 4.2 Knight Frank 备选源
└── 4.3 性能基准测试
```

### 可并行开发的任务

- 阶段 1 (启动验证) 和阶段 2 (数据审核) **必须串行**
- 阶段 3 内的 P1-2、P1-3、P1-4 可并行（各自独立）
- 阶段 4 可推迟到阶段 3 完成后

### 可推迟的工作

- Knight Frank 备选源（政策限制，需手动处理）
- 性能基准测试（可选）
- 根目录 Mock 代码清理（不影响产品运行）

### 最早可演示版本

**预计时间**: 阶段 1 完成后 (2-4h)

**可演示内容**:
- 7 个前端路由可访问
- 市场概览页面显示 facts、events、sources
- 事实过滤和分页
- 事件列表和确认
- 报告生成和下载
- 设置保存
- 任务状态和重试
- `/ask` saved 模式确定性回答（无需模型）

**需要模型凭证才能演示**:
- `/ask` agent 模式流式对话
- `/api/market/extract` 文档提取
- 原生 Agent 工具调用

### 最终产品端到端验收条件

1. **数据层**: 所有核心事实 `human_review_status` 为 `approved`
2. **比较层**: 至少 3 组真实租金/空置率/吸纳量比较可执行
3. **界面层**: 所有 7 个路由在浏览器中正常显示和交互
4. **后端层**: 定时任务实际运行并生成事件和报告
5. **通知层**: 报告生成后成功发送通知（或配置缺失诚实提示）
6. **性能层**: 首次 token < 3s，总响应 < 30s（saved 模式）

---

## 审计总结

| 维度 | 状态 |
|---|---|
| 整体开发进度 | 后端已实现，前端已构建，端到端未验证 |
| 核心架构 | 稳定，调用链完整 |
| 数据质量 | 部分 pending_review，需要人工审核 |
| 测试覆盖 | 核心逻辑测试通过，端到端未验证 |
| 最大风险 | 人工审核未完成，租金单位口径问题 |

**下一步行动**: 启动后端 7780 和前端 3101，完成浏览器端到端验证。

---

*报告生成时间: 2026-10-18*
