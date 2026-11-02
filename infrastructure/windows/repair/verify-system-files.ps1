$ErrorActionPreference = 'Stop'
Start-Transcript -Path "$PSScriptRoot\system-files.log" -Force
try {
    Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform | Format-List FeatureName,State
    Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux | Format-List FeatureName,State
    sfc /scannow
    Write-Output "SFC exit: $LASTEXITCODE"
    Write-Output "vmcompute present: $(Test-Path C:\Windows\System32\vmcompute.exe)"
} finally { Stop-Transcript }
