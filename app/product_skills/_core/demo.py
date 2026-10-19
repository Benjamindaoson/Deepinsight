"""
Skill Core Demo - 展示前沿技能能力

运行方式:
    python -m app.product_skills._core.demo
"""
import time
from datetime import datetime

from .skill_core import SkillVersionManager, SkillCache
from .skill_optimizer import SkillOptimizer, ParallelExecutor, SmartCache
from .skill_auto_trigger import SkillAutoTrigger, SkillSelfEvolution
from .skill_visualization import SkillDashboard, SkillRenderer, VisualStyle
from .skill_orchestrator import SkillOrchestrator


def demo_version_manager():
    """演示版本管理器"""
    print("\n" + "="*60)
    print("1. 技能版本管理器 - 版本化与自进化")
    print("="*60)

    # 模拟技能内容
    skill_content = """
# Market Intelligence Skill
You are responsible for monitoring London CRE market data.
## Responsibilities
- Track rent, vacancy, take-up
- Compare across submarkets
"""

    # 创建版本管理器
    vm = SkillVersionManager(".")

    # 注册版本
    v1 = vm.register_version(
        "market-intelligence",
        skill_content,
        "Initial version with basic metrics",
        author="system"
    )
    print(f"\n注册 v1: {v1.version_id[:8]}...")
    print(f"  版本号: {v1.version_number}")
    print(f"  状态: {v1.status.value}")

    # 更新版本
    updated_content = skill_content + "\n## Additional: ESG metrics"
    v2 = vm.register_version(
        "market-intelligence",
        updated_content,
        "Added ESG metrics tracking",
        author="system"
    )
    print(f"\n注册 v2: {v2.version_id[:8]}...")
    print(f"  版本号: {v2.version_number}")
    print(f"  状态: {v2.status.value}")

    # 记录使用
    vm.record_usage("market-intelligence", success=True, latency_ms=150)
    vm.record_usage("market-intelligence", success=True, latency_ms=200)

    # 获取活跃版本
    active = vm.get_active_version("market-intelligence")
    print(f"\n当前活跃版本: {active.version_number}")
    print(f"  使用次数: {active.usage_count}")
    print(f"  成功率: {active.success_rate:.1%}")

    # 模拟性能下降触发进化
    vm.record_usage("market-intelligence", success=True, latency_ms=6000)

    # 获取进化建议
    suggestions = vm.get_evolution_suggestions()
    if suggestions:
        print(f"\n⚠️ 进化建议: {len(suggestions)} 条")
        for s in suggestions:
            print(f"  - {s.event_type}: {s.recommendation}")


def demo_auto_trigger():
    """演示智能触发引擎"""
    print("\n" + "="*60)
    print("2. 技能智能触发引擎 - 自动路由")
    print("="*60)

    trigger = SkillAutoTrigger()

    # 测试查询
    queries = [
        "What is the current vacancy rate in Canary Wharf?",
        "Compare West End vs City office rents",
        "What are the key risks in the London office market?",
        "Generate a weekly market report",
        "最近租金趋势如何？"
    ]

    for query in queries:
        results = trigger.match(query)
        sequence = trigger.suggest_skill_sequence(query)

        print(f"\n查询: {query[:50]}...")
        print(f"  触发技能: {[r.skill for r in results[:3]]}")
        print(f"  执行顺序: {sequence}")


def demo_optimizer():
    """演示性能优化器"""
    print("\n" + "="*60)
    print("3. 技能性能优化器 - 并行执行与缓存")
    print("="*60)

    optimizer = SkillOptimizer()

    # 规划执行
    skills = ["market-intelligence", "comparison", "analysis", "reporting"]
    plan = optimizer.plan_execution(skills)

    print(f"\n技能: {skills}")
    print(f"  可并行组: {plan.parallel_groups}")
    print(f"  预估延迟: {plan.estimated_latency_ms:.0f}ms")
    print(f"  缓存机会: {plan.cache_opportunities}")

    # 演示缓存
    cache = SmartCache()

    # 第一次查询（缓存未命中）
    result = cache.get("market-intelligence", {"query": "vacancy rate"})
    print(f"\n缓存测试:")
    print(f"  第一次查询: {'命中' if result else '未命中'}")

    # 设置缓存
    cache.set("market-intelligence", {"query": "vacancy rate"},
              {"status": "sample_only", "value": None})

    # 第二次查询（缓存命中）
    result = cache.get("market-intelligence", {"query": "vacancy rate"})
    print(f"  第二次查询: {'命中' if result else '未命中'}")

    # 统计
    stats = cache.get_stats()
    print(f"  命中率: {stats['hit_rate']:.1%}")


def demo_dashboard():
    """演示可视化仪表板"""
    print("\n" + "="*60)
    print("4. 技能可视化仪表板")
    print("="*60)

    # 创建仪表板
    dashboard = SkillDashboard()

    # 添加技能卡片
    skills = [
        ("market-intelligence", "London CRE市场数据管理", "active", {"latency_ms": 150, "success_rate": 0.95}),
        ("comparison", "历史数据比较", "active", {"latency_ms": 100, "success_rate": 0.98}),
        ("event-monitor", "新闻与事件监测", "active", {"latency_ms": 200, "success_rate": 0.92}),
        ("reporting", "报告生成", "draft", {"latency_ms": 300, "success_rate": 0.88}),
    ]

    for name, desc, status, metrics in skills:
        dashboard.add_skill(
            name=name,
            description=desc,
            status=status,
            version="1.0.0",
            metrics=metrics,
            tags=["core", "business"]
        )

    # 渲染
    renderer = SkillRenderer(VisualStyle.PROFESSIONAL)

    print("\n技能矩阵:")
    print(renderer.render_skill_matrix(dashboard.cards))

    print("\n技能卡片示例 (comparison):")
    card = next(c for c in dashboard.cards if c.name == "comparison")
    print(renderer.render_skill_card(card))


def demo_self_evolution():
    """演示自进化引擎"""
    print("\n" + "="*60)
    print("5. 技能自进化引擎 - 反馈驱动改进")
    print("="*60)

    evolution = SkillSelfEvolution()

    # 模拟用户反馈
    # Structural examples deliberately contain no market value, title or fixed
    # business answer. Product answers must always come from cited evidence.
    queries = [
        ("market-intelligence", "How is this metric defined?", "See the cited source definition.", True),
        ("market-intelligence", "Which period is covered?", "See the cited reporting period.", True),
        ("market-intelligence", "Is a value available?", "Data is insufficient without a source.", True),
        ("analysis", "Market analysis?", "Unsupported conclusion.", False),
        ("analysis", "Risk assessment?", "Unsupported conclusion.", False),
    ]

    for skill, query, response, helpful in queries:
        evolution.record_feedback(skill, query, response, helpful)
        print(f"反馈: {skill} - {'👍' if helpful else '👎'}")

    # 获取统计
    stats = evolution.get_skill_stats("analysis")
    print(f"\n分析技能统计:")
    print(f"  反馈数: {stats.get('feedback_count', 0)}")
    print(f"  有用率: {stats.get('feedback_helpful_rate', 0):.1%}")

    # 获取建议
    suggestions = evolution.get_suggestions()
    if suggestions:
        print(f"\n⚠️ 进化建议: {len(suggestions)} 条")
        for s in suggestions:
            print(f"  - {s['reason']}: {s['suggestion']}")


def demo_orchestrator():
    """演示编排器"""
    print("\n" + "="*60)
    print("6. 技能编排器 - 整合所有能力")
    print("="*60)

    orch = SkillOrchestrator()

    # 模拟查询
    query = "What is the current vacancy rate in Canary Wharf and how does it compare to last quarter?"

    print(f"\n查询: {query}")

    # 执行编排
    result = orch.orchestrate(query)

    print(f"\n执行结果:")
    print(f"  使用技能: {[s.skill for s in result.skills_used]}")
    print(f"  总延迟: {result.total_latency_ms:.0f}ms")
    print(f"  缓存命中: {result.cache_hit}")


def demo_full_pipeline():
    """演示完整管道"""
    print("\n" + "="*60)
    print("7. 完整技能管道演示")
    print("="*60)

    # 创建组件
    trigger = SkillAutoTrigger()
    optimizer = SkillOptimizer()
    cache = SmartCache()
    evolution = SkillSelfEvolution()

    # 用户查询
    query = "What are the key risks and opportunities in the London office market?"

    print(f"\n查询: {query}")

    # 1. 智能触发
    start = time.time()
    matches = trigger.match(query)
    print(f"\n1. 触发分析: {len(matches)} 个匹配")
    for m in matches[:3]:
        print(f"   - {m.skill}: {m.confidence:.1%} ({m.match_type})")

    # 2. 技能序列
    sequence = trigger.suggest_skill_sequence(query)
    print(f"\n2. 执行序列: {sequence}")

    # 3. 执行规划
    plan = optimizer.plan_execution(sequence)
    print(f"\n3. 执行计划:")
    print(f"   并行组: {plan.parallel_groups}")
    print(f"   预估延迟: {plan.estimated_latency_ms:.0f}ms")

    # 4. 模拟执行
    print(f"\n4. 执行技能:")
    for skill in sequence:
        # 检查缓存
        cached = cache.get(skill, {"query": query})
        if cached:
            print(f"   ✓ {skill}: 缓存命中")
            continue

        # 模拟执行
        latency = 100 + hash(skill) % 200
        time.sleep(0.01)  # 模拟延迟

        cache.set(skill, {"query": query}, {"skill": skill, "latency": latency})
        evolution.record_performance(skill, latency, True)

        print(f"   ✓ {skill}: {latency:.0f}ms")

    # 5. 性能统计
    stats = cache.get_stats()
    print(f"\n5. 缓存统计:")
    print(f"   命中率: {stats['hit_rate']:.1%}")

    print(f"\n总耗时: {(time.time() - start) * 1000:.0f}ms")


def main():
    """运行所有演示"""
    print("="*60)
    print("London CRE Market Intelligence - Skill Core Demo")
    print("="*60)
    print(f"时间: {datetime.now().isoformat()}")

    try:
        demo_version_manager()
        demo_auto_trigger()
        demo_optimizer()
        demo_dashboard()
        demo_self_evolution()
        demo_orchestrator()
        demo_full_pipeline()

        print("\n" + "="*60)
        print("✅ 所有演示完成!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 演示出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
