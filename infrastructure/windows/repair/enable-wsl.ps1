$ErrorActionPreference = 'Stop'
$log = Join-Path $PSScriptRoot 'windows-features.log'
Start-Transcript -Path $log -Force
try {
    foreach ($feature in @('Microsoft-Windows-Subsystem-Linux', 'VirtualMachinePlatform')) {
        $result = Enable-WindowsOptionalFeature -Online -FeatureName $feature -All -NoRestart
        $result | Format-List Online, RestartNeeded
    }
    Get-CimInstance Win32_Processor | Select-Object Name, VirtualizationFirmwareEnabled, SecondLevelAddressTranslationExtensions | Format-List
} finally { Stop-Transcript }
