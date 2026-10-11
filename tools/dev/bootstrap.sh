#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

fail() {
  printf 'bootstrap: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command '$1' (${2:-run bootstrap prerequisites})"
}

[[ "$(uname -s)" == "Linux" ]] || fail "the supported source-development path is Linux or WSL2"
require_command uv "install uv, then rerun this script"
require_command node "install Node.js >= 18.20.4"
require_command npm "install Node.js >= 18.20.4 and npm"
require_command docker "enable Docker Engine or Docker Desktop WSL integration"
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required"

node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 18 || (major === 18 && minor < 20)) process.exit(1)' \
  || fail "Node.js >= 18.20.4 is required"

printf '==> Syncing locked Python 3.13 test environment\n'
uv sync --python 3.13 --group test --frozen

printf '==> Installing the local Python SDK into the project environment\n'
uv pip install --python .venv/bin/python --editable sdk/python

printf '==> Downloading parser and native build dependencies\n'
download_args=()
if [[ "${RAGFLOW_USE_CHINA_MIRRORS:-0}" == "1" ]]; then
  download_args+=(--china-mirrors)
fi
uv run --frozen python ragflow_deps/download_deps.py "${download_args[@]}"

printf '==> Installing locked frontend dependencies\n'
npm --prefix web ci

if [[ "${RAGFLOW_BOOTSTRAP_START_SERVICES:-1}" == "1" ]]; then
  printf '==> Starting base services\n'
  docker compose -f docker/docker-compose-base.yml up -d
else
  printf '==> Base-service startup skipped (RAGFLOW_BOOTSTRAP_START_SERVICES=0)\n'
fi

printf '\nBootstrap complete. Run: bash tools/dev/verify.sh\n'
