# Source publication snapshot

This repository contains the DeepInsight Lite application source, tests, locked
dependencies, and product documentation. The frozen official Agno and Agent UI
checkouts are linked as Git submodules. Clone them with:

```bash
git clone --recurse-submodules https://github.com/Benjamindaoson/Deepinsight.git
```

Local credentials, databases, downloaded market documents, model ledgers,
screenshots, and runtime logs are intentionally excluded from the public source
snapshot. Configure credentials locally from `app/.env.product.example` and
`app/frontend/.env.example`; never commit populated `.env` files.

The legacy `b0/test_agno.py` file is also excluded because it contains a
hard-coded credential. Its local copy was left untouched; it must be sanitized
before it can be published.

This upload is a source snapshot, not a final market-data acceptance claim.
The latest independent audit found a conflicting rent annualization gate and
concurrent edits. See the local QA evidence before treating historical test
results as verification of this exact commit.
