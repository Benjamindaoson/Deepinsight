"""
London Office Market Skills Module
===================================
Specialized skills for the London Office Market Monitoring Agent.
Each skill handles a specific domain of market intelligence.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class MarketDataPoint:
    """A single data point from the market"""
    metric: str
    value: float
    unit: str
    area: str
    timestamp: datetime
    source: str


class BaseSkill(ABC):
    """Abstract base class for all skills"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Skill name"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Skill description"""
        pass
    
    @abstractmethod
    def execute(self, params: Dict) -> Dict:
        """Execute the skill with given parameters"""
        pass


class MarketDataSkill(BaseSkill):
    """Skill for fetching and analyzing market data"""
    
    @property
    def name(self) -> str:
        return "MarketDataSkill"
    
    @property
    def description(self) -> str:
        return "Fetches real-time market data including rents, vacancy, and take-up"
    
    def __init__(self):
        self.data_sources = {
            "CoStar": "https://www.costar.com",
            "CBRE": "https://www.cbre.com",
            "JLL": "https://www.jll.com",
            "Knight Frank": "https://www.knightfrank.com"
        }
    
    def execute(self, params: Dict) -> Dict:
        """Fetch market data based on parameters"""
        metric = params.get("metric", "rents")
        area = params.get("area", "all")
        
        # Simulated data - in production would call actual APIs
        return {
            "status": "success",
            "metric": metric,
            "area": area,
            "data": self._get_market_data(metric, area),
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_market_data(self, metric: str, area: str) -> Dict:
        """Get market data (simulated)"""
        data_templates = {
            "rents": {
                "City": {"prime": 70, "grade_a": 60, "unit": "£/sq ft"},
                "West End": {"prime": 110, "grade_a": 85, "unit": "£/sq ft"},
                "Canary Wharf": {"prime": 55, "grade_a": 48, "unit": "£/sq ft"},
                "Midtown": {"prime": 75, "grade_a": 65, "unit": "£/sq ft"}
            },
            "vacancy": {
                "City": 8.2,
                "West End": 5.5,
                "Canary Wharf": 10.5,
                "Midtown": 7.0
            }
        }
        return data_templates.get(metric, {})


class NewsMonitorSkill(BaseSkill):
    """Skill for monitoring news and market events"""
    
    @property
    def name(self) -> str:
        return "NewsMonitorSkill"
    
    @property
    def description(self) -> str:
        return "Monitors news feeds for London office market developments"
    
    def execute(self, params: Dict) -> Dict:
        """Monitor news based on filters"""
        keywords = params.get("keywords", [])
        date_range = params.get("date_range", "7d")
        
        return {
            "status": "success",
            "news_items": self._fetch_news(keywords, date_range),
            "count": 5,
            "timestamp": datetime.now().isoformat()
        }
    
    def _fetch_news(self, keywords: List[str], date_range: str) -> List[Dict]:
        """Fetch news items (simulated)"""
        return [
            {
                "title": "Major tech firm expands in King's Cross",
                "source": "CoStar",
                "date": "2024-10-15",
                "summary": "Google secures additional 700,000 sq ft at King's Cross development"
            },
            {
                "title": "ESG-certified buildings command 15% rental premium",
                "source": "JLL",
                "date": "2024-10-14",
                "summary": "Green credentials increasingly important for occupiers"
            },
            {
                "title": "Canary Wharf announces new 500,000 sq ft development",
                "source": "Property Week",
                "date": "2024-10-12",
                "summary": "Wood Wharf expansion continues with Phase 3"
            }
        ]


class AnalysisEngineSkill(BaseSkill):
    """Skill for trend analysis and forecasting"""
    
    @property
    def name(self) -> str:
        return "AnalysisEngineSkill"
    
    @property
    def description(self) -> str:
        return "Performs trend analysis and market forecasting"
    
    def execute(self, params: Dict) -> Dict:
        """Run analysis based on parameters"""
        analysis_type = params.get("type", "trend")
        areas = params.get("areas", ["City", "West End"])
        
        return {
            "status": "success",
            "analysis_type": analysis_type,
            "results": self._analyze(analysis_type, areas),
            "confidence": 0.85,
            "timestamp": datetime.now().isoformat()
        }
    
    def _analyze(self, analysis_type: str, areas: List[str]) -> Dict:
        """Run analysis (simulated)"""
        if analysis_type == "trend":
            return {
                "direction": "upward",
                "magnitude": "3-5%",
                "timeframe": "12 months",
                "key_drivers": ["flight-to-quality", "limited supply", "tech demand"]
            }
        return {}


class ReportGeneratorSkill(BaseSkill):
    """Skill for generating formatted reports"""
    
    @property
    def name(self) -> str:
        return "ReportGeneratorSkill"
    
    @property
    def description(self) -> str:
        return "Generates formatted market reports and summaries"
    
    def execute(self, params: Dict) -> Dict:
        """Generate report based on parameters"""
        report_type = params.get("type", "summary")
        format = params.get("format", "markdown")
        
        return {
            "status": "success",
            "report_type": report_type,
            "format": format,
            "content": self._generate_content(report_type),
            "timestamp": datetime.now().isoformat()
        }
    
    def _generate_content(self, report_type: str) -> str:
        """Generate report content"""
        templates = {
            "summary": "## Market Summary\n\nLondon office market showing resilience...",
            "detailed": "## Detailed Market Analysis\n\n### Vacancy Rates\n...",
            "executive": "## Executive Summary\n\nKey takeaways for leadership..."
        }
        return templates.get(report_type, templates["summary"])


class AlertSkill(BaseSkill):
    """Skill for managing market alerts"""
    
    @property
    def name(self) -> str:
        return "AlertSkill"
    
    @property
    def description(self) -> str:
        return "Manages market alerts based on user-defined thresholds"
    
    def execute(self, params: Dict) -> Dict:
        """Check alerts based on current data"""
        alert_type = params.get("alert_type", "rent_change")
        threshold = params.get("threshold", 5.0)
        
        triggered = self._check_alerts(alert_type, threshold)
        
        return {
            "status": "success",
            "alert_type": alert_type,
            "threshold": threshold,
            "alerts_triggered": triggered,
            "count": len(triggered),
            "timestamp": datetime.now().isoformat()
        }
    
    def _check_alerts(self, alert_type: str, threshold: float) -> List[Dict]:
        """Check for triggered alerts"""
        return [
            {
                "message": "Canary Wharf vacancy dropped below 10%",
                "severity": "info",
                "value": 9.8
            }
        ]


# Skill registry for dynamic loading
SKILL_REGISTRY = {
    "MarketDataSkill": MarketDataSkill,
    "NewsMonitorSkill": NewsMonitorSkill,
    "AnalysisEngineSkill": AnalysisEngineSkill,
    "ReportGeneratorSkill": ReportGeneratorSkill,
    "AlertSkill": AlertSkill
}


def get_skill(skill_name: str) -> Optional[BaseSkill]:
    """Factory function to get a skill instance"""
    skill_class = SKILL_REGISTRY.get(skill_name)
    if skill_class:
        return skill_class()
    return None


def list_available_skills() -> List[str]:
    """List all available skills"""
    return list(SKILL_REGISTRY.keys())
