#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_PREREQUISITES=0
SKIP_FRONTEND=0
SKIP_LLM=0
for arg in "$@"; do
  case "$arg" in
    --install-prerequisites) INSTALL_PREREQUISITES=1 ;;
    --skip-frontend) SKIP_FRONTEND=1 ;;
    --skip-llm-providers) SKIP_LLM=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

install_apt() {
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip nodejs npm swi-prolog-nox
}
install_dnf() {
  sudo dnf install -y python3 python3-pip nodejs npm pl
}

missing=0
for command in python3 node npm swipl; do
  command -v "$command" >/dev/null 2>&1 || missing=1
done
if [[ "$missing" == 1 ]]; then
  if [[ "$INSTALL_PREREQUISITES" != 1 ]]; then
    echo "Prerequisites are missing; re-run with --install-prerequisites" >&2
    exit 1
  fi
  if command -v apt-get >/dev/null 2>&1; then install_apt
  elif command -v dnf >/dev/null 2>&1; then install_dnf
  else echo "Unsupported package manager; install Python, Node, npm, and SWI-Prolog manually" >&2; exit 1
  fi
fi

if ! command -v uv >/dev/null 2>&1; then
  python3 -m venv "$ROOT/.uv-bootstrap"
  "$ROOT/.uv-bootstrap/bin/python" -m pip install --disable-pip-version-check "uv==0.9.28"
  UV="$ROOT/.uv-bootstrap/bin/uv"
else
  UV=uv
fi

cd "$ROOT"
extras=(--extra engines)
[[ "$SKIP_LLM" == 1 ]] || extras+=(--extra llm)
"$UV" sync --frozen --extra dev "${extras[@]}"
if [[ "$SKIP_FRONTEND" != 1 ]]; then
  test -f web/package-lock.json || { echo "web/package-lock.json is missing" >&2; exit 1; }
  npm ci --prefix web --ignore-scripts
  npm run build --prefix web
fi
"$UV" run llm-expert diagnostics --json
"$UV" run pytest -q
