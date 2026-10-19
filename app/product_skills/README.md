# London CRE Market Intelligence — Skill Architecture

## 概述

本目录包含 **8 个核心业务 Skills + 1 个 Orchestrator** 的完整实现，以及前沿的技能基础设施。

## 目录结构

```
product_skills/
├── README.md                    # 本文件
├── _core/                      # 前沿技能基础设施
│   ├── __init__.py             # 模块导出
│   ├── demo.py                  # 功能演示
│   ├── skill_core.py            # 版本管理与缓存
│   ├── skill_optimizer.py       # 性能优化
│   ├── skill_auto_trigger.py     # 智能触发
│   ├── skill_visualization.py    # 可视化
│   └── skill_orchestrator.py    # 编排器
├── orchestrator/                 # 编排器 Skill
├── source-discovery/            # 数据源发现
├── fact-extraction/             # 事实提取
├── market-intelligence/         # 市场情报
├── comparison/                  # 比较与变化
├── event-monitor/               # 事件监测
├── macro-drivers/               # 宏观驱动
├── analysis/                    # 分析
├── verification/                 # 核验
├── reporting/                   # 报告
└── alerting/                     # 预警
```

## 核心 Skills (8 + 1)

| # | Skill | 职责 |
|---|-------|------|
| 1 | `source-discovery` | 发现和采集市场数据源 |
| 2 | `fact-extraction` | 从报告中提取结构化事实 |
| 3 | `market-intelligence` | 管理 CRE 指标和子市场 |
| 4 | `comparison` | 比较观测、检测变化 |
| 5 | `event-monitor` | 监测新闻和事件 |
| 6 | `macro-drivers` | 分析宏观因素和需求驱动 |
| 7 | `analysis` | 证据驱动的分析与风险评估 |
| 8 | `verification` | 事实核验与发布门禁 |
| 9 | `orchestrator` | 编排器，协调 Skill 执行 |

## 前沿能力 (_core/)

### 1. 版本化管理 (skill_core.py)

```python
from _core import SkillVersionManager, SkillCache

vm = SkillVersionManager("app/product_skills")
v = vm.register_version("market-intelligence", content, "Added ESG metrics")
vm.record_usage("market-intelligence", success=True, latency_ms=150)
```

**功能**:
- Semver 版本号自动管理
- 版本状态追踪 (draft/active/deprecated/retired)
- 使用统计和成功率
- 性能下降检测和自动进化建议

### 2. 性能优化 (skill_optimizer.py)

```python
from _core import SkillOptimizer, ParallelExecutor, SmartCache

optimizer = SkillOptimizer()
plan = optimizer.plan_execution(["market-intelligence", "comparison", "analysis"])
# plan.parallel_groups: [['market-intelligence'], ['comparison'], ['analysis']]
# plan.estimated_latency_ms: 预计总延迟
```

**功能**:
- 依赖拓扑排序
- 并行执行规划
- 多层缓存 (L1 精确 / L2 语义 / L3 模式)
- 智能批处理
- 性能监控

### 3. 智能触发 (skill_auto_trigger.py)

```python
from _core import SkillAutoTrigger

trigger = SkillAutoTrigger()
results = trigger.match("What is the vacancy rate in Canary Wharf?")
# results: [TriggerResult(skill='market-intelligence', confidence=0.8, ...)]

sequence = trigger.suggest_skill_sequence(query)
# sequence: ['market-intelligence', 'comparison']
```

**功能**:
- 关键词匹配
- 正则模式匹配
- 时间触发 (定时任务)
- 阈值触发 (告警)
- 冷却期管理

### 4. 自进化 (skill_self_evolution.py)

```python
from _core import SkillSelfEvolution

evolution = SkillSelfEvolution()
evolution.record_feedback("analysis", query, response, helpful=True)
evolution.record_performance("market-intelligence", latency_ms=150, success=True)
suggestions = evolution.get_suggestions()
```

**功能**:
- 用户反馈追踪
- 性能趋势分析
- 有用率统计
- 自动进化建议生成

### 5. 可视化 (skill_visualization.py)

```python
from _core import SkillDashboard, SkillRenderer, VisualStyle

dashboard = SkillDashboard()
dashboard.add_skill("market-intelligence", "London CRE data", "active")
print(dashboard.render())  # Markdown 格式

renderer = SkillRenderer(VisualStyle.PROFESSIONAL)
print(renderer.render_dependency_diagram(diagram))  # Mermaid 格式
```

**功能**:
- 技能卡片渲染 (minimal/professional/detailed)
- 技能矩阵
- 依赖关系图 (Mermaid)
- 性能趋势图表

### 6. 编排器 (skill_orchestrator.py)

```python
from _core import SkillOrchestrator

orch = SkillOrchestrator("app/product_skills")
result = orch.orchestrate("What are the key risks in London office market?")

print(f"Skills: {[s.skill for s in result.skills_used]}")
print(f"Latency: {result.total_latency_ms}ms")
print(f"Cache hit: {result.cache_hit}")
```

**功能**:
- 智能路由和编排
- 版本管理集成
- 性能优化集成
- 自进化集成
- 缓存管理

## 数据流

```
用户查询
    ↓
编排器 (orchestrator)
    ↓
智能触发 (auto_trigger)
    ↓
执行规划 (optimizer)
    ↓
并行执行 (executor) ←→ 缓存 (cache)
    ↓
技能执行 (skills)
    ↓
版本管理 (version_manager)
    ↓
自进化 (self_evolution)
    ↓
结果合成 → 响应
```

## 编排流程

1. **触发分析**: 基于关键词、模式、上下文匹配技能
2. **序列规划**: 拓扑排序确定执行顺序
3. **并行执行**: 独立技能并行运行
4. **缓存检查**: 避免重复执行
5. **结果合成**: 整合多技能输出
6. **反馈收集**: 记录性能和质量数据

## 质量保证

所有 Skills 必须遵守：

1. **证据优先**: 所有事实 claim 引用保存的证据 ID
2. **审核状态**: 显示 `approved`/`pending_review`/`needs_review`
3. **不确定性透明**: 区分事实、推断和未知
4. **范围边界**: 不声称超出证据支持的范围
5. **无编造**: 不捏造统计数据

## 运行演示

```bash
cd app
python -m product_skills._core.demo
```

## 版本要求

- Python 3.10+
- agno (用于 Skill 加载)
- 标准库: dataclasses, pathlib, json, re

---

*Generated: 2026-10-19*
