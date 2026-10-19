# Public source snapshot

This repository publishes the DeepInsight Lite source, tests, dependency locks,
configuration examples, and a distributable offline evidence fixture. The
official Agno and Agent UI checkouts are pinned Git submodules:

```bash
git clone --recurse-submodules https://github.com/Benjamindaoson/Deepinsight.git
```

`app/london_product/runtime.py:create_app` is the product backend composition
root; `app/frontend` is the Next.js business UI. See
[`docs/architecture/CURRENT_RUNTIME_AND_INTEGRATION.md`](docs/architecture/CURRENT_RUNTIME_AND_INTEGRATION.md)
for the current runtime boundaries and remaining physical consolidation.

For a source-checkout demonstration without credentials, create the project
environment from `app/requirements-product.lock.txt`, install the frontend from
`app/frontend/pnpm-lock.yaml`, build it, and run `scripts/run.ps1 -Offline` on
Windows. The seeded offline fixture contains saved public-evidence receipts;
it does not claim fresh collection, a live model response, or human approval.
The default `scripts/run.ps1` path instead validates a separately frozen local
release under ignored `docs/delivery/`; it is unavailable in a fresh clone.

Local credentials, original downloaded documents, databases, model ledgers,
screenshots, and runtime logs are deliberately excluded. Copy only example
configuration files; keep populated `.env` files and provider keys outside
Git. Configure local settings from `app/.env.product.example` and
`app/frontend/.env.example`.

The legacy `b0/test_agno.py` file is excluded because its historical local
copy contains a hard-coded credential. Sanitize that file and rotate the
credential before publishing it elsewhere.

GitHub publication replaces the default branch's current file tree while Git
history remains available for rollback. The Railway Lite and Mini services
were deployed separately; pushing this source snapshot does not itself prove
that either cloud service is running this exact commit.
