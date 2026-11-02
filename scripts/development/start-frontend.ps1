$ErrorActionPreference = "Stop"

$bankAgentRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$bankAgentFrontend = Join-Path $bankAgentRoot "apps\frontend"

# Keep Vite's localhost API proxy out of system/environment proxies without
# disabling the proxy for external package registries or other services.
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

# A PowerShell window opened before Node was installed does not automatically
# receive the updated user PATH. Refresh it here without depending on a drive.
$bankAgentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($bankAgentUserPath) {
    $env:Path = "$bankAgentUserPath;$env:Path"
}

# An explicit runtime location is optional for portable installations and CI.
# Use System.IO rather than Join-Path so a stale/nonexistent drive cannot abort
# the script before normal PATH discovery runs.
$bankAgentNodeHome = $env:BANK_AGENT_NODE_HOME
if ($bankAgentNodeHome) {
    $bankAgentExplicitNode = [System.IO.Path]::Combine($bankAgentNodeHome, "node.exe")
    if (-not [System.IO.File]::Exists($bankAgentExplicitNode)) {
        throw "BANK_AGENT_NODE_HOME does not contain node.exe: $bankAgentNodeHome"
    }
    $env:Path = "$bankAgentNodeHome;$env:Path"
}

$bankAgentNodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $bankAgentNodeCommand) {
    throw "Node.js is not available. Install Node.js 22.12 or newer."
}

$bankAgentNodeVersionText = & $bankAgentNodeCommand.Source --version
if ($LASTEXITCODE -ne 0) {
    throw "Node.js could not be executed."
}
$bankAgentNodeVersion = [Version]$bankAgentNodeVersionText.TrimStart("v")
if ($bankAgentNodeVersion -lt [Version]"22.12.0") {
    throw "Node.js $bankAgentNodeVersionText is too old. Install Node.js 22.12 or newer."
}

$bankAgentNodeDirectory = Split-Path -Parent $bankAgentNodeCommand.Source
$bankAgentNpmCommand = [System.IO.Path]::Combine($bankAgentNodeDirectory, "npm.cmd")
if (-not [System.IO.File]::Exists($bankAgentNpmCommand)) {
    throw "npm.cmd was not found beside Node.js: $bankAgentNodeDirectory"
}

Write-Host "Using Node.js $bankAgentNodeVersionText from $bankAgentNodeDirectory"

Push-Location $bankAgentFrontend
try {
    & $bankAgentNpmCommand run dev -- --host 127.0.0.1
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend exited with code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
