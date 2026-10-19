"""Versioned wire contract shared by chat delivery and existing Reports storage."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Scope(Contract):
    report_type: Literal['fact_answer', 'topic_analysis', 'market_report']
    geographies: list[str]
    observation_period: str | None
    metrics: list[str]
    needs_comparison: bool = False
    needs_history: bool = False
    requested_periods: list[str] = Field(default_factory=list)


class Claim(Contract):
    kind: Literal['observation','change','source_statement','research_action','state_assertion','conditional_scenario','regional_ordering']
    metric: str | None = None
    value: str | None = None
    unit: str | None = None
    geography: str
    observation_period: str | None = None
    definition: str | None = None
    method: str | None = None
    evidence_ids: list[str]
    locator: str | None = None
    action: Literal['monitor','investigate_demand','review_supply','check_comparability'] | None = None
    quote: str | None = None
    old_id: str | None = None
    new_id: str | None = None
    old_observation_period: str | None = None
    direction: Literal['increase','decrease','unchanged'] | None = None
    state: Literal['regions_approved','coverage_complete','saved_presence','approved_presence','pending_presence','semantic_approved'] | None = None
    expected: bool | None = None
    scope_geographies: list[str] | None = None
    scope_metrics: list[str] | None = None
    rule: Literal['takeup_up_vacancy_down'] | None = None
    perspective: Literal['occupier_risk','landlord_opportunity'] | None = None
    takeup_old_id: str | None = None
    takeup_new_id: str | None = None
    vacancy_old_id: str | None = None
    vacancy_new_id: str | None = None
    other_geography: str | None = None
    left_id: str | None = None
    right_id: str | None = None
    relative_direction: Literal['higher','lower'] | None = None


class Finding(Contract):
    text: str
    classification: Literal['fact', 'calculation', 'inference', 'scenario']
    evidence_ids: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list,max_length=8)
    origin: Literal['deterministic', 'model_interpretation'] = 'deterministic'
    verification: dict | None = None


class Point(Contract):
    label: str
    value: str | None = None
    fact_id: str | None = None
    evidence_ids: list[str]
    geography: str | None = None
    period: str | None = None
    date: str | None = None
    category: str | None = None


class Chart(Contract):
    id: str
    type: Literal['time_series','regional_comparison','supply_structure','event_timeline']
    title: str
    metric: str | None = None
    unit: str | None = None
    geographies: list[str]
    observation_period: str | None
    status: Literal['ready','unavailable','error']
    reason: str | None = None
    points: list[Point] = Field(default_factory=list)


class ReportArtifact(Contract):
    schema_version: Literal['1.0'] = '1.0'
    report_id: str
    title: str
    report_type: Literal['fact_answer','topic_analysis','market_report']
    generated_at: str
    query: str
    parent_report_id: str | None = None
    scope: Scope
    geographies: list[str]
    observation_period: str | None
    executive_summary: list[Finding]
    market_snapshot: list[dict]
    related_observations: list[dict] = Field(default_factory=list)
    regional_comparison: list[dict]
    calculations: list[dict]
    conflicts: list[dict] = Field(default_factory=list)
    charts: list[Chart]
    key_findings: list[Finding]
    risks: list[Finding]
    opportunities: list[Finding]
    outlook: list[Finding]
    data_gaps: list[dict]
    limitations: list[str]
    sources: list[dict]
    evidence: list[dict]
    generation_status: Literal['success','partial','insufficient_evidence','failed']
    publication_review: dict
    ai_analysis: dict | None = None
    acquisition: dict


class ReportInterpretation(Contract):
    """The model may propose prose, never facts, numbers, charts or publication state."""
    key_findings: list[Finding] = Field(default_factory=list,max_length=4)
    risks: list[Finding] = Field(default_factory=list,max_length=3)
    opportunities: list[Finding] = Field(default_factory=list,max_length=3)
    outlook: list[Finding] = Field(default_factory=list,max_length=3)
