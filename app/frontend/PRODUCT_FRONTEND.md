# London Office Market business UI

This independent working copy originates from official Agent UI commit `6dad9593fca6756e1813e4f4b3b2620be6377691` using `git archive`. It has its own installed dependencies. The official source, older UI, `.env`, native histories, and B0/B1 records are untouched.

## Run

Use WSL Node 24.18.0 and pnpm 10.34.5 (the frozen lockfile versions):

```bash
export PATH=/home/benjamin/.nvm/versions/node/v24.18.0/bin:$PATH
cd /mnt/d/deepinsight-lite/app/frontend
bash ./build-product.sh --check
# Stop the frontend with the root-owned launcher before replacing its output.
bash ./build-product.sh --build
npm exec --yes --package=pnpm@10.34.5 -- pnpm start
```

The rebuild helper uses only the existing independent dependencies. For a fresh environment, bootstrap those frozen dependencies once before invoking the helper:

```bash
export PATH=/home/benjamin/.nvm/versions/node/v24.18.0/bin:$PATH
cd /mnt/d/deepinsight-lite/app/frontend
mkdir -p /home/benjamin/.cache/deepinsight-product-frontend/node_modules
# For a fresh copy with no node_modules directory:
ln -s /home/benjamin/.cache/deepinsight-product-frontend/node_modules node_modules
npm exec --yes --package=pnpm@10.34.5 -- pnpm install --offline --frozen-lockfile --package-import-method=copy --virtual-store-dir /home/benjamin/.cache/deepinsight-product-frontend/node_modules/.pnpm
```

Business URL: `http://localhost:3101`. API default: `http://127.0.0.1:7780/api/market`. The backend must allow this origin. Optional public endpoint overrides are documented in `.env.example`; no provider secret belongs in a public Next.js environment variable. This copy already has the correct independent dependency symlink; do not run `ln` again on an existing installation. Native Windows-mount package import repeatedly failed with rename EACCES; the Linux virtual store avoids that failure. Do not pass an absolute `--modules-dir` to pnpm; the virtual store is sufficient.

## Reproducible isolated build

`build-product.sh` is a WSL helper rooted at the exact authoritative source `/mnt/d/deepinsight-lite/app/frontend`. Its fixed Linux mirror is `/home/benjamin/.cache/deepinsight-product-frontend/build-mirror`, with frozen dependencies at `/home/benjamin/.cache/deepinsight-product-frontend/node_modules`. It refuses unexpected absolute targets, dependency-link destinations, Node/package versions, or lockfile hashes. `--check` is read-only and works while the current UI is serving. `--help` and `bash -n ./build-product.sh` do not build.

`--build` refuses to replace a serving project frontend, serializes its own runs with a file lock, preserves the previous mirror under `/home/benjamin/.cache/deepinsight-product-frontend/build-history/<UTC timestamp>-<PID>/previous-mirror`, and copies a fresh authoritative snapshot. It excludes `.env*`, `.git`, `node_modules`, `.next*`, failed dependency imports, accidental `home` imports and the incremental TypeScript cache. Public endpoint overrides must be exported explicitly into the build environment rather than copied from secret-bearing environment files.

The mirror runs these existing tools, sequentially, without installation:

```bash
cd /home/benjamin/.cache/deepinsight-product-frontend/build-mirror
CI=1 NEXT_TELEMETRY_DISABLED=1 ./node_modules/.bin/next build
./node_modules/.bin/tsc --noEmit
node --experimental-strip-types --test tests/*.test.mjs
```

Use the actual `.bin/next` shim. Invoking Next through `node next/dist/bin/next` bypasses the shim's private-hoisted `NODE_PATH` and was observed to break ESLint plugin resolution. Do not add package installation or an unfrozen lock update to recover from a missing dependency.

The helper hashes source/configuration before and after building, compares the mirror byte-for-byte, and refuses publication if authoritative source changed. It stages only successful `.next` output, moves the previous ordinary project `.next` to the guarded Linux history directory as `previous-next`, and publishes the staged output to the exact authoritative directory. It writes the verified source receipt to `FRONTEND_BUILD_IDENTITY.json`; old builds and source receipts remain outside project source. It performs no recursive deletion and never stops a server or calls a model. Root owns stopping/restarting the UI and browser acceptance.

The earlier intermittent disappearance of the Windows-mount dependency symlink remains unexplained. Dependency checks run before mirroring, before compilation and after verification; a missing or redirected link fails closed and requires environment bootstrap/inspection. The helper does not silently recreate it, reinstall packages or claim the underlying disappearance is fixed.

## Pages and verification targets

| Route | User flow |
| --- | --- |
| `/` | Chat-first London Office Intelligence homepage, native sessions/tools, quick prompts, persisted light/dark theme |
| `/overview` | Saved market counts, recent observations, events, background jobs, source health |
| `/market-data` | Geography/metric/period/review-status filters, pagination, fact evidence drawer, original files, explicit per-document model extraction |
| `/events` | Event filters, acknowledgement, comparison eligibility checks on saved observations |
| `/ask` | Deterministic saved retrieval or actual native model/tool SSE; completion receipt, citations, partial/error state |
| `/reports` | Deterministic daily/weekly generation, separate explicit background AI weekly analysis (REVIEW_REQUIRED), read Markdown, download HTML/Markdown, truthful notification attempt |
| `/settings` | Save geography, metrics, intervals, notifications; show server configuration and schedules |
| `/jobs` | Actual job stage/progress/errors/run receipts, bounded visible-tab polling, retry failed jobs |
| `/chat` | Official Agent UI chat components, sessions, streaming, tool rendering; independent endpoint persistence key |

Reads show cached data immediately on return, then revalidate. Filter requests use request sequencing so delayed responses cannot replace the currently selected filter. Background job polling runs every five seconds while visible for at most ten minutes. Reloading a page starts a new polling window; pause/resume is explicit. Only user event handlers perform writes. A synchronous guard prevents repeated clicks within an in-flight action, and requests include a fresh Idempotency-Key.

Evidence quotes and report Markdown are rendered as React text; the business UI does not inject HTML. Publisher URLs only accept HTTP or HTTPS. Model extraction is never automatic. Saved answers and default generated briefings are explicitly labelled deterministic; optional AI analysis remains review-required. Unknown data stays unknown; pending review is never automatically represented as human-validated.

The native chat uses its existing AgentOS protocol. The default endpoint for this copy is port 7780. No font download is required for build; the business copy uses system fonts. Its copied image error fallback now uses React elements instead of HTML interpolation. Existing native Markdown rendering still sanitizes HTML through its official sanitizer.


## Chat-first UI (2026-10-18)

The shared workspace defaults to light mode. Light/Dark is stored by the existing next-themes provider under `london-office-theme`; the model is never called to initialize the page. The sidebar uses native Agno Sessions, with local title filtering over the loaded session page. No new message database was added. `/chat` remains an alias view of the native chat; `/ask` retains the earlier guarded business question flow.

Native chat and history are explicitly labelled `REVIEW_REQUIRED`. A completed native run is not a publication approval. Candidate metric tables preserve units, periods, definitions and review states; tool evidence expands to source links, quotes and locators. No trend chart is generated without eligible data. Stop requests the existing AgentOS cancellation endpoint; cancellation is cooperative, and already incurred provider usage cannot be undone. Edit question to retry only restores text; it never resubmits automatically.

For the verified source build and browser evidence see `FRONTEND_ACCEPTANCE_REPORT.md` and `evidence/chat-home-20261018/`. Backend code, provider settings, review states and the official upstream were not modified for this UI task.
