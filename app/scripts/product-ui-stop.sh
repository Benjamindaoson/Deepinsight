#!/usr/bin/env bash
set -euo pipefail
target_dir=/mnt/d/deepinsight-lite/app/frontend
for proc in /proc/[0-9]*; do
  candidate="${proc##*/}"
  if [ "$(readlink "$proc/cwd" 2>/dev/null || true)" = "$target_dir" ]; then
    command_text="$(tr '\0' ' ' < "$proc/cmdline" 2>/dev/null || true)"
    if [[ "$command_text" == *"next-server"* || "$command_text" == *"next start --port 3101"* ]]; then
      kill -TERM "$candidate"
      echo "Stopped verified business UI PID $candidate"
    fi
  fi
done
