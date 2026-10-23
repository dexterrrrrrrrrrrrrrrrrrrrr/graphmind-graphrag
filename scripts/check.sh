#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-/workspace/.cache/uv}"
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/python -m pytest -m 'not integration and not live' -q
npm --prefix frontend test
npm --prefix frontend run build
# Integration is deliberately opt-in and must target a separate Neo4j instance.
if [[ -n "${TEST_NEO4J_URI:-}" ]]; then
  .venv/bin/python -m pytest -m integration -k 'not live_sentence' -q
fi
