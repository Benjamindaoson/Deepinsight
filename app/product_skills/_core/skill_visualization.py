"""
Skill Visualization - 技能可视化与美观展示
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class VisualStyle(Enum):
    MINIMAL = "minimal"
    PROFESSIONAL = "professional"
    DETAILED = "detailed"
    MOBILE = "mobile"


@dataclass
class SkillCard:
    """技能卡片可视化"""
    name: str
    description: str
    status: str
    version: str
    last_updated: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class SkillDiagram:
    """技能关系图"""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    clusters: List[Dict[str, Any]]


class SkillRenderer:
    """技能渲染器 - 生成美观的技能展示"""

    # 技能状态颜色
    STATUS_COLORS = {
        "active": "#22c55e",      # 绿色
        "deprecated": "#f59e0b",   # 橙色
        "draft": "#6366f1",       # 紫色
        "retired": "#ef4444"      # 红色
    }

    # 指标图标
    METRIC_ICONS = {
        "latency": "⏱️",
        "success_rate": "✅",
        "usage": "📊",
        "errors": "❌"
    }

    def __init__(self, style: VisualStyle = VisualStyle.PROFESSIONAL):
        self.style = style

    def render_skill_card(self, card: SkillCard) -> str:
        """渲染技能卡片"""
        if self.style == VisualStyle.MINIMAL:
            return self._render_minimal(card)
        elif self.style == VisualStyle.PROFESSIONAL:
            return self._render_professional(card)
        else:
            return self._render_detailed(card)

    def _render_minimal(self, card: SkillCard) -> str:
        """最小化渲染"""
        return f"**{card.name}** — {card.description[:60]}..."

    def _render_professional(self, card: SkillCard) -> str:
        """专业渲染"""
        status_color = self.STATUS_COLORS.get(card.status, "#666666")
        metrics_html = self._render_metrics(card.metrics)
        tags_html = " ".join(f"`{t}`" for t in card.tags[:3])

        return f"""
## {card.name}

| 属性 | 值 |
|------|-----|
| 状态 | <span style="color:{status_color}">●</span> {card.status} |
| 版本 | {card.version} |
| 更新 | {card.last_updated} |

{card.description}

**指标**: {metrics_html}
**标签**: {tags_html}
"""

    def _render_detailed(self, card: SkillCard) -> str:
        """详细渲染"""
        status_color = self.STATUS_COLORS.get(card.status, "#666666")
        deps = ", ".join(f"`{d}`" for d in card.dependencies) or "无"
        metrics_html = self._render_detailed_metrics(card.metrics)

        return f"""
## {card.name}

### 基本信息
- **状态**: <span style="color:{status_color}">●</span> {card.status}
- **版本**: {card.version}
- **更新时间**: {card.last_updated}

### 描述
{card.description}

### 依赖关系
{deps}

### 性能指标
{metrics_html}

### 标签
{" ".join(f"`{t}`" for t in card.tags)}
"""

    def _render_metrics(self, metrics: Dict) -> str:
        """渲染指标概览"""
        if not metrics:
            return "无数据"

        parts = []
        for key, icon in self.METRIC_ICONS.items():
            if key in metrics:
                parts.append(f"{icon} {metrics[key]}")

        return " | ".join(parts) if parts else "无数据"

    def _render_detailed_metrics(self, metrics: Dict) -> str:
        """渲染详细指标"""
        if not metrics:
            return "暂无指标数据"

        rows = []
        for key, value in metrics.items():
            icon = self.METRIC_ICONS.get(key, "📈")
            rows.append(f"| {icon} {key} | {value} |")

        return "| 指标 | 值 |\n|------|-----|\n" + "\n".join(rows)

    def render_skill_matrix(self, skills: List[SkillCard]) -> str:
        """渲染技能矩阵"""
        header = "| 技能 | 状态 | 版本 | 描述摘要 |"
        separator = "|------|------|------|------------|"
        rows = []

        for skill in skills:
            status_color = self.STATUS_COLORS.get(skill.status, "#666666")
            desc = skill.description[:40] + "..." if len(skill.description) > 40 else skill.description
            rows.append(f"| {skill.name} | <span style='color:{status_color}'>●</span> {skill.status} | {skill.version} | {desc} |")

        return header + "\n" + separator + "\n" + "\n".join(rows)

    def render_dependency_diagram(self, diagram: SkillDiagram) -> str:
        """渲染依赖关系图 (Mermaid 格式)"""
        lines = ["```mermaid", "graph TD"]

        # 添加节点
        for node in diagram.nodes:
            node_id = node["id"].replace("-", "_")
            label = node.get("label", node_id)
            style = node.get("style", "")
            lines.append(f'    {node_id}["{label}"]{style}')

        # 添加边
        for edge in diagram.edges:
            from_id = edge["from"].replace("-", "_")
            to_id = edge["to"].replace("-", "_")
            label = edge.get("label", "")
            if label:
                lines.append(f'    {from_id} -->|{label}| {to_id}')
            else:
                lines.append(f'    {from_id} --> {to_id}')

        # 添加聚类
        for cluster in diagram.clusters:
            cluster_id = cluster["id"].replace("-", "_")
            label = cluster.get("label", cluster_id)
            nodes = [n.replace("-", "_") for n in cluster.get("nodes", [])]
            if nodes:
                lines.append(f'    subgraph {cluster_id}["{label}"]')
                for n in nodes:
                    lines.append(f'        {n}')
                lines.append("    end")

        lines.append("```")
        return "\n".join(lines)


class SkillDashboard:
    """技能仪表板"""

    def __init__(self):
        self.renderer = SkillRenderer(VisualStyle.PROFESSIONAL)
        self.cards: List[SkillCard] = []

    def add_skill(self, name: str, description: str, status: str = "active",
                  version: str = "1.0.0", metrics: Dict = None,
                  tags: List[str] = None, dependencies: List[str] = None):
        """添加技能卡片"""
        card = SkillCard(
            name=name,
            description=description,
            status=status,
            version=version,
            last_updated=datetime.now().isoformat()[:10],
            metrics=metrics or {},
            tags=tags or [],
            dependencies=dependencies or []
        )
        self.cards.append(card)
        return card

    def render(self) -> str:
        """渲染整个仪表板"""
        sections = [
            "# London CRE Market Intelligence — Skill Dashboard",
            f"\n*Generated: {datetime.now().isoformat()}*\n",
            "## Skill Overview",
            self.renderer.render_skill_matrix(self.cards),
            "\n## Skill Details"
        ]

        for card in self.cards:
            sections.append(self.renderer.render_skill_card(card))

        return "\n".join(sections)

    def render_diagram(self) -> str:
        """渲染依赖关系图"""
        nodes = [{"id": c.name, "label": c.name} for c in self.cards]

        edges = []
        for card in self.cards:
            for dep in card.dependencies:
                edges.append({"from": dep, "to": card.name})

        diagram = SkillDiagram(
            nodes=nodes,
            edges=edges,
            clusters=[
                {"id": "core", "label": "核心技能", "nodes": ["market-intelligence", "comparison"]},
                {"id": "ingestion", "label": "数据采集", "nodes": ["source-discovery", "fact-extraction"]},
                {"id": "output", "label": "输出", "nodes": ["reporting", "alerting"]}
            ]
        )

        return self.renderer.render_dependency_diagram(diagram)


class SkillPerformanceChart:
    """技能性能图表"""

    def __init__(self):
        self.data: Dict[str, List[Dict]] = {}

    def add_datapoint(self, skill: str, latency_ms: float,
                     success: bool, timestamp: str = None):
        """添加数据点"""
        if skill not in self.data:
            self.data[skill] = []

        self.data[skill].append({
            "timestamp": timestamp or datetime.now().isoformat(),
            "latency_ms": latency_ms,
            "success": success
        })

    def render_ascii(self) -> str:
        """渲染 ASCII 图表"""
        if not self.data:
            return "No data available"

        lines = ["## Performance Over Time", ""]

        for skill, points in self.data.items():
            if not points:
                continue

            # 计算统计数据
            latencies = [p["latency_ms"] for p in points]
            successes = sum(1 for p in points if p["success"])
            total = len(points)

            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            success_rate = successes / total if total > 0 else 0

            # 渲染趋势线
            line = self._render_trend_line(latencies)

            lines.append(f"### {skill}")
            lines.append(f"```")
            lines.append(line)
            lines.append(f"```")
            lines.append(f"- Average latency: {avg_latency:.0f}ms")
            lines.append(f"- Success rate: {success_rate:.1%}")
            lines.append("")

        return "\n".join(lines)

    def _render_trend_line(self, values: List[float], width: int = 50) -> str:
        """渲染趋势线"""
        if not values:
            return ""

        min_val = min(values)
        max_val = max(values)
        range_val = max_val - min_val if max_val != min_val else 1

        # 简化渲染
        chars = " ▁▂▃▄▅▆▇█"
        n_chars = len(chars) - 1

        bars = []
        for v in values[-width:]:
            idx = int((v - min_val) / range_val * n_chars)
            idx = max(0, min(n_chars, idx))
            bars.append(chars[idx])

        return "".join(bars)

    def render_summary_table(self) -> str:
        """渲染汇总表格"""
        if not self.data:
            return "No data available"

        header = "| Skill | Avg Latency | Success Rate | Requests |"
        separator = "|------|-------------|-------------|----------|"
        rows = [header, separator]

        for skill, points in sorted(self.data.items()):
            if not points:
                continue

            latencies = [p["latency_ms"] for p in points]
            successes = sum(1 for p in points if p["success"])
            total = len(points)

            avg_lat = sum(latencies) / len(latencies) if latencies else 0
            success_rate = successes / total if total > 0 else 0

            rows.append(f"| {skill} | {avg_lat:.0f}ms | {success_rate:.1%} | {total} |")

        return "\n".join(rows)
