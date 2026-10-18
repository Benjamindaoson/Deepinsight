#!/usr/bin/env bash
set -euo pipefail
export PATH=/home/benjamin/.nvm/versions/node/v24.18.0/bin:$PATH
cd /mnt/d/deepinsight-lite/b0
npm exec --yes --package=pnpm@10.34.5 -- pnpm --version
