[CmdletBinding()]
param(
    [switch]$InstallPrerequisites,
    [switch]$SkipFrontend,
    [switch]$SkipLlmProviders
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = Split-Path -Parent $PSScriptRoot

function Test-Command([string]$Name) {
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Install-WingetPackage([string]$Id) {
    if (-not (Test-Command 'winget')) { throw "winget is required to install $Id" }
    winget install --id $Id --exact --silent --accept-package-agreements --accept-source-agreements
}

$requirements = @(
    @{ Command = 'python'; Package = 'Python.Python.3.11' },
    @{ Command = 'node'; Package = 'OpenJS.NodeJS.LTS' },
    @{ Command = 'swipl'; Package = 'SWI-Prolog.SWI-Prolog' },
    @{ Command = 'uv'; Package = 'astral-sh.uv' }
)
foreach ($requirement in $requirements) {
    if (-not (Test-Command $requirement.Command)) {
        if (-not $InstallPrerequisites) {
            throw "$($requirement.Command) is missing. Re-run with -InstallPrerequisites."
        }
        Install-WingetPackage $requirement.Package
    }
}

Push-Location $Root
try {
    $extras = @('--extra', 'engines')
    if (-not $SkipLlmProviders) { $extras += @('--extra', 'llm') }
    uv sync --native-tls --frozen --extra dev @extras
    if (-not $SkipFrontend) {
        if (-not (Test-Path (Join-Path $Root 'web\package-lock.json'))) { throw 'web/package-lock.json is missing' }
        npm ci --prefix web --ignore-scripts
        npm run build --prefix web
    }
    uv run llm-expert diagnostics --json
    uv run pytest -q
} finally {
    Pop-Location
}
