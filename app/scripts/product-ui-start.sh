#!/usr/bin/env bash
set -euo pipefail
export PATH="/home/benjamin/.nvm/versions/node/v24.18.0/bin:$PATH"
export NEXT_TELEMETRY_DISABLED=1
cd /mnt/d/deepinsight-lite/app/frontend
if ss -ltn 'sport = :3101' | tail -n +2 | grep -q .; then echo 'Product UI3101 already occupied'; exit 1; fi
exec node node_modules/next/dist/bin/next start --port 3101 --hostname 127.0.0.1
