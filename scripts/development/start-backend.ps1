$ErrorActionPreference = "Stop"

$bankAgentRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$bankAgentBackend = Join-Path $bankAgentRoot "apps\backend"
$bankAgentVenv = Join-Path $bankAgentBackend ".venv"
$bankAgentPython = Join-Path $bankAgentVenv "Scripts\python.exe"

# Keep localhost traffic out of system/environment proxies without disabling
# the proxy for external services such as SiliconFlow or GitHub.
$bankAgentNoProxyEntries = @()
foreach ($bankAgentNoProxyValue in @($env:NO_PROXY, $env:no_proxy)) {
    if ($bankAgentNoProxyValue) {
        $bankAgentNoProxyEntries += $bankAgentNoProxyValue.Split(",") |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
    }
}
$bankAgentNoProxyEntries += @("localhost", "127.0.0.1", "::1")
$bankAgentNoProxy = ($bankAgentNoProxyEntries | Select-Object -Unique) -join ","
$env:NO_PROXY = $bankAgentNoProxy
$env:no_proxy = $bankAgentNoProxy

if (-not (Test-Path -LiteralPath $bankAgentPython)) {
    throw "Python venv not found at $bankAgentVenv. Run setup-backend.ps1 first."
}

Push-Location $bankAgentBackend
try {
    Write-Host "Starting FastAPI backend on http://127.0.0.1:8080 (reload enabled)"
    & $bankAgentPython -m uvicorn main:app --host 127.0.0.1 --port 8080 --reload
    if ($LASTEXITCODE -ne 0) {
        throw "Backend exited with code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
