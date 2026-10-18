#!/usr/bin/env bash
set -euo pipefail
root=/mnt/d/deepinsight-lite
pid=$(ss -ltnp 'sport = :3100' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1)
if [ -z "$pid" ]; then echo 'No UI listener'; exit 0; fi
if [ "$(readlink -f "/proc/$pid/cwd")" != "$root/upstream/agent-ui" ]; then
  echo 'Listener working directory is not B0; refusing to stop'; exit 1
fi
launcher=$(cat "$root/b0/evidence/logs/ui.pid")
ancestor=$pid
owned=false
for n in $(seq 1 8); do
  if [ "$ancestor" = "$launcher" ]; then owned=true; break; fi
  ancestor=$(awk '/^PPid:/ {print $2}' "/proc/$ancestor/status")
  if [ "$ancestor" -le 1 ]; then break; fi
done
if [ "$owned" != true ]; then echo 'Listener is not a child of recorded B0 launcher'; exit 1; fi
kill -TERM "$pid"
echo "Stopped B0 UI PID=$pid"
