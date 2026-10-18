"""
DeepInsight Lite - London Office Market Agent
B路线：基于 Agno 框架的快速开发

项目路径：D:\deepinsight-lite
中转 API：https://toapis.cn/v1
"""

import os
from dotenv import load_dotenv
from agno import Agent, RunResponse, Session, Team
from agno.tools import Toolkit
from agno.skills import skill
from agno.workflow import Workflow, WorkflowResult
from pydantic import Field
from datetime import datetime

# 加载环境变量
load_dotenv("D:/deepinsight-lite/.env")

# 获取中转 API 配置
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://toapis.cn/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o")

print(f"""
╔══════════════════════════════════════════════════════════════╗
║  DeepInsight Lite - London Office Market Agent             ║
║  B路线：基于 Agno 框架开发                                  ║
╠══════════════════════════════════════════════════════════════╣
║  API Endpoint: {OPENAI_BASE_URL:<40} ║
║  Default Model: {DEFAULT_MODEL:<40} ║
╚══════════════════════════════════════════════════════════════╝
""")

# ============================================================================
# 1. 市场工具 (Market Tools)
# ============================================================================

class MarketTools(Toolkit):
    """市场数据工具集"""
    
    def __init__(self):
        super().__init__(name="market_tools")
    
    def get_current_date(self) -> str:
        """获取当前日期"""
        return datetime.now().strftime("%Y-%m-%d")
    
    def get_london_offices(self) -> dict:
        """获取伦敦办公楼子市场列表"""
        return {
            "city": {"name": "City of London", "alias": ["Square Mile", "City", "Bank"]},
            "west_end": {"name": "West End", "alias": ["Oxford Street", "Bond Street", "Mayfair"]},
            "canary_wharf": {"name": "Canary Wharf", "alias": ["Isle of Dogs", "Docklands"]},
            "midtown": {"name": "Midtown", "alias": ["Holborn", "Strand", "Fleet Street"]},
            "fringe": {"name": "Fringe", "alias": ["South Bank", "King's Cross", "Battersea"]},
        }
    
    def get_metric_types(self) -> dict:
        """获取监测指标类型"""
        return {
            "prime_rent": {"name": "Prime Rent", "unit": "£/sq ft/year"},
            "grade_a_rent": {"name": "Grade A Rent", "unit": "£/sq ft/year"},
            "vacancy_rate": {"name": "Vacancy Rate", "unit": "%"},
            "availability": {"name": "Availability", "unit": "sq ft"},
            "take_up": {"name": "Leasing Take-up", "unit": "sq ft"},
            "new_supply": {"name": "New Supply", "unit": "sq ft"},
        }


# ============================================================================
# 2. 市场技能 (Market Skills)
# ============================================================================

@skill(
    name="market_research",
    description="Research London office market data from web sources",
    instructions=[
        "Use Tavily or web search to find latest London office market reports",
        "Focus on: Savills, CBRE, JLL, Knight Frank reports",
        "Extract key metrics: rents, vacancy, take-up, supply",
        "Always cite sources with URLs",
    ],
)
def market_research(query: str) -> str:
    """研究伦敦办公楼市场数据"""
    return f"Research query: {query}"


@skill(
    name="market_analysis",
    description="Analyze London office market trends and changes",
    instructions=[
        "Compare current data with historical data",
        "Identify significant changes (>5% in rent, >2% in vacancy)",
        "Provide evidence-based insights",
        "Assess risks and opportunities",
    ],
)
def market_analysis(data: dict) -> str:
    """分析市场趋势"""
    return f"Analysis of: {data}"


# ============================================================================
# 3. 市场 Agent
# ============================================================================

market_agent = Agent(
    name="Market Analyst",
    model=DEFAULT_MODEL,
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
    tools=[MarketTools()],
    instructions=[
        "You are a London commercial real estate market expert.",
        "Provide accurate, data-driven insights.",
        "Always cite your sources.",
        "Focus on City, West End, and Canary Wharf markets.",
    ],
    markdown=True,
    show_tool_calls=True,
)


# ============================================================================
# 4. 市场问答 Agent
# ============================================================================

qa_agent = Agent(
    name="Market Q&A",
    model=DEFAULT_MODEL,
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
    tools=[MarketTools()],
    instructions=[
        "Answer questions about London office market.",
        "Use simple, clear language for business users.",
        "Include relevant data and sources.",
    ],
    markdown=True,
)


# ============================================================================
# 5. 多 Agent Team
# ============================================================================

research_team = Team(
    name="Market Research Team",
    mode="coordinate",  # or "collaborate", "handover"
    agents=[market_agent, qa_agent],
    instructions=[
        "The team researches and answers London office market questions.",
        "Use the Market Analyst for deep research.",
        "Use the Market Q&A for simple questions.",
        "Always verify data accuracy.",
    ],
)


# ============================================================================
# 6. 定时监测 Workflow
# ============================================================================

class MarketMonitorWorkflow(Workflow):
    """市场监测工作流"""
    
    name: str = "market_monitor"
    description: str = "Daily London office market monitoring workflow"
    
    # Workflow 参数
    areas: list[str] = Field(default=["city", "west_end", "canary_wharf"])
    check_events: bool = Field(default=True)
    
    def run(self) -> WorkflowResult:
        """执行监测工作流"""
        steps = []
        
        # Step 1: 收集数据
        steps.append("1. Collecting market data...")
        
        # Step 2: 提取指标
        steps.append("2. Extracting metrics...")
        
        # Step 3: 检测变化
        steps.append("3. Detecting changes...")
        
        # Step 4: 分析洞察
        steps.append("4. Generating insights...")
        
        # Step 5: 生成报告
        steps.append("5. Building report...")
        
        return WorkflowResult(
            success=True,
            message="Market monitoring completed",
            data={
                "steps": steps,
                "areas": self.areas,
                "timestamp": datetime.now().isoformat(),
            },
        )


# ============================================================================
# 测试函数
# ============================================================================

async def test_agent():
    """测试 Agent"""
    print("\n" + "="*60)
    print("Testing Market Agent...")
    print("="*60 + "\n")
    
    # 测试工具
    print("1. Testing Market Tools:")
    tools = MarketTools()
    print(f"   Current date: {tools.get_current_date()}")
    print(f"   Areas: {list(tools.get_london_offices().keys())}")
    
    # 测试 Agent
    print("\n2. Testing Market Agent:")
    response: RunResponse = market_agent.run(
        "What are the key London office market trends in 2025?"
    )
    print(f"   Response: {response.content[:200]}...")
    
    print("\n✅ Agent test completed!")


async def test_team():
    """测试 Team"""
    print("\n" + "="*60)
    print("Testing Research Team...")
    print("="*60 + "\n")
    
    response = research_team.run(
        "Compare City vs West End office rents in Q3 2025"
    )
    print(f"Team Response: {response.content[:300]}...")
    
    print("\n✅ Team test completed!")


async def test_workflow():
    """测试 Workflow"""
    print("\n" + "="*60)
    print("Testing Market Monitor Workflow...")
    print("="*60 + "\n")
    
    workflow = MarketMonitorWorkflow(
        areas=["city", "west_end", "canary_wharf"]
    )
    
    result = await workflow.run()
    
    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    print(f"Steps: {len(result.data.get('steps', []))}")
    
    print("\n✅ Workflow test completed!")


# ============================================================================
# 主程序
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    # 检查 API 配置
    print("\n" + "="*60)
    print("Configuration Check")
    print("="*60)
    
    if OPENAI_API_KEY:
        print(f"✅ OpenAI API Key: {OPENAI_API_KEY[:10]}...{OPENAI_API_KEY[-4:]}")
    else:
        print("❌ OpenAI API Key not set!")
    
    print(f"✅ API Base URL: {OPENAI_BASE_URL}")
    print(f"✅ Default Model: {DEFAULT_MODEL}")
    print("="*60)
    
    if not OPENAI_API_KEY:
        print("\n⚠️ Please set OPENAI_API_KEY in .env file")
        exit(1)
    
    print("\n选择测试项目:")
    print("  1. Test Agent")
    print("  2. Test Team")
    print("  3. Test Workflow")
    print("  4. Run all tests")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        asyncio.run(test_agent())
    elif choice == "2":
        asyncio.run(test_team())
    elif choice == "3":
        asyncio.run(test_workflow())
    else:
        asyncio.run(test_agent())
        asyncio.run(test_team())
        asyncio.run(test_workflow())
