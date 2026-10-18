#!/usr/bin/env bash
set -euo pipefail
export PATH=/home/benjamin/.nvm/versions/node/v24.18.0/bin:$PATH
cd /mnt/d/deepinsight-lite/upstream/agent-ui
exec > >(tee /mnt/d/deepinsight-lite/b0/evidence/logs/ui-install.log) 2>&1
node --version
npm --version
npm exec --yes --package=pnpm@10.34.5 -- pnpm --version
npm exec --yes --package=pnpm@10.34.5 -- pnpm install --frozen-lockfile
