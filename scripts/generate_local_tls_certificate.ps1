param(
    [string]$OutputDirectory = "secrets",
    [int]$Days = 7
)

$ErrorActionPreference = "Stop"

$openssl = Get-Command openssl -ErrorAction SilentlyContinue
if (-not $openssl) {
    throw "OpenSSL was not found on PATH. Install OpenSSL or generate secrets/tls_certificate.pem and secrets/tls_private_key.pem manually."
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$certificatePath = Join-Path $OutputDirectory "tls_certificate.pem"
$privateKeyPath = Join-Path $OutputDirectory "tls_private_key.pem"

& $openssl.Source req `
    -x509 `
    -nodes `
    -newkey rsa:2048 `
    -sha256 `
    -days $Days `
    -keyout $privateKeyPath `
    -out $certificatePath `
    -subj "/CN=localhost" `
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

Write-Host "Generated local self-signed certificate: $certificatePath"
Write-Host "Generated local private key: $privateKeyPath"
Write-Host "These files are for local TLS verification only and are ignored by Git."
