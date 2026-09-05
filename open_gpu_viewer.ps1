param(
    [string]$Url = "http://127.0.0.1:5173"
)

$ErrorActionPreference = "Stop"

$browserCandidates = @(
    (Join-Path $env:ProgramFiles "BraveSoftware\Brave-Browser\Application\brave.exe"),
    (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe")
)
$browser = $browserCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $browser) {
    throw "Brave, Chrome, or Edge was not found in its standard installation directory."
}

$profileDirectory = Join-Path $PSScriptRoot "depthwizard_person5\runtime\gpu-browser-profile"
New-Item -ItemType Directory -Force -Path $profileDirectory | Out-Null

Write-Host "Opening DepthWizard with Chromium's high-performance GPU preference..."
Start-Process -FilePath $browser -ArgumentList @(
    "--force_high_performance_gpu",
    "--use-angle=d3d11",
    "--new-window",
    "--start-maximized",
    "--no-first-run",
    "--no-default-browser-check",
    "--user-data-dir=$profileDirectory",
    $Url
)
