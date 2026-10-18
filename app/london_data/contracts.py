from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, create_model
import re
import copy


class Evidence(BaseModel):
    model_config = ConfigDict(extra='forbid')
    segment_id: str
    quote: str = Field(max_length=2200)


class Observation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    metric: Literal['rent', 'vacancy', 'takeup']
    value: Decimal | None
    unit: str
    currency: str | None
    source_id: str
    series: str
    geography: str
    definition: str
    period: str
    basis: str
    grade: str
    method: str | None
    precision: str = Field(description='Lexical disclosure increment after scaling, NOT market tick or uncertainty: 92.50 -> 0.01; 95 -> 1; 2.5m sqft -> 100000; 2.69m -> 10000; 8.4% -> 0.1.')
    evidence: Evidence
    status: str = 'candidate'
    document_id: str = ''
    attempt_id: str = ''
    notes: str = ''


class Extraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    observations: list[Observation] = Field(max_length=3)
    missing_or_ambiguous: list[str] = Field(default_factory=list)


# LLM supplies facts and verbatim evidence. Python derives lexical disclosure
# precision; provider output is retained separately, never manually repaired.
RawObservation = create_model('RawObservation',__config__=ConfigDict(extra='forbid'),**{
    name:(info.annotation,copy.deepcopy(info)) for name,info in Observation.model_fields.items() if name!='precision'
})
RawExtraction = create_model('RawExtraction',__config__=ConfigDict(extra='forbid'),
    observations=(list[RawObservation],Field(max_length=3)),
    missing_or_ambiguous=(list[str],Field(default_factory=list)))


def source_precision(value,quote):
    if value is None:return 'unknown'
    steps=set()
    for m in re.finditer(r'(?<![\w.])(?:c\.\s*)?(\d[\d,]*(?:\.\d+)?)\s*([mM]|million|[kK]|thousand)?\b',quote):
        number=Decimal(m[1].replace(',',''));scale=Decimal({'m':1000000,'million':1000000,'k':1000,'thousand':1000}.get((m[2] or '').lower(),1))
        if number*scale==Decimal(str(value)):steps.add(Decimal(10)**number.as_tuple().exponent*scale)
    return format(next(iter(steps)).normalize(),'f') if len(steps)==1 else 'unknown'


def materialize(raw):
    data=RawExtraction.model_validate(raw).model_dump(mode='json')
    return Extraction.model_validate(dict(data,observations=[dict(o,precision=source_precision(o['value'],o['evidence']['quote'])) for o in data['observations']]))
