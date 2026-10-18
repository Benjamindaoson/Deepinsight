#!/usr/bin/env bash
set -uo pipefail
export PATH=/home/benjamin/.nvm/versions/node/v24.18.0/bin:$PATH
export NEXT_TELEMETRY_DISABLED=1
cd /mnt/d/deepinsight-lite/upstream/agent-ui || exit 1
failed=0
for check in lint typecheck format; do
  npm exec --yes --package=pnpm@10.34.5 -- pnpm "$check" > "/mnt/d/deepinsight-lite/b0/evidence/logs/ui-$check.log" 2>&1
  result=$?
  echo "$check exit=$result"
  printf '%s\t%s\n' "$check" "$result" >> /mnt/d/deepinsight-lite/b0/evidence/logs/ui-check-exits.tsv
  if [ "$result" -ne 0 ]; then failed=1; fi
done
exit "$failed"
