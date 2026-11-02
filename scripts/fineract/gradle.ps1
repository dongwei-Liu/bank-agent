param(
    [ValidateSet('help', 'compile', 'build')]
    [string]$Action = 'help'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$jdkRoot = Join-Path $root 'tools\jdk'
$env:GRADLE_USER_HOME = Join-Path $root 'tools\gradle'
$sourceRoot = Join-Path $root 'platform\fineract'
if (!(Test-Path -LiteralPath (Join-Path $sourceRoot 'gradlew.bat'))) {
    throw 'Fineract source is missing from platform/fineract.'
}
$task = switch ($Action) {
    'help' { 'help' }
    'compile' { ':fineract-provider:classes' }
    'build' { ':fineract-provider:bootJar' }
}
$jdk = Get-ChildItem $jdkRoot -Directory -Filter 'jdk-25*' -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
if ($jdk) {
    $env:JAVA_HOME = $jdk.FullName
    $env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
    Push-Location $sourceRoot
    try {
        & .\gradlew.bat $task --console=plain --max-workers=2 --no-configuration-cache
        if ($LASTEXITCODE -ne 0) { throw "Gradle failed with exit code $LASTEXITCODE" }
    } finally { Pop-Location }
    exit
}

if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Neither the project JDK nor Docker is available.'
}
New-Item -ItemType Directory -Force -Path $env:GRADLE_USER_HOME | Out-Null
docker info --format '{{.OSType}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and retry.' }
docker run --rm --init `
    --mount "type=bind,source=$sourceRoot,target=/workspace" `
    --mount "type=bind,source=$env:GRADLE_USER_HOME,target=/home/gradle/.gradle" `
    --tmpfs "/workspace/.git:rw,noexec,nosuid,size=1m" `
    --workdir /workspace `
    gradle:9.7.1-jdk25 gradle $task --no-daemon --console=plain --max-workers=2 --no-configuration-cache
if ($LASTEXITCODE -ne 0) { throw "Gradle failed with exit code $LASTEXITCODE" }
