"""
Skill Core Module - 前沿技能基础设施

提供以下核心能力:
1. 版本化管理 - SkillVersionManager
2. 性能优化 - SkillOptimizer, ParallelExecutor, SmartCache
3. 智能触发 - SkillAutoTrigger
4. 自进化 - SkillSelfEvolution
5. 可视化 - SkillDashboard, SkillRenderer
6. 编排 - SkillOrchestrator
"""

from .skill_core import (
    SkillVersionManager,
    SkillCache,
    SkillVersion,
    SkillEvolutionEvent,
    get_skill_core
)

from .skill_optimizer import (
    SkillOptimizer,
    ParallelExecutor,
    SmartCache,
    SkillBatcher,
    PerformanceMonitor,
    get_optimizer,
    get_executor,
    get_cache,
    get_monitor
)

from .skill_auto_trigger import (
    SkillAutoTrigger,
    SkillSelfEvolution,
    TriggerRule,
    TriggerResult,
    TriggerType,
    SkillTrigger,
    get_auto_trigger,
    get_self_evolution
)

from .skill_visualization import (
    SkillDashboard,
    SkillRenderer,
    SkillCard,
    SkillDiagram,
    SkillPerformanceChart,
    VisualStyle
)

from .skill_orchestrator import (
    SkillOrchestrator,
    SkillCall,
    OrchestrationResult,
    get_orchestrator
)

__all__ = [
    # Version & Cache
    "SkillVersionManager",
    "SkillCache",
    "SkillVersion",
    "SkillEvolutionEvent",
    "get_skill_core",

    # Optimization
    "SkillOptimizer",
    "ParallelExecutor",
    "SmartCache",
    "SkillBatcher",
    "PerformanceMonitor",
    "get_optimizer",
    "get_executor",
    "get_cache",
    "get_monitor",

    # Auto Trigger
    "SkillAutoTrigger",
    "SkillSelfEvolution",
    "TriggerRule",
    "TriggerResult",
    "TriggerType",
    "SkillTrigger",
    "get_auto_trigger",
    "get_self_evolution",

    # Visualization
    "SkillDashboard",
    "SkillRenderer",
    "SkillCard",
    "SkillDiagram",
    "SkillPerformanceChart",
    "VisualStyle",

    # Orchestration
    "SkillOrchestrator",
    "SkillCall",
    "OrchestrationResult",
    "get_orchestrator",
]
