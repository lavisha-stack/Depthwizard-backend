param(
    [string]$Url = "http://127.0.0.1:5173"
)

$ErrorActionPreference = "Stop"
$frontendUrl = "http://127.0.0.1:5173/"
$backendUrl = "http://127.0.0.1:8000/health"
$deadline = [DateTime]::UtcNow.AddSeconds(45)
$frontendReady = $false
$backendReady = $false

while ([DateTime]::UtcNow -lt $deadline) {
    try {
        $frontendReady = (Invoke-WebRequest -UseBasicParsing -Uri $frontendUrl -TimeoutSec 2).StatusCode -eq 200
    } catch {
        $frontendReady = $false
    }
    try {
        $health = Invoke-RestMethod -Uri $backendUrl -TimeoutSec 2
        $backendReady = $health.status -eq "ok"
    } catch {
        $backendReady = $false
    }
    if ($frontendReady -and $backendReady) {
        Write-Host "DepthWizard is ready. Opening $Url"
        & (Join-Path $PSScriptRoot "open_gpu_viewer.ps1") -Url $Url
        exit $LASTEXITCODE
    }
    Start-Sleep -Milliseconds 500
}

throw "Startup timed out. Frontend ready: $frontendReady; backend ready: $backendReady."
