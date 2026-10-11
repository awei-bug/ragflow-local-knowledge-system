#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

fail() {
  printf 'verify: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command '$1'; ${2:-run bash tools/dev/bootstrap.sh first}"
}

[[ "$(uname -s)" == "Linux" ]] || fail "the supported verification path is Linux or WSL2"
require_command uv
require_command node "install Node.js >= 18.20.4"
require_command npm
require_command docker
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required"
[[ -x .venv/bin/python ]] || fail "missing .venv/bin/python; run bash tools/dev/bootstrap.sh first"
[[ -d web/node_modules ]] || fail "missing web/node_modules; run bash tools/dev/bootstrap.sh first"

printf '==> Checking dependency locks and Compose rendering\n'
uv lock --check
docker compose -f docker/docker-compose-base.yml config --quiet

printf '==> Running credential-free enterprise smoke tests\n'
env -u ZHIPU_AI_API_KEY -u SILICONFLOW_API_KEY \
  uv run --frozen python -m pytest -q \
    test/unit_test/test_testcases/test_optional_model_api_keys.py \
    test/unit_test/api/db/joint_services/test_memory_graph_service.py \
    test/unit_test/api/apps/services/test_memory_search_with_graph.py \
    test/unit_test/api/apps/restful_apis/test_memory_search_graph_payload.py \
    test/unit_test/memory/services

printf '==> Checking changed enterprise-readiness Python files\n'
uvx --from "ruff==0.12.12" ruff check \
  api/db/joint_services/memory_message_service.py \
  memory/services/graph.py \
  test/unit_test/test_testcases/test_optional_model_api_keys.py \
  test/unit_test/api/db/joint_services/test_memory_graph_service.py \
  test/unit_test/api/apps/services/test_memory_search_with_graph.py \
  test/unit_test/api/apps/restful_apis/test_memory_search_graph_payload.py \
  test/unit_test/memory/services

printf '==> Running frontend static checks\n'
npm --prefix web run type-check
npm --prefix web run lint

printf '\nEnvironment verification passed.\n'
