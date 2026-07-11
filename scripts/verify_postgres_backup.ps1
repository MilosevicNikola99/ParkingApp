param(
    [Parameter(Mandatory = $true)][string]$BackupFile,
    [string[]]$ComposeFiles = @("docker-compose.yml"),
    [string]$ProjectName = "",
    [string]$DatabaseService = "db",
    [string]$ExpectedSha256 = "",
    [switch]$SkipArchiveValidation
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\postgres_backup_common.ps1"

$backupItem = Assert-BackupFileReadable -BackupFile $BackupFile
$actualSha256 = Get-FileSha256Lower -Path $backupItem.FullName
$metadataPath = "$($backupItem.FullName).metadata.json"

if (Test-Path -LiteralPath $metadataPath -PathType Leaf) {
    $metadata = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json
    if ($metadata.backupFilename -and $metadata.backupFilename -ne $backupItem.Name) {
        throw "Metadata backup filename does not match backup file."
    }
    if ($metadata.sha256 -and $metadata.sha256.ToLowerInvariant() -ne $actualSha256) {
        throw "Backup checksum does not match metadata."
    }
}

if (-not [string]::IsNullOrWhiteSpace($ExpectedSha256) -and $ExpectedSha256.ToLowerInvariant() -ne $actualSha256) {
    throw "Backup checksum does not match expected value."
}

if (-not $SkipArchiveValidation) {
    $composeCommand = Resolve-ComposeCommand
    $composeBaseArguments = Get-ComposeBaseArguments -ComposeFiles $ComposeFiles -ProjectName $ProjectName
    Invoke-NativeWithInputFileText `
        -ComposeCommand $composeCommand `
        -ComposeBaseArguments $composeBaseArguments `
        -CommandArguments @("exec", "-T", $DatabaseService, "pg_restore", "--list") `
        -InputFile $backupItem.FullName | Out-Null
}

Write-Host "backup verification passed: $($backupItem.FullName)"
Write-Host "sha256: $actualSha256"
