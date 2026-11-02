$ErrorActionPreference = "Stop"

$bankAgentRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$bankAgentBackend = Join-Path $bankAgentRoot "apps\backend"
$bankAgentPython = Join-Path $bankAgentBackend ".venv\Scripts\python.exe"

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
    throw "Python venv not found. Run setup-backend.ps1 first."
}

Push-Location $bankAgentBackend
try {
    Write-Host "Starting durable Agent worker (Ctrl+C to stop)"
    & $bankAgentPython .\agent_worker.py
    if ($LASTEXITCODE -ne 0) {
        throw "Agent worker exited with code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
