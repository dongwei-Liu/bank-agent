$ErrorActionPreference = 'Stop'
Start-Transcript -Path "$PSScriptRoot\virtualization-repair.log" -Force
try {
    bcdedit /set hypervisorlaunchtype auto
    if ($LASTEXITCODE -ne 0) { throw 'Failed to enable hypervisor launch.' }
    Repair-WindowsImage -Online -ScanHealth | Format-List
    Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform | Format-List FeatureName,State
} finally { Stop-Transcript }
