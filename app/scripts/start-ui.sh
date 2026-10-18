#!/usr/bin/env bash
set -euo pipefail
export PATH="/home/benjamin/.nvm/versions/node/v24.18.0/bin:$PATH"
cd /mnt/d/deepinsight-lite/upstream/agent-ui
if ss -ltn 'sport = :3100' | tail -n +2 | grep -q .; then echo 'Port 3100 occupied; use verified stop-ui.sh or reuse existing UI'; exit 1; fi
test "$(git rev-parse HEAD)" = 6dad9593fca6756e1813e4f4b3b2620be6377691
export NEXT_TELEMETRY_DISABLED=1
exec npm exec --yes --package=pnpm@10.34.5 -- pnpm dev --turbopack --port 3100
