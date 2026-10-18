# G4 — DeepInsight Lite P0/P1 实际运行验收

验收日期：2026-10-18。范围：`D:/deepinsight-lite` 的现有 Web App；主要实现位于 `app/frontend`。本轮保留原有技术栈、九条路由、业务接口、原件、审核与比较门禁。结果是可运行的增量改进。

**最新结论（2026-10-18，Asia/Shanghai）：P0/P1 前端实现及已执行的本地流程通过；修复后的一次新真实问答技术执行 PASS，安全回答回退 PASS，AI 草稿语义分析未通过，整体 G4 保持 PARTIAL。** 新真实运行由 `lite` 交付会话按用户单独授权执行。本次 G4 更新只读取结果、账本、只读发布投影和保存原件，不提交问题、不调用模型、不修改业务代码或重启服务。

## 最新真实问答验收（当前结论）

这次验收已结束，交付会话已释放运行协调占用。它是新的真实网页提交，不是旧会话离线回放。以下结论取代前期“新真实问答 NOT RUN”的状态；后文旧阶段记录保留用于追踪版本与验证范围。

| 验收维度 | 当前状态 | 实际证据与含义 |
|---|---|---|
| 一次真实网页提交 | **PASS** | 2026-10-18 12:15:59 +08:00 提交固定问题“最近一个季度伦敦写字楼市场有哪些变化、风险和机会？”；浏览器网络记录只有 1 次 Native POST |
| 检索与模型技术执行 | **PASS** | 1 次 `search_market_evidence`；2 次模型请求；原生 Run `COMPLETED`，原始草稿非空，账本正常保存 |
| 预算与用量回执 | **PASS（本次约束）** | 服务商回执累计输入 2,394、输出 1,356 Token；请求数、累计用量和单次输出均未超限；无重试/供应商切换。费用 **N/A**，不能解释成免费 |
| AI 草稿语义与引用完整性 | **未通过 / FAIL** | `publication_review.status=withheld`、`semantic_approval=false`；草稿将 Tower of London 误写为“塔桥”，部分候选数字缺少对应机构的逐项引用，不能直接发布 |
| 原生完成→发布检查→页面显示 | **PASS（安全回退路径）** | 实际 GET 只读 publication，页面显示非空安全回答及明确回退标签；Native POST 至流完成约 21.540 秒，至发布投影下载完成约 21.646 秒 |
| 安全回退证据内容 | **PASS（所测 9 条）** | 0 条已核验事实、1 条机构披露变化、8 条待审核原始披露；保留原文、来源、时期、审核状态，不发布模型的不安全判断、不执行新变化计算 |
| 引用核查与原件保护 | **PASS（所测范围）** | 执行方 9 条记录核对均通过；本会话另外读取 4 份涉及的保存原件，SHA-256 均与发布结果相等；Run/Session/账本身份、原始草稿哈希、当前只读投影与落盘结果相互一致 |
| 原业务数据与历史保护 | **PASS（执行方完整性收据）** | 事实、文档、事件、来源、设置、原件、既有会话、既有账本及源码无变化；只新增本次 Session/Run 和账本 |
| 规划事件完整展示 | **PARTIAL** | 1 条事件因检索包 `human_review_status=pending_review` 与保存字段 `null` 不一致，被保守省略；页面没有发布错误规划分析，但信息覆盖受限 |
| 机构变化字段展示 | **PARTIAL** | 通用“原记录数值/单位”未读取该类记录的 `reported_value/reported_unit`，显示“未披露”；下方机构原文仍正确显示 2.6 million sq.ft. 和 15%，不得称机构没披露数字 |
| 正式趋势、风险机会结论与人工审核 | **BLOCKED** | 本次没有已核验事实，数据未被批准，正式比较及风险/机会结论仍缺少审核及相容方法依据；安全回答明确说明证据不足 |
| 全产品全面通过 | **PARTIAL** | 单次真实问答的技术和安全回退成功不等于 AI 语义分析通过，也不覆盖未重测的新闻、调度、通知或完整辅助技术体验 |

**真实运行身份：** Run `d075bf6b-9e43-4c01-b944-9f4babc66764`；Session `1733da71-4be0-4b67-a641-690007db8952`；构建仍为 `bfbfd31e01cb87d6c0b9715afe26396cf77e87495821c7ffbbfa6bd68691cb1f`。网页提交 1 次、模型请求 2 次、检索 1 次。回退本身额外模型调用为 0；界面“未新增模型调用”只指回退步骤，整次真实问答并非 0 调用。

服务商回执累计 3,750 Token：输入 2,394、输出 1,356。缓存字段原样保留，没有再次累加或据此推算费用。模型响应 TTFT 约 4.414 秒，不是用户可见最终正文的精确 TTFT；最终正文精确渲染时点 **N/A**。

自动门禁代码为 `LEASE_STATUS_QUANTITY`、`UNVERIFIED_INDICATOR_TREND`、`UNVERIFIED_PLANNING_STATUS`、`NO_VERIFIED_FACTS`。代码命中是保守规则的结果，不能逐项当作已经证实的模型错误：本次草稿确实写了“80%已预租或洽谈中”，保留了两种状态，不能说它误写成“80%全已签预租”。本次明确核实的错误是“伦敦塔→塔桥”和引用不完整。原草稿保持原样作为审计材料。

可查看本次保存会话：[打开本次安全回答](http://127.0.0.1:3101/?agent=london-market-agent&db_id=london-product&session=1733da71-4be0-4b67-a641-690007db8952)。该链接只用于查看现有记录，验收更新没有重新提交问题。

证据索引：

- [本次真实验收报告](../../app/data/product/evidence/post-fallback-live-20261018/AI_QA_ACCEPTANCE_REPORT.md)、[执行摘要](../../app/data/product/evidence/post-fallback-live-20261018/result-summary.json)、[浏览器提交与网络](../../app/data/product/evidence/post-fallback-live-20261018/browser-network.json)。
- [原始 AI 草稿](../../app/data/product/evidence/post-fallback-live-20261018/raw-draft.md)、[实际发布结果](../../app/data/product/evidence/post-fallback-live-20261018/publication.json)、[最终安全回答](../../app/data/product/evidence/post-fallback-live-20261018/final-answer.md)、[原始模型账本](../../app/data/product/evidence/post-fallback-live-20261018/model-call-ledger.json)。
- [9 条引用核查](../../app/data/product/evidence/post-fallback-live-20261018/citation-checks.json)、[执行方完整性核对](../../app/data/product/evidence/post-fallback-live-20261018/integrity-checks.json)、[本会话追加的只读核验](evidence/live-acceptance-independent-check.json)。最后一份收据中的引用核查数组来自执行方，独立重复核对的范围为身份、用量、原始草稿哈希、当前发布投影和涉及的 4 份原件哈希。
- [实际页面截图](../../app/data/product/evidence/post-fallback-live-20261018/browser-screenshot.png)、[机构披露证据截图](../../app/data/product/evidence/post-fallback-live-20261018/browser-publisher-evidence.png)。这些是本次 `bfb…` 新运行证据；不能用来替换较早 `a54…` 构建的所有 UX 回归记录。

当前阻塞与限制无需通过重复模型调用来确认：AI 草稿语义/引用完整性仍未通过；人工审核和相容方法仍缺失；规划事件状态映射和机构变化数值/单位展示存在上述两个已记录限制。本轮只更新验收记录，未修复这些业务/展示问题，也不扩大测试范围。

## 版本与并发边界

本轮已发布、重启并进行最终浏览器复查的生产构建：

```text
manifest_sha256: a54dc20a3ccf3dfa3d704d865a8381ef508829afdf6675850c4d86cf1023b152
source/config files: 99
frontend: http://127.0.0.1:3101
backend: http://127.0.0.1:7780
```

构建时源文件与 Linux 构建镜像逐个相等，22 项测试通过。原始构建日志为 [final-build.log](evidence/final-build.log)，冻结身份为 [ux-build-identity.json](evidence/ux-build-identity.json)。之前的 `f488…`、`ea7e…` 是阶段构建，不能作为本轮最终身份。

11:35 后，用户另一个已授权的交付会话 `lite` 协调接管离线安全回答回退，开始修改 `MessageItem`、`useAIStreamHandler`、`useSessionLoader`、消息类型等文件。本轮随即停止源码修改和构建/重启，只保存验收文档。11:37 的 [runtime-final.json](evidence/runtime-final.json) 如实记录了这四份源码已与正在运行的本轮构建不同。此差异属于后续协调改动，不能将本轮浏览器截图或 22 项测试追认为后续版本的验收。后续版本应以其自身构建、测试和浏览器记录为准。

## 按原始意图验收

| 项目 | 状态 | 实际结果 |
|---|---|---|
| 保留页面与能力，增量修改 | Done / PASS | `/`、`/chat`、`/overview`、`/market-data`、`/events`、`/ask`、`/reports`、`/settings`、`/jobs` 均 HTTP 200；保留确定性检索、抽取、比较、任务、导出、监控 |
| P0 命名与导航一致性 | Done / PASS | DeepInsight Lite / London Office Intelligence / DeepInsight AI 层级明确；一个主要 AI 入口；原 `/ask` 高级能力保留 |
| P0 会话与错误恢复 | Done / PASS | 列表失败与空列表区分；历史恢复独立状态；同一会话可重读；旧请求不能覆盖新选择/流式消息；失败记录可编辑问题，诊断保留 |
| P0 真实状态 | Done / PASS | 失败任务不显示成功式 100%；重试仅匹配服务支持的 refresh/extract 和失败/中断/部分成功；未配置通知禁用 |
| P1 导航与历史 | Done / PASS | 分组导航、标题搜索、真实 ISO 时间、空状态、New chat 清空草稿、跨历史清理上下文 |
| P1 来源可信度 | Done / PASS | 原文、页码/定位、原件与发布者链接、统计期、采集/发布日期、机器校验与人工审批分别展示；未知值明确 |
| P1 市场→AI | Done / PASS（至发送前） | fact/event/report 的真实 ID 经 API 解析，生成可编辑问题与独立可检查证据；不自动提交；身份选择保留，发送可用；缺失记录禁止上下文发送 |
| P1 比较入口 | Done / PASS | Data 复用现有比较面板及后端运算；真实两期 BNP 空置率返回方法/校验/人工审核阻塞，未生成未经批准的变化值 |
| P1 报告→监控 | Done / PASS | 实际任务 result.report_id→对应报告→下载→监控设置；报告来源标识保留，未伪装成单报告订阅 |
| P1 监控选择与可读性 | Done / PASS | 可搜索地域/指标勾选，保存值缺失于目录时仍保留；阈值单位和审核条件明确；实际下一运行时间标注 Asia/Shanghai |
| 响应式/主题 | Done / PASS（所测范围） | 1440/1280/820/375；概览、报告、监控 12 个布局组合无整页横向溢出；最终概览四档重测；深色标签修复 |
| 可访问性 | Partially done | 已检验侧栏焦点环、Escape/焦点返回、按钮语义、删除确认、标签、部分色彩对比；未做完整 WCAG 或屏幕阅读器审计 |
| 全新真实 AI 问答 | PARTIAL（已更新） | 新真实提交的技术执行与安全回退 PASS；AI 草稿 withheld、semantic_approval=false；见文首最新验收，不再记为 NOT RUN |
| 首次用户无说明完成任务 | Assumption / 尚未用户研究验证 | 操作员任务路径由实际浏览器走通相应部分；未招募商业地产运营人员做首次使用研究，不能声称实测学习成本下降 |

P2 Market Pulse、额外首页情报流和更复杂执行可视化，依附件优先级未实施；P3 装饰动画不在本轮范围。

## 浏览器实际流程

使用 Codex in-app browser 的真实 DOM、点击与截图，没有用设计图或 Mock 页面替代。早期实测问题及修复保留于 [browser-preliminary.json](evidence/browser-preliminary.json)；最终复查记录为 [browser-final.json](evidence/browser-final.json)。前者包含发现问题时的旧 URL/颜色，不能全部当作最终通过证据。

| 流程 | 结果及证据 |
|---|---|
| A 首次进入→建议问题 | 首页真实加载、AI service connected；点击建议只填入并聚焦输入框，网络记录无模型 POST；New chat 清空草稿。新提交与合格模型最终答案未重跑 |
| B 概览→证据→AI | 查看 West End 租金原文、页码、时期和单位不确定性；fact/event/report 都经 SPA 带入真实记录、可编辑问题、发送可用；未自动调用模型 |
| C 历史恢复 | 真实已保存 session `eb36e907-46cb-41c3-818a-a4341864a2eb` 可恢复，离开概览再回来仍是同一会话；从 fact 切到另一历史，URL 不含旧 context/record、草稿为空 |
| 历史负例 | `ux-missing-conversation` 出现恢复失败与 Reload；实际 GET 重复，无模型 POST；Delete 键打开确认，Cancel 保留记录，未执行删除 |
| D 监控→任务→结果 | 查看现有设置与任务；完成的报告任务链接使用实际 `result.report_id`，打开正确报告；失败/重试规则经测试和服务契约交叉验证；未触发抓取或抽取 |
| E 报告→阅读→下载→监控 | 实际报告 `2772fbc3-7dbd-471a-a094-198572a6f9dd` 可打开并下载 Markdown；继续到监控，显示真实报告 ID。通过按钮生成确定性日报 `8a061b97-5398-435d-a592-2f1cfe56f29c`，结果可读并保留 |
| 比较门禁 | BNP Q1/Q2 vacancy 返回 `UNKNOWN_METHOD; NOT_VALIDATED; HUMAN_REVIEW_PENDING`；这是业务正确拒绝，UI 检查 PASS，正式变化计算保持 BLOCKED |
| 缺失上下文 | `ux-missing-fact` 显示 record not found、Reload context，发送禁用，没有编造证据 |
| 真实失败 Run | session `05a18e1b-3c5c-4117-99b7-9a19fcb84942` / run `bc3d6a09-34db-47b5-9771-2a4cb5f449d1` 的 ERROR 保留；友好失败正文、技术详情和 Edit question to retry 可用；点击仅填回原问题 |
| 确定性查询 | `/ask` Saved evidence 实际查询返回已保存观测、时期、来源；此路径不调用模型，不能称为真实 LLM 回答 |
| 移动端与主题 | 375px 侧栏焦点可环绕、Escape 关闭后回到 Open sidebar；深色主题刷新后保留；结束时恢复浅色和默认测试视口 |

最终浏览器读取的 error/warn 控制台记录为空。负例仅用于读取缺失记录，没有新建假业务记录。实际日报是保留的验收输出，没有删除历史、原件或报告。

深色输入实测前景 `rgb(235,237,241)` / 背景 `rgb(34,36,40)`，对比约 13.26:1；标签 `rgb(170,177,189)` 对面板 `rgb(43,46,51)` 约 6.31:1。这里只覆盖所采样的表单文字，不代表全站对比度合规。

## 工程命令与结果

所有依赖使用本项目已有独立环境，无新增或升级依赖。命令实际运行，日志留存。

```powershell
# WSL 已有 Node 24.18.0 与前端依赖；22/22、TypeScript、ESLint
wsl.exe --cd /mnt/d/deepinsight-lite/app/frontend --exec env PATH=/home/benjamin/.nvm/versions/node/v24.18.0/bin:/usr/bin:/bin bash -c 'node --experimental-strip-types --test tests/*.test.mjs && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/eslint src'

# 已运行的最终生产构建；仅在停好本项目 UI 且源码无人写入时可重跑
wsl.exe --exec bash /mnt/d/deepinsight-lite/app/frontend/build-product.sh --build

# 本轮规格校验；工作目录 D:\deepinsight-lite\app
openspec validate ux-workflow-p0-p1 --strict --no-interactive

# 实际源码差异与只读运行收据
& .\app\.venv\Scripts\python.exe docs\ux\source_diff.py
& .\app\.venv\Scripts\python.exe docs\ux\verify_runtime.py
```

| 检查 | 结果 | 留存 |
|---|---|---|
| 原始测试基线 | 9/9 PASS | G0 / checks.log |
| 最终 Node 测试 | 22/22 PASS | [final-checks.log](evidence/final-checks.log) |
| TypeScript | PASS | 同上，链式命令继续到 ESLint |
| ESLint | 0 errors，1 个原有 `<img>` 性能建议 | 同上；未关闭规则或改原多媒体组件 |
| 改动 `.ts/.tsx` Prettier | PASS | [format-check.log](evidence/format-check.log) |
| 生产 Next.js 构建 | PASS；99 文件构建身份相等 | [final-build.log](evidence/final-build.log) |
| 独立定向复审 | 13/13 PASS；所审修复未见 P0/P1 残留 | [INDEPENDENT_REVIEW.md](evidence/INDEPENDENT_REVIEW.md) |
| HTTP 路由 | 9/9 为 200 | [runtime-final.json](evidence/runtime-final.json) |
| 源码/部署版本 | 构建发布时一致；11:37 后续会话已修改四文件 | 同上，明确标出 drift；不可称后续源码已验收 |

独立复审曾发现机器校验误称人工审批、跨历史旧上下文、嵌套删除按钮键盘事件三个问题，均已修复并复审。真实浏览器另发现 ISO 日期、SPA 身份选择、深色继承三个问题，均在最终构建前修复。初次 P1 发布因并发源码漂移被构建脚本拒绝，日志保留，没有关闭保护来强行发布。

## 主要修改文件

精确的本轮基线差异为 [changed-files.json](evidence/changed-files.json) 和 [source-diff.patch](evidence/source-diff.patch)，包含 20 份 src 文件与 2 份测试。它们在后续离线回退改动前生成，包含为兼容交付会话而保留的错误诊断修改，不声称全部由本轮独立完成。

| 文件（相对 app/frontend） | 改动目的 |
|---|---|
| `src/components/workspace/WorkspaceShell.tsx`、`src/app/layout.tsx` | 命名、分组导航、身份初始化、移动侧栏、New chat |
| `src/store.ts`、`src/hooks/useChatActions.ts`、`src/hooks/useSessionLoader.tsx`、`src/api/os.ts` | 会话独立状态、请求保护、实际重读、恢复错误 |
| `src/components/chat/Sidebar/Sessions/{Sessions,SessionItem,SessionBlankState}.tsx` | 搜索、空状态、时间、上下文清理与键盘删除 |
| `src/components/chat/ChatArea/ChatArea.tsx`、`ChatInput/ChatInput.tsx`、`Messages/MessageItem.tsx` | 输入、恢复反馈、失败编辑、上下文与诊断展示 |
| `src/components/chat/ResearchContext.tsx`、`src/lib/workflow.ts` | 真实记录解析、可检查证据、状态/导航/时间/隔离纯逻辑 |
| `src/components/market/MarketApp.tsx`、`CoveragePicker.tsx` | 来源证据、事件、复用比较、报告与任务结果、监控选择 |
| `src/lib/market-api.ts`、`src/lib/chat-errors.ts`、`src/types/os.ts` | 保持实际响应契约、明确错误与数据字段 |
| `src/app/globals.css` | 文字、主题、上下文与响应式容纳 |
| `tests/ux-workflow.test.mjs`、`tests/ux-errors.test.mjs` | 13 项针对性回归，加原有 9 项共 22 项 |

`package.json` 与 `pnpm-lock.yaml` 对比基线均未变化。32 条事实的 ID、业务字段与审核状态保留；API 时间字符串由 `+08:00`/不同小数精度投影为等价 UTC，所以原始 JSON 不逐字相等。递归 ISO 时间规范化后 32 条完整记录相等；原始差异详见 [fact-differences.json](evidence/fact-differences.json)。9 项监控业务设置逐项相等，未点击保存或通知。

规格与过程文档：`app/openspec/changes/ux-workflow-p0-p1/`、[G0](G0_FRONTEND_AUDIT.md)、[G1](G1_UI_REFINEMENT.md)、[G2](G2_AGENT_EXPERIENCE.md)、[G3](G3_WORKFLOW_INTEGRATION.md)、[执行记录](LEDGER.md)。

## 修改前后运行截图

全部来自实际本地 Web App，图片点击可查看原图。一次真实历史回答只证明恢复显示，不能证明新模型调用已成功或内容已通过审核。

| 页面/流程 | Before | After |
|---|---|---|
| 聊天主页及侧栏 | [原主页](evidence/before/home.png) | [最终主页](evidence/after/home-desktop.png) |
| 历史会话 | [原历史](evidence/before/history.png) | [真实历史回答恢复](evidence/after/restored-real-answer.png)、[真实失败 Run 恢复](evidence/after/real-model-failure-restored.png) |
| Market Overview | [原概览](evidence/before/overview.png) | [最终概览](evidence/after/overview-desktop.png) |
| Monitoring | [原监控](evidence/before/monitoring.png) | [改后监控](evidence/after/monitoring-desktop.png)、[最终移动深色](evidence/after/monitoring-mobile-dark.png) |
| 证据与后续调查 | — | [来源证据](evidence/after/evidence-desktop.png)、[fact→AI](evidence/after/fact-ai-context.png)、[event→AI](evidence/after/event-ai-context.png)、[report→AI](evidence/after/report-ai-context.png) |
| 报告/阻塞/负例 | — | [真实日报](evidence/after/generated-daily-report.png)、[比较门禁](evidence/after/comparison-blocked.png)、[缺失记录](evidence/after/missing-evidence.png) |

## 保留问题与验收限制

- **Frontend Issues：** 本轮所检查范围未发现未修复 P0/P1；完整辅助技术审计、真实手机虚拟键盘、压力/弱网测试未执行；历史搜索准确标为标题搜索，不声称全文搜索。另一个会话的后续前端回退需独立验收。
- **Backend Dependencies：** 最新模型成功结果未在本轮重新验证。现有 WinError 5 失败和语义发布门禁拦截是不同 Run，均不能算成功分析。后续离线回退由 `lite` 会话处理，本轮不改 Agent 执行、调度或门禁，不发起新的付费请求。通知凭据未配置，通知发送保持不可用。
- **Data Availability Issues：** 观测人工审核未完成、方法/租金时间分母/部分日期未知；正式变化计算仍被正确阻止；不填入模拟市场数据，也不添加界面内审批假功能。
- **Future Enhancements：** Market Pulse、最近情报首页、真正单报告监控、聊天自动创建报告/监控、人工审批工作台，均需相应产品/后端能力；本轮没有虚构这些能力。

本轮完成了用户授权的前端 P0/P1 增量交付及相应可执行的验证。后续已单独授权并执行的新真实问答结果见文首；整体 G4 继续 **PARTIAL**，原因已从“未执行新真实问答”更新为“安全回退通过、AI 草稿语义与引用完整性未通过，仍存在审核/数据与两个展示限制”。

## 后续协调版本补充（2026-10-18）

`lite` 交付会话已完成其独立的离线安全回答回退并释放源码/构建占用。后续已部署版本为 `bfbfd31e01cb87d6c0b9715afe26396cf77e87495821c7ffbbfa6bd68691cb1f`，100 份源文件清单。该版本保留本轮 UX 改动，新增发布投影：拦截 AI 草稿后从本次已检索且可追溯的保存证据生成安全回答，不将待审核事实升级为已核验结论；原生完成后与历史恢复使用相同的只读投影。

本会话另行执行了只读身份与 HTTP 核对，结果见 [coordinated-build-check.json](evidence/coordinated-build-check.json)：100 文件当前源码哈希与该构建清单相等，首页 HTTP 200。没有重新运行完整测试或浏览器流程，也没有新增模型请求。

后续会话的独立 [REPAIR_ACCEPTANCE_REPORT.md](../../app/data/product/evidence/safe-answer-fallback-20261018/REPAIR_ACCEPTANCE_REPORT.md) 记录：192 项后端测试、25 项前端测试及类型/Lint/生产构建通过；真实旧 Session `5d772b21-87a6-4c7a-947c-4b78c57c9c29` 在浏览器显示非空安全回答及来源、刷新恢复通过；事实/原件/原 Run/账本完整性核对通过。以上测试与浏览器结论归属于该交付会话，本会话只核对报告及当前身份，不将本轮 `a54…` 的截图追认成后续 `bfb…` 的验收。

此处记录的是离线回退交付时的历史状态：当时新真实模型问答 **NOT RUN**。该状态已由文首 12:15:59 的新真实验收结果取代；整体仍为 **PARTIAL**，但新真实技术执行与安全回退已通过，AI 语义草稿未通过。当前本地入口仍为 http://127.0.0.1:3101 。
