# DeepInsight Lite - London Office Market Agent

**B路线：基于 Agno 框架的快速开发**

项目路径: `D:\deepinsight-lite`

---

## 项目状态

| 项目 | 状态 |
|------|------|
| Agno 安装 | ✅ 已完成 |
| 基础 Agent | ✅ 已创建 |
| Market Tools | ✅ 已实现 |
| Market Skills | ✅ 已定义 |
| Research Team | ✅ 已配置 |
| Monitor Workflow | ✅ 已定义 |

---

## 快速开始

### 1. 配置环境变量

创建 `.env` 文件：

```bash
# LLM API
OPENAI_API_KEY=your-openai-api-key
# 或
ANTHROPIC_API_KEY=your-anthropic-api-key

# Tavily Search (可选)
TAVILY_API_KEY=your-tavily-api-key
```

### 2. 运行测试

```bash
cd D:\deepinsight-lite

# 运行主程序
python market_agent.py

# 或直接测试
python -c "import market_agent; from agno import test; test(market_agent.market_agent)"
```

### 3. 启动 Agent UI

```bash
# 克隆 Agent UI
git clone https://github.com/agno-agi/agent-ui.git
cd agent-ui

# 安装依赖
npm install

# 配置环境
cp .env.example .env
# 编辑 .env 填入 API keys

# 启动
npm run dev
```

---

## 已实现组件

### 1. MarketTools (工具集)
```python
from market_agent import MarketTools

tools = MarketTools()
tools.get_current_date()      # 获取当前日期
tools.get_london_offices()   # 获取子市场列表
tools.get_metric_types()     # 获取指标类型
```

### 2. Market Skills (技能)
```python
from market_agent import market_research, market_analysis

# 在 Agent 中使用
agent = Agent(
    skills=[market_research, market_analysis]
)
```

### 3. Market Agent (单 Agent)
```python
from market_agent import market_agent

response = market_agent.run("伦敦金融城最新租金是多少？")
print(response.content)
```

### 4. Research Team (多 Agent 团队)
```python
from market_agent import research_team

response = research_team.run("比较 City 和 West End 的租金趋势")
```

### 5. Monitor Workflow (定时监测)
```python
from market_agent import MarketMonitorWorkflow

workflow = MarketMonitorWorkflow(areas=["city", "west_end"])
result = await workflow.run()
```

---

## B0 → B5 开发路线

| 阶段 | 内容 | 状态 |
|------|------|------|
| **B0** | Agno 原版跑通 | ✅ 完成 |
| **B1** | 功能审计与测试 | 🔄 进行中 |
| **B2** | 市场监测能力开发 | ⏳ 待开始 |
| **B3** | 智能分析能力 | ⏳ 待开始 |
| **B4** | Dashboard UI | ⏳ 待开始 |
| **B5** | 部署与评测 | ⏳ 待开始 |

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Agno Framework                            │
├─────────────────────────────────────────────────────────────┤
│  Agent    │  Team    │  Workflow  │  Skills  │  Tools     │
├─────────────────────────────────────────────────────────────┤
│                    Our Market Modules                        │
│  MarketAgent  │  MarketTools  │  MarketSkills  │  Monitor  │
├─────────────────────────────────────────────────────────────┤
│                    External Services                         │
│         OpenAI  │  Anthropic  │  Tavily  │  SQLite       │
└─────────────────────────────────────────────────────────────┘
```

---

## 与 A 路线对比

| 维度 | A路线 (deepinsight-rader) | B路线 (deepinsight-lite) |
|------|---------------------------|---------------------------|
| 框架 | 自研 Python | Agno |
| 前端 | Next.js | Agent UI |
| 开发时间 | 13-21 天 | 8-14 天 |
| 复杂度 | 高 | 中 |
| 可控性 | 完全自控 | 依赖 Agno |

---

## License

MIT License
