[CmdletBinding()]
param(
    [string]$BackendUrl = "http://localhost:8000",
    [string]$FrontendUrl = "http://localhost:8080",
    [string]$AllowedOrigin = "http://localhost:8080"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$LoginIdentifier = $null
$LoginPassword = $null
$IncompleteCredentialPair = $false
$credentialPairs = @(
    @{ Username = $env:SMOKE_TEST_USERNAME; Password = $env:SMOKE_TEST_PASSWORD },
    @{ Username = $env:SMOKE_LOGIN_IDENTIFIER; Password = $env:SMOKE_LOGIN_PASSWORD },
    @{ Username = $env:SEED_ADMIN_USERNAME; Password = $env:SEED_ADMIN_PASSWORD }
)
foreach ($credentialPair in $credentialPairs) {
    $hasUsername = -not [string]::IsNullOrWhiteSpace($credentialPair.Username)
    $hasPassword = -not [string]::IsNullOrWhiteSpace($credentialPair.Password)
    if ($hasUsername -and $hasPassword) {
        $LoginIdentifier = $credentialPair.Username
        $LoginPassword = $credentialPair.Password
        break
    }
    if ($hasUsername -xor $hasPassword) {
        $IncompleteCredentialPair = $true
    }
}

function Invoke-SmokeRequest {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [string]$Method = "GET",
        [hashtable]$Headers = @{},
        [string]$Body,
        [string]$ContentType
    )

    try {
        $requestParameters = @{
            Uri = $Uri
            Method = $Method
            Headers = $Headers
            UseBasicParsing = $true
        }
        if ($PSBoundParameters.ContainsKey("Body")) {
            $requestParameters.Body = $Body
        }
        if ($PSBoundParameters.ContainsKey("ContentType")) {
            $requestParameters.ContentType = $ContentType
        }
        return Invoke-WebRequest @requestParameters
    }
    catch {
        if ($null -eq $_.Exception.Response) {
            throw
        }
        return [pscustomobject]@{
            StatusCode = [int]$_.Exception.Response.StatusCode
            Headers = $_.Exception.Response.Headers
            Content = ""
        }
    }
}

function Assert-Status {
    param(
        [Parameter(Mandatory = $true)]$Response,
        [Parameter(Mandatory = $true)][int[]]$Expected,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $statusCode = [int]$Response.StatusCode
    if ($statusCode -notin $Expected) {
        throw "$Label returned HTTP $statusCode; expected $($Expected -join ', ')."
    }
    Write-Host "PASS $Label HTTP $statusCode"
}

$healthResponse = Invoke-SmokeRequest -Uri "$BackendUrl/health"
Assert-Status -Response $healthResponse -Expected 200 -Label "backend health"

foreach ($path in @("/", "/login", "/dashboard")) {
    $frontendResponse = Invoke-SmokeRequest -Uri "$FrontendUrl$path"
    Assert-Status -Response $frontendResponse -Expected 200 -Label "frontend $path"
}

$unauthenticatedMe = Invoke-SmokeRequest -Uri "$BackendUrl/auth/me"
Assert-Status -Response $unauthenticatedMe -Expected 401 -Label "unauthenticated auth/me"

$unauthenticatedAdmin = Invoke-SmokeRequest -Uri "$BackendUrl/admin/teams"
Assert-Status -Response $unauthenticatedAdmin -Expected 401 -Label "unauthenticated admin endpoint"

$preflightHeaders = @{
    Origin = $AllowedOrigin
    "Access-Control-Request-Method" = "GET"
    "Access-Control-Request-Headers" = "Authorization"
}
$preflightResponse = Invoke-SmokeRequest -Uri "$BackendUrl/auth/me" -Method "OPTIONS" -Headers $preflightHeaders
Assert-Status -Response $preflightResponse -Expected 200 -Label "CORS preflight"
if ($preflightResponse.Headers["Access-Control-Allow-Origin"] -ne $AllowedOrigin) {
    throw "CORS preflight did not allow the configured origin."
}

if ([string]::IsNullOrWhiteSpace($LoginIdentifier) -and $IncompleteCredentialPair) {
    throw "Provide both smoke-test username and password variables, or neither."
}

if (-not [string]::IsNullOrWhiteSpace($LoginIdentifier)) {
    $loginBody = @{
        identifier = $LoginIdentifier
        password = $LoginPassword
    } | ConvertTo-Json
    $loginResponse = Invoke-SmokeRequest `
        -Uri "$BackendUrl/auth/login" `
        -Method "POST" `
        -Body $loginBody `
        -ContentType "application/json"
    Assert-Status -Response $loginResponse -Expected 200 -Label "prepared-user login"
    $token = ($loginResponse.Content | ConvertFrom-Json).access_token
    if ([string]::IsNullOrWhiteSpace($token)) {
        throw "Login response did not contain an access token."
    }

    $authenticatedHeaders = @{ Authorization = "Bearer $token" }
    $authenticatedMe = Invoke-SmokeRequest -Uri "$BackendUrl/auth/me" -Headers $authenticatedHeaders
    Assert-Status -Response $authenticatedMe -Expected 200 -Label "authenticated auth/me"

    $authenticatedAdmin = Invoke-SmokeRequest -Uri "$BackendUrl/admin/teams" -Headers $authenticatedHeaders
    Assert-Status -Response $authenticatedAdmin -Expected @(200, 403) -Label "authenticated admin endpoint"
}
else {
    Write-Host "SKIP authenticated checks; no prepared-user credentials were supplied."
}

$currentRevision = & docker-compose exec -T backend alembic -c alembic.ini current
if ($LASTEXITCODE -ne 0 -or ($currentRevision -join "`n") -notmatch "\(head\)") {
    throw "Alembic current revision is not at head."
}
$headRevision = & docker-compose exec -T backend alembic -c alembic.ini heads
if ($LASTEXITCODE -ne 0 -or ($headRevision -join "`n") -notmatch "\(head\)") {
    throw "Alembic head check failed."
}
Write-Host "PASS Alembic current revision is at head"
Write-Host "Smoke test completed successfully."
