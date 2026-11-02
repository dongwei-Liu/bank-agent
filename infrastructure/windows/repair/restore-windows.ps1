$ErrorActionPreference = 'Stop'
Start-Transcript -Path "$PSScriptRoot\windows-restore.log" -Force
try {
    Repair-WindowsImage -Online -RestoreHealth | Format-List
    Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All -NoRestart | Format-List
    Write-Output "vmcompute executable present: $(Test-Path C:\Windows\System32\vmcompute.exe)"
    Get-Service vmcompute -ErrorAction SilentlyContinue | Format-List Name,Status,StartType
} finally { Stop-Transcript }
