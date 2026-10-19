"""Read-only authenticated model discovery for the isolated relay benchmark."""
from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

BASE_URL = "https://toapis.cn/v1"
OUT = Path(__file__).resolve().parents[1] / "results" / "model-list.json"


def main() -> int:
    key = os.environ.get("TOAPIS_BENCHMARK_API_KEY") or getpass.getpass("ToAPIs benchmark key (hidden): ")
    if not key:
        print("BLOCKED: missing benchmark key")
        return 2
    request = urllib.request.Request(
        BASE_URL + "/models",
        headers={"Authorization": "Bearer " + key, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
            http_status = response.status
    except urllib.error.HTTPError as exc:
        print(f"BLOCKED: model-list HTTP {exc.code}")
        return 1
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"BLOCKED: model-list {type(exc).__name__}")
        return 1
    models = payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(models, list):
        print("BLOCKED: unexpected model-list shape")
        return 1
    safe = []
    for model in models:
        if not isinstance(model, dict):
            continue
        ident = model.get("id")
        if not isinstance(ident, str):
            continue
        safe.append({"id": ident, "owned_by": model.get("owned_by")})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"endpoint": BASE_URL, "http_status": http_status, "count": len(safe), "models": safe}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"HTTP {http_status}; {len(safe)} model IDs; saved sanitized list to {OUT}")
    for item in safe:
        ident = item["id"].lower()
        if any(term in ident for term in ("gpt-6", "qwen3", "deepseek-v4")):
            print(f"{item['id']} | owned_by={item['owned_by']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
