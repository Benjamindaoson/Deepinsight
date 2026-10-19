# DeepInsight Lite

London office market intelligence with traceable source evidence, deterministic calculations and explicit publication controls.

The application uses FastAPI, Agno/AgentOS, SQLite and Next.js. Saved-evidence mode runs without model or search credentials. It does not claim live research or AI analysis.

## Run locally

Requires Python 3.12, Node.js 24 and pnpm 10. Install Python packages only in the project environment.

```powershell
uv venv app/.venv --python 3.12
uv pip install --python app/.venv/Scripts/python.exe -r app/requirements-product.lock.txt
cd app/frontend
pnpm install --frozen-lockfile
$env:NEXT_PUBLIC_AGENT_OS_URL='http://127.0.0.1:8000'
$env:NEXT_PUBLIC_MARKET_API_URL='http://127.0.0.1:8000/api/market'
pnpm build
cd ../..
powershell -ExecutionPolicy Bypass -File scripts/run.ps1
```

Open **http://127.0.0.1:3101/ask**. The API is **http://127.0.0.1:8000**. Both ports must be available. The frontend API addresses are compiled at build time: changing a backend port requires rebuilding the frontend with the matching addresses. The launch script does not replace other running services.

On Linux/macOS use `./scripts/run.sh` after the equivalent environment setup. Stop only launcher-owned processes with `scripts/stop.ps1` or `scripts/stop.sh`.

## Product paths

- `/ask`: new market briefings, focused lookups, evidence audits and follow-ups.
- `/reports`: saved reports, evidence, HTML and Markdown exports; use **Audit evidence** to inspect a report without replacing it.
- `/market-data`, `/overview`, `/events`: stored market observations, coverage and changes.
- `/jobs`, `/settings`: actual job records and monitoring configuration.
- `/chat`: native AgentOS conversations when a provider-backed Agent is configured.

An audit inspects the selected report and its stored evidence. It does not create a replacement report or approve records. Matching an original-file hash, quotation or literal number establishes traceability, not semantic approval. Units, geographic boundaries, periods and review states remain explicit.

## Validation

```powershell
app/.venv/Scripts/python.exe -m pytest app/tests/test_emergency_intents.py -q
cd app/frontend
pnpm test
pnpm typecheck
pnpm lint
pnpm build
```

The focused emergency regression is self-contained and uses isolated, explicitly synthetic fault controls. The broader historical replay tests also require local source originals, provider receipts and SQLite snapshots; these private runtime assets are intentionally not committed. A passing local replay suite must not be interpreted as a fresh provider evaluation.

## Limits and credentials

See [release acceptance](reports/RELEASE_ACCEPTANCE.md) for observed behavior and current limitations. Pending records remain pending. Current saved periods are not necessarily the latest public release. Missing annual rent denominators are not inferred by convention. Unsupported figures, causal explanations and forecasts cannot be published to make a report appear complete.

Optional server configuration is documented in `app/.env.product.example`. Credentials belong in server environment variables or ignored local configuration; never in `NEXT_PUBLIC_*`, source control, logs or screenshots. Enabling external model calls, search or notifications requires explicit configuration and a bounded operating budget. Jev is optional and falls back when no credential is available.

Temporary acceptance snapshots, build outputs, databases, developer-tool metadata and private research traces are excluded from this release tree. Runtime source, tests, public source fixtures, dependency locks and licenses are retained.
