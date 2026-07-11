$PostgresBackupNamePattern = '^[A-Za-z0-9_-]+_\d{8}T\d{6}Z\.pgdump$'

function Resolve-ComposeCommand {
    $dockerCompose = Get-Command docker-compose -ErrorAction SilentlyContinue
    if ($dockerCompose) {
        return [pscustomobject]@{
            Executable = $dockerCompose.Source
            Prefix = @()
            DisplayName = "docker-compose"
        }
    }

    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) {
        & $docker.Source compose version *> $null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{
                Executable = $docker.Source
                Prefix = @("compose")
                DisplayName = "docker compose"
            }
        }
    }

    throw "Neither docker-compose nor docker compose is available."
}

function Get-ComposeBaseArguments {
    param(
        [string[]]$ComposeFiles,
        [string]$ProjectName
    )

    $composeArgs = @()
    foreach ($composeFile in $ComposeFiles) {
        if ([string]::IsNullOrWhiteSpace($composeFile)) {
            throw "Compose file path must not be empty."
        }
        $composeArgs += @("-f", $composeFile)
    }
    if (-not [string]::IsNullOrWhiteSpace($ProjectName)) {
        $composeArgs += @("-p", $ProjectName)
    }
    return $composeArgs
}

function Invoke-NativeText {
    param(
        [Parameter(Mandatory = $true)]$ComposeCommand,
        [string[]]$ComposeBaseArguments = @(),
        [Parameter(Mandatory = $true)][string[]]$CommandArguments,
        [switch]$AllowFailure
    )

    $allArguments = @($ComposeCommand.Prefix) + $ComposeBaseArguments + $CommandArguments
    $output = & $ComposeCommand.Executable @allArguments 2>&1
    if ($LASTEXITCODE -ne 0 -and -not $AllowFailure) {
        throw "Command failed with exit code ${LASTEXITCODE}: $($ComposeCommand.DisplayName) $($CommandArguments -join ' ')"
    }
    return ($output | Out-String).Trim()
}

function ConvertTo-NativeArgument {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Argument)

    if ($Argument.Length -eq 0) {
        return '""'
    }
    if ($Argument -notmatch '[\s"]') {
        return $Argument
    }

    $quoted = '"'
    $backslashCount = 0
    foreach ($character in $Argument.ToCharArray()) {
        if ($character -eq '\') {
            $backslashCount += 1
            continue
        }
        if ($character -eq '"') {
            $quoted += ('\' * (($backslashCount * 2) + 1))
            $quoted += '"'
            $backslashCount = 0
            continue
        }
        if ($backslashCount -gt 0) {
            $quoted += ('\' * $backslashCount)
            $backslashCount = 0
        }
        $quoted += $character
    }
    if ($backslashCount -gt 0) {
        $quoted += ('\' * ($backslashCount * 2))
    }
    $quoted += '"'
    return $quoted
}

function ConvertTo-NativeArgumentString {
    param([string[]]$Arguments = @())

    return ($Arguments | ForEach-Object { ConvertTo-NativeArgument -Argument $_ }) -join " "
}

function Invoke-NativeToFile {
    param(
        [Parameter(Mandatory = $true)]$ComposeCommand,
        [string[]]$ComposeBaseArguments = @(),
        [Parameter(Mandatory = $true)][string[]]$CommandArguments,
        [Parameter(Mandatory = $true)][string]$OutputFile
    )

    $allArguments = @($ComposeCommand.Prefix) + $ComposeBaseArguments + $CommandArguments
    $processInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $processInfo.FileName = $ComposeCommand.Executable
    $processInfo.Arguments = ConvertTo-NativeArgumentString -Arguments $allArguments
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    $processInfo.UseShellExecute = $false

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $processInfo
    [void]$process.Start()
    $stderrTask = $process.StandardError.ReadToEndAsync()

    $fileStream = [System.IO.File]::Open($OutputFile, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try {
        $process.StandardOutput.BaseStream.CopyTo($fileStream)
    }
    finally {
        $fileStream.Dispose()
    }

    $process.WaitForExit()
    $stderr = $stderrTask.Result
    if ($process.ExitCode -ne 0) {
        throw "Command failed with exit code $($process.ExitCode): $($ComposeCommand.DisplayName) $($CommandArguments -join ' '). $stderr"
    }
}

function Invoke-NativeWithInputFileText {
    param(
        [Parameter(Mandatory = $true)]$ComposeCommand,
        [string[]]$ComposeBaseArguments = @(),
        [Parameter(Mandatory = $true)][string[]]$CommandArguments,
        [Parameter(Mandatory = $true)][string]$InputFile
    )

    $allArguments = @($ComposeCommand.Prefix) + $ComposeBaseArguments + $CommandArguments
    $processInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $processInfo.FileName = $ComposeCommand.Executable
    $processInfo.Arguments = ConvertTo-NativeArgumentString -Arguments $allArguments
    $processInfo.RedirectStandardInput = $true
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    $processInfo.UseShellExecute = $false

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $processInfo
    [void]$process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()

    $inputStream = [System.IO.File]::OpenRead($InputFile)
    try {
        $inputStream.CopyTo($process.StandardInput.BaseStream)
        $process.StandardInput.Close()
    }
    finally {
        $inputStream.Dispose()
    }

    $process.WaitForExit()
    if ($process.ExitCode -ne 0) {
        throw "Command failed with exit code $($process.ExitCode): $($ComposeCommand.DisplayName) $($CommandArguments -join ' '). $($stderrTask.Result)"
    }
    return $stdoutTask.Result.Trim()
}

function Assert-DirectoryIsUsable {
    param([Parameter(Mandatory = $true)][string]$Directory)

    if (Test-Path -LiteralPath $Directory -PathType Leaf) {
        throw "Output directory path points to a file: $Directory"
    }
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) {
        New-Item -ItemType Directory -Force -Path $Directory | Out-Null
    }
    return (Resolve-Path -LiteralPath $Directory).Path
}

function Assert-BackupFileReadable {
    param([Parameter(Mandatory = $true)][string]$BackupFile)

    if (-not (Test-Path -LiteralPath $BackupFile -PathType Leaf)) {
        throw "Backup file does not exist: $BackupFile"
    }
    $item = Get-Item -LiteralPath $BackupFile
    if ($item.Length -le 0) {
        throw "Backup file is empty: $BackupFile"
    }
    return $item
}

function Get-FileSha256Lower {
    param([Parameter(Mandatory = $true)][string]$Path)

    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function New-PostgresBackupFileName {
    param(
        [Parameter(Mandatory = $true)][string]$DatabaseName,
        [datetime]$TimestampUtc = (Get-Date).ToUniversalTime()
    )

    $safeDatabaseName = $DatabaseName -replace '[^A-Za-z0-9_-]', '_'
    return "$safeDatabaseName`_$($TimestampUtc.ToString('yyyyMMddTHHmmssZ')).pgdump"
}

function Test-PostgresBackupGeneratedName {
    param([Parameter(Mandatory = $true)][string]$FileName)

    return [regex]::IsMatch($FileName, $PostgresBackupNamePattern)
}

function Invoke-PostgresBackupRetention {
    param(
        [Parameter(Mandatory = $true)][string]$OutputDirectory,
        [Parameter(Mandatory = $true)][int]$RetentionDays,
        [switch]$DryRun
    )

    if ($RetentionDays -lt 0) {
        return @()
    }
    $resolvedDirectory = Assert-DirectoryIsUsable -Directory $OutputDirectory
    $cutoff = (Get-Date).ToUniversalTime().AddDays(-1 * $RetentionDays)
    $matched = Get-ChildItem -LiteralPath $resolvedDirectory -File | Where-Object {
        (Test-PostgresBackupGeneratedName -FileName $_.Name) -and $_.LastWriteTimeUtc -lt $cutoff
    }

    foreach ($item in $matched) {
        if ($DryRun) {
            Write-Host "retention dry-run would delete: $($item.FullName)"
        }
        else {
            Remove-Item -LiteralPath $item.FullName -Force
            $metadataPath = "$($item.FullName).metadata.json"
            if (Test-Path -LiteralPath $metadataPath -PathType Leaf) {
                Remove-Item -LiteralPath $metadataPath -Force
            }
            Write-Host "retention deleted: $($item.FullName)"
        }
    }
    return $matched
}

function Assert-SafeDatabaseIdentifier {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$Label = "database identifier"
    )

    if ($Name -notmatch '^[A-Za-z_][A-Za-z0-9_]{0,62}$') {
        throw "$Label must contain only letters, numbers, and underscores, and must not start with a number."
    }
    if ($Name -in @("postgres", "template0", "template1")) {
        throw "$Label uses a reserved database name: $Name"
    }
}

function Assert-ProductionRestoreAllowed {
    param(
        [string]$Environment,
        [bool]$AllowProductionRestore
    )

    if ($Environment.Trim().ToLowerInvariant() -in @("production", "prod") -and -not $AllowProductionRestore) {
        throw "Production restore requires -AllowProductionRestore."
    }
}
