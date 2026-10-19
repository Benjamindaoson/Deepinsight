"""The compatibility API uses saved evidence and never requests a model."""

from fastapi.testclient import TestClient
import hashlib
import shutil
import sqlite3
from pathlib import Path

from london_product.runtime import create_app
from london_product import offline_runtime, runtime
from london_product.offline_api import saved_context_answer
from london_product.store import Store


def test_offline_contract_without_sources(tmp_path):
    client = TestClient(create_app(tmp_path, seed=False, scheduler=False, offline=True))
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["mode"] == "mock"
    assert health.json()["data_asof"] is None
    assert health.json()["sources"] == []
    assert client.get("/skills").status_code == 200
    skills = client.get("/skills").json()["skills"]
    assert len(skills) >= 10
    assert {"reporting", "alerting", "macro-drivers"} <= {skill["name"] for skill in skills}
    assert all(skill["input_schema"] and skill["output_schema"] for skill in skills)
    assert client.get("/alerts").status_code == 200

    answer = client.post("/chat", json={"message": "City vacancy", "session_id": "s1"})
    assert answer.status_code == 200
    payload = answer.json()
    assert payload["session_id"] == "s1"
    assert "Insufficient evidence" in payload["answer"]
    assert payload["sources"] == []
    assert all(call["datasource"] == "saved_snapshots" for call in payload["skill_calls"])

    report = client.post("/report", json={})
    assert report.status_code == 200
    assert "Insufficient evidence" in report.json()["markdown"]
    assert report.json()["sources"] == []
    assert report.json()["skill_calls"][0]["skill"] == "reporting"


def test_offline_inputs_reject_invalid_values(tmp_path):
    client = TestClient(create_app(tmp_path, seed=False, scheduler=False, offline=True))
    assert client.post("/chat", json={"message": " "}).status_code == 422
    invalid_month = client.post("/report", json={"month": "2026-99"})
    assert invalid_month.status_code == 422
    assert invalid_month.json()["sources"] == []
    assert invalid_month.json()["disclaimer"]
    assert client.post("/chat", json={"message": "City rent", "unexpected": True}).status_code == 422
    assert client.post("/alerts", json={"rent_threshold_pct": -1}).status_code == 422
    assert client.post("/alerts", json={}).status_code == 422


def test_offline_safety_boundaries_do_not_invent_answers(tmp_path):
    client = TestClient(create_app(tmp_path, seed=False, scheduler=False, offline=True))
    future = client.post("/chat", json={"message": "Give me the exact certain 2027 rent value"}).json()
    assert future["quality_status"] == "refused_false_precision"
    assert future["sources"] == []
    private = client.post("/chat", json={"message": "Give me the tenant contact email"}).json()
    assert private["quality_status"] == "refused_private_data"
    assert private["sources"] == []


def test_future_certainty_boundary_is_not_tied_to_one_year(tmp_path):
    client = TestClient(create_app(tmp_path, seed=False, scheduler=False, offline=True))
    for year in (2027, 2028, 2030):
        payload = client.post("/chat", json={
            "message": f"Give me the exact certain {year} rent value"
        }).json()
        assert payload["quality_status"] == "refused_false_precision"
        assert payload["sources"] == []


def test_offline_session_inherits_scope_without_inventing_data(tmp_path):
    client = TestClient(create_app(tmp_path, seed=False, scheduler=False, offline=True))
    first = client.post("/chat", json={"message": "City rent in 2026Q2", "session_id": "follow-up"})
    assert first.status_code == 200
    second = client.post("/chat", json={"message": "What about vacancy?", "session_id": "follow-up"})
    assert second.status_code == 200
    assert "Scope: City" in second.json()["answer"]
    assert "Insufficient evidence" in second.json()["answer"]


def test_every_chat_skill_call_is_registered(tmp_path):
    client = TestClient(create_app(tmp_path, seed=False, scheduler=False, offline=True))
    registered = {skill["name"] for skill in client.get("/skills").json()["skills"]}
    for message in ("What is the Bank Rate?", "How does hybrid working affect Midtown?"):
        payload = client.post("/chat", json={"message": message}).json()
        assert {call["skill"] for call in payload["skill_calls"]} <= registered


def test_offline_context_does_not_invent_macro_or_hybrid_evidence(tmp_path):
    store = Store(tmp_path)
    for question in ("Bank of England interest rate", "London employment", "ESG and hybrid working"):
        result = saved_context_answer(store, question)
        assert result["sources"] == []
        assert result["quality_status"] == "insufficient_evidence"
        assert "Insufficient evidence" in result["answer"]


def test_offline_app_never_constructs_a_provider_agent(tmp_path, monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("offline startup attempted to construct a provider agent")

    monkeypatch.setattr(runtime, "query_agent", fail_if_called)
    client = TestClient(create_app(tmp_path, seed=False, scheduler=False, offline=True))
    assert client.get("/health").json()["mode"] == "mock"
    response = client.post("/api/market/ask", json={
        "message": "Compare City and Canary Wharf vacancy",
        "mode": "agent",
    })
    assert response.status_code == 200
    assert '"mode": "saved"' in response.text
    assert '"model_requests": 0' in response.text
    assert '"skill_calls":' in response.text


def test_offline_ask_never_routes_shadows_or_refreshes_external_sources(tmp_path, monkeypatch):
    app = create_app(tmp_path, seed=False, scheduler=False, offline=True)

    async def fail_classify(*_args, **_kwargs):
        raise AssertionError("offline ask called the provider-backed classifier")

    def fail_external(*_args, **_kwargs):
        raise AssertionError("offline ask attempted external work")

    monkeypatch.setattr(app.state.query_router, "classify", fail_classify)
    monkeypatch.setattr(app.state.jev_shadow, "submit", fail_external)
    monkeypatch.setattr(app.state.market, "submit", fail_external)
    client = TestClient(app)
    response = client.post("/api/market/ask", json={
        "message": "Compare City and Canary Wharf vacancy",
        "mode": "agent",
        "refresh_sources": True,
    })
    assert response.status_code == 200
    assert '"mode": "saved"' in response.text
    assert '"mode": "offline_disabled"' in response.text
    assert '"model_requests": 0' in response.text


def test_offline_external_io_endpoints_fail_closed(tmp_path, monkeypatch):
    app = create_app(tmp_path, seed=False, scheduler=False, offline=True)

    async def fail_classify(*_args, **_kwargs):
        raise AssertionError("offline endpoint called the classifier")

    def fail_submit(*_args, **_kwargs):
        raise AssertionError("offline endpoint submitted external work")

    monkeypatch.setattr(app.state.query_router, "classify", fail_classify)
    monkeypatch.setattr(app.state.market, "submit", fail_submit)
    client = TestClient(app)
    responses = [
        client.post("/api/market/routing/classify", json={
            "message": "latest market", "mode": "auto"
        }),
        client.post("/api/market/refresh"),
        client.post("/api/market/scheduled/news"),
        client.post("/api/market/reports", json={
            "period": "weekly", "include_analysis": True
        }),
        client.post("/api/market/notifications", json={
            "report_id": "never-send"
        }),
    ]
    for response in responses:
        assert response.status_code == 409
        assert response.json()["detail"] == "OFFLINE_EXTERNAL_IO_DISABLED"
        assert response.json()["sources"] == []
        assert response.json()["disclaimer"]


def test_scoped_alert_round_trip(tmp_path):
    client = TestClient(create_app(tmp_path, seed=False, scheduler=False, offline=True))
    rule = {
        "geography": "City",
        "metric": "prime_rent",
        "definition": "prime headline rent",
        "comparison_window": "month_over_month",
        "operator": ">",
        "threshold": 2.0,
        "unit": "percent",
        "enabled": True,
    }
    posted = client.post("/alerts", json={"rules": [rule]})
    assert posted.status_code == 200
    assert posted.json()["rules"] == [rule]
    assert client.get("/alerts").json()["rules"] == [rule]


def test_offline_app_never_reads_local_model_credentials(tmp_path, monkeypatch):
    model_config = (runtime.ROOT / "secrets/model.json").resolve()
    original_read_text = Path.read_text

    def guarded_read_text(path, *args, **kwargs):
        if path.resolve() == model_config:
            raise AssertionError("offline startup attempted to read model credentials")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    client = TestClient(create_app(tmp_path, seed=False, scheduler=False, offline=True))
    assert client.get("/skills").status_code == 200
    assert client.post("/chat", json={"message": "City vacancy"}).status_code == 200


def test_saved_snapshot_is_read_only_and_reuses_existing_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(offline_runtime, "ROOT", tmp_path)
    source = tmp_path / "app/data/product/market.sqlite3"
    source.parent.mkdir(parents=True)
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE marker(value TEXT)")
        connection.execute("INSERT INTO marker VALUES ('source')")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    target = offline_runtime.saved_snapshot_directory()
    assert target is not None
    assert sqlite3.connect(target / "market.sqlite3").execute("SELECT value FROM marker").fetchone() == ("source",)
    assert offline_runtime.saved_snapshot_directory() == target
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_clean_checkout_fixture_bootstraps_source_backed_offline_chat(tmp_path, monkeypatch):
    fixture_source = runtime.ROOT / "app/fixtures/offline_evidence.json"
    fixture_target = tmp_path / "app/fixtures/offline_evidence.json"
    fixture_target.parent.mkdir(parents=True)
    shutil.copyfile(fixture_source, fixture_target)
    monkeypatch.setattr(runtime, "ROOT", tmp_path)
    monkeypatch.setattr(offline_runtime, "ROOT", tmp_path)

    assert offline_runtime.saved_snapshot_directory() is None
    app = create_app(tmp_path / "app/data/product/offline-demo", seed=True,
                     scheduler=False, offline=True)
    client = TestClient(app)
    health = client.get("/health").json()
    assert health["mode"] == "mock"
    answer = client.post("/chat", json={
        "message": "Compare City and Canary Wharf vacancy on the saved definition",
        "session_id": "clean-checkout",
    }).json()
    assert answer["sources"]
    assert all(source["url"].startswith("https://") for source in answer["sources"])
    assert all(source.get("published_at") or source.get("collected_at")
               for source in answer["sources"])
