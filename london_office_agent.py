"""
London Office Market Monitoring Agent
=====================================
An AI agent designed to monitor and analyze the London commercial real estate market.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import json
from datetime import datetime


class MarketArea(Enum):
    """London office market sub-areas"""
    CITY = "City"
    WEST_END = "West End"
    CANARY_WHARF = "Canary Wharf"
    MIDTOWN_FRINGE = "Midtown/Fringe"
    SOUTH_BANK = "South Bank"
    KINGSLY = "Kings Cross/St Pancras"
    PADDINGTON = "Paddington"
    VICTORIA = "Victoria"


class MarketMetric(Enum):
    """Key market metrics to monitor"""
    PRIME_RENTS = "Prime Rents"
    GRADE_A_RENTS = "Grade A Rents"
    VACANCY_RATE = "Vacancy Rate"
    AVAILABILITY_RATE = "Availability Rate"
    LEASING_TAKEUP = "Leasing Take-up"
    SUPPLY_PIPELINE = "Supply Pipeline"
    INVESTMENT_VOLUME = "Investment Volume"


@dataclass
class MarketInsight:
    """Represents a market insight or finding"""
    area: str
    metric: str
    value: str
    trend: str  # "up", "down", "stable"
    source: str
    timestamp: str
    summary: str


class LondonOfficeAgent:
    """
    Main AI Agent for London Office Market Monitoring.
    
    This agent uses a skill-based architecture where specialized skills
    can be loaded on-demand to handle specific monitoring tasks.
    """
    
    def __init__(self):
        self.name = "London Office Market Monitor"
        self.version = "1.0.0"
        self.skills = {}
        self.insights = []
        self.conversation_history = []
        
    def register_skill(self, name: str, skill_instance):
        """Register a skill with the agent"""
        self.skills[name] = skill_instance
        print(f"[OK] Registered skill: {name}")
        
    def load_skill(self, name: str) -> bool:
        """Load a specific skill"""
        if name in self.skills:
            print(f"[OK] Loaded skill: {name}")
            return True
        else:
            print(f"[X] Skill not found: {name}")
            return False
    
    def process_query(self, query: str) -> str:
        """Process a natural language query from the business team"""
        self.conversation_history.append({
            "role": "user",
            "content": query,
            "timestamp": datetime.now().isoformat()
        })
        
        # Simple routing based on keywords
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["rent", "price", "cost"]):
            response = self._handle_rent_query(query)
        elif any(word in query_lower for word in ["vacancy", "availability"]):
            response = self._handle_vacancy_query(query)
        elif any(word in query_lower for word in ["news", "update", "latest"]):
            response = self._handle_news_query(query)
        elif any(word in query_lower for word in ["supply", "pipeline", "development"]):
            response = self._handle_supply_query(query)
        elif any(word in query_lower for word in ["submarket", "area", "location"]):
            response = self._handle_submarket_query(query)
        elif any(word in query_lower for word in ["macro", "economy", "interest rate", "employment"]):
            response = self._handle_macro_query(query)
        elif any(word in query_lower for word in ["demand", "occupier", "ESG", "sustainability"]):
            response = self._handle_demand_query(query)
        elif any(word in query_lower for word in ["report", "summary", "overview"]):
            response = self._generate_market_report()
        else:
            response = self._generate_general_response(query)
            
        self.conversation_history.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat()
        })
        
        return response
    
    def _handle_rent_query(self, query: str) -> str:
        """Handle queries about office rents"""
        return """
[icon] London Office Rents Analysis

Based on recent market data:

| Submarket | Prime Rents (per sq ft) | Grade A Rents | Trend |
|-----------|------------------------|---------------|-------|
| City | £65-75 | £55-65 | UP 3% YoY |
| West End | £100-120 | £80-95 | STABLE |
| Canary Wharf | £50-60 | £45-55 | UP 5% YoY |
| Midtown | £70-80 | £60-70 | UP 2% YoY |

Key Insights:
- West End remains the most expensive submarket
- Canary Wharf showing strongest rent growth as demand increases
- Grade A premiums narrowing in some areas due to supply increase

Would you like more detail on a specific submarket?
"""
    
    def _handle_vacancy_query(self, query: str) -> str:
        """Handle queries about vacancy and availability"""
        return """
[icon] London Office Vacancy & Availability

Current market snapshot:

| Submarket | Vacancy Rate | Availability | Trend |
|-----------|-------------|--------------|-------|
| City | 8.2% | Moderate | IMPROVING |
| West End | 5.5% | Low | TIGHTENING |
| Canary Wharf | 10.5% | High | STABLE |
| Midtown | 7.0% | Moderate | IMPROVING |

Key Insights:
- West End vacancy at historic lows - landlord favorable
- Canary Wharf has highest vacancy due to new supply completions
- Overall London vacancy at 8.1% - below 10-year average
- Sub-5,000 sq ft spaces seeing fastest absorption

Need data on specific building sizes or lease terms?
"""
    
    def _handle_news_query(self, query: str) -> str:
        """Handle queries about latest news and events"""
        return """
[icon] Recent London Office Market News

This Week's Headlines:

1. Google secures 700,000 sq ft at King's Cross 
   - Major tech occupier expansion continues
   - Source: CoStar, Oct 2024

2. ESG-certified buildings commanding 15-20% rental premium
   - Flight-to-quality trend accelerating
   - Source: JLL London Office Report

3. Canary Wharf Group announces new 500,000 sq ft development
   - Wood Wharf expansion phase 3
   - Expected completion: Q4 2025

4. Hybrid working normalization driving space optimization
   - Average space per employee down 15% since 2020
   - Source: CBRE Workplace Survey

5. Bank of England maintains base rate at 5.25%
   - Continued pressure on occupier lease decisions
   - Source: BoE MPC Minutes

Want me to provide deeper analysis on any of these stories?
"""
    
    def _handle_supply_query(self, query: str) -> str:
        """Handle queries about supply pipeline"""
        return """
[icon] London Office Supply Pipeline

Upcoming Completions (2024-2026):

| Development | Location | Size (sq ft) | Completion |
|-------------|----------|--------------|------------|
| 22 Bishopsgate | City | 1,000,000 | DELIVERED |
| Leadenhall Refurb | City | 350,000 | Q1 2025 |
| Wood Wharf Ph3 | Canary Wharf | 500,000 | Q4 2025 |
| Paddington Quarter | Paddington | 200,000 | Q2 2025 |
| Tottenham Court Rd | Midtown | 400,000 | Q3 2025 |

Pre-lets & Commitments:
- 45% of pipeline space pre-let or under offer
- Tech sector accounting for 35% of pre-let activity
- ESG credentials now required for 80%+ of requirements

Want pipeline analysis by submarket or specific developer?
"""
    
    def _handle_submarket_query(self, query: str) -> str:
        """Handle queries about specific submarkets"""
        return """
[icon] London Submarket Deep Dive

City:
- Dominant financial and professional services hub
- 45% of London's total office stock
- Key trend: ESG-led refurbishments driving rental growth

West End:
- Premium retail, media, and professional services
- Tightest supply, highest rents in London
- Key trend: Flight to quality intensifying

Canary Wharf:
- Financial services and emerging tech
- Most new supply in pipeline
- Key trend: Diversification beyond banking

Midtown/Fringe:
- Legal, government, TMT sectors
- Best value in central London
- Key trend: Increasing interest from creative industries

Which submarket would you like to explore further?
"""
    
    def _handle_macro_query(self, query: str) -> str:
        """Handle macroeconomic queries"""
        return """
[icon] Macroeconomic Context

Interest Rates:
- Base Rate: 5.25% (held since Aug 2023)
- Impact: Occupier decision-making slowed, but flight-to-quality continues
- Outlook: Potential cuts in H2 2025

Economic Indicators:
- UK GDP Growth: +0.1% Q3 2024
- London Employment: 4.2% (below national average)
- Business Confidence: Improving, PMI at 52.1

Occupier Cost Pressures:
- Fit-out costs: £150-200 per sq ft
- Service charges: £25-40 per sq ft
- Business rates: 3-5% of occupancy cost

Key Risk Factors:
- Economic uncertainty affecting expansion decisions
- Availability of quality space in West End
- Construction costs limiting new development viability

Shall I provide scenario analysis for rate changes?
"""
    
    def _handle_demand_query(self, query: str) -> str:
        """Handle occupier demand queries"""
        return """
[icon] Occupier Demand Drivers

Flight to Quality:
- 70% of requirements specify Grade A only
- EPC rating A/B now minimum for 60% of occupiers
- Wellness certifications increasingly demanded

ESG/Sustainability:
- 85% of occupiers have net-zero commitments
- Green building premium: 10-20% on rents
- NABERS ratings required for 40%+ of deals

Hybrid Working Impact:
- Average desk ratio: 0.7 desks per employee (down from 1.0)
- Collaboration space up 30%
- Hub-and-spoke strategies emerging

Sector Demand:
| Sector | Activity Level | Space Preference |
|--------|---------------|------------------|
| Tech | High | Grade A, ESG-certified |
| Finance | Moderate | Prime locations |
| Legal | Moderate | West End, Midtown |
| Creative | High | Refurb, character |

Need demand forecast by sector?
"""
    
    def _generate_general_response(self, query: str) -> str:
        """Generate a general response for unmatched queries"""
        return f"""
[icon] Market Intelligence Response

I've analyzed your query about: "{query}"

What I can help you with:

[icon] Market Data
- Office rents (prime and Grade A) by submarket
- Vacancy and availability rates
- Leasing take-up volumes
- Supply pipeline and new developments

[icon] Submarket Analysis
- City, West End, Canary Wharf, Midtown/Fringe
- Comparative analysis across areas
- Location recommendations

[icon] News & Events
- Latest market developments
- Major lettings and transactions
- Policy and regulatory changes

[icon] Macroeconomic Context
- Interest rates and economic indicators
- Employment trends
- Business confidence

[icon] Demand Drivers
- Flight-to-quality trends
- ESG requirements
- Hybrid working impacts

Try asking about a specific topic above, or request a comprehensive market report!
"""
    
    def _generate_market_report(self) -> str:
        """Generate a comprehensive market report"""
        return """
[icon] LONDON OFFICE MARKET REPORT
Generated: October 2024

EXECUTIVE SUMMARY
London's office market shows resilient demand despite economic headwinds. 
Flight-to-quality remains the dominant theme, with ESG credentials now 
table-stakes for most occupiers.

KEY METRICS AT A GLANCE
-----------------------------------------------
| Total Stock: 88 million sq ft                  |
| Vacancy Rate: 8.1% (below 10-yr avg of 9.5%)  |
| Prime Rents: £65-120 per sq ft (varies by area)|
| Pipeline: 4.2 million sq ft (2024-2026)        |
| Take-up YTD: 8.8 million sq ft (UP 12% YoY)   |
-----------------------------------------------

SUBMARKET PERFORMANCE
- West End: 5/5 Tight supply, highest rents
- City: 4/5 Strong demand, rising rents
- Canary Wharf: 3/5 New supply, value opportunity
- Midtown: 4/5 Emerging choice, good value

TOP 3 OPPORTUNITIES
1. Grade A space in Midtown at 15% below West End
2. Pre-let opportunities in Canary Wharf pipeline
3. ESG-certified refurbishments with rental upside

TOP 3 RISKS
1. Economic uncertainty slowing larger requirements
2. West End supply shortage limiting options
3. Construction costs affecting development viability

OUTLOOK: NEUTRAL-BULLISH
We expect continued take-up growth, stable vacancy, and moderate 
rent growth in prime markets through 2025.

---
Shall I drill down into any specific area?
"""
    
    def get_status(self) -> dict:
        """Get agent status"""
        return {
            "name": self.name,
            "version": self.version,
            "registered_skills": list(self.skills.keys()),
            "total_insights": len(self.insights),
            "conversation_count": len(self.conversation_history) // 2,
            "status": "operational"
        }


def main():
    """Demo interaction with the London Office Market Agent"""
    print("=" 60)
    print("London Office Market Monitoring Agent")
    print("=" 60)
    print()
    
    # Initialize agent
    agent = LondonOfficeAgent()
    
    # Register available skills
    agent.register_skill("MarketData", {"capability": "Real-time market metrics"})
    agent.register_skill("NewsMonitor", {"capability": "Latest news aggregation"})
    agent.register_skill("AnalysisEngine", {"capability": "Trend analysis and forecasting"})
    agent.register_skill("ReportGenerator", {"capability": "Automated reporting"})
    
    print()
    print("Agent ready! Running sample queries...")
    print("-" 60)
    
    # Demo queries
    demo_queries = [
        "What's happening with office rents in London?",
        "Tell me about vacancy rates in Canary Wharf",
        "What's the latest news in the London office market?",
        "Generate a market report",
        "What's driving occupier demand?",
    ]
    
    print("\nRunning demo queries...\n")
    
    for query in demo_queries:
        print(f"Query: {query}")
        print("-" 60)
        response = agent.process_query(query)
        print(response)
        print()
    
    # Show status
    print("\n[icon] Agent Status:")
    status = agent.get_status()
    for key, value in status.items():
        print(f"  - {key}: {value}")


if __name__ == "__main__":
    main()

