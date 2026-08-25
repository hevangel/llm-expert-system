#!/usr/bin/env bash
set -euo pipefail
WORKSPACE="${1:-.acceptance-workspace}"
uv run llm-expert generate examples/family --workspace "$WORKSPACE" --json
uv run llm-expert versions --workspace "$WORKSPACE" --json
uv run python -m llm_expert_system.evaluation examples/family --workspace "${WORKSPACE}-evaluation"
uv run pytest -q
