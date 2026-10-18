#!/usr/bin/env bash
set -eu
pid=$(ss -ltnp 'sport = :3100' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1)
if [ -n "$pid" ] && [ "$(readlink -f /proc/$pid/cwd)" = /mnt/d/deepinsight-lite/upstream/agent-ui ]; then
  date --iso-8601=seconds
  ps -p "$pid" -o pid,comm,etime,pcpu,rss,vsz
fi
