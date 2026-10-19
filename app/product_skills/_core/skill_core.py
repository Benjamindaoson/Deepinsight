"""
Skill Core - 版本化、自进化、智能触发的核心基础设施
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set


class SkillVersionStatus(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


@dataclass
class SkillVersion:
    """技能版本记录"""
    version_id: str
    version_number: str  # semver: major.minor.patch
    content_hash: str  # SHA-256 of SKILL.md content
    created_at: str
    status: SkillVersionStatus
    changelog: str
    author: str = "system"
    test_results: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    usage_count: int = 0
    success_rate: float = 1.0

    @classmethod
    def from_content(cls, content: str, version: str, changelog: str = "") -> "SkillVersion":
        return cls(
            version_id=hashlib.sha256(f"{version}{content}".encode()).hexdigest()[:16],
            version_number=version,
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
            created_at=datetime.now().isoformat(),
            status=SkillVersionStatus.DRAFT,
            changelog=changelog
        )


@dataclass
class SkillEvolutionEvent:
    """技能进化事件"""
    event_id: str
    skill_name: str
    event_type: str  # usage_feedback, performance_drop, new_capability, bug_fix
    timestamp: str
    trigger: str
    evidence: Dict[str, Any]
    recommendation: Optional[str] = None
    auto_applied: bool = False


class SkillVersionManager:
    """技能版本管理器 - 支持自进化"""

    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)
        self.versions_db: Dict[str, List[SkillVersion]] = {}
        self.evolution_events: List[SkillEvolutionEvent] = []
        self._load_versions()

    def _load_versions(self):
        """从文件系统加载版本信息"""
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                skill_name = skill_dir.name
                versions_file = skill_dir / ".versions.json"
                if versions_file.exists():
                    data = json.loads(versions_file.read_text())
                    self.versions_db[skill_name] = [
                        SkillVersion(**v) for v in data.get("versions", [])
                    ]
                else:
                    # 从当前内容创建初始版本
                    content = (skill_dir / "SKILL.md").read_text()
                    v = SkillVersion.from_content(content, "1.0.0", "Initial version")
                    v.status = SkillVersionStatus.ACTIVE
                    self.versions_db[skill_name] = [v]
                    self._save_versions(skill_name)

    def _save_versions(self, skill_name: str):
        """保存版本信息"""
        skill_dir = self.skills_dir / skill_name
        versions_file = skill_dir / ".versions.json"
        versions_file.write_text(json.dumps({
            "skill_name": skill_name,
            "versions": [vars(v) for v in self.versions_db.get(skill_name, [])]
        }, indent=2, ensure_ascii=False))

    def register_version(self, skill_name: str, content: str,
                        changelog: str, author: str = "system") -> SkillVersion:
        """注册新版本"""
        existing = self.versions_db.get(skill_name, [])

        # 计算新版本号
        if existing:
            last_ver = existing[-1].version_number
            new_ver = self._bump_version(last_ver, changelog)
        else:
            new_ver = "1.0.0"

        version = SkillVersion.from_content(content, new_ver, changelog)
        version.author = author
        version.status = SkillVersionStatus.ACTIVE

        # 停用旧版本
        for v in existing:
            if v.status == SkillVersionStatus.ACTIVE:
                v.status = SkillVersionStatus.DEPRECATED

        self.versions_db.setdefault(skill_name, []).append(version)
        self._save_versions(skill_name)
        return version

    def _bump_version(self, current: str, changelog: str) -> str:
        """智能版本号提升"""
        parts = current.split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

        # 根据变更类型决定升级级别
        if "breaking" in changelog.lower() or "breaking" in changelog.lower():
            major += 1; minor = 0; patch = 0
        elif "feature" in changelog.lower() or "capability" in changelog.lower():
            minor += 1; patch = 0
        else:
            patch += 1

        return f"{major}.{minor}.{patch}"

    def record_usage(self, skill_name: str, success: bool, latency_ms: float):
        """记录技能使用情况 - 用于自进化分析"""
        if skill_name not in self.versions_db or not self.versions_db[skill_name]:
            return

        v = self.versions_db[skill_name][-1]
        v.usage_count += 1
        v.performance_metrics["latency_ms"] = latency_ms
        v.performance_metrics["last_used"] = datetime.now().isoformat()

        # 滑动平均计算成功率
        total = v.usage_count
        v.success_rate = (v.success_rate * (total - 1) + (1 if success else 0)) / total

        # 检测性能下降，触发进化
        if v.performance_metrics.get("latency_ms", 0) > 5000:  # >5s
            self._trigger_evolution(skill_name, "performance_drop", {
                "latency_ms": latency_ms,
                "threshold": 5000
            })

        self._save_versions(skill_name)

    def _trigger_evolution(self, skill_name: str, event_type: str, evidence: Dict):
        """触发技能自进化"""
        event = SkillEvolutionEvent(
            event_id=hashlib.md5(f"{skill_name}{time.time()}".encode()).hexdigest()[:12],
            skill_name=skill_name,
            event_type=event_type,
            timestamp=datetime.now().isoformat(),
            trigger="auto",
            evidence=evidence,
            recommendation=self._generate_evolution_recommendation(event_type, evidence)
        )
        self.evolution_events.append(event)

        # 根据事件类型决定是否自动应用
        if event_type == "performance_drop":
            event.auto_applied = True

    def _generate_evolution_recommendation(self, event_type: str,
                                         evidence: Dict) -> str:
        """生成进化建议"""
        recommendations = {
            "performance_drop": "建议添加更多上下文缓存，或减少输出长度限制",
            "low_success_rate": "建议简化技能指令，或添加更多示例",
            "new_capability": "考虑拆分为独立技能或合并到现有技能",
            "bug_fix": "自动更新版本号并记录修复内容"
        }
        return recommendations.get(event_type, "需要人工评估")

    def get_active_version(self, skill_name: str) -> Optional[SkillVersion]:
        """获取当前激活版本"""
        versions = self.versions_db.get(skill_name, [])
        for v in reversed(versions):
            if v.status == SkillVersionStatus.ACTIVE:
                return v
        return versions[-1] if versions else None

    def get_evolution_suggestions(self) -> List[SkillEvolutionEvent]:
        """获取进化建议"""
        return [e for e in self.evolution_events if not e.auto_applied]


class SkillCache:
    """技能结果缓存 - 减轻Agent负担"""

    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0

    def make_key(self, skill_name: str, params: Dict) -> str:
        """生成缓存键"""
        param_str = json.dumps(params, sort_keys=True, default=str)
        return f"{skill_name}:{hashlib.md5(param_str.encode()).hexdigest()}"

    def get(self, skill_name: str, params: Dict) -> Optional[Any]:
        """获取缓存结果"""
        key = self.make_key(skill_name, params)
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["timestamp"] < self.ttl:
                self.hits += 1
                return entry["result"]
            else:
                del self.cache[key]
        self.misses += 1
        return None

    def set(self, skill_name: str, params: Dict, result: Any):
        """设置缓存结果"""
        key = self.make_key(skill_name, params)
        self.cache[key] = {
            "result": result,
            "timestamp": time.time(),
            "skill": skill_name
        }

    def invalidate(self, skill_name: str = None):
        """使缓存失效"""
        if skill_name:
            self.cache = {k: v for k, v in self.cache.items() if v["skill"] != skill_name}
        else:
            self.cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / total if total > 0 else 0,
            "size": len(self.cache)
        }


class SkillTriggerEngine:
    """技能智能触发引擎"""

    def __init__(self):
        self.triggers: Dict[str, List[Dict[str, Any]]] = {
            "keyword": [],
            "pattern": [],
            "context": [],
            "time": [],
            "event": []
        }
        self._register_default_triggers()

    def _register_default_triggers(self):
        """注册默认触发器"""
        # 关键词触发
        self.register_trigger("keyword", {
            "keywords": ["rent", "租金", "vacancy", "空置", "market", "市场"],
            "skill": "market-intelligence",
            "priority": 10
        })
        self.register_trigger("keyword", {
            "keywords": ["trend", "趋势", "compare", "比较", "变化"],
            "skill": "comparison",
            "priority": 15
        })
        self.register_trigger("keyword", {
            "keywords": ["event", "事件", "news", "新闻", "development", "开发"],
            "skill": "event-monitor",
            "priority": 12
        })
        self.register_trigger("keyword", {
            "keywords": ["report", "报告", "brief", "简报", "summary", "总结"],
            "skill": "reporting",
            "priority": 20
        })
        self.register_trigger("keyword", {
            "keywords": ["macro", "宏观", "interest", "利率", "economy", "经济"],
            "skill": "macro-drivers",
            "priority": 12
        })
        self.register_trigger("keyword", {
            "keywords": ["risk", "风险", "opportunity", "机会", "analyze", "分析"],
            "skill": "analysis",
            "priority": 18
        })
        self.register_trigger("keyword", {
            "keywords": ["verify", "核验", "fact", "事实", "check", "检查"],
            "skill": "verification",
            "priority": 25
        })

        # 模式触发
        self.register_trigger("pattern", {
            "pattern": r"what is.*trend|最近.*趋势",
            "skill": "comparison",
            "priority": 18
        })
        self.register_trigger("pattern", {
            "pattern": r"compare.*vs|比较.*和",
            "skill": "comparison",
            "priority": 20
        })

        # 事件触发
        self.register_trigger("event", {
            "event": "scheduled_daily",
            "skill": "reporting",
            "priority": 30
        })
        self.register_trigger("event", {
            "event": "scheduled_weekly",
            "skill": "reporting",
            "priority": 30
        })
        self.register_trigger("event", {
            "event": "threshold_breached",
            "skill": "alerting",
            "priority": 35
        })

    def register_trigger(self, trigger_type: str, config: Dict[str, Any]):
        """注册触发器"""
        self.triggers[trigger_type].append(config)

    def match(self, query: str, context: Dict = None) -> List[Dict[str, Any]]:
        """匹配触发器，返回排序的技能列表"""
        matches = []
        query_lower = query.lower()

        # 关键词匹配
        for trigger in self.triggers["keyword"]:
            for kw in trigger["keywords"]:
                if kw.lower() in query_lower:
                    matches.append({
                        "skill": trigger["skill"],
                        "priority": trigger["priority"],
                        "match_type": "keyword",
                        "matched": kw
                    })
                    break

        # 模式匹配
        import re
        for trigger in self.triggers["pattern"]:
            if re.search(trigger["pattern"], query, re.I):
                matches.append({
                    "skill": trigger["skill"],
                    "priority": trigger["priority"] + 5,  # 模式匹配优先级更高
                    "match_type": "pattern",
                    "matched": trigger["pattern"]
                })

        # 上下文匹配
        if context:
            for skill in context.get("required_skills", []):
                matches.append({
                    "skill": skill,
                    "priority": 40,  # 明确要求的技能优先级最高
                    "match_type": "context"
                })

        # 事件触发
        for trigger in self.triggers["event"]:
            event = context.get("event") if context else None
            if event == trigger["event"]:
                matches.append({
                    "skill": trigger["skill"],
                    "priority": trigger["priority"],
                    "match_type": "event"
                })

        # 去重并排序
        seen = set()
        unique_matches = []
        for m in sorted(matches, key=lambda x: -x["priority"]):
            if m["skill"] not in seen:
                seen.add(m["skill"])
                unique_matches.append(m)

        return unique_matches

    def suggest_skill_sequence(self, query: str, context: Dict = None) -> List[str]:
        """建议技能执行顺序"""
        matches = self.match(query, context)

        # 基于依赖关系的序列规划
        skill_sequence = []
        for m in matches:
            skill = m["skill"]
            deps = self._get_dependencies(skill)
            for dep in deps:
                if dep not in skill_sequence:
                    skill_sequence.append(dep)
            if skill not in skill_sequence:
                skill_sequence.append(skill)

        return skill_sequence

    def _get_dependencies(self, skill: str) -> List[str]:
        """获取技能依赖"""
        dependencies = {
            "reporting": ["market-intelligence", "comparison"],
            "alerting": ["comparison", "verification"],
            "analysis": ["market-intelligence", "event-monitor", "macro-drivers"],
            "comparison": ["market-intelligence"]
        }
        return dependencies.get(skill, [])


class SkillOrchestrator:
    """技能编排器 - 智能协调多个技能"""

    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)
        self.version_manager = SkillVersionManager(skills_dir)
        self.cache = SkillCache()
        self.trigger_engine = SkillTriggerEngine()
        self.execution_history: List[Dict] = []

    def orchestrate(self, query: str, context: Dict = None) -> Dict[str, Any]:
        """编排技能执行"""
        context = context or {}

        # 1. 智能触发分析
        skill_sequence = self.trigger_engine.suggest_skill_sequence(query, context)
        trigger_matches = self.trigger_engine.match(query, context)

        # 2. 检查缓存
        cached = self.cache.get("orchestrate", {"query": query, "context": context})
        if cached:
            return {**cached, "cache_hit": True}

        # 3. 执行技能链
        results = {}
        shared_context = {"query": query, "history": []}

        for skill_name in skill_sequence:
            start_time = time.time()

            try:
                # 获取技能版本
                version = self.version_manager.get_active_version(skill_name)

                # 检查缓存
                skill_result = self.cache.get(skill_name, {"query": query})

                if skill_result is None:
                    # 实际执行技能（这里简化，实际需要调用LLM）
                    skill_result = self._execute_skill(skill_name, query, shared_context)
                    self.cache.set(skill_name, {"query": query}, skill_result)

                # 记录执行
                latency = time.time() - start_time
                self.version_manager.record_usage(skill_name, True, latency * 1000)

                results[skill_name] = {
                    "result": skill_result,
                    "latency_ms": latency * 1000,
                    "version": version.version_number if version else "unknown"
                }

                shared_context["history"].append({
                    "skill": skill_name,
                    "timestamp": datetime.now().isoformat()
                })

            except Exception as e:
                self.version_manager.record_usage(skill_name, False, 0)
                results[skill_name] = {
                    "error": str(e),
                    "latency_ms": (time.time() - start_time) * 1000
                }

        # 4. 合成最终结果
        orchestration_result = {
            "query": query,
            "skills_used": skill_sequence,
            "skill_results": results,
            "trigger_matches": trigger_matches,
            "shared_context": shared_context,
            "timestamp": datetime.now().isoformat(),
            "cache_hit": False
        }

        # 5. 缓存结果
        self.cache.set("orchestrate", {"query": query, "context": context}, orchestration_result)

        return orchestration_result

    def _execute_skill(self, skill_name: str, query: str,
                       context: Dict) -> Dict[str, Any]:
        """执行单个技能"""
        skill_file = self.skills_dir / skill_name / "SKILL.md"
        if not skill_file.exists():
            return {"error": f"Skill {skill_name} not found"}

        content = skill_file.read_text()

        # 这里应该调用LLM执行技能
        # 简化实现
        return {
            "skill": skill_name,
            "content_preview": content[:200],
            "executed": True
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取编排统计"""
        return {
            "cache_stats": self.cache.get_stats(),
            "version_count": sum(len(v) for v in self.version_manager.versions_db.values()),
            "active_triggers": sum(len(t) for t in self.trigger_engine.triggers.values()),
            "evolution_events": len(self.version_manager.evolution_events)
        }


# 全局实例
_skill_core: Optional[SkillOrchestrator] = None


def get_skill_core(skills_dir: str = None) -> SkillOrchestrator:
    """获取技能核心实例"""
    global _skill_core
    if _skill_core is None:
        from pathlib import Path
        skills_path = skills_dir or Path(__file__).parent.parent
        _skill_core = SkillOrchestrator(Path(skills_path))
    return _skill_core
