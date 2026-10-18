#!/usr/bin/env bash
set -euo pipefail
export PATH=/home/benjamin/.nvm/versions/node/v24.18.0/bin:$PATH
root=/mnt/d/deepinsight-lite
cd "$root/upstream/agent-ui"
# Stop only the listener whose working directory is the B0 official UI clone.
pid=$(ss -ltnp 'sport = :3100' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1)
if [ -n "$pid" ]; then
  actual=$(readlink -f "/proc/$pid/cwd")
  if [ "$actual" != "$root/upstream/agent-ui" ]; then echo 'Unexpected listener owner'; exit 1; fi
  kill -TERM "$pid"
  for n in $(seq 1 20); do
    if ! ss -ltn 'sport = :3100' | grep -q ':3100'; then break; fi
    sleep 1
  done
fi
export NEXT_TELEMETRY_DISABLED=1
echo $$ > "$root/b0/evidence/logs/ui.pid"
exec npm exec --yes --package=pnpm@10.34.5 -- pnpm dev --turbopack --port 3100
