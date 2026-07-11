param(
    [Parameter(Mandatory = $true)][string]$BackupFile,
    [string[]]$ComposeFiles = @("docker-compose.yml"),
    [string]$ProjectName = "",
    [string]$DatabaseService = "db",
    [string]$DatabaseUser = $(if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "parking_app" }),
    [string]$SourceDatabaseName = $(if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "parking_app" }),
    [string]$TargetDatabase = "",
    [ValidateSet("FreshDatabase", "ExistingDatabase")][string]$Mode = "FreshDatabase",
    [string]$Environment = $(if ($env:ENVIRONMENT) { $env:ENVIRONMENT } else { "local" }),
    [switch]$ConfirmDestructive,
    [switch]$AllowProductionRestore,
    [switch]$SkipArchiveValidation
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\postgres_backup_common.ps1"

if ([string]::IsNullOrWhiteSpace($TargetDatabase)) {
    $TargetDatabase = "$($SourceDatabaseName)_restore_$((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmss'))"
}

Assert-ProductionRestoreAllowed -Environment $Environment -AllowProductionRestore:$AllowProductionRestore
Assert-SafeDatabaseIdentifier -Name $TargetDatabase -Label "target database"
Assert-SafeDatabaseIdentifier -Name $DatabaseUser -Label "database user"

if ($Mode -eq "FreshDatabase" -and $TargetDatabase -eq $SourceDatabaseName) {
    throw "FreshDatabase restore target must differ from the source database name."
}
if ($Mode -eq "ExistingDatabase" -and -not $ConfirmDestructive) {
    throw "ExistingDatabase restore is destructive and requires -ConfirmDestructive."
}
if ($Mode -eq "ExistingDatabase") {
    Write-Host "destructive restore target database: $TargetDatabase"
}

$backupItem = Assert-BackupFileReadable -BackupFile $BackupFile
$composeCommand = Resolve-ComposeCommand
$composeBaseArguments = Get-ComposeBaseArguments -ComposeFiles $ComposeFiles -ProjectName $ProjectName
Write-Host "using compose command: $($composeCommand.DisplayName)"
Write-Host "validating backup archive: $($backupItem.FullName)"

if (-not $SkipArchiveValidation) {
    Invoke-NativeWithInputFileText `
        -ComposeCommand $composeCommand `
        -ComposeBaseArguments $composeBaseArguments `
        -CommandArguments @("exec", "-T", $DatabaseService, "pg_restore", "--list") `
        -InputFile $backupItem.FullName | Out-Null
}

if ($Mode -eq "ExistingDatabase") {
    $dropSql = @"
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$TargetDatabase' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS "$TargetDatabase";
CREATE DATABASE "$TargetDatabase" OWNER "$DatabaseUser";
"@
    Invoke-NativeText `
        -ComposeCommand $composeCommand `
        -ComposeBaseArguments $composeBaseArguments `
        -CommandArguments @("exec", "-T", $DatabaseService, "psql", "-U", $DatabaseUser, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", $dropSql) | Out-Null
}
else {
    Invoke-NativeText `
        -ComposeCommand $composeCommand `
        -ComposeBaseArguments $composeBaseArguments `
        -CommandArguments @("exec", "-T", $DatabaseService, "createdb", "-U", $DatabaseUser, "-O", $DatabaseUser, $TargetDatabase) | Out-Null
}

Write-Host "restoring backup into database: $TargetDatabase"
Invoke-NativeWithInputFileText `
    -ComposeCommand $composeCommand `
    -ComposeBaseArguments $composeBaseArguments `
    -CommandArguments @("exec", "-T", $DatabaseService, "pg_restore", "--no-owner", "--role", $DatabaseUser, "-U", $DatabaseUser, "-d", $TargetDatabase) `
    -InputFile $backupItem.FullName | Out-Null

$alembicRevision = Invoke-NativeText `
    -ComposeCommand $composeCommand `
    -ComposeBaseArguments $composeBaseArguments `
    -CommandArguments @("exec", "-T", $DatabaseService, "psql", "-U", $DatabaseUser, "-d", $TargetDatabase, "-At", "-c", "SELECT version_num FROM alembic_version LIMIT 1;")

Write-Host "restore completed: $TargetDatabase"
Write-Host "restored alembic revision: $alembicRevision"
