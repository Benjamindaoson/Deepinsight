# ToAPIs London office benchmark

This isolated benchmark evaluates three relay-listed model IDs on six fixed, real-source London office market tasks. It does not change production configuration or approved facts. The reference checks are provisional source annotations pending human review.

Run from `D:\deepinsight-lite` using the project-local Python environment:

```powershell
app\.venv\Scripts\python.exe -m pytest tools\model_benchmark\tests -q
app\.venv\Scripts\python.exe tools\model_benchmark\src\preflight.py
app\.venv\Scripts\python.exe tools\model_benchmark\src\benchmark.py
app\.venv\Scripts\python.exe tools\model_benchmark\src\report.py
```

The preflight and benchmark prompt for the key without echoing it. Alternatively set `TOAPIS_BENCHMARK_API_KEY` only in an ephemeral local process. Never put the key in `config.example.env`, reports or Git. The authenticated `/v1/models` listing is saved without credentials. The benchmark verifies all source hashes and model IDs before paid calls. It makes at most one Chat Completions request per model/case, 18 overall, with no SDK retry or fallback. A failure or token-bound violation stops immediately; a rerun skips recorded pairs, so it cannot silently repeat a charged call. Each request uses at most 1,600 output tokens, a 90-second timeout, a conservative 8,000-input-token bound, and an ¥8 ceiling based on the authenticated account price snapshot. The ceiling is a local guard, not a provider billing guarantee.

`datasets/cases.json` contains the shared prompts, excerpt snapshots, URL/locator references, SHA-256 hashes, and automatic screening assertions. Each source path refers to an already-saved original in this repository. `results/raw/` contains each relay response and reported usage; `results/ledger.json` is the request ledger. `src/report.py` generates `results/summary.csv` and `results/REPORT.md`. Actual billed cost is N/A unless a trustworthy fee receipt exists; price-derived CNY estimates are labeled estimates. The heuristic score needs human semantic review and cannot by itself decide a production default model.
