[CmdletBinding()]
param(
    [switch]$KeepStack
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"
$composeProject = if ($env:E2E_COMPOSE_PROJECT) { $env:E2E_COMPOSE_PROJECT } else { "parkingappe2e" }
if ($composeProject -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]*$') {
    throw "E2E_COMPOSE_PROJECT contains unsupported characters."
}
$runId = [DateTime]::UtcNow.ToString("yyyyMMddHHmmss")
$adminPassword = "E2E-Admin-$([Guid]::NewGuid().ToString('N'))-Aa1!"
$userPassword = "E2E-User-$([Guid]::NewGuid().ToString('N'))-Aa1!"
$databasePassword = [Guid]::NewGuid().ToString("N")
$jwtSecret = "$([Guid]::NewGuid().ToString('N'))$([Guid]::NewGuid().ToString('N'))"

$environment = @{
    "ENVIRONMENT" = "test"
    "POSTGRES_DB" = "parking_app_e2e"
    "POSTGRES_USER" = "parking_app_e2e"
    "POSTGRES_PASSWORD" = $databasePassword
    "POSTGRES_PORT" = "55435"
    "BACKEND_PORT" = "18003"
    "FRONTEND_PORT" = "18083"
    "VITE_API_BASE_URL" = "http://localhost:18003"
    "CORS_ALLOWED_ORIGINS" = '["http://localhost:18083"]'
    "JWT_SECRET_KEY" = $jwtSecret
    "SAME_TEAM_PRIORITY_WINDOW_HOURS" = "0"
    "SEED_ADMIN_ENABLED" = "true"
    "SEED_ADMIN_EMAIL" = "e2e.admin.$runId@example.com"
    "SEED_ADMIN_USERNAME" = "e2e_admin_$runId"
    "SEED_ADMIN_FIRST_NAME" = "E2E"
    "SEED_ADMIN_LAST_NAME" = "Admin"
    "SEED_ADMIN_PASSWORD" = $adminPassword
    "SEED_ADMIN_UPDATE_PASSWORD" = "true"
    "E2E_COMPOSE_PROJECT" = $composeProject
    "E2E_RUN_ID" = $runId
    "E2E_BASE_URL" = "http://localhost:18083"
    "E2E_API_BASE_URL" = "http://localhost:18003"
    "E2E_ADMIN_USERNAME" = "e2e_admin_$runId"
    "E2E_ADMIN_PASSWORD" = $adminPassword
    "E2E_USER_PASSWORD" = $userPassword
}

$previousEnvironment = @{}
foreach ($name in $environment.Keys) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
    [Environment]::SetEnvironmentVariable($name, $environment[$name], "Process")
}

function Wait-ForHttp([string]$Uri, [int]$Attempts = 40) {
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -eq 200) {
                return
            }
        }
        catch {
            if ($attempt -eq $Attempts) {
                throw "Timed out waiting for $Uri"
            }
        }
        Start-Sleep -Seconds 2
    }
}

function Invoke-CheckedCommand([string]$FilePath, [string[]]$Arguments) {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed with exit code $LASTEXITCODE."
    }
}

Push-Location $repoRoot
try {
    Write-Host "Preparing disposable E2E Docker project '$composeProject'."
    docker-compose -p $composeProject down -v --remove-orphans | Out-Null
    Invoke-CheckedCommand "docker-compose" @("-p", $composeProject, "config", "--quiet")
    Invoke-CheckedCommand "docker-compose" @("-p", $composeProject, "build", "backend", "frontend")
    Invoke-CheckedCommand "docker-compose" @("-p", $composeProject, "up", "-d", "db", "backend", "frontend")
    Invoke-CheckedCommand "docker-compose" @(
        "-p", $composeProject, "exec", "-T", "backend", "alembic", "-c", "alembic.ini", "upgrade", "head"
    )
    Invoke-CheckedCommand "docker-compose" @(
        "-p", $composeProject, "exec", "-T", "backend", "alembic", "-c", "alembic.ini", "current"
    )
    Invoke-CheckedCommand "docker-compose" @(
        "-p", $composeProject, "exec", "-T", "backend", "python", "-m", "app.commands.seed_admin"
    )

    Wait-ForHttp -Uri "http://localhost:18003/health"
    Wait-ForHttp -Uri "http://localhost:18083/"

    Push-Location $frontendRoot
    try {
        npm.cmd run e2e:smoke
        if ($LASTEXITCODE -ne 0) {
            throw "Playwright E2E smoke failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    if (-not $KeepStack) {
        docker-compose -p $composeProject down -v --remove-orphans
    }
    else {
        Write-Host "Disposable E2E stack retained because -KeepStack was specified."
    }

    foreach ($name in $environment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], "Process")
    }
    Pop-Location
}
