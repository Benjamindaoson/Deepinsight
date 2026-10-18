#!/usr/bin/env bash
set -euo pipefail
target=/mnt/d/deepinsight-lite/upstream/agent-ui
line=$(ss -ltnp 'sport = :3100' | tail -n +2)
if test -z "$line"; then echo 'UI not listening'; exit 0; fi
ui_pid=$(printf '%s' "$line" | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -n1)
test -n "$ui_pid"
test "$(readlink -f /proc/$ui_pid/cwd)" = "$target" || { echo 'Port owner is not this UI'; exit 1; }
parent_pid=$(awk '/^PPid:/{print $2}' /proc/$ui_pid/status)
parent_command=$(tr '\0' ' ' </proc/$parent_pid/cmdline)
if [[ "$parent_command" == *"next/dist/bin/next dev"* ]] && test "$(readlink -f /proc/$parent_pid/cwd)" = "$target"; then
  kill -TERM "$parent_pid"
else
  kill -TERM "$ui_pid"
fi
for i in {1..30}; do
  if ! ss -ltn 'sport = :3100' | tail -n +2 | grep -q .; then echo 'Verified UI stopped'; exit 0; fi
  sleep .3
done
echo 'UI listener remains; inspect explicitly'; exit 1
