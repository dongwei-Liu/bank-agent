$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$envPath = Join-Path $projectRoot '.env'
if (!(Test-Path -LiteralPath $envPath)) {
    function New-LocalPassword {
        $bytes = New-Object byte[] 32
        $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
        return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
    }
    @(
        'FINERACT_IMAGE=apache/fineract@sha256:ab9f271fb27f445ac0622fbdae00c84e0780f957adc1bba356925b0e3b26a38d'
        "POSTGRES_ADMIN_PASSWORD=$(New-LocalPassword)"
        "FINERACT_DB_PASSWORD=$(New-LocalPassword)"
        "FINERACT_MASTER_PASSWORD=$(New-LocalPassword)"
    ) | Set-Content -LiteralPath $envPath -Encoding ascii
    Write-Host 'Created .env with random local database passwords.'
} else {
    Write-Host 'Existing .env preserved.'
}
