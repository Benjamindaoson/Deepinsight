#!/usr/bin/env bash
set -euo pipefail
export PATH=/home/benjamin/.nvm/versions/node/v24.18.0/bin:$PATH
export NEXT_TELEMETRY_DISABLED=1
cd /mnt/d/deepinsight-lite/upstream/agent-ui
echo $$ > /mnt/d/deepinsight-lite/b0/evidence/logs/ui-build.pid
exec timeout --signal=TERM --kill-after=10s 300 npm exec --yes --package=pnpm@10.34.5 -- pnpm build "$@"
