$ErrorActionPreference = 'Stop'
Start-Transcript -Path "$PSScriptRoot\wsl-diagnostics.log" -Force
try {
    Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform | Select-Object FeatureName, State
    Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux | Select-Object FeatureName, State
    Get-CimInstance Win32_OperatingSystem | Select-Object LastBootUpTime
    Get-CimInstance Win32_ComputerSystem | Select-Object HypervisorPresent
    Get-CimInstance Win32_Processor | Select-Object Name, VirtualizationFirmwareEnabled
    bcdedit /enum '{current}'
} finally { Stop-Transcript }
