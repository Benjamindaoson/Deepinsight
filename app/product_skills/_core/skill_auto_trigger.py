"""
Skill Auto-Trigger - 智能触发引擎与自进化
"""
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class TriggerType(Enum):
    KEYWORD = "keyword"
    PATTERN = "pattern"
    CONTEXT = "context"
    TIME = "time"
    EVENT = "event"
    SEMANTIC = "semantic"
    THRESHOLD = "threshold"


class SkillTrigger(Enum):
    """预定义技能触发类型"""
    SOURCE_DISCOVERY = "source-discovery"
    FACT_EXTRACTION = "fact-extraction"
    MARKET_INTELLIGENCE = "market-intelligence"
    COMPARISON = "comparison"
    EVENT_MONITOR = "event-monitor"
    MACRO_DRIVERS = "macro-drivers"
    ANALYSIS = "analysis"
    VERIFICATION = "verification"
    REPORTING = "reporting"
    ALERTING = "alerting"


@dataclass
class TriggerRule:
    """触发规则"""
    id: str
    trigger_type: TriggerType
    skill: str
    priority: int = 10
    keywords: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    cooldown_seconds: int = 0

    last_triggered: Optional[float] = None

    def can_trigger(self) -> bool:
        """检查是否可以触发"""
        if not self.enabled:
            return False
        if self.cooldown_seconds > 0 and self.last_triggered:
            if time.time() - self.last_triggered < self.cooldown_seconds:
                return False
        return True

    def mark_triggered(self):
        """标记已触发"""
        self.last_triggered = time.time()


@dataclass
class TriggerResult:
    """触发结果"""
    skill: str
    confidence: float
    match_type: str
    matched_content: str
    context: Dict[str, Any] = field(default_factory=dict)


class SkillAutoTrigger:
    """技能自动触发引擎"""

    def __init__(self):
        self.rules: List[TriggerRule] = []
        self.trigger_history: List[Dict] = []
        self._register_default_rules()

    def _register_default_rules(self):
        """注册默认触发规则"""

        # 市场数据查询
        self.add_rule(TriggerRule(
            id="rent-query",
            trigger_type=TriggerType.KEYWORD,
            skill=SkillTrigger.MARKET_INTELLIGENCE.value,
            priority=10,
            keywords=["rent", "租金", "租赁成本", "office cost"]
        ))

        self.add_rule(TriggerRule(
            id="vacancy-query",
            trigger_type=TriggerType.KEYWORD,
            skill=SkillTrigger.MARKET_INTELLIGENCE.value,
            priority=10,
            keywords=["vacancy", "空置率", "空置", "available"]
        ))

        self.add_rule(TriggerRule(
            id="takeup-query",
            trigger_type=TriggerType.KEYWORD,
            skill=SkillTrigger.MARKET_INTELLIGENCE.value,
            priority=10,
            keywords=["take-up", "takeup", "成交", "absorption", "leasing"]
        ))

        # 趋势比较
        self.add_rule(TriggerRule(
            id="trend-query",
            trigger_type=TriggerType.PATTERN,
            skill=SkillTrigger.COMPARISON.value,
            priority=15,
            patterns=[r"trend", r"趋势", r"变化", r"compare.*vs", r"比较.*和"]
        ))

        self.add_rule(TriggerRule(
            id="change-query",
            trigger_type=TriggerType.KEYWORD,
            skill=SkillTrigger.COMPARISON.value,
            priority=15,
            keywords=["change", "变化", "increase", "decrease", "增长", "下降"]
        ))

        # 事件监测
        self.add_rule(TriggerRule(
            id="event-query",
            trigger_type=TriggerType.KEYWORD,
            skill=SkillTrigger.EVENT_MONITOR.value,
            priority=12,
            keywords=["event", "事件", "news", "新闻", "development", "开发项目"]
        ))

        self.add_rule(TriggerRule(
            id="lease-query",
            trigger_type=TriggerType.KEYWORD,
            skill=SkillTrigger.EVENT_MONITOR.value,
            priority=12,
            keywords=["lease", "租约", "letting", "pre-let", "预租"]
        ))

        # 报告生成
        self.add_rule(TriggerRule(
            id="report-query",
            trigger_type=TriggerType.KEYWORD,
            skill=SkillTrigger.REPORTING.value,
            priority=20,
            keywords=["report", "报告", "brief", "简报", "summary", "总结", "generate"]
        ))

        self.add_rule(TriggerRule(
            id="daily-report",
            trigger_type=TriggerType.TIME,
            skill=SkillTrigger.REPORTING.value,
            priority=30,
            conditions={"hour": 8, "minute": 0}
        ))

        self.add_rule(TriggerRule(
            id="weekly-report",
            trigger_type=TriggerType.TIME,
            skill=SkillTrigger.REPORTING.value,
            priority=30,
            conditions={"day": 1, "hour": 8, "minute": 0}
        ))

        # 风险分析
        self.add_rule(TriggerRule(
            id="risk-query",
            trigger_type=TriggerType.KEYWORD,
            skill=SkillTrigger.ANALYSIS.value,
            priority=18,
            keywords=["risk", "风险", "opportunity", "机会", "analyze", "分析"]
        ))

        # 验证
        self.add_rule(TriggerRule(
            id="verify-query",
            trigger_type=TriggerType.KEYWORD,
            skill=SkillTrigger.VERIFICATION.value,
            priority=25,
            keywords=["verify", "核验", "check", "检查", "fact", "事实"]
        ))

        # 预警
        self.add_rule(TriggerRule(
            id="alert-threshold",
            trigger_type=TriggerType.THRESHOLD,
            skill=SkillTrigger.ALERTING.value,
            priority=35,
            conditions={"metric": "any", "threshold_breach": True}
        ))

        # 宏观因素
        self.add_rule(TriggerRule(
            id="macro-query",
            trigger_type=TriggerType.KEYWORD,
            skill=SkillTrigger.MACRO_DRIVERS.value,
            priority=12,
            keywords=["macro", "宏观", "interest rate", "利率", "economy", "经济", "employment", "就业"]
        ))

        # 来源发现
        self.add_rule(TriggerRule(
            id="source-discovery",
            trigger_type=TriggerType.KEYWORD,
            skill=SkillTrigger.SOURCE_DISCOVERY.value,
            priority=5,
            keywords=["new source", "discover", "add data", "新数据源"]
        ))

    def add_rule(self, rule: TriggerRule):
        """添加触发规则"""
        self.rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """移除触发规则"""
        for i, rule in enumerate(self.rules):
            if rule.id == rule_id:
                self.rules.pop(i)
                return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """启用规则"""
        for rule in self.rules:
            if rule.id == rule_id:
                rule.enabled = True
                return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """禁用规则"""
        for rule in self.rules:
            if rule.id == rule_id:
                rule.enabled = False
                return True
        return False

    def match(self, query: str, context: Dict[str, Any] = None) -> List[TriggerResult]:
        """匹配触发规则"""
        results = []
        query_lower = query.lower()

        for rule in self.rules:
            if not rule.can_trigger():
                continue

            confidence = 0.0
            matched_content = ""

            # 关键词匹配
            if rule.trigger_type == TriggerType.KEYWORD:
                for keyword in rule.keywords:
                    if keyword.lower() in query_lower:
                        confidence = 0.8
                        matched_content = keyword
                        break

            # 模式匹配
            elif rule.trigger_type == TriggerType.PATTERN:
                for pattern in rule.patterns:
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        confidence = 0.9
                        matched_content = match.group()
                        break

            # 时间触发
            elif rule.trigger_type == TriggerType.TIME:
                now = datetime.now()
                conditions = rule.conditions
                hour_match = conditions.get("hour") is None or now.hour == conditions["hour"]
                minute_match = conditions.get("minute") is None or now.minute == conditions["minute"]
                day_match = conditions.get("day") is None or now.weekday() == conditions["day"]

                if hour_match and minute_match and day_match:
                    confidence = 1.0
                    matched_content = f"time: {now.isoformat()}"

            # 阈值触发
            elif rule.trigger_type == TriggerType.THRESHOLD:
                if context and context.get("threshold_breach"):
                    confidence = 1.0
                    matched_content = "threshold_breach"

            # 事件触发
            elif rule.trigger_type == TriggerType.EVENT:
                event = context.get("event") if context else None
                if event == rule.conditions.get("event"):
                    confidence = 0.95
                    matched_content = str(event)

            if confidence > 0:
                results.append(TriggerResult(
                    skill=rule.skill,
                    confidence=confidence,
                    match_type=rule.trigger_type.value,
                    matched_content=matched_content,
                    context={"rule_id": rule.id, "priority": rule.priority}
                ))
                rule.mark_triggered()

        # 按置信度和优先级排序
        results.sort(key=lambda r: (r.confidence, r.context.get("priority", 0)), reverse=True)

        # 记录历史
        self.trigger_history.append({
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "results": [{"skill": r.skill, "confidence": r.confidence} for r in results]
        })

        return results

    def suggest_skill_sequence(self, query: str, context: Dict = None) -> List[str]:
        """建议技能执行顺序"""
        matches = self.match(query, context)

        if not matches:
            return []

        # 构建依赖图
        dependencies = self._get_skill_dependencies()

        # 拓扑排序
        skill_set = set(r.skill for r in matches)
        ordered = self._topological_sort(skill_set, dependencies)

        return ordered

    def _get_skill_dependencies(self) -> Dict[str, Set[str]]:
        """获取技能依赖关系"""
        return {
            "reporting": {"market-intelligence", "comparison", "event-monitor"},
            "alerting": {"comparison", "verification"},
            "analysis": {"market-intelligence", "comparison", "event-monitor", "macro-drivers"},
            "comparison": {"market-intelligence"},
            "market-intelligence": set(),
            "event-monitor": set(),
            "macro-drivers": set(),
            "verification": set(),
            "source-discovery": set(),
            "fact-extraction": {"source-discovery"}
        }

    def _topological_sort(self, skills: Set[str], dependencies: Dict[str, Set[str]]) -> List[str]:
        """拓扑排序"""
        result = []
        visited = set()

        def visit(skill: str):
            if skill in visited:
                return
            visited.add(skill)
            for dep in dependencies.get(skill, set()):
                if dep in skills:
                    visit(dep)
            result.append(skill)

        for skill in skills:
            visit(skill)

        return result

    def get_trigger_stats(self) -> Dict[str, Any]:
        """获取触发统计"""
        skill_counts = {}
        for entry in self.trigger_history:
            for r in entry["results"]:
                skill = r["skill"]
                skill_counts[skill] = skill_counts.get(skill, 0) + 1

        return {
            "total_triggers": len(self.trigger_history),
            "skill_counts": skill_counts,
            "active_rules": sum(1 for r in self.rules if r.enabled),
            "disabled_rules": sum(1 for r in self.rules if not r.enabled)
        }

    def export_rules(self) -> List[Dict]:
        """导出规则"""
        return [{
            "id": r.id,
            "trigger_type": r.trigger_type.value,
            "skill": r.skill,
            "priority": r.priority,
            "keywords": r.keywords,
            "patterns": r.patterns,
            "conditions": r.conditions,
            "enabled": r.enabled,
            "cooldown_seconds": r.cooldown_seconds
        } for r in self.rules]

    def import_rules(self, rules: List[Dict]):
        """导入规则"""
        self.rules = [
            TriggerRule(
                id=r["id"],
                trigger_type=TriggerType(r["trigger_type"]),
                skill=r["skill"],
                priority=r.get("priority", 10),
                keywords=r.get("keywords", []),
                patterns=r.get("patterns", []),
                conditions=r.get("conditions", {}),
                enabled=r.get("enabled", True),
                cooldown_seconds=r.get("cooldown_seconds", 0)
            )
            for r in rules
        ]


class SkillSelfEvolution:
    """技能自进化引擎"""

    def __init__(self):
        self.feedback_history: List[Dict] = []
        self.performance_history: Dict[str, List[Dict]] = {}
        self.evolution_suggestions: List[Dict] = []

    def record_feedback(self, skill: str, query: str, response: str,
                       helpful: bool, error: Optional[str] = None):
        """记录用户反馈"""
        entry = {
            "skill": skill,
            "query": query,
            "response_length": len(response),
            "helpful": helpful,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        self.feedback_history.append(entry)

        # 更新性能历史
        if skill not in self.performance_history:
            self.performance_history[skill] = []

        self.performance_history[skill].append({
            "helpful": helpful,
            "timestamp": datetime.now().isoformat()
        })

        # 检查是否需要进化
        self._check_evolution_needed(skill)

    def _check_evolution_needed(self, skill: str):
        """检查是否需要进化"""
        history = self.performance_history.get(skill, [])
        if len(history) < 10:
            return

        recent = history[-10:]
        helpful_rate = sum(1 for h in recent if h["helpful"]) / len(recent)

        if helpful_rate < 0.7:
            self.evolution_suggestions.append({
                "skill": skill,
                "reason": "low_helpfulness",
                "helpful_rate": helpful_rate,
                "suggestion": "Consider improving skill instructions or adding more examples",
                "timestamp": datetime.now().isoformat()
            })

    def record_performance(self, skill: str, latency_ms: float,
                          success: bool, error: Optional[str] = None):
        """记录性能数据"""
        if skill not in self.performance_history:
            self.performance_history[skill] = []

        self.performance_history[skill].append({
            "latency_ms": latency_ms,
            "success": success,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })

        # 检查性能下降
        self._check_performance_degradation(skill)

    def _check_performance_degradation(self, skill: str):
        """检查性能下降"""
        history = self.performance_history.get(skill, [])
        if len(history) < 20:
            return

        recent = history[-20:]
        recent_avg = sum(h.get("latency_ms", 0) for h in recent) / len(recent)

        older = history[-40:-20] if len(history) >= 40 else history[:-20]
        if older:
            older_avg = sum(h.get("latency_ms", 0) for h in older) / len(older)

            if recent_avg > older_avg * 1.5:
                self.evolution_suggestions.append({
                    "skill": skill,
                    "reason": "performance_degradation",
                    "recent_avg_ms": recent_avg,
                    "older_avg_ms": older_avg,
                    "degradation_pct": (recent_avg - older_avg) / older_avg * 100,
                    "suggestion": "Consider optimizing skill or reducing output requirements",
                    "timestamp": datetime.now().isoformat()
                })

    def get_suggestions(self, skill: Optional[str] = None) -> List[Dict]:
        """获取进化建议"""
        if skill:
            return [s for s in self.evolution_suggestions if s["skill"] == skill]
        return self.evolution_suggestions

    def get_skill_stats(self, skill: str) -> Dict[str, Any]:
        """获取技能统计"""
        history = self.performance_history.get(skill, [])
        if not history:
            return {"status": "no_data"}

        recent = history[-20:]
        return {
            "total_calls": len(history),
            "recent_calls": len(recent),
            "recent_success_rate": sum(1 for h in recent if h.get("success", False)) / len(recent),
            "recent_avg_latency_ms": sum(h.get("latency_ms", 0) for h in recent) / len(recent),
            "feedback_count": len([f for f in self.feedback_history if f["skill"] == skill]),
            "feedback_helpful_rate": sum(1 for f in self.feedback_history
                                        if f["skill"] == skill and f.get("helpful", False)) /
                                       max(1, len([f for f in self.feedback_history if f["skill"] == skill]))
        }


# 全局实例
_auto_trigger: Optional[SkillAutoTrigger] = None
_self_evolution: Optional[SkillSelfEvolution] = None


def get_auto_trigger() -> SkillAutoTrigger:
    """获取自动触发引擎"""
    global _auto_trigger
    if _auto_trigger is None:
        _auto_trigger = SkillAutoTrigger()
    return _auto_trigger


def get_self_evolution() -> SkillSelfEvolution:
    """获取自进化引擎"""
    global _self_evolution
    if _self_evolution is None:
        _self_evolution = SkillSelfEvolution()
    return _self_evolution
