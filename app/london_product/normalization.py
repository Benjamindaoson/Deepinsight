"""Deterministic derived fields; annual rent requires explicit source wording.

Raw values are preserved. Model-provided units and industry convention cannot
supply a missing time denominator, including for legacy approved observations.
"""
import re
from decimal import Decimal
from london_data.contracts import source_precision

VERSION = 'product-normalization-v5-explicit-annual'

ANNUAL_PATTERN = re.compile(r'\bper\s+annum\b|\bper\s+year\b|/\s*(?:year|annum)\b|\bp\.?\s?a\.?\b|每年|年租金', re.I)
AREA_RENT_PATTERN = re.compile(
    r'(?:gbp|£)\s*[0-9.,]*\s*(?:/|per)\s*(?:sq|square)'
    r'|per\s+(?:sq|square)\s*\.?\s*(?:ft|foot|feet|m)\b'
    r'|sq\s*\.?\s*ft|\bsqft\b|平方英尺|平方尺|每平方', re.I)
YEAR_UNITS = {'GBP/sqft/year', 'GBP/sqm/year'}


def annualization(value, unit=None, quote=''):
    """Classify the annual basis of a rent observation; never guesses a number."""
    quote = quote or ''
    unit = unit or ''
    if ANNUAL_PATTERN.search(quote):
        return 'explicit'
    return 'unknown'


def derive(fact):
    raw = fact.get('raw_value', fact.get('value'))
    unit = fact.get('raw_unit', fact.get('unit'))
    value = Decimal(str(raw)) if raw is not None else None
    normalized_unit = unit
    scale = Decimal(1)
    notes = []
    if unit in ['%', 'percent']:
        normalized_unit = 'percent'
    elif unit in ['m sq ft', 'million sq ft', 'million sqft']:
        normalized_unit = 'sqft'
        scale = Decimal(1000000)
    elif unit in ['sq ft', 'sq.ft.', 'sqft']:
        normalized_unit = 'sqft'
    elif unit in ['sq m', 'sq.m.', 'sqm']:
        normalized_unit = 'sqm'
    else:
        # Descriptive units from reports ("million sqft for a single quarter")
        # still describe an area; normalise the scale so magnitudes compare.
        lowered_unit = (unit or '').lower()
        if fact.get('metric') in ('takeup', 'supply', 'prelet', 'availability') and 'sq' in lowered_unit:
            normalized_unit = 'sqft'
            if 'million' in lowered_unit or re.search(r'\bm\s*sq', lowered_unit):
                scale = Decimal(1000000)
    period = fact.get('raw_period', fact.get('period'))
    match = re.fullmatch(r'Q([1-4]) (\d{4})', period or '')
    normalized_period = match[2] + 'Q' + match[1] if match else period
    quote = fact.get('evidence', {}).get('quote') or fact.get('quote', '')
    precision = source_precision(value * scale if value is not None else None, quote)
    verified = value is not None and precision != 'unknown'
    is_rent = fact.get('metric') == 'rent'
    basis = annualization(value, unit, quote) if is_rent else 'not_applicable'
    annual = (not is_rent) or basis == 'explicit'
    if not verified:
        notes.append('NUMERIC_VALUE_NOT_BOUND_TO_QUOTE')
    if is_rent and basis == 'unknown':
        notes.append('ANNUAL_TIME_DENOMINATOR_NOT_CONFIRMED')
    if is_rent and annual:
        lowered = (unit or '').lower()
        per_sqm = 'sqm' in lowered or 'sq m' in lowered or 'sq.m' in lowered
        if per_sqm:
            normalized_unit = 'GBP/sqm/year'
        elif 'sq' in lowered or 'square' in lowered or 'per ft' in lowered:
            normalized_unit = 'GBP/sqft/year'
    if is_rent and not annual:
        normalized_unit = 'GBP/sqft/unknown' if 'sq ft' in (unit or '') or 'sqft' in (unit or '') else None
    return dict(raw_value=raw, raw_unit=unit, raw_period=period,
        normalized_value=str(value * scale) if verified and annual else None,
        normalized_unit=normalized_unit, normalized_period=normalized_period, normalized_precision=precision,
        normalization_version=VERSION, normalization_notes=notes,
        annualization=basis,
        annualization_assumption=('来源原文明确按年' if basis == 'explicit'
            else '无法确认年度分母' if is_rent else '不适用'))


def current_fact(fact):
    """Read projection: enforce the current contract without rewriting history."""
    if fact.get('metric') != 'rent':
        return fact
    derived = derive(fact)
    result = dict(fact, **derived)
    if derived['annualization'] != 'explicit' and fact.get('status') not in ['rejected', 'superseded']:
        result.update(status='needs_review', human_review_status='pending_review', annual_basis_blocked=True,
                      stored_status=fact.get('status'), stored_human_review_status=fact.get('human_review_status'))
    return result
