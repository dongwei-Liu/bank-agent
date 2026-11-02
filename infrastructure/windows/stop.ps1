$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$composeFile = Join-Path $projectRoot 'infrastructure\docker\compose.yaml'
$envFile = Join-Path $projectRoot '.env'
Set-Location $projectRoot
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    $env:PATH = "C:\Program Files\Docker\Docker\resources\bin;$env:PATH"
}
docker compose --env-file $envFile -f $composeFile stop
if ($LASTEXITCODE -ne 0) { throw 'Failed to stop the containers.' }
