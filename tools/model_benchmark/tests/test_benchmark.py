import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))
import benchmark
import report


def test_six_cases_and_original_hashes():
    cases = benchmark.load_cases()
    assert len(cases) == 6
    assert len({case["id"] for case in cases}) == 6
    for case in cases:
        assert all(e["locator"] and e["url"] and e["text"] for e in case["evidence"])


def test_cost_bound_and_request_count():
    assert len(benchmark.MODELS) * len(benchmark.load_cases()) == benchmark.MAX_CALLS == 18
    maximum = sum((benchmark.estimate_cny(8000, 1600, ir, or_) for _, ir, or_ in benchmark.MODELS), 0) * 6
    assert maximum < benchmark.MAX_CNY
    assert benchmark.conservative_input_bound(benchmark.messages(benchmark.load_cases()[0])) < 8000


def test_missing_and_invalid_model_response_are_not_scored():
    case = benchmark.load_cases()[0]
    assert report.score(case, {"error": "HTTP_403", "parsed_content": None})["total"] == 0
    assert report.score(case, {"error": None, "parsed_content": "not json"})["total"] == 0


def test_critical_annual_rent_fabrication_is_flagged():
    case = benchmark.load_cases()[0]
    content = json.dumps({"facts": [{"claim": "City annual rent rose to GBP/sqft/year 95", "status": "verified_source_statement", "evidence_ids": ["BNP_Q2_P3"]}], "limitations": ["unknown"]})
    result = report.score(case, {"error": None, "parsed_content": content, "latency_seconds": 1})
    assert result["critical_flags"] and result["reasoning"] == 0


def test_key_never_in_request_metadata_or_source():
    source = (HERE / "src" / "benchmark.py").read_text(encoding="utf-8")
    assert "TOAPIS_BENCHMARK_API_KEY" in source
    assert '"Authorization"' in source
    assert '"raw_response"' in source
    assert '"key": key' not in source


def test_news_input_erratum_is_explicit_and_source_checked():
    cases = {case["id"]: case for case in benchmark.load_cases()}
    excerpt = cases["news_planning"]["evidence"][0]["text"]
    original = (benchmark.ROOT / cases["news_planning"]["evidence"][0]["path"]).read_text(encoding="utf-8")
    assert "Planning and Transportation Committee" in excerpt  # frozen as-sent input
    assert "Planning Applications Sub-Committee" in original  # authoritative saved HTML
    assert "INVALID" in (HERE / "datasets" / "ERRATA.md").read_text(encoding="utf-8")
