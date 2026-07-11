param(
    [string[]]$ComposeFiles = @("docker-compose.yml"),
    [string]$ProjectName = "",
    [string]$DatabaseService = "db",
    [string]$DatabaseName = $(if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "parking_app" }),
    [string]$DatabaseUser = $(if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "parking_app" }),
    [string]$OutputDirectory = "backups/postgres",
    [string]$OutputFileName = "",
    [ValidateRange(0, 9)][int]$CompressionLevel = 6,
    [int]$RetentionDays = -1,
    [switch]$DryRunRetention,
    [switch]$RetentionOnly,
    [switch]$PlanOnly,
    [switch]$SkipArchiveValidation
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\postgres_backup_common.ps1"

function Get-BackupMetadataValue {
    param(
        [Parameter(Mandatory = $true)]$ComposeCommand,
        [string[]]$ComposeBaseArguments,
        [string]$DatabaseService,
        [string]$DatabaseUser,
        [string]$DatabaseName,
        [string]$Sql,
        [string]$Fallback = "unknown"
    )

    try {
        return Invoke-NativeText `
            -ComposeCommand $ComposeCommand `
            -ComposeBaseArguments $ComposeBaseArguments `
            -CommandArguments @("exec", "-T", $DatabaseService, "psql", "-U", $DatabaseUser, "-d", $DatabaseName, "-At", "-c", $Sql)
    }
    catch {
        return $Fallback
    }
}

$resolvedOutputDirectory = Assert-DirectoryIsUsable -Directory $OutputDirectory

if ($RetentionOnly) {
    Invoke-PostgresBackupRetention -OutputDirectory $resolvedOutputDirectory -RetentionDays $RetentionDays -DryRun:$DryRunRetention | Out-Null
    exit 0
}

$backupFileName = $OutputFileName
if ([string]::IsNullOrWhiteSpace($backupFileName)) {
    $backupFileName = New-PostgresBackupFileName -DatabaseName $DatabaseName
}
if ([System.IO.Path]::GetFileName($backupFileName) -ne $backupFileName) {
    throw "OutputFileName must be a file name, not a path."
}

$backupPath = Join-Path $resolvedOutputDirectory $backupFileName
$partialPath = "$backupPath.partial"
$metadataPath = "$backupPath.metadata.json"

if ($PlanOnly) {
    Write-Host "planned backup path: $backupPath"
    exit 0
}

if (Test-Path -LiteralPath $backupPath) {
    throw "Backup file already exists: $backupPath"
}
if (Test-Path -LiteralPath $partialPath) {
    Remove-Item -LiteralPath $partialPath -Force
}

$composeCommand = Resolve-ComposeCommand
$composeBaseArguments = Get-ComposeBaseArguments -ComposeFiles $ComposeFiles -ProjectName $ProjectName
Write-Host "using compose command: $($composeCommand.DisplayName)"
Write-Host "creating PostgreSQL custom-format backup for database '$DatabaseName'"

try {
    Invoke-NativeToFile `
        -ComposeCommand $composeCommand `
        -ComposeBaseArguments $composeBaseArguments `
        -CommandArguments @("exec", "-T", $DatabaseService, "pg_dump", "-U", $DatabaseUser, "-d", $DatabaseName, "-Fc", "-Z", "$CompressionLevel") `
        -OutputFile $partialPath

    $partialItem = Assert-BackupFileReadable -BackupFile $partialPath
    Move-Item -LiteralPath $partialItem.FullName -Destination $backupPath

    if (-not $SkipArchiveValidation) {
        Invoke-NativeWithInputFileText `
            -ComposeCommand $composeCommand `
            -ComposeBaseArguments $composeBaseArguments `
            -CommandArguments @("exec", "-T", $DatabaseService, "pg_restore", "--list") `
            -InputFile $backupPath | Out-Null
    }

    $backupItem = Assert-BackupFileReadable -BackupFile $backupPath
    $serverVersion = Get-BackupMetadataValue `
        -ComposeCommand $composeCommand `
        -ComposeBaseArguments $composeBaseArguments `
        -DatabaseService $DatabaseService `
        -DatabaseUser $DatabaseUser `
        -DatabaseName $DatabaseName `
        -Sql "SHOW server_version;"
    $alembicRevision = Get-BackupMetadataValue `
        -ComposeCommand $composeCommand `
        -ComposeBaseArguments $composeBaseArguments `
        -DatabaseService $DatabaseService `
        -DatabaseUser $DatabaseUser `
        -DatabaseName $DatabaseName `
        -Sql "SELECT version_num FROM alembic_version LIMIT 1;"

    $metadata = [ordered]@{
        backupFilename = $backupItem.Name
        createdAtUtc = (Get-Date).ToUniversalTime().ToString("o")
        databaseName = $DatabaseName
        postgresServerVersion = $serverVersion
        alembicCurrentRevision = $alembicRevision
        composeProjectName = $ProjectName
        composeFiles = $ComposeFiles
        databaseService = $DatabaseService
        format = "pg_dump custom -Fc"
        compressionLevel = $CompressionLevel
        backupSizeBytes = $backupItem.Length
        sha256 = Get-FileSha256Lower -Path $backupPath
    }
    $metadata | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $metadataPath -Encoding UTF8

    Write-Host "backup created: $backupPath"
    Write-Host "metadata created: $metadataPath"
    if ($RetentionDays -ge 0) {
        Invoke-PostgresBackupRetention -OutputDirectory $resolvedOutputDirectory -RetentionDays $RetentionDays -DryRun:$DryRunRetention | Out-Null
    }
}
catch {
    if (Test-Path -LiteralPath $partialPath) {
        Remove-Item -LiteralPath $partialPath -Force
    }
    if ((Test-Path -LiteralPath $backupPath) -and -not (Test-Path -LiteralPath $metadataPath)) {
        Remove-Item -LiteralPath $backupPath -Force
    }
    throw
}
