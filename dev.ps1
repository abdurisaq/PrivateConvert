param(
    [ValidateSet("development", "single")]
    [string]$Mode = "development"
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = "$root\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "$root\backend\.venv\Scripts\python.exe"
}
if (-not (Test-Path $python)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}

if ($Mode -eq "single") {
    & $python "$root\run_dev_stack.py"
    exit $LASTEXITCODE
}

$backend = Start-Job -ArgumentList $root, $python -ScriptBlock {
    param($projectRoot, $pythonExecutable)
    Set-Location "$projectRoot\backend"
    & $pythonExecutable -m uvicorn app.app:app --reload --host 127.0.0.1 --port 8000
}
$frontend = Start-Job -ArgumentList $root -ScriptBlock {
    param($projectRoot)
    Set-Location "$projectRoot\frontend"
    npm run dev -- --host 127.0.0.1
}

Write-Host "Backend: http://127.0.0.1:8000"
Write-Host "Frontend: http://127.0.0.1:5173"
Write-Host "Press Ctrl+C to stop both development servers."

try {
    while ($true) {
        Receive-Job -Job $backend, $frontend
        if ($backend.State -in @("Failed", "Completed") -or $frontend.State -in @("Failed", "Completed")) {
            throw "A development server exited."
        }
        Start-Sleep -Seconds 1
    }
}
finally {
    foreach ($job in @($backend, $frontend)) {
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    }
}
