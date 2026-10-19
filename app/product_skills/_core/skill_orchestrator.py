"""
Skill Orchestrator - 智能编排器，整合所有技能能力
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from .skill_core import SkillVersionManager, SkillCache, get_skill_core
from .skill_optimizer import SkillOptimizer, ParallelExecutor, SmartCache, get_optimizer, get_cache
from .skill_auto_trigger import SkillAutoTrigger, SkillSelfEvolution, get_auto_trigger, get_self_evolution
from .skill_visualization import SkillDashboard, SkillRenderer, VisualStyle


@dataclass
class SkillCall:
    """技能调用记录"""
    skill: str
    version: str
    started_at: str
    latency_ms: float
    success: bool
    result: Any = None
    error: Optional[str] = None
    cache_hit: bool = False


@dataclass
class OrchestrationResult:
    """编排结果"""
    query: str
    skills_used: List[SkillCall]
    total_latency_ms: float
    cache_hit: bool
    final_result: Any
    orchestrator_version: str = "1.0.0"


class SkillOrchestrator:
    """
    技能编排器 - 整合版本管理、性能优化、自动触发、自进化、可视化

    核心功能:
    1. 智能路由 - 基于关键词、模式、上下文自动选择技能
    2. 版本管理 - 技能版本追踪和自进化
    3. 性能优化 - 并行执行、智能缓存、批处理
    4. 自进化 - 基于反馈和性能数据自动改进
    5. 可视化 - 技能状态、性能图表展示
    """

    def __init__(self, skills_dir: str = None):
        # 技能目录
        self.skills_dir = Path(skills_dir) if skills_dir else Path(__file__).parent.parent

        # 核心组件
        self.version_manager = SkillVersionManager(self.skills_dir)
        self.cache = SkillCache(ttl_seconds=300)
        self.optimizer = get_optimizer()
        self.auto_trigger = get_auto_trigger()
        self.self_evolution = get_self_evolution()

        # 并行执行器
        self.executor = ParallelExecutor(max_workers=4)

        # 可视化
        self.dashboard = SkillDashboard()

        # 执行历史
        self.execution_history: List[Dict] = []

        # 初始化仪表板
        self._init_dashboard()

    def _init_dashboard(self):
        """初始化仪表板"""
        # 注册所有技能
        skill_configs = [
            ("source-discovery", "数据源发现与采集", "active", ["ingestion", "http", "pdf"]),
            ("fact-extraction", "市场事实提取与标准化", "active", ["extraction", "normalization"]),
            ("market-intelligence", "伦敦CRE市场指标管理", "active", ["rent", "vacancy", "submarket"]),
            ("comparison", "历史比较与变化检测", "active", ["trend", "change"]),
            ("event-monitor", "新闻与事件监测", "active", ["event", "news"]),
            ("macro-drivers", "宏观因素分析", "active", ["macro", "economy"]),
            ("analysis", "证据驱动分析与风险评估", "active", ["risk", "opportunity"]),
            ("reporting", "报告生成与质量保证", "active", ["report", "qa"]),
            ("verification", "事实核验与发布门禁", "active", ["verify", "gate"]),
            ("orchestrator", "技能编排协调器", "active", ["routing", "orchestration"]),
        ]

        for name, desc, status, tags in skill_configs:
            version = self.version_manager.get_active_version(name)
            version_str = version.version_number if version else "unknown"

            self.dashboard.add_skill(
                name=name,
                description=desc,
                status=status,
                version=version_str,
                tags=tags,
                metrics=self.self_evolution.get_skill_stats(name)
            )

    def orchestrate(self, query: str, context: Dict = None,
                    force_refresh: bool = False) -> OrchestrationResult:
        """
        编排技能执行

        Args:
            query: 用户查询
            context: 执行上下文
            force_refresh: 是否强制刷新（忽略缓存）

        Returns:
            OrchestrationResult: 编排结果
        """
        context = context or {}
        start_time = time.time()

        # 1. 检查缓存
        cache_hit = False
        if not force_refresh:
            cached = self.cache.get("orchestrate", {"query": query})
            if cached:
                return OrchestrationResult(
                    query=query,
                    skills_used=[],
                    total_latency_ms=0,
                    cache_hit=True,
                    final_result=cached
                )

        # 2. 智能触发分析
        skill_sequence = self.auto_trigger.suggest_skill_sequence(query, context)
        trigger_results = self.auto_trigger.match(query, context)

        # 3. 规划执行
        plan = self.optimizer.plan_execution(skill_sequence)

        # 4. 执行技能
        skill_calls = []
        results = {}

        for skill in skill_sequence:
            call_start = time.time()

            # 检查缓存
            skill_cache_hit = False
            cached_result = self.cache.get(skill, {"query": query})

            if cached_result:
                skill_cache_hit = True
                result = cached_result
                success = True
            else:
                # 执行技能
                result, success = self._execute_skill(skill, query, context, results)

                # 更新缓存
                if success:
                    self.cache.set(skill, {"query": query}, result)

            # 记录调用
            call = SkillCall(
                skill=skill,
                version=self.version_manager.get_active_version(skill).version_number if self.version_manager.get_active_version(skill) else "unknown",
                started_at=datetime.now().isoformat(),
                latency_ms=(time.time() - call_start) * 1000,
                success=success,
                result=result if success else None,
                error=str(result) if not success else None,
                cache_hit=skill_cache_hit
            )
            skill_calls.append(call)
            results[skill] = result

            # 更新版本管理器
            self.version_manager.record_usage(
                skill,
                success=success,
                latency_ms=call.latency_ms
            )

            # 更新自进化引擎
            self.self_evolution.record_performance(
                skill,
                latency_ms=call.latency_ms,
                success=success
            )

        # 5. 合成最终结果
        final_result = self._synthesize_results(query, results, trigger_results)

        # 6. 记录历史
        orchestration = OrchestrationResult(
            query=query,
            skills_used=skill_calls,
            total_latency_ms=(time.time() - start_time) * 1000,
            cache_hit=cache_hit,
            final_result=final_result
        )

        self.execution_history.append({
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "skills_used": [s.skill for s in skill_calls],
            "total_latency_ms": orchestration.total_latency_ms,
            "cache_hit": cache_hit
        })

        # 7. 更新缓存
        if not cache_hit:
            self.cache.set("orchestrate", {"query": query}, final_result)

        return orchestration

    def _execute_skill(self, skill: str, query: str,
                       context: Dict, results: Dict) -> tuple:
        """执行单个技能"""
        try:
            # 读取技能文件
            skill_file = self.skills_dir / skill / "SKILL.md"
            if not skill_file.exists():
                return f"Skill {skill} not found", False

            skill_content = skill_file.read_text()

            # 这里应该调用 LLM 执行技能
            # 简化实现：返回技能元信息
            result = {
                "skill": skill,
                "description": skill_content[:100],
                "executed": True,
                "depends_on": list(results.keys())[:-1] if len(results) > 1 else []
            }

            return result, True

        except Exception as e:
            return str(e), False

    def _synthesize_results(self, query: str, results: Dict,
                           trigger_results: List) -> Dict:
        """合成结果"""
        return {
            "query": query,
            "skills_used": list(results.keys()),
            "results": results,
            "trigger_confidence": max((r.confidence for r in trigger_results), default=0),
            "synthesized_at": datetime.now().isoformat()
        }

    def render_dashboard(self) -> str:
        """渲染仪表板"""
        return self.dashboard.render()

    def render_stats(self) -> Dict:
        """渲染统计"""
        return {
            "cache_stats": self.cache.get_stats(),
            "trigger_stats": self.auto_trigger.get_trigger_stats(),
            "evolution_suggestions": len(self.self_evolution.evolution_suggestions),
            "execution_history_count": len(self.execution_history),
            "version_count": sum(len(v) for v in self.version_manager.versions_db.values())
        }

    def get_skill_status(self) -> List[Dict]:
        """获取技能状态"""
        status = []
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                version = self.version_manager.get_active_version(skill_dir.name)
                stats = self.self_evolution.get_skill_stats(skill_dir.name)
                status.append({
                    "name": skill_dir.name,
                    "version": version.version_number if version else "unknown",
                    "status": version.status.value if version else "unknown",
                    "stats": stats
                })
        return status

    def suggest_evolution(self) -> List[Dict]:
        """获取进化建议"""
        return self.self_evolution.get_suggestions()

    def export_config(self) -> Dict:
        """导出配置"""
        return {
            "skills_dir": str(self.skills_dir),
            "auto_trigger_rules": self.auto_trigger.export_rules(),
            "version_count": sum(len(v) for v in self.version_manager.versions_db.values()),
            "cache_config": {
                "ttl_seconds": 300
            }
        }


# 全局实例
_orchestrator: Optional[SkillOrchestrator] = None


def get_orchestrator(skills_dir: str = None) -> SkillOrchestrator:
    """获取编排器实例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SkillOrchestrator(skills_dir)
    return _orchestrator
