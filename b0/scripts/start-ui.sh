#!/usr/bin/env bash
set -euo pipefail
export PATH=/home/benjamin/.nvm/versions/node/v24.18.0/bin:$PATH
cd /mnt/d/deepinsight-lite/upstream/agent-ui
if ss -ltn | grep -q ':3100 '; then echo 'Port 3100 occupied; refusing to terminate anything'; exit 1; fi
export NEXT_TELEMETRY_DISABLED=1
echo $$ > /mnt/d/deepinsight-lite/b0/evidence/logs/ui.pid
exec npm exec --yes --package=pnpm@10.34.5 -- pnpm dev --turbopack --port 3100
