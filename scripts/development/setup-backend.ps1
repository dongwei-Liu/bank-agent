$ErrorActionPreference = "Stop"

# Create apps/backend/.venv and restore the locked Python dependencies.
# Supported and tested interpreter range: Python 3.11 through 3.13.

$bankAgentRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$bankAgentBackend = Join-Path $bankAgentRoot "apps\backend"
$bankAgentVenv = Join-Path $bankAgentBackend ".venv"
$bankAgentPython = Join-Path $bankAgentVenv "Scripts\python.exe"

function Get-PythonVersion([string]$executable, [string[]]$arguments) {
    try {
        $text = & $executable @arguments -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $text) { return $null }
        return [Version]$text.Trim()
    }
    catch {
        return $null
    }
}

$bankAgentCandidates = @(
    [pscustomobject]@{ Command = "py.exe"; Arguments = @("-3.13") },
    [pscustomobject]@{ Command = "py.exe"; Arguments = @("-3.12") },
    [pscustomobject]@{ Command = "py.exe"; Arguments = @("-3.11") },
    [pscustomobject]@{ Command = "python.exe"; Arguments = @() },
    [pscustomobject]@{ Command = "python3.exe"; Arguments = @() }
)

$bankAgentPythonExecutable = $null
$bankAgentPythonArguments = @()
if (Test-Path -LiteralPath $bankAgentPython) {
    $version = Get-PythonVersion $bankAgentPython @()
    if (-not $version -or $version -lt [Version]"3.11" -or $version -ge [Version]"3.14") {
        throw "Existing venv uses unsupported Python. Remove apps/backend/.venv and install Python 3.11-3.13 before retrying."
    }
    Write-Host "Reusing existing Python $version virtual environment at $bankAgentVenv"
}
else {
    foreach ($candidate in $bankAgentCandidates) {
        $command = Get-Command $candidate.Command -ErrorAction SilentlyContinue
        if (-not $command) { continue }
        $version = Get-PythonVersion $command.Source $candidate.Arguments
        if ($version -and $version -ge [Version]"3.11" -and $version -lt [Version]"3.14") {
            $bankAgentPythonExecutable = $command.Source
            $bankAgentPythonArguments = $candidate.Arguments
            Write-Host "Using Python $version from $($command.Source) $($candidate.Arguments -join ' ')"
            break
        }
    }

    if (-not $bankAgentPythonExecutable) {
        throw "Python 3.11, 3.12 or 3.13 was not found. Install a supported 64-bit Python and reopen PowerShell."
    }

    Write-Host "Creating venv at $bankAgentVenv"
    & $bankAgentPythonExecutable @bankAgentPythonArguments -m venv $bankAgentVenv
    if ($LASTEXITCODE -ne 0) { throw "Failed to create Python virtual environment." }
}

Write-Host "Installing locked backend dependencies"
Push-Location $bankAgentBackend
try {
    & $bankAgentPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
    & $bankAgentPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    & $bankAgentPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw "pip dependency check failed" }
}
finally {
    Pop-Location
}

Write-Host "Backend environment ready: $bankAgentPython"
