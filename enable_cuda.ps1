$ErrorActionPreference = "Stop"

$pythonExecutable = Join-Path $PSScriptRoot "depthwizard_person5\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
    throw "Backend environment is missing. Create depthwizard_person5\.venv first."
}

$cudaProbe = @(& $pythonExecutable -c "import torch; print('yes' if torch.cuda.is_available() else 'no')")
$cudaReady = if ($cudaProbe.Count -gt 0) { [string]$cudaProbe[-1] } else { "no" }
if ($LASTEXITCODE -eq 0 -and $cudaReady.Trim() -eq "yes") {
    & $pythonExecutable -c "import torch; print(f'CUDA already active: {torch.__version__} | {torch.cuda.get_device_name(0)}')"
    exit $LASTEXITCODE
}

Write-Host "Installing the official PyTorch CUDA 13.0 wheels..."
& $pythonExecutable -m pip install --force-reinstall --no-deps torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cu130
if ($LASTEXITCODE -ne 0) { throw "CUDA PyTorch installation failed with exit code $LASTEXITCODE." }

& $pythonExecutable -c "import torch; assert torch.cuda.is_available(), 'CUDA is still unavailable'; print(f'CUDA active: {torch.__version__} | {torch.cuda.get_device_name(0)}')"
if ($LASTEXITCODE -ne 0) { throw "The CUDA verification failed with exit code $LASTEXITCODE." }
