#!/usr/bin/env bash
set -u
cd /mnt/d/deepinsight-lite
exec > >(tee b0/evidence/logs/environment.log) 2>&1
date --iso-8601=seconds
pwd
uname -a
for c in python3 git node npm pnpm uv docker; do
  echo "TOOL=$c"
  command -v "$c" || true
  "$c" --version || true
done
docker compose version || true
ss -ltnp
echo 'Credential variable names only:'
printenv | cut -d= -f1 | grep -Ei 'API_KEY|BASE_URL|MODEL|TOKEN' || true
echo 'Optional user-local runtimes:'
ls -d "$HOME"/.local/bin/uv "$HOME"/.nvm/versions/node/*/bin/node 2>/dev/null || true
