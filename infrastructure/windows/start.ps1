$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$composeFile = Join-Path $projectRoot 'infrastructure\docker\compose.yaml'
$envFile = Join-Path $projectRoot '.env'
Set-Location $projectRoot
& "$PSScriptRoot\setup.ps1"
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    $dockerBin = 'C:\Program Files\Docker\Docker\resources\bin'
    if (Test-Path "$dockerBin\docker.exe") { $env:PATH = "$dockerBin;$env:PATH" }
    else { throw 'Install Docker Desktop and enable its WSL2 engine first.' }
}
docker info --format '{{.OSType}}'
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and wait for the Linux engine to be ready, then retry.' }
docker compose --env-file $envFile -f $composeFile config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Invalid Docker Compose configuration.' }
docker compose --env-file $envFile -f $composeFile up -d
if ($LASTEXITCODE -ne 0) { throw 'Container startup failed. Run docker compose logs.' }
Write-Host 'Waiting up to 15 minutes for database migrations and API readiness...'
$ready = $false
for ($i = 0; $i -lt 180; $i++) {
    $health = docker compose --env-file $envFile -f $composeFile exec -T fineract `
        sh -c 'wget --no-check-certificate -qO- https://127.0.0.1:8443/fineract-provider/actuator/health 2>/dev/null'
    if ($LASTEXITCODE -eq 0 -and $health -match '"status"\s*:\s*"UP"') {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 5
}
if (!$ready) { docker compose --env-file $envFile -f $composeFile logs --tail 80 fineract; throw 'API is not healthy yet. Inspect container logs.' }
Write-Host 'Fineract is ready: https://localhost:8443/fineract-provider'
Write-Host 'Local demo login: mifos / password; tenant: default. Change this password before sharing access.'
