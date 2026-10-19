# DeepInsight Lite 业务 Skills

本目录有 **17 个业务 Skill**。每个 `SKILL.md` 是 Agno 可加载的任务指引，说明何时使用、输入、工具、步骤、输出与边界。实际能力由现有工具和后端工作流执行；文档名称不代表系统实现了同名独立 Agent 或执行器。

写法对齐用户提供的 sql-insight 示例：明确触发条件、Capabilities、Input、Workflow、Quick Start、Output、Examples、Safety Mechanisms、Dependencies 与 Runtime Integration。示例是格式说明，不能当真实运行结果。

## 目录与职责

| Skill | 触发任务 | 实际执行依托 |
|---|---|---|
| [orchestrator](orchestrator/SKILL.md) | 综合问题、分解任务、追问范围 | 当前路由、单 Agent 和已提供工具 |
| [market-intelligence](market-intelligence/SKILL.md) | 指标与已存市场事实 | search_market_evidence / facts / coverage |
| [comparison](comparison/SKILL.md) | 历史变化、百分比与百分点 | compare_market_facts / MarketService.compare |
| [fact-extraction](fact-extraction/SKILL.md) | 保存文档的结构化抽取 | ProductExtraction 与现有模型抽取工作流 |
| [source-discovery](source-discovery/SKILL.md) | 数据源发现、采集、失败检查 | Sources / Refresh / Jobs |
| [multi-source-search](multi-source-search/SKILL.md) | 多源核对、冲突、证据台账 | 有界保存证据检索与来源核对 |
| [event-monitor](event-monitor/SKILL.md) | 新闻、规划、租赁事件 | 保存 events、原文和现有采集工作流 |
| [macro-drivers](macro-drivers/SKILL.md) | 利率、就业、因果解释 | 保存宏观/市场证据；不预置市场判断 |
| [analysis](analysis/SKILL.md) | 风险、机会、条件情景 | 当前 analysis_contract、finding/publication 校验 |
| [verification](verification/SKILL.md) | 引用、口径、发布门禁 | 原文核验、当前事实投影和确定性门禁 |
| [reporting](reporting/SKILL.md) | 保存、重开、导出报告 | ReportArtifact / Reports / 导出接口 |
| [review-workflow](review-workflow/SKILL.md) | 待审与人工决策记录 | Reviews、原文、实际人工审核界面 |
| [deep-research](deep-research/SKILL.md) | 有界深度研究、断点 | 原生工具或持久 research job/checkpoints |
| [submarket-analysis](submarket-analysis/SKILL.md) | 子市场资料和口径差异 | 保存证据、原始地域和比较门禁 |
| [supply-pipeline](supply-pipeline/SKILL.md) | 开发、竣工、翻新、预租 | 保存 facts/events 和原始阶段定义 |
| [business-briefing](business-briefing/SKILL.md) | 面向业务团队的简报内容 | 已存报告/已释放内容；不自行生成幻灯片文件 |
| [alerting](alerting/SKILL.md) | 阈值、通知、去重、送达 | Settings、monitor、实际 Apprise 尝试与回执 |

```text
product_skills/
  <skill-name>/SKILL.md       # 17 个规范任务指引
  <skill-name>/references/runtime-contract.md # Agno 实际可读的同步副本
  references/runtime-contract.md            # 共享原稿
  scripts/skill_helper.py    # 只读 list/show/check，标准库即可
  _core/                    # 既有版本/缓存/触发/编排等辅助代码
```

## 本地快速开始

从仓库的 `app/` 目录使用现有项目环境：

```powershell
.\.venv\Scripts\python.exe product_skills\scripts\skill_helper.py --help
.\.venv\Scripts\python.exe product_skills\scripts\skill_helper.py list
.\.venv\Scripts\python.exe product_skills\scripts\skill_helper.py show comparison
.\.venv\Scripts\python.exe product_skills\scripts\skill_helper.py check
```

命令只读取文档；不调用模型、不连数据库、不执行 Markdown 中的命令、不注册计划、不发送通知。`list` 输出实际名称/描述/路径；`show` 输出某份文档；`check` 校验 frontmatter、名称、触发说明、必需章节、本地引用、JSON 示例及 Skill 本地参考副本与原稿的一致性。检查失败返回非零退出码，不能将失败输出当成功。

## 实际运行时如何使用

[skill_registry.py](../london_product/skill_registry.py) 与 [intelligence.py](../london_product/intelligence.py) 的 `native_skills()` 指向同一个 `app/product_skills`。Agno 通过元数据发现 Skill，并提供按需读取 instructions 的能力；`GET /skills` 返回描述性契约。元数据存在、加载成功和模型是否正确遵循是三个不同的验证层次。

原生聊天实际提供 `search_market_evidence`、`compare_market_facts`。前者查询保存证据并可能保存确定性报告，后者计算并持久化比较。Skills 不能凭文字获得额外的网络、数据库、文件、审批或通知工具。外部采集、抽取、报告、审核和投递使用现有界面/服务接口，按其授权、配置与门禁执行。

[共享运行契约](references/runtime-contract.md) 列出接口、副作用、预算/失败停止、证据规范和输出优先级。特别注意：注册表通用输入输出用于描述；ProductExtraction、ReportArtifact 和实际 analysis_contract 才是对应调用的机器响应契约，不得混用。

Agno 只发现每个 Skill 自己的 `references/` 文件，不会通过 `../references` 自动读取共享文档。因此各 Skill 保留一份同步副本，指引明确使用 `get_skill_reference(skill_name=实际名称, reference_path=runtime-contract.md)`。副本仅调整源码链接的相对层级；检查器验证同步，测试使用真实 Agno 接口逐一读取内容，避免“链接存在但模型读不到”。

## 写作与证据规则

- description 包含具体任务及触发语言；不只写“负责某项工作”。
- 工作流说明真实工具名、所需 ID、失败/缺证据处理和实际输出。
- 缺年度分母不强制年化；季度/YTD/年度不混算；保留来源地域，不把 Docklands 合并成 Canary Wharf。
- 多源一致只是交叉佐证，不等于人工批准；技术校验、人工审核、可比性和语义批准分开。
- 不在 Skill 内嵌无来源的“当前”市场事实、行业需求等级、法律门槛或预测。
- 模型失败、usage 缺失、预算保护与未知费用保持可见，不自动重试或用模板替代。
- 没有真实保存、导出、事件或投递回执，就不声称已经执行。Apprise json:// 是 HTTP 传输，不是本地文件通知。
- 仅引用存在的文件、命令和服务。可选 scripts/references/assets 按实际需要添加，不为凑目录结构创建虚构执行器。

## _core 的真实边界

既有 [skill_core.py](_core/skill_core.py)、[skill_auto_trigger.py](_core/skill_auto_trigger.py)、[skill_optimizer.py](_core/skill_optimizer.py)、[skill_visualization.py](_core/skill_visualization.py) 和 [skill_orchestrator.py](_core/skill_orchestrator.py) 提供辅助类。`SkillSelfEvolution` 实际定义在 `skill_auto_trigger.py`，没有独立的 skill_self_evolution.py。

这些辅助类的存在不证明所有业务 Skill 被生产路由逐一执行，也不证明模型自动进化、并行研究或语义审核已完成。本轮聚焦 Skill 指令与真实接口对齐，不借此宣布这些额外能力通过业务验收。

## 验证与依赖

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_skill_authoring.py tests/test_skill_registry.py -q
```

本地检查器使用 Python 3.10+ 标准库。Agno 实际加载测试使用已有项目 `.venv` 和锁定依赖。没有新增外部包，也不要求 PostgreSQL、SQL 工具或模型 Key 来运行检查器。

此验证覆盖文档契约、负例、本地命令和真实加载；不构成真实模型遵循或市场业务正确性的证明。现有冻结验收副本保持原状；新文档由当前源码启动的实例重新加载后使用。
