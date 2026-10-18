#!/usr/bin/env bash
set -eu
root=/mnt/d/deepinsight-lite/upstream/agent-ui
for process in /proc/[0-9]*; do
  if [ "$(readlink -f "$process/cwd" 2>/dev/null || true)" = "$root" ]; then
    pid=${process##*/}
    ps -p "$pid" -o pid,ppid,comm,etime,pcpu,rss,wchan:20 --no-headers
    tr '\0' ' ' < "$process/cmdline"
    echo
  fi
done
