"""
Skill Performance Optimizer - 性能优化、并行执行、结果缓存
"""
import asyncio
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import threading


@dataclass
class PerformanceMetrics:
    """性能指标"""
    skill_name: str
    version: str
    latency_ms: float
    tokens_used: int = 0
    cache_hit: bool = False
    parallel_execution: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def is_slow(self) -> bool:
        return self.latency_ms > 2000

    @property
    def is_expensive(self) -> bool:
        return self.tokens_used > 5000


@dataclass
class ExecutionPlan:
    """执行计划"""
    parallel_groups: List[List[str]]  # 可以并行执行的技能组
    sequential_chains: List[str]  # 必须顺序执行的技能链
    estimated_latency_ms: float
    cache_opportunities: List[str]  # 可缓存的结果


class SkillOptimizer:
    """技能性能优化器"""

    def __init__(self):
        self.metrics_history: List[PerformanceMetrics] = []
        self._lock = threading.RLock()

        # 技能依赖关系图
        self.dependencies: Dict[str, Set[str]] = {
            "reporting": {"market-intelligence", "comparison", "event-monitor"},
            "alerting": {"comparison", "verification"},
            "analysis": {"market-intelligence", "comparison", "event-monitor", "macro-drivers"},
            "comparison": {"market-intelligence"},
            "market-intelligence": set(),
            "event-monitor": set(),
            "macro-drivers": set(),
            "verification": set(),
            "orchestrator": set()
        }

        # 技能执行时间预估（基于历史）
        self.execution_estimates: Dict[str, float] = {
            "market-intelligence": 200,
            "comparison": 150,
            "event-monitor": 300,
            "macro-drivers": 250,
            "analysis": 400,
            "verification": 100,
            "reporting": 500,
            "alerting": 200,
            "orchestrator": 50
        }

    def record_metric(self, metric: PerformanceMetrics):
        """记录性能指标"""
        with self._lock:
            self.metrics_history.append(metric)
            # 保持最近1000条记录
            if len(self.metrics_history) > 1000:
                self.metrics_history = self.metrics_history[-1000:]

    def get_avg_latency(self, skill_name: str, version: str = None) -> float:
        """获取平均延迟"""
        with self._lock:
            relevant = [m for m in self.metrics_history
                      if m.skill_name == skill_name
                      and (version is None or m.version == version)]
            if not relevant:
                return self.execution_estimates.get(skill_name, 300)
            return sum(m.latency_ms for m in relevant) / len(relevant)

    def plan_execution(self, skills: List[str]) -> ExecutionPlan:
        """规划最优执行顺序"""

        # 1. 构建依赖拓扑排序
        ordered = self._topological_sort(skills)

        # 2. 识别并行机会
        parallel_groups = []
        sequential_chains = []

        current_group = []
        for skill in ordered:
            deps = self.dependencies.get(skill, set())
            # 如果有依赖不在当前组，需要等待
            if deps & set(current_group):
                if current_group:
                    parallel_groups.append(current_group)
                current_group = [skill]
            elif deps <= set(sum(parallel_groups, [])):
                # 所有依赖已经执行完成，可以并行
                current_group.append(skill)
            else:
                # 有依赖未执行，先执行依赖
                if current_group:
                    parallel_groups.append(current_group)
                current_group = [skill]

        if current_group:
            parallel_groups.append(current_group)

        # 3. 估算总延迟
        estimated_latency = 0
        for group in parallel_groups:
            group_latency = max(self.get_avg_latency(s) for s in group)
            estimated_latency += group_latency

        # 4. 识别缓存机会
        cache_opportunities = []
        for skill in skills:
            if self._should_cache(skill):
                cache_opportunities.append(skill)

        return ExecutionPlan(
            parallel_groups=parallel_groups,
            sequential_chains=sequential_chains,
            estimated_latency_ms=estimated_latency,
            cache_opportunities=cache_opportunities
        )

    def _topological_sort(self, skills: List[str]) -> List[str]:
        """拓扑排序"""
        result = []
        visited = set()

        def visit(skill: str):
            if skill in visited:
                return
            visited.add(skill)
            # 先访问依赖
            for dep in self.dependencies.get(skill, set()):
                if dep in skills:
                    visit(dep)
            result.append(skill)

        for skill in skills:
            visit(skill)

        return result

    def _should_cache(self, skill: str) -> bool:
        """判断是否应该缓存"""
        # 基于技能的特性和使用频率
        cacheable = {"market-intelligence", "comparison", "macro-drivers"}
        return skill in cacheable


class ParallelExecutor:
    """并行执行器"""

    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.optimizer = SkillOptimizer()

    async def execute_parallel(self,
                            skills: List[str],
                            executor_func: Callable[[str], Dict]) -> Dict[str, Any]:
        """并行执行技能"""

        # 1. 获取执行计划
        plan = self.optimizer.plan_execution(skills)

        results = {}

        # 2. 分组并行执行
        for group_idx, group in enumerate(plan.parallel_groups):
            group_start = time.time()

            # 并行执行组内技能
            futures = {
                skill: self.executor.submit(executor_func, skill)
                for skill in group
            }

            # 收集结果
            for skill, future in futures.items():
                try:
                    result = future.result(timeout=30)
                    results[skill] = result

                    # 记录指标
                    self.optimizer.record_metric(PerformanceMetrics(
                        skill_name=skill,
                        version="current",
                        latency_ms=(time.time() - group_start) * 1000,
                        parallel_execution=len(group) > 1
                    ))
                except Exception as e:
                    results[skill] = {"error": str(e)}

        return results

    def shutdown(self):
        """关闭执行器"""
        self.executor.shutdown(wait=True)


class SmartCache:
    """智能缓存 - 多层缓存策略"""

    def __init__(self):
        # L1: 精确匹配缓存
        self.l1_exact: Dict[str, Tuple[Any, float]] = {}  # key -> (value, timestamp)

        # L2: 语义相似缓存
        self.l2_semantic: Dict[str, List[Tuple[Dict, float]]] = {}  # skill -> [(embedding, result)]

        # L3: 模式缓存
        self.l3_pattern: Dict[str, Any] = {}  # pattern -> result

        self.l1_ttl = 60  # 1分钟
        self.l2_ttl = 300  # 5分钟
        self.l3_ttl = 3600  # 1小时

        self.hits = {"l1": 0, "l2": 0, "l3": 0, "miss": 0}
        self._lock = threading.RLock()

    def _make_key(self, skill: str, params: Dict) -> str:
        """生成精确缓存键"""
        param_str = json.dumps(params, sort_keys=True, default=str)
        return f"{skill}:{hashlib.md5(param_str.encode()).hexdigest()}"

    def get(self, skill: str, params: Dict) -> Optional[Any]:
        """获取缓存（多层检查）"""
        key = self._make_key(skill, params)
        now = time.time()

        with self._lock:
            # L1 精确匹配
            if key in self.l1_exact:
                value, timestamp = self.l1_exact[key]
                if now - timestamp < self.l1_ttl:
                    self.hits["l1"] += 1
                    return value
                del self.l1_exact[key]

            # L2 语义相似（简化实现）
            if skill in self.l2_semantic:
                for embedding, result in self.l2_semantic[skill]:
                    if self._semantic_match(params, embedding):
                        self.hits["l2"] += 1
                        return result

            # L3 模式匹配（简化实现）
            for pattern, result in self.l3_pattern.items():
                if self._pattern_match(key, pattern):
                    self.hits["l3"] += 1
                    return result

            self.hits["miss"] += 1
            return None

    def set(self, skill: str, params: Dict, result: Any,
            level: str = "l1", pattern: str = None):
        """设置缓存"""
        key = self._make_key(skill, params)
        now = time.time()

        with self._lock:
            if level == "l1":
                self.l1_exact[key] = (result, now)
            elif level == "l2":
                self.l2_semantic.setdefault(skill, []).append((params, result))
            elif level == "l3" and pattern:
                self.l3_pattern[pattern] = result

    def _semantic_match(self, params1: Dict, params2: Dict) -> bool:
        """语义匹配（简化实现：检查关键词重叠）"""
        # 简化：检查主要键值对是否相同
        return params1.get("query", "").split()[:3] == params2.get("query", "").split()[:3]

    def _pattern_match(self, key: str, pattern: str) -> bool:
        """模式匹配"""
        return pattern in key

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            total = sum(self.hits.values())
            return {
                "l1_hits": self.hits["l1"],
                "l2_hits": self.hits["l2"],
                "l3_hits": self.hits["l3"],
                "misses": self.hits["miss"],
                "hit_rate": (total - self.hits["miss"]) / total if total > 0 else 0,
                "l1_size": len(self.l1_exact),
                "l2_size": sum(len(v) for v in self.l2_semantic.values()),
                "l3_size": len(self.l3_pattern)
            }

    def invalidate(self, skill: str = None):
        """使缓存失效"""
        with self._lock:
            if skill:
                if skill in self.l2_semantic:
                    self.l2_semantic[skill].clear()
            else:
                self.l1_exact.clear()
                self.l2_semantic.clear()
                self.l3_pattern.clear()


class SkillBatcher:
    """技能批处理器 - 合并相似请求"""

    def __init__(self, batch_window_ms: int = 100):
        self.batch_window = batch_window_ms / 1000
        self.pending: Dict[str, List[Dict]] = {}
        self.results: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def add_request(self, skill: str, params: Dict) -> str:
        """添加请求到批处理队列"""
        batch_key = self._make_batch_key(skill, params)

        with self._lock:
            if batch_key not in self.pending:
                self.pending[batch_key] = []
            request_id = f"{batch_key}:{len(self.pending[batch_key])}"
            self.pending[batch_key].append({
                "id": request_id,
                "params": params,
                "timestamp": time.time()
            })
            return request_id

    def get_batch(self, skill: str) -> Optional[List[Dict]]:
        """获取可执行的批次"""
        with self._lock:
            batch_key = self._make_batch_key(skill, {})

            # 查找所有以skill开头的批次
            matching = [(k, v) for k, v in self.pending.items()
                       if k.startswith(skill + ":")]

            for batch_key, requests in matching:
                # 检查是否满足执行条件
                if not requests:
                    continue

                first_time = requests[0]["timestamp"]
                if time.time() - first_time >= self.batch_window or len(requests) >= 10:
                    # 达到时间窗口或数量限制，执行批次
                    del self.pending[batch_key]
                    return requests

            return None

    def _make_batch_key(self, skill: str, params: Dict) -> str:
        """生成批次键"""
        # 简化：按技能分组
        return skill

    def set_result(self, request_id: str, result: Any):
        """设置请求结果"""
        with self._lock:
            self.results[request_id] = result

    def get_result(self, request_id: str) -> Optional[Any]:
        """获取请求结果"""
        with self._lock:
            return self.results.get(request_id)


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self.current_execution: Dict[str, float] = {}  # skill -> start_time
        self.skill_stats: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def start_execution(self, skill: str):
        """开始执行监控"""
        with self._lock:
            self.current_execution[skill] = time.time()

    def end_execution(self, skill: str, success: bool = True):
        """结束执行监控"""
        with self._lock:
            if skill in self.current_execution:
                latency = (time.time() - self.current_execution[skill]) * 1000
                del self.current_execution[skill]

                if skill not in self.skill_stats:
                    self.skill_stats[skill] = {
                        "count": 0,
                        "total_latency": 0,
                        "successes": 0,
                        "failures": 0,
                        "slow_count": 0
                    }

                stats = self.skill_stats[skill]
                stats["count"] += 1
                stats["total_latency"] += latency
                if success:
                    stats["successes"] += 1
                else:
                    stats["failures"] += 1
                if latency > 2000:
                    stats["slow_count"] += 1

    def get_stats(self, skill: str = None) -> Dict:
        """获取性能统计"""
        with self._lock:
            if skill:
                stats = self.skill_stats.get(skill, {})
                if stats:
                    return {
                        **stats,
                        "avg_latency": stats["total_latency"] / stats["count"] if stats["count"] > 0 else 0,
                        "success_rate": stats["successes"] / stats["count"] if stats["count"] > 0 else 0,
                        "slow_rate": stats["slow_count"] / stats["count"] if stats["count"] > 0 else 0
                    }
                return {}

            # 所有技能统计
            return {
                skill: {
                    **stats,
                    "avg_latency": stats["total_latency"] / stats["count"] if stats["count"] > 0 else 0,
                    "success_rate": stats["successes"] / stats["count"] if stats["count"] > 0 else 0
                }
                for skill, stats in self.skill_stats.items()
            }

    def get_active_executions(self) -> Dict[str, float]:
        """获取正在执行的技能"""
        with self._lock:
            return {
                skill: (time.time() - start) * 1000
                for skill, start in self.current_execution.items()
            }


# 全局实例
_optimizer: Optional[SkillOptimizer] = None
_executor: Optional[ParallelExecutor] = None
_cache: Optional[SmartCache] = None
_monitor: Optional[PerformanceMonitor] = None


def get_optimizer() -> SkillOptimizer:
    global _optimizer
    if _optimizer is None:
        _optimizer = SkillOptimizer()
    return _optimizer


def get_executor(max_workers: int = 4) -> ParallelExecutor:
    global _executor
    if _executor is None:
        _executor = ParallelExecutor(max_workers)
    return _executor


def get_cache() -> SmartCache:
    global _cache
    if _cache is None:
        _cache = SmartCache()
    return _cache


def get_monitor() -> PerformanceMonitor:
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor
