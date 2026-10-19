"""Bounded, no-retry, source-grounded first-round relay benchmark."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
import getpass
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parents[1]
RESULTS = HERE / "results"
CASES = HERE / "datasets" / "cases.json"
MODEL_LIST = RESULTS / "model-list.json"
LEDGER = RESULTS / "ledger.json"
URL = "https://toapis.cn/v1/chat/completions"
MODELS = [
    ("gpt-6-astra-official", Decimal("56"), Decimal("280")),
    ("qwen3-max", Decimal("4.90"), Decimal("19.60")),
    ("deepseek-v4-pro", Decimal("3.23"), Decimal("9.70")),
]
MAX_CALLS = 18
MAX_INPUT_PER_CALL = 8000
MAX_OUTPUT_PER_CALL = 1600
MAX_CNY = Decimal("8")
TIMEOUT_SECONDS = 90

SYSTEM = """You are an evidence-bound London office market analyst. Use ONLY the numbered source excerpts in the user message. No external knowledge, no invented values, definitions, annual rental period, approvals or transactions. Separate publisher-reported statements from your own arithmetic. An unresolved conflict remains unresolved. Output one JSON object with exactly two top-level fields: facts (list of objects with claim:string, status:verified_source_statement|publisher_reported_change|needs_review|not_comparable, evidence_ids:list of source IDs) and limitations (list of strings). Each numeric claim must cite relevant source IDs. Do not treat a source excerpt as a human-approved database fact. Write concise English. No Markdown fences."""


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_cases() -> list[dict]:
    data = json.loads(CASES.read_text(encoding="utf-8"))
    cases = data["cases"]
    assert len(cases) == 6 and len({c["id"] for c in cases}) == 6
    for case in cases:
        for evidence in case["evidence"]:
            path = ROOT / evidence["path"]
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != evidence["sha256"]:
                raise ValueError(f"Source hash mismatch or missing: {evidence['id']}")
    return cases


def messages(case: dict) -> list[dict]:
    excerpts = "\n\n".join(
        f"[{e['id']}] {e['locator']} | {e['url']}\n{e['text']}"
        for e in case["evidence"]
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Question: {case['question']}\n\nSource excerpts:\n{excerpts}"}]


def conservative_input_bound(message_list: list[dict]) -> int:
    # UTF-8 byte count is used only as a deliberately loose upper BOUND for
    # short prompts, never as a claim about actual token usage.
    return sum(len(item["content"].encode("utf-8")) + 50 for item in message_list) + 300


def estimate_cny(input_tokens: int, output_tokens: int, input_rate: Decimal, output_rate: Decimal) -> Decimal:
    return (Decimal(input_tokens) * input_rate + Decimal(output_tokens) * output_rate) / Decimal(1_000_000)


def read_ledger() -> list[dict]:
    return json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else []


def persist_ledger(ledger: list[dict]) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(LEDGER)


def authenticated_ids() -> set[str]:
    payload = json.loads(MODEL_LIST.read_text(encoding="utf-8"))
    if payload.get("endpoint") != "https://toapis.cn/v1" or payload.get("http_status") != 200:
        raise ValueError("Authenticated model-list preflight is invalid")
    return {item["id"] for item in payload.get("models", [])}


def parse_response(payload: object) -> tuple[str | None, dict | None, str | None]:
    if not isinstance(payload, dict):
        return None, None, "non_object_response"
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None, payload.get("usage"), "missing_choices"
    first = choices[0]
    message = first.get("message", {}) if isinstance(first, dict) else {}
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        return None, payload.get("usage"), "empty_content"
    return content, payload.get("usage"), None


def run() -> int:
    cases = load_cases()
    ids = authenticated_ids()
    absent = [model for model, _, _ in MODELS if model not in ids]
    if absent:
        print("BLOCKED: candidate absent from authenticated model list: " + ", ".join(absent))
        return 2
    all_tasks = [(model, ir, or_, case) for model, ir, or_ in MODELS for case in cases]
    theoretical_max = sum((estimate_cny(MAX_INPUT_PER_CALL, MAX_OUTPUT_PER_CALL, ir, or_) for _, ir, or_, _ in all_tasks), Decimal(0))
    if theoretical_max > MAX_CNY:
        print("BLOCKED: theoretical cost exceeds configured ceiling")
        return 2
    ledger = read_ledger()
    existing = {(x["model"], x["case_id"]) for x in ledger}
    if len(ledger) > MAX_CALLS or len(existing) != len(ledger):
        print("BLOCKED: ledger integrity failure")
        return 2
    # A relay model can be advertised yet have no live upstream route. Never
    # repeat a failed pair or try further cases for that model; other models
    # remain independently eligible within the original 18-call ceiling.
    blocked_models = {x["model"] for x in ledger if x.get("error")}
    remaining = [(m, ir, or_, c) for m, ir, or_, c in all_tasks if (m, c["id"]) not in existing and m not in blocked_models]
    print(f"Preflight: {len(remaining)} requests remaining of {MAX_CALLS}; worst-case reference CNY {theoretical_max:.4f}, ceiling CNY {MAX_CNY}. No retry or fallback.")
    if not remaining:
        return 0
    key = os.environ.get("TOAPIS_BENCHMARK_API_KEY") or getpass.getpass("ToAPIs key (hidden): ")
    if not key:
        print("BLOCKED: no key supplied")
        return 2
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "raw").mkdir(exist_ok=True)
    for model, input_rate, output_rate, case in remaining:
        if model in blocked_models:
            continue
        actual_estimate = sum(Decimal(str(x.get("cost_estimate_cny", "0"))) for x in ledger)
        outstanding_bound = sum(
            (estimate_cny(MAX_INPUT_PER_CALL, MAX_OUTPUT_PER_CALL, ir, or_)
             for m, ir, or_, c in all_tasks if (m, c["id"]) not in {(x["model"], x["case_id"]) for x in ledger}),
            Decimal(0),
        )
        if actual_estimate + outstanding_bound > MAX_CNY or len(ledger) >= MAX_CALLS:
            print("BLOCKED: CNY or call ceiling reached")
            return 2
        msg = messages(case)
        input_bound = conservative_input_bound(msg)
        if input_bound > MAX_INPUT_PER_CALL:
            print(f"BLOCKED: {case['id']} input bound {input_bound} exceeds {MAX_INPUT_PER_CALL}")
            return 2
        body = json.dumps({"model": model, "messages": msg, "max_tokens": MAX_OUTPUT_PER_CALL, "stream": False}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(URL, data=body, method="POST", headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "Accept": "application/json"})
        started = now()
        tick = time.perf_counter()
        response: object = None
        http_status: int | None = None
        error: str | None = None
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as handle:
                http_status = handle.status
                response = json.loads(handle.read())
        except urllib.error.HTTPError as exc:
            http_status = exc.code
            try:
                response = json.loads(exc.read())
            except ValueError:
                response = {"error": "non_json_http_error"}
            error = f"HTTP_{exc.code}"
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            error = type(exc).__name__
        duration = round(time.perf_counter() - tick, 3)
        content, usage, parse_error = parse_response(response)
        if not error:
            error = parse_error
        usage = usage if isinstance(usage, dict) else {}
        in_tokens = usage.get("prompt_tokens")
        out_tokens = usage.get("completion_tokens")
        if isinstance(in_tokens, int) and isinstance(out_tokens, int):
            cost = estimate_cny(in_tokens, out_tokens, input_rate, output_rate)
        else:
            # Still reserve worst-case cost; missing usage cannot be treated as free.
            cost = estimate_cny(MAX_INPUT_PER_CALL, MAX_OUTPUT_PER_CALL, input_rate, output_rate)
        receipt_name = f"{model}__{case['id']}.json"
        receipt = {
            "timestamp_utc": started, "endpoint": URL, "http_status": http_status,
            "requested_model": model, "case_id": case["id"], "latency_seconds": duration,
            "input_byte_bound_not_actual_tokens": input_bound,
            "input_tokens": in_tokens if isinstance(in_tokens, int) else None,
            "output_tokens": out_tokens if isinstance(out_tokens, int) else None,
            "cost_estimate_cny": str(cost.quantize(Decimal("0.000001"))),
            "actual_billed_cny": None, "error": error,
            "raw_response": response, "parsed_content": content,
        }
        (RESULTS / "raw" / receipt_name).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        row = {k: receipt[k] for k in ("timestamp_utc", "http_status", "requested_model", "case_id", "latency_seconds", "input_tokens", "output_tokens", "cost_estimate_cny", "actual_billed_cny", "error")}
        row["model"] = row.pop("requested_model")
        row["receipt"] = f"raw/{receipt_name}"
        ledger.append(row)
        persist_ledger(ledger)
        print(f"{len(ledger):02d}/{MAX_CALLS} {model} {case['id']}: HTTP {http_status}; in={in_tokens if in_tokens is not None else 'N/A'} out={out_tokens if out_tokens is not None else 'N/A'}; {duration:.2f}s; {'OK' if not error else error}")
        if (isinstance(in_tokens, int) and in_tokens > MAX_INPUT_PER_CALL) or (isinstance(out_tokens, int) and out_tokens > MAX_OUTPUT_PER_CALL):
            print("STOP: provider usage exceeded configured bound. No further requests.")
            return 1
        if error:
            if error == "HTTP_404":
                print(f"SKIP {model}: no live route; no repeat or further cases for this model.")
                blocked_models.add(model)
            else:
                print("STOP: request failed and charge/status is uncertain. No further requests.")
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(run())
