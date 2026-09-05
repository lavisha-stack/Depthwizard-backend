$ErrorActionPreference = "Stop"

$frontendDirectory = Join-Path $PSScriptRoot "depthwizard_person4"
$viteEntryPoint = Join-Path $frontendDirectory "node_modules\vite\bin\vite.js"
$codexNode = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
$nodeExecutable = $null

# Invoke Node directly. This avoids globally installed pnpm/npm command shims
# that can exist on PATH even when their node.exe dependency is unavailable.
if (Test-Path -LiteralPath $codexNode -PathType Leaf) {
    $nodeExecutable = $codexNode
} else {
    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeCommand) {
        $nodeExecutable = $nodeCommand.Source
    }
}

if (-not $nodeExecutable) {
    throw "Node.js was not found. Install Node.js LTS, reopen PowerShell, and run this script again."
}

if (-not (Test-Path -LiteralPath $viteEntryPoint -PathType Leaf)) {
    throw "Frontend dependencies are missing. Install them in depthwizard_person4 before starting the site."
}

Set-Location -LiteralPath $frontendDirectory
Write-Host "DepthWizard frontend: http://127.0.0.1:5173"
Write-Host "Node runtime: $nodeExecutable"
& $nodeExecutable $viteEntryPoint
