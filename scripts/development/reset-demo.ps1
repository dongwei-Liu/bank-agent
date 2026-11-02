param(
    [long]$HistorySeed,
    [string]$AsOf
)

$ErrorActionPreference = "Stop"

$bankAgentRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$bankAgentPython = Join-Path $bankAgentRoot "apps\backend\.venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $bankAgentPython)) {
    throw "Python venv not found. Run scripts/development/setup-backend.ps1 first."
}

# Keep local Fineract/PostgreSQL traffic out of the machine proxy while leaving
# external services on their existing proxy path.
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

Push-Location $bankAgentRoot
try {
    $bankAgentResetArgs = @("--execute")
    if ($PSBoundParameters.ContainsKey("HistorySeed")) {
        $bankAgentResetArgs += @("--history-seed", $HistorySeed.ToString())
    }
    if ($PSBoundParameters.ContainsKey("AsOf")) {
        $bankAgentResetArgs += @("--as-of", $AsOf)
    }
    & $bankAgentPython ".\scripts\development\reset_demo.py" @bankAgentResetArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Demo Reset exited with code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
