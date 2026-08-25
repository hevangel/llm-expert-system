[CmdletBinding()]
param([string]$Workspace = '.acceptance-workspace')
$ErrorActionPreference = 'Stop'
uv run llm-expert generate examples/family --workspace $Workspace --json | Write-Output
uv run llm-expert versions --workspace $Workspace --json | Write-Output
uv run python -m llm_expert_system.evaluation examples/family --workspace "$Workspace-evaluation" | Write-Output
uv run pytest -q
