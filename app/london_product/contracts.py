from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductFact(BaseModel):
    model_config = ConfigDict(extra='forbid')
    metric: Literal['rent','vacancy','availability','takeup','supply','prelet','prelet_share','grade_a_share','interest_rate','inflation_rate','employment']
    value: Decimal | None = None
    unit: str | None = None
    geography: str | None = None
    period: str | None = None
    definition: str | None = None
    grade: str | None = None
    method: str | None = None
    currency: str | None = None
    basis: str | None = None
    segment_id: str
    quote: str = Field(max_length=1200)


class ProductExtraction(BaseModel):
    facts: list[ProductFact] = Field(default_factory=list,max_length=30)
    themes: list[str] = Field(default_factory=list,max_length=12)
    missing_or_ambiguous: list[str] = Field(default_factory=list,max_length=30)


class AskInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str = Field(min_length=1,max_length=4000)
    mode: Literal['auto','saved','agent'] = 'saved'
    parent_report_id: str | None = Field(default=None,max_length=160)
    session_id: str | None = Field(default=None,max_length=160)
    refresh_sources: bool = False

    @field_validator('message')
    @classmethod
    def meaningful_message(cls,value):
        if not value.strip():raise ValueError('Message cannot be whitespace only')
        return value


class ClassifyInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str = Field(min_length=1,max_length=4000)
    mode: Literal['auto','saved','agent'] = 'auto'

    @field_validator('message')
    @classmethod
    def meaningful_message(cls,value):
        if not value.strip():raise ValueError('Message cannot be whitespace only')
        return value


class CompareInput(BaseModel):
    old_id: str = Field(max_length=160)
    new_id: str = Field(max_length=160)


class ReportInput(BaseModel):
    period: Literal['daily','weekly']='weekly'
    include_analysis: bool=False
    geography: Literal['City','West End','Canary Wharf','Midtown','Fringe','Midtown / Fringe','Central London'] | None = None


class NotifyInput(BaseModel):
    report_id: str


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['approve', 'reject', 'reopen']
    reviewer: str = Field(min_length=2, max_length=80)
    note: str = Field(default='', max_length=1000)
