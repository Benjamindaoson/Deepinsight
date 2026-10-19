"""Offline, transparent heuristic scoring; never substitutes for human fact review."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import statistics

from benchmark import CASES, LEDGER, RESULTS


def decode_answer(content: str | None) -> dict | None:
    if not content:
        return None
    candidate = content.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.I)
    try:
        value = json.loads(candidate)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def score(case: dict, receipt: dict) -> dict:
    if receipt.get("error"):
        return {"total": 0, "extraction": 0, "evidence": 0, "reasoning": 0, "structure": 0, "efficiency": 0, "critical_flags": [], "review_note": "API/parse failure"}
    answer = decode_answer(receipt.get("parsed_content"))
    if answer is None or not isinstance(answer.get("facts"), list) or not isinstance(answer.get("limitations"), list):
        return {"total": 0, "extraction": 0, "evidence": 0, "reasoning": 0, "structure": 0, "efficiency": 0, "critical_flags": [], "review_note": "Invalid shared JSON schema"}
    facts = answer["facts"]
    valid_ids = {item["id"] for item in case["evidence"]}
    valid_status = {"verified_source_statement", "publisher_reported_change", "needs_review", "not_comparable"}
    typed = [f for f in facts if isinstance(f, dict) and isinstance(f.get("claim"), str) and isinstance(f.get("evidence_ids"), list) and f.get("status") in valid_status]
    structure = 15 if len(typed) == len(facts) and facts and all(isinstance(x, str) for x in answer["limitations"]) else 7
    prose = " ".join([str(f.get("claim", "")) for f in typed] + [str(x) for x in answer["limitations"]])
    required = case["checks"]["required"]
    matched = sum(bool(re.search(re.escape(term), prose, flags=re.I)) for term in required)
    extraction = round(30 * matched / len(required)) if required else 0
    cited = [f for f in typed if f["evidence_ids"] and all(x in valid_ids for x in f["evidence_ids"])]
    evidence = round(25 * len(cited) / len(typed)) if typed else 0
    critical = [pattern for pattern in case["checks"]["critical_forbidden"] if re.search(pattern, prose, re.I)]
    reasoning = 0 if critical else (20 if answer["limitations"] else 12)
    latency = receipt.get("latency_seconds")
    # Efficiency is deliberately only 10% of the screening score.
    efficiency = 10 if isinstance(latency, (int, float)) and latency <= 30 else 5
    total = extraction + evidence + reasoning + structure + efficiency
    return {"total": total, "extraction": extraction, "evidence": evidence, "reasoning": reasoning, "structure": structure, "efficiency": efficiency, "critical_flags": critical, "review_note": "Provisional automatic screening; human semantic review still required"}


def main() -> None:
    cases = {x["id"]: x for x in json.loads(CASES.read_text(encoding="utf-8"))["cases"]}
    ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else []
    rows = []
    for item in ledger:
        receipt = json.loads((RESULTS / item["receipt"]).read_text(encoding="utf-8"))
        review = score(cases[item["case_id"]], receipt)
        invalid_input = item["case_id"] == "news_planning"
        rows.append({"model": item["model"], "case_id": item["case_id"], "http_status": item["http_status"], "error": item["error"], "input_tokens": item["input_tokens"], "output_tokens": item["output_tokens"], "latency_seconds": item["latency_seconds"], "cost_estimate_cny": item["cost_estimate_cny"] if item["input_tokens"] is not None and item["output_tokens"] is not None else "N/A", "budget_reservation_cny": item["cost_estimate_cny"], "actual_billed_cny": "N/A", "input_validity": "INVALID" if invalid_input else "PROVISIONAL", **{k: ("N/A" if invalid_input else review[k]) for k in ("total", "extraction", "evidence", "reasoning", "structure", "efficiency")}, "critical_flags": ";".join(review["critical_flags"]), "receipt": item["receipt"]})
    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / "summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["model", "case_id", "http_status", "error", "input_tokens", "output_tokens", "latency_seconds", "cost_estimate_cny", "budget_reservation_cny", "actual_billed_cny", "input_validity", "total", "extraction", "evidence", "reasoning", "structure", "efficiency", "critical_flags", "receipt"])
        writer.writeheader()
        writer.writerows(rows)
    lines = ["# ToAPIs London office model benchmark — first round", "", "**Outcome: PARTIAL / no valid three-model ranking.** Six GPT requests returned usable JSON; the relay-advertised Qwen ID returned model_not_found on its first real request; DeepSeek used its entire 1,600-token output allowance for reasoning and returned no answer. No failed request was retried or replaced with another model.", "", "Status: provisional source-grounded screening. The reference assertions were checked against preserved source files but have **not** been signed off as a human gold standard. Provider identity is relay-reported; underlying upstream identity is not independently attested. The news_planning input mistakenly names the Planning and Transportation Committee; the actual saved City of London source says Planning Applications Sub-Committee. This case is **INVALID as a factual-quality test** and is excluded from any conclusion. The original as-sent input and response remain preserved; see [`../datasets/ERRATA.md`](../datasets/ERRATA.md).", "", f"Requests recorded: {len(rows)}/18. Authentication: bearer key supplied at runtime, never saved. Endpoint: `https://toapis.cn/v1/chat/completions`. One request per model/case; no retry or fallback. Actual billed fee: N/A (no reliable invoice returned); CNY figures below are usage-derived account-price estimates where usage exists. A no-usage request has N/A cost estimate but still reserves budget.", "", "| Model | Cases recorded | Mean provisional score /100 | Critical flags | Median latency | Input tokens | Output tokens | Reference cost CNY |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for model in ["gpt-6-astra-official", "qwen3-max", "deepseek-v4-pro"]:
        group = [r for r in rows if r["model"] == model]
        vals = [r["total"] for r in group if not r["error"] and r["case_id"] != "news_planning"]
        median = statistics.median(r["latency_seconds"] for r in group) if group else 0
        total_in = sum(r["input_tokens"] or 0 for r in group)
        total_out = sum(r["output_tokens"] or 0 for r in group)
        total_cost = sum(float(r["cost_estimate_cny"]) for r in group if r["cost_estimate_cny"] != "N/A")
        mean_score = f"{statistics.mean(vals):.1f}" if vals else "N/A"
        input_display = total_in if all(r["input_tokens"] is not None for r in group) else "N/A"
        output_display = total_out if all(r["output_tokens"] is not None for r in group) else "N/A"
        cost_display = (f"{total_cost:.4f}" if any(r["cost_estimate_cny"] != "N/A" for r in group) else "N/A")
        if cost_display != "N/A" and any(r["cost_estimate_cny"] == "N/A" for r in group):
            cost_display += " (partial)"
        lines.append(f"| {model} | {len(group)}/6 | {mean_score} (eligible {len(vals)}) | {sum(bool(r['critical_flags']) for r in group)} | {median:.2f}s | {input_display} | {output_display} | {cost_display} |" if group else f"| {model} | 0/6 | N/A | N/A | N/A | N/A | N/A | N/A |")
    lines += ["", "Scores are deterministic heuristics: extraction 30, valid evidence references 25, guarded reasoning 20, JSON/schema 15, latency 10. Regex critical flags require manual inspection because a model may mention an unsafe claim only to reject it. Price is reported separately and never treated as a quality substitute. A single sample per case does not establish statistical superiority. The invalid news_planning input is marked N/A in the CSV and excluded from any model-quality claim.", "", "## Per-case receipts", "", "| Model | Case | Status | Score | Critical flags | Raw receipt |", "|---|---|---|---:|---|---|"]
    for r in rows:
        lines.append(f"| {r['model']} | {r['case_id']} | {r['error'] or 'HTTP '+str(r['http_status'])}{' / INVALID INPUT' if r['case_id'] == 'news_planning' else ''} | {r['total']} | {r['critical_flags'] or 'none flagged'} | [{r['receipt']}]({r['receipt']}) |")
    if len(rows) < 18:
        lines += ["", "## Unexecuted cases", "", "Remaining calls were not run. The first failing receipt and ledger show the stop reason; unrun work is not marked PASS."]
    lines += ["", "## Protocol and limits", "", "See [`PREFLIGHT.md`](PREFLIGHT.md) for authenticated model discovery, requested versus returned model IDs, reference pricing, and the capability matrix. See [`MANUAL_AUDIT.md`](MANUAL_AUDIT.md) for source-level assessment and the invalid case explanation. The complete request ledger is [`ledger.json`](ledger.json).", "", "The six fixed cases, reference assertions, source URLs, page/HTML locators, and SHA-256 hashes are in [`../datasets/cases.json`](../datasets/cases.json). Each model received the same system prompt, schema, question, and excerpts for each case. Calls use Chat Completions, non-streaming, max output 1,600 tokens and 90-second timeout. Chat/JSON capability was exercised only where a request completed. Responses API, tools and streaming were not independently tested by this round.", "", "Do not promote `verified_source_statement` generated by a model to an approved database fact. Rent annual denominator and vacancy-method comparability remain under review. Published take-up percent and rounded-value arithmetic are different statements."]
    (RESULTS / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} rows to summary.csv and REPORT.md")


if __name__ == "__main__":
    main()
