[CmdletBinding()]
param(
    [switch]$ConfirmOverwrite,
    [switch]$KeepStack
)

$ErrorActionPreference = "Stop"

if (-not $ConfirmOverwrite) {
    throw "Pass -ConfirmOverwrite to generate and replace resources/docs/images/user_guide/*.png."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"
$finalScreenshotDir = Join-Path $repoRoot "resources\docs\images\user_guide"
$temporaryScreenshotDir = Join-Path $finalScreenshotDir ".generated-$([DateTime]::UtcNow.ToString('yyyyMMddHHmmss'))"
$composeProject = if ($env:E2E_COMPOSE_PROJECT) { $env:E2E_COMPOSE_PROJECT } else { "parkingappuserguide" }
if ($composeProject -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]*$') {
    throw "E2E_COMPOSE_PROJECT contains unsupported characters."
}

$runId = "guide$([DateTime]::UtcNow.ToString('yyyyMMddHHmmss'))"
$adminPassword = "Guide-Admin-$([Guid]::NewGuid().ToString('N'))-Aa1!"
$userPassword = "Guide-User-$([Guid]::NewGuid().ToString('N'))-Aa1!"
$databasePassword = [Guid]::NewGuid().ToString("N")
$jwtSecret = "$([Guid]::NewGuid().ToString('N'))$([Guid]::NewGuid().ToString('N'))"

$expectedScreenshots = @(
    "login-page.png",
    "employee-dashboard.png",
    "employee-open-availabilities.png",
    "employee-applications.png",
    "employee-reservations.png",
    "owner-publish-availability.png",
    "owner-availability-list.png",
    "admin-teams.png",
    "admin-users.png",
    "admin-parking-spots.png",
    "admin-applications.png",
    "admin-reservations.png",
    "admin-overrides.png",
    "admin-audit-logs.png",
    "admin-reports.png",
    "mobile-admin-overrides.png"
)

$environment = @{
    "ENVIRONMENT" = "test"
    "POSTGRES_DB" = "parking_app_userguide"
    "POSTGRES_USER" = "parking_app_userguide"
    "POSTGRES_PASSWORD" = $databasePassword
    "POSTGRES_PORT" = "15438"
    "BACKEND_PORT" = "18005"
    "FRONTEND_PORT" = "18085"
    "VITE_API_BASE_URL" = "http://localhost:18005"
    "CORS_ALLOWED_ORIGINS" = '["http://localhost:18085"]'
    "JWT_SECRET_KEY" = $jwtSecret
    "SAME_TEAM_PRIORITY_WINDOW_HOURS" = "0"
    "SEED_ADMIN_ENABLED" = "true"
    "SEED_ADMIN_EMAIL" = "qa.admin@example.com"
    "SEED_ADMIN_USERNAME" = "qa_admin"
    "SEED_ADMIN_FIRST_NAME" = "QA"
    "SEED_ADMIN_LAST_NAME" = "Admin"
    "SEED_ADMIN_PASSWORD" = $adminPassword
    "SEED_ADMIN_UPDATE_PASSWORD" = "true"
    "E2E_COMPOSE_PROJECT" = $composeProject
    "E2E_RUN_ID" = $runId
    "E2E_BASE_URL" = "http://localhost:18085"
    "E2E_API_BASE_URL" = "http://localhost:18005"
    "E2E_ADMIN_USERNAME" = "qa_admin"
    "E2E_ADMIN_PASSWORD" = $adminPassword
    "E2E_USER_PASSWORD" = $userPassword
    "USER_GUIDE_SCREENSHOTS" = "true"
    "USER_GUIDE_SCREENSHOT_DIR" = $temporaryScreenshotDir
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

New-Item -ItemType Directory -Force -Path $temporaryScreenshotDir | Out-Null

Push-Location $repoRoot
try {
    Write-Host "Preparing disposable user guide screenshot Docker project '$composeProject'."
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

    Wait-ForHttp -Uri "http://localhost:18005/health"
    Wait-ForHttp -Uri "http://localhost:18085/"

    Push-Location $frontendRoot
    try {
        npm.cmd run e2e:user-guide
        if ($LASTEXITCODE -ne 0) {
            throw "Playwright user guide screenshot generation failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }

    foreach ($fileName in $expectedScreenshots) {
        $candidate = Join-Path $temporaryScreenshotDir $fileName
        if (-not (Test-Path -LiteralPath $candidate)) {
            throw "Expected screenshot was not generated: $fileName"
        }
    }

    New-Item -ItemType Directory -Force -Path $finalScreenshotDir | Out-Null
    Get-ChildItem -LiteralPath $finalScreenshotDir -Filter "*.png" -File | Remove-Item -Force
    foreach ($fileName in $expectedScreenshots) {
        Move-Item -LiteralPath (Join-Path $temporaryScreenshotDir $fileName) -Destination (Join-Path $finalScreenshotDir $fileName)
    }
    Write-Host "Generated $($expectedScreenshots.Count) user guide screenshots in resources/docs/images/user_guide."
}
finally {
    if (-not $KeepStack) {
        docker-compose -p $composeProject down -v --remove-orphans
    }
    else {
        Write-Host "Disposable user guide stack retained because -KeepStack was specified."
    }

    if (Test-Path -LiteralPath $temporaryScreenshotDir) {
        Remove-Item -LiteralPath $temporaryScreenshotDir -Recurse -Force
    }

    foreach ($name in $environment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], "Process")
    }
    Pop-Location
}
