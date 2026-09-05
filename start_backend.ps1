$ErrorActionPreference = "Stop"

$backendDirectory = Join-Path $PSScriptRoot "depthwizard_person5"
$pythonExecutable = Join-Path $backendDirectory ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
    throw "Backend environment is missing. Create depthwizard_person5\.venv and install requirements.txt plus requirements-pipeline.txt."
}

if (-not $env:MAX_UPLOAD_SIZE_MB) {
    $env:MAX_UPLOAD_SIZE_MB = "500"
}

Set-Location -LiteralPath $backendDirectory
Write-Host "DepthWizard backend: http://127.0.0.1:8000 (upload limit: $env:MAX_UPLOAD_SIZE_MB MB)"
& $pythonExecutable -c "import torch; print('ML compute: ' + (torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU (run ..\\enable_cuda.ps1 to enable NVIDIA CUDA)'))"
& $pythonExecutable -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
