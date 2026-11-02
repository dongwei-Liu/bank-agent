$ErrorActionPreference = "Stop"

$bankAgentBackendHealth = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/health" -TimeoutSec 5
$bankAgentFrontendProxyHealth = Invoke-RestMethod -Uri "http://127.0.0.1:5173/api/health" -TimeoutSec 5

Write-Host "Backend direct:" ($bankAgentBackendHealth | ConvertTo-Json -Compress)
Write-Host "Vite proxy:" ($bankAgentFrontendProxyHealth | ConvertTo-Json -Compress)

if ($bankAgentBackendHealth.status -ne "UP" -or $bankAgentFrontendProxyHealth.status -ne "UP") {
    throw "Frontend/backend connection check failed."
}

Write-Host "Frontend/backend connection is healthy."
