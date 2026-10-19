"""Field-level smoke test for the public offline compatibility API."""

from __future__ import annotations

import json
import argparse
from urllib.request import Request, urlopen


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("base_url", nargs="?", help="Compatibility positional base URL")
parser.add_argument("--base-url", dest="base_url_option", help="API base URL")
args = parser.parse_args()
BASE = (args.base_url_option or args.base_url or "http://127.0.0.1:8000").rstrip("/")


def call(path: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode()
    request = Request(BASE + path, data=body, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=30) as response:
        assert response.status == 200, (path, response.status)
        return json.load(response)


health = call("/health")
assert health["status"] == "ok" and health["mode"] == "mock"
assert {"version", "data_asof", "sources", "disclaimer"} <= health.keys()
skills = call("/skills")
assert len(skills["skills"]) >= 10
assert all({"name", "input_schema", "output_schema", "file"} <= item.keys() for item in skills["skills"])
chat = call("/chat", {"message": "What is the latest saved West End prime rent?", "session_id": "smoke"})
assert {"answer", "sources", "as_of", "skill_calls", "disclaimer"} <= chat.keys()
assert chat["answer"] and chat["skill_calls"]
report = call("/report", {})
assert {"report_id", "markdown", "sources", "as_of", "skill_calls", "disclaimer"} <= report.keys()
alerts = call("/alerts")
assert {"settings", "sources", "disclaimer"} <= alerts.keys()
print(f"PASS health skills chat report alerts; skills={len(skills['skills'])}; "
      f"chat_sources={len(chat['sources'])}; report_sources={len(report['sources'])}; "
      f"data_asof={health['data_asof']}")
