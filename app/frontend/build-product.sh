#!/usr/bin/env bash
# Run in WSL. Uses only the existing frozen dependency environment; never installs.
set -euo pipefail

usage() {
  cat <<'HELP'
Usage: bash build-product.sh [--check|--build|--help]
  --check  Read-only preflight: paths, existing dependencies, runtime, lock,
           source identity and required tools. Does not build or replace output.
  --build  Build an exact Linux source mirror, run typecheck and SSE tests,
           verify source stability, preserve the prior output, publish .next.
           Stop the project frontend through its root-owned launcher first.
  --help   Show this help. Default action is --build.
No dependency installation, package upgrades, network or model requests occur.
HELP
}
mode="${1:---build}"
case "$mode" in --help|-h) usage; exit 0;; --check|--build) ;; *) usage >&2; exit 2;; esac
[[ $# -le 1 ]] || { usage >&2; exit 2; }

readonly EXPECTED_SOURCE=/mnt/d/deepinsight-lite/app/frontend
readonly SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly CACHE=/home/benjamin/.cache/deepinsight-product-frontend
if [[ -L "$SOURCE/node_modules" ]]; then
  readonly DEPS="$CACHE/node_modules"
else
  readonly DEPS="$SOURCE/node_modules"
fi
readonly MIRROR="$CACHE/build-mirror"
readonly NODE_BIN=/home/benjamin/.nvm/versions/node/v24.18.0/bin
readonly LOCK_SHA=bc77014327a2c46cc37e1d0b38706475432f6b46987e6b0808237bab4dd699f8
die() { printf 'Build refused: %s\n' "$*" >&2; exit 1; }
[[ "$SOURCE" == "$EXPECTED_SOURCE" ]] || die "unexpected source: $SOURCE"
[[ "$(realpath -m -- "$CACHE")" == "$CACHE" ]] || die 'cache path must be an ordinary absolute directory'
[[ "$(realpath -m -- "$MIRROR")" == "$CACHE/build-mirror" ]] || die 'unexpected mirror target'
export PATH="$NODE_BIN:$PATH"
for command in node python3 tar flock realpath sha256sum cp mv; do command -v "$command" >/dev/null || die "missing tool: $command"; done
[[ "$(node --version)" == v24.18.0 ]] || die 'expected existing Node v24.18.0'
[[ "$(sha256sum "$SOURCE/pnpm-lock.yaml" | cut -d' ' -f1)" == "$LOCK_SHA" ]] || die 'frozen lock identity changed; review dependencies explicitly'

check_dependencies() {
  [[ "$(sha256sum "$SOURCE/pnpm-lock.yaml" | cut -d' ' -f1)" == "$LOCK_SHA" ]] || die 'frozen lock changed during build'
  if [[ "$DEPS" == "$CACHE/node_modules" ]]; then
    [[ -L "$SOURCE/node_modules" && "$(readlink -f -- "$SOURCE/node_modules")" == "$DEPS" ]] || die 'unexpected dependency target'
    [[ "$(realpath -m -- "$DEPS")" == "$CACHE/node_modules" ]] || die 'dependency path escaped approved cache'
  else
    [[ -d "$DEPS" && ! -L "$DEPS" && "$(realpath -- "$DEPS")" == "$SOURCE/node_modules" ]] || die 'project-local dependency directory missing'
  fi
  for shim in next tsc eslint; do [[ -x "$DEPS/.bin/$shim" ]] || die "missing frozen dependency shim: $shim"; done
  for dependency_file in next/package.json typescript/lib/typescript.js @types/react/index.d.ts @types/node/index.d.ts eslint/package.json; do
    [[ -f "$DEPS/$dependency_file" ]] || die "incomplete frozen dependency: $dependency_file"
  done
  node - "$DEPS" <<'JS'
const fs = require('node:fs'); const root = process.argv[2]
for (const [name, version] of [['next','15.5.18'],['typescript','5.7.3'],['react','18.3.1']]) {
  const actual = JSON.parse(fs.readFileSync(`${root}/${name}/package.json`, 'utf8')).version
  if (actual !== version) throw new Error(`Frozen dependency mismatch: ${name} ${actual}`)
}
JS
}
identity() {
  python3 - "$SOURCE" "$1" "${2:-}" <<'PY'
import hashlib,json,pathlib,sys
source=pathlib.Path(sys.argv[1]); output=sys.argv[2]; mirror=pathlib.Path(sys.argv[3]) if sys.argv[3] else None
configs=['package.json','pnpm-lock.yaml','pnpm-workspace.yaml','next.config.ts','tsconfig.json','tailwind.config.ts','eslint.config.mjs','postcss.config.mjs','prettier.config.cjs']
paths=sorted([p for p in (source/'src').rglob('*') if p.is_file()]+[source/n for n in configs])
entries=[]
for path in paths:
    relative=str(path.relative_to(source)); digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if mirror and hashlib.sha256((mirror/relative).read_bytes()).hexdigest()!=digest: raise SystemExit('Mirror source mismatch: '+relative)
    entries.append({'path':relative,'sha256':digest})
receipt={'authoritative_source':str(source),'build_mirror':str(mirror) if mirror else None,'all_files_equal':bool(mirror),'files':entries,'manifest_sha256':hashlib.sha256(json.dumps(entries,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
if output: pathlib.Path(output).write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'source_files':len(entries),'manifest_sha256':receipt['manifest_sha256']}))
PY
}
check_dependencies
if [[ "$mode" == --check ]]; then
  identity ''
  printf 'Preflight PASS. Source=%s\nMirror=%s\nDependencies=%s\n' "$SOURCE" "$MIRROR" "$DEPS"
  exit 0
fi

# Serialize only this helper. Never stop a serving process or unrelated work.
exec 9>"$CACHE/build-product.lock"
flock -n 9 || die 'another product build helper is active'
python3 - "$SOURCE" <<'PY'
import pathlib,sys
source=pathlib.Path(sys.argv[1])
for process in pathlib.Path('/proc').iterdir():
    if not process.name.isdigit(): continue
    try:
        if (process/'cwd').resolve()!=source: continue
        args=(process/'cmdline').read_bytes().decode(errors='replace').split('\0')
        native_server=any('next-server' in arg for arg in args)
        next_start='start' in args and any('next/dist/bin/next' in arg for arg in args)
        if native_server or next_start: raise SystemExit('Build refused: project frontend is serving (PID '+process.name+'). Stop it through the root-owned launcher first.')
    except (OSError,PermissionError): continue
PY
readonly RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
readonly ARCHIVE="$CACHE/build-history/$RUN_ID"
mkdir -p -- "$ARCHIVE"
[[ "$(realpath -m -- "$ARCHIVE")" == "$CACHE/build-history/$RUN_ID" ]] || die 'unexpected archive target'
if [[ -e "$MIRROR" ]]; then
  [[ -d "$MIRROR" && ! -L "$MIRROR" ]] || die 'mirror must be an ordinary directory'
  mv -- "$MIRROR" "$ARCHIVE/previous-mirror"
fi
mkdir -- "$MIRROR"
(cd -- "$SOURCE" && tar --exclude=./node_modules --exclude='./.next*' --exclude=./node_modules.failed --exclude=./home --exclude=./.git --exclude='./.env*' --exclude=./tsconfig.tsbuildinfo -cf - .) | (cd -- "$MIRROR" && tar -xf -)
ln -s -- "$DEPS" "$MIRROR/node_modules"
identity "$ARCHIVE/source-before.json" "$MIRROR"
check_dependencies
(
  cd -- "$MIRROR"
  # Use the real pnpm-generated shim: it preserves private-hoisted NODE_PATH.
  CI=1 NEXT_TELEMETRY_DISABLED=1 NODE_PATH="$DEPS/.pnpm/node_modules" ./node_modules/.bin/next build
  ./node_modules/.bin/tsc --noEmit
  node --experimental-strip-types --test tests/*.test.mjs
)
check_dependencies
identity "$ARCHIVE/source-after.json" "$MIRROR"
cmp -- "$ARCHIVE/source-before.json" "$ARCHIVE/source-after.json" || die 'authoritative source changed during build'

readonly STAGE="$SOURCE/.next.product-stage-$RUN_ID"
[[ "$(realpath -m -- "$STAGE")" == "$EXPECTED_SOURCE/.next.product-stage-$RUN_ID" ]] || die 'unexpected staged output target'
[[ -d "$MIRROR/.next" && ! -L "$MIRROR/.next" && -f "$MIRROR/.next/BUILD_ID" ]] || die 'missing successful build output'
[[ ! -e "$STAGE" && ! -L "$STAGE" ]] || die 'stage already exists'
mkdir -- "$STAGE"
(cd -- "$MIRROR/.next" && tar --exclude=./cache -cf - .) | (cd -- "$STAGE" && tar -xf -)
if [[ -e "$SOURCE/.next" || -L "$SOURCE/.next" ]]; then
  [[ -d "$SOURCE/.next" && ! -L "$SOURCE/.next" && "$(realpath -- "$SOURCE/.next")" == "$EXPECTED_SOURCE/.next" ]] || die 'existing output is not the exact ordinary project build directory'
  # Both absolute targets are checked; old output is preserved outside source.
  mv -- "$SOURCE/.next" "$ARCHIVE/previous-next"
fi
mv -- "$STAGE" "$SOURCE/.next"
cp -- "$ARCHIVE/source-after.json" "$SOURCE/FRONTEND_BUILD_IDENTITY.json"
printf 'Build PASS. Published %s/.next\nPrevious build and receipts: %s\nRestart the frontend with the root-owned launcher.\n' "$SOURCE" "$ARCHIVE"
