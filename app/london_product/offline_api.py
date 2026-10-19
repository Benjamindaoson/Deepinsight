"""Small, model-free API for a local saved-evidence demonstration.

The `mock` mode name describes execution without provider credentials. Market
facts are read from saved source snapshots and are never fabricated here.
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .store import now
from .skill_registry import validate_registry
from .version import PRODUCT_VERSION


DISCLAIMER = (
    "Offline saved-evidence mode. Values may be missing, stale or pending human "
    "review; no live retrieval or model analysis is claimed. Not investment advice."
)


def structured_log(skill, started, *, datasource="saved_snapshots", error=None, status="ok"):
    logging.getLogger("uvicorn.error").info(json.dumps({
        "timestamp": now(), "skill": skill, "datasource": datasource,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "error": error, "status": status,
    }, ensure_ascii=False))


class OfflineContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OfflineChatInput(OfflineContract):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=160)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be blank")
        return value


class OfflineReportInput(OfflineContract):
    month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")

    @field_validator("month")
    @classmethod
    def real_month(cls, value: str | None) -> str | None:
        if value is not None and not 1 <= int(value[-2:]) <= 12:
            raise ValueError("Month must be between 01 and 12")
        return value


class AlertRule(OfflineContract):
    geography: str = Field(min_length=1, max_length=120)
    metric: Literal["prime_rent", "vacancy", "takeup", "supply"]
    definition: str = Field(min_length=1, max_length=200)
    comparison_window: Literal["month_over_month", "quarter_over_quarter", "year_over_year"]
    operator: Literal[">", ">=", "<", "<="]
    threshold: float
    unit: Literal["percent", "percentage_points", "sqft"]
    enabled: bool = True


class AlertInput(OfflineContract):
    rent_threshold_pct: float | None = Field(default=None, gt=0)
    takeup_threshold_pct: float | None = Field(default=None, gt=0)
    vacancy_threshold_pp: float | None = Field(default=None, gt=0)
    rules: list[AlertRule] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def not_empty(self):
        if not self.rules and all(value is None for value in (
                self.rent_threshold_pct, self.takeup_threshold_pct,
                self.vacancy_threshold_pp)):
            raise ValueError("Provide a threshold or at least one scoped alert rule")
        return self


def saved_context_answer(store, message: str):
    """Read saved macro and office-demand disclosures at their own geography."""
    from .safe_answer import render_groups, safe_evidence

    rate = bool(re.search(r"bank rate|interest rate|利率|基准利率", message, re.I))
    employment = bool(re.search(r"employment|就业", message, re.I))
    esg = bool(re.search(r"\bESG\b|sustainab|可持续", message, re.I))
    hybrid = bool(re.search(r"hybrid work|混合办公", message, re.I))
    if not any((rate, employment, esg, hybrid)):
        return None

    facts = []
    if rate:
        facts.extend(f for f in store.all("facts") if f.get("metric") == "interest_rate"
                     and f.get("geography") == "United Kingdom")
    if employment:
        area = "London (workplace)" if re.search(r"London|伦敦", message, re.I) else "United Kingdom"
        facts.extend(f for f in store.all("facts") if f.get("metric") == "employment"
                     and f.get("geography") == area)
    events = []
    if esg:
        events = [e for e in store.all("events") if e.get("kind") == "demand"
                  and re.search(r"office|occupier|accommodation", str((e.get("evidence") or {}).get("quote", "")), re.I)
                  and re.search(r"sustainab|BREEAM|ESG", str((e.get("evidence") or {}).get("quote", "")), re.I)][:2]
    groups, omitted = safe_evidence(store, [dict(facts=facts, events=events)])
    items = [item for rows in groups.values() for item in rows]
    sources = list({item["document_id"]: dict(document_id=item["document_id"],
        title=item["report_title"], url=item["url"], published_at=item["published_at"],
        sha256=item["source_document_sha256"], receipt_sha256=item.get("receipt_sha256"),
        collected_at=(store.get("documents", item["document_id"]) or {}).get("collected_at"))
        for item in items}.values())
    lines = ["Saved source disclosures follow. Geography, period and pending review status are retained; these are not approved London office market changes."]
    lines += render_groups(groups, omitted)
    if hybrid:
        lines.append("数据不足 / Insufficient verified evidence to establish the effect of hybrid working on London office demand. ESG disclosures do not substitute for hybrid-working evidence.")
    if not sources:
        lines.insert(0, "数据不足 / Insufficient evidence: no relevant saved record passed the original-hash and quote-location checks.")
    lines.append("No cross-publisher comparison, causal inference or forecast was performed. Not investment advice.")
    return dict(answer="\n\n".join(lines), sources=sources,
                quality_status="insufficient_evidence")


def skill_names_for_message(message: str) -> list[str]:
    """Return canonical Skill names for a deterministic saved-evidence route."""
    from .chat_report import resolve_scope

    scope = resolve_scope(message)
    names = {"market-intelligence", "verification"}
    metrics = set(scope["metrics"])
    if metrics & {"supply", "prelet"}:
        names.add("supply-pipeline")
    if metrics & {"interest_rate", "employment", "inflation_rate"} or re.search(
            r"Bank of England|Bank Rate|BoE|macro|interest rate|employment|宏观|利率|就业",
            message, re.I):
        names.add("macro-drivers")
    if len(scope["geographies"]) > 1 or any(
            geography != "Central London" for geography in scope["geographies"]):
        names.add("submarket-analysis")
    if re.search(r"submarket|子市场", message, re.I):
        names.add("submarket-analysis")
    if re.search(r"news|event|新闻|事件", message, re.I):
        names.add("event-monitor")
    if scope["needs_comparison"] or scope["needs_history"]:
        names.add("comparison")
    if scope["report_type"] != "fact_answer" or re.search(
            r"evidence supports|flight.to.quality|ESG|hybrid working|证据|影响",
            message, re.I):
        names.add("analysis")
    return sorted(names)


def register_offline_endpoints(app: FastAPI, service) -> None:
    """Attach compatibility routes without adding another agent or data store."""
    from .intelligence import run_saved_query_workflow

    session_reports: dict[str, str] = {}

    def stamp():
        dates = [str(d.get("collected_at")) for d in service.store.all("documents") if d.get("collected_at")]
        return max(dates) if dates else None

    @app.get("/skills")
    def offline_skills():
        started = time.perf_counter()
        skills = validate_registry()
        structured_log("skill-registry", started)
        return dict(skills=skills, sources=[], as_of=stamp(), disclaimer=DISCLAIMER)

    @app.post("/chat")
    def offline_chat(data: OfflineChatInput):
        from .chat_report import render_markdown

        started = time.perf_counter()
        try:
            message = data.message.strip()
            if re.search(r"\b(email|e-mail|phone|contact details?)\b|邮箱|电话|联系方式", message, re.I):
                structured_log(["verification"], started, datasource="policy_boundary")
                return dict(answer="Personal contact information cannot be provided or inferred. The saved evidence service does not perform personal-data searches.",
                            session_id=data.session_id, sources=[], as_of=stamp(),
                            skill_calls=[dict(skill="verification", datasource="policy_boundary")],
                            quality_status="refused_private_data", disclaimer=DISCLAIMER)
            years = [int(year) for year in re.findall(r"\b(20\d{2})\b", message)]
            requests_future = any(year > datetime.now(timezone.utc).year for year in years) or bool(
                re.search(r"\b(next year|future)\b|明年|未来", message, re.I))
            future_precision = requests_future and re.search(
                r"\b(exact|certain|definite|guaranteed)\b|确定值|保证|精确预测", message, re.I)
            if future_precision:
                structured_log(["verification"], started, datasource="policy_boundary")
                return dict(answer="数据不足 / A future rent cannot be stated as certain. Any supported scenario must retain its assumptions, source date and uncertainty.",
                            session_id=data.session_id, sources=[], as_of=stamp(),
                            skill_calls=[dict(skill="verification", datasource="policy_boundary")],
                            quality_status="refused_false_precision", disclaimer=DISCLAIMER)
            focused,focused_run_id=run_saved_query_workflow(service,'focused',question=message,
                parent_report_id=session_reports.get(data.session_id),session_id=data.session_id)
            if focused['handled']:
                structured_log(["verification"], started)
                return dict(focused,session_id=data.session_id,as_of=stamp(),disclaimer=DISCLAIMER,
                    quality_status=focused.get('status'),skill_calls=[dict(skill='verification',datasource='saved_snapshots')],
                    run_id=focused_run_id,execution_path='agno_workflow')
            context_result,context_run_id=run_saved_query_workflow(service,'context',question=message)
            context=context_result['context']
            if context is not None:
                context_skills = {"market-intelligence", "verification"}
                if re.search(r"Bank of England|Bank Rate|BoE|interest rate|employment|利率|就业", message, re.I):
                    context_skills.add("macro-drivers")
                if re.search(r"ESG|sustainab|hybrid work|影响|证据", message, re.I):
                    context_skills.add("analysis")
                if re.search(r"Midtown|Canary Wharf|submarket|子市场", message, re.I):
                    context_skills.add("submarket-analysis")
                structured_log(sorted(context_skills), started)
                return dict(answer=context["answer"], session_id=data.session_id,
                            sources=context["sources"], as_of=stamp(),
                            skill_calls=[dict(skill=name, datasource="saved_snapshots")
                                         for name in sorted(context_skills)],
                            quality_status=context["quality_status"], disclaimer=DISCLAIMER,
                            run_id=context_run_id,execution_path='agno_workflow')
            parent_report_id = session_reports.get(data.session_id) if data.session_id else None
            result,report_run_id=run_saved_query_workflow(service,'report_context',question=data.message,
                parent_report_id=parent_report_id)
            artifact=service.store.get('reports',result['report_id'])['artifact']
            if data.session_id:
                session_reports[data.session_id] = artifact["report_id"]
            answer = render_markdown(artifact)
            if not artifact["sources"]:
                answer = "数据不足 / Insufficient evidence: no citable market original is saved locally.\n\n" + answer
            skill_names = skill_names_for_message(message)
            structured_log(sorted(skill_names), started)
            return dict(answer=answer, session_id=data.session_id, sources=artifact["sources"],
                        as_of=stamp(), skill_calls=[dict(skill=name, datasource="saved_snapshots")
                                                   for name in sorted(skill_names)],
                        quality_status=artifact["generation_status"], disclaimer=DISCLAIMER,
                        run_id=report_run_id,execution_path='agno_workflow')
        except Exception as exc:
            structured_log(["market-intelligence"], started, error=type(exc).__name__, status="error")
            raise

    @app.post("/report")
    def offline_report(data: OfflineReportInput):
        from .chat_report import render_markdown

        started = time.perf_counter()
        question = "Monthly London office market rent vacancy take-up supply news monitoring brief"
        if data.month:
            question += " for " + data.month
        try:
            result,run_id=run_saved_query_workflow(service,'report_context',question=question)
            artifact=service.store.get('reports',result['report_id'])['artifact']
            structured_log(["reporting", "verification"], started)
            markdown = render_markdown(artifact)
            if not artifact["sources"]:
                markdown = "数据不足 / Insufficient evidence: no citable market original is saved locally.\n\n" + markdown
            return dict(report_id=artifact["report_id"], markdown=markdown,
                        sources=artifact["sources"], as_of=stamp(),
                        skill_calls=[dict(skill="reporting", datasource="saved_snapshots"),
                                     dict(skill="verification", datasource="saved_snapshots")],
                        quality_status=artifact["generation_status"], disclaimer=DISCLAIMER,
                        run_id=run_id,execution_path='agno_workflow')
        except Exception as exc:
            structured_log(["reporting", "verification"], started, error=type(exc).__name__, status="error")
            raise

    @app.get("/alerts")
    def offline_alerts():
        started = time.perf_counter()
        settings = service.settings()
        record = service.store.get("settings", "offline-alert-rules") or {"rules": []}
        structured_log(["alerting"], started)
        return dict(settings={k: settings[k] for k in ("rent_threshold_pct", "takeup_threshold_pct",
                                                  "vacancy_threshold_pp", "monitoring_enabled")},
                    rules=record.get("rules", []), sources=[], as_of=stamp(),
                    skill_calls=[dict(skill="alerting", datasource="saved_settings")],
                    disclaimer=DISCLAIMER)

    @app.post("/alerts")
    def set_offline_alerts(data: AlertInput):
        started = time.perf_counter()
        values = data.model_dump(exclude_none=True, exclude={"rules"})
        settings = service.save_settings(values) if values else service.settings()
        record = service.store.get("settings", "offline-alert-rules")
        rules = [rule.model_dump() for rule in data.rules]
        if record:
            record = service.store.update("settings", record["id"], {"rules": rules})
        else:
            record = service.store.put("settings", "offline-alert-rules", {"rules": rules})
        structured_log(["alerting"], started, datasource="saved_settings")
        return dict(settings={k: settings[k] for k in ("rent_threshold_pct", "takeup_threshold_pct",
                                                  "vacancy_threshold_pp", "monitoring_enabled")},
                    rules=record["rules"], sources=[], as_of=stamp(),
                    skill_calls=[dict(skill="alerting", datasource="saved_settings")],
                    disclaimer=DISCLAIMER)


def offline_health_payload(service):
    started = time.perf_counter()
    dates = [str(d.get("collected_at")) for d in service.store.all("documents") if d.get("collected_at")]
    payload = dict(status="ok", version=PRODUCT_VERSION, mode="mock", data_asof=max(dates) if dates else None,
                   sources=[], disclaimer=DISCLAIMER)
    structured_log("system-health", started)
    return payload
