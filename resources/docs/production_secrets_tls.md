# Production Secrets And TLS

This document defines the current production-hardening baseline for secrets and HTTPS/TLS. It is groundwork for deployment; it is not a cloud-specific deployment manifest or an external secret-manager integration.

## Secret Inventory

Sensitive production values:

- `JWT_SECRET_KEY` or `JWT_SECRET_FILE`: signs bearer access tokens.
- PostgreSQL password through `DATABASE_PASSWORD`, `DATABASE_PASSWORD_FILE`, or `POSTGRES_PASSWORD_FILE`.
- `SEED_ADMIN_PASSWORD`: local-only seed credential. It must remain disabled in production.
- TLS private key mounted as `tls_private_key`.
- Future SMTP/OIDC/client-secret values are not implemented yet, but must follow the same secret-file or secret-manager pattern.

Non-secret values that still need production review:

- `CORS_ALLOWED_ORIGINS`
- `VITE_API_BASE_URL`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `ASSIGNMENT_SCHEDULER_*`
- public TLS certificate path

## Environment Classification

The backend normalizes `ENVIRONMENT` to lowercase.

- Local/development/test: `local`, `development`, `dev`, `test`, `testing`
- Production: `production`, `prod`
- Other values, such as `staging`, are neither local nor production. Local-only tools such as seed admin still refuse them.

Production settings fail fast when unsafe defaults remain configured.

## Secret Loading Rules

Direct environment variables remain supported for local development. File-based values are supported for Docker secrets:

```text
JWT_SECRET_FILE=/run/secrets/jwt_secret
DATABASE_PASSWORD_FILE=/run/secrets/postgres_password
POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
```

Precedence and conflict behavior:

- If no file variable is set, the direct value is used.
- If a file variable is set and the direct value is still a documented local default, the file value is used.
- If a file variable is set and a custom direct value is also set, startup fails unless both values are identical.
- `DATABASE_URL` cannot be combined with a database password file. Use component settings instead.
- Secret files trim one trailing newline.
- Missing, unreadable, or empty secret files fail startup.
- Error messages name the failing setting but do not print secret contents.

The database URL is built from components when `DATABASE_URL` is empty. Username, password, and database name are URL-encoded.

## Production Validation Rules

When `ENVIRONMENT=production` or `ENVIRONMENT=prod`, startup rejects:

- default/example JWT secret values,
- JWT secrets shorter than 32 characters,
- empty or example database passwords,
- database URLs containing an example password,
- `SEED_ADMIN_ENABLED=true`,
- `LOG_LEVEL=DEBUG`,
- localhost/loopback CORS origins,
- non-HTTPS CORS origins,
- wildcard or malformed CORS origins.

Local/test settings continue to allow development defaults.

## Docker Secret Layout

The production-oriented Compose file expects local secret files at:

```text
secrets/jwt_secret.txt
secrets/postgres_password.txt
secrets/tls_certificate.pem
secrets/tls_private_key.pem
```

The `secrets/` directory is gitignored except for `secrets/.gitkeep`. Do not commit real secret files, private keys, or generated certificates.

Create local test secrets manually for verification:

```powershell
New-Item -ItemType Directory -Force secrets
Set-Content -Path secrets\jwt_secret.txt -Value "<high-entropy local test JWT secret>"
Set-Content -Path secrets\postgres_password.txt -Value "<local test database password>"
```

Use your platform secret manager for real deployments.

## TLS Architecture

`docker-compose.production.yml` defines a production-oriented shape:

- `proxy`: nginx TLS terminator and static frontend server.
- `backend`: FastAPI exposed only on the internal Docker network.
- `db`: PostgreSQL exposed only on the internal Docker network.
- `assignment-scheduler`: optional profile service with no host ports.

Production Compose intentionally uses `PRODUCTION_CORS_ALLOWED_ORIGINS` and `PRODUCTION_VITE_API_BASE_URL` instead of the local `CORS_ALLOWED_ORIGINS` and `VITE_API_BASE_URL` names. This prevents local `.env` defaults such as `localhost` and `http://localhost:8000` from leaking into a production/TLS render.

The proxy:

- listens on HTTP and redirects to HTTPS,
- listens on HTTPS with mounted certificate/key secrets,
- serves Vue static assets,
- keeps Vue Router fallback through `try_files`,
- proxies `/api/` to FastAPI,
- forwards `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`, and `X-Request-ID`,
- uses TLS 1.2 and TLS 1.3 only,
- has `server_tokens off`,
- leaves HSTS commented by default.

Enable HSTS only after HTTPS is verified for the real production domain. The committed config places the HSTS line only in the HTTPS server block so it is not emitted on HTTP redirects.

The production backend command enables Uvicorn proxy-header handling. This is safe only because the backend has no host-published port in `docker-compose.production.yml`; do not trust forwarded headers when backend is directly exposed to arbitrary clients.

## Local Self-Signed TLS Verification

Generate a disposable localhost certificate:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_local_tls_certificate.ps1
```

The helper requires `openssl` on PATH. If OpenSSL is unavailable, generate equivalent localhost SAN files manually at the same paths.

The script writes:

- `secrets/tls_certificate.pem`
- `secrets/tls_private_key.pem`

The certificate includes `localhost` and `127.0.0.1` SANs. Browsers will still show trust warnings unless you explicitly trust the certificate locally. These certificates are for local verification only.

Start the production-oriented stack with disposable local secrets:

```powershell
docker-compose -f docker-compose.production.yml config
docker-compose -f docker-compose.production.yml build backend proxy
docker-compose -f docker-compose.production.yml up -d db backend proxy
docker-compose -f docker-compose.production.yml exec -T backend alembic -c alembic.ini upgrade head
```

Smoke checks with self-signed certificate verification disabled:

```powershell
curl.exe -k -I https://localhost:8443/
curl.exe -k -I https://localhost:8443/login
curl.exe -k https://localhost:8443/api/health
curl.exe -I http://localhost:8081/
```

Stop and remove the temporary production-oriented stack:

```powershell
docker-compose -f docker-compose.production.yml down -v
```

Use a temporary Compose project name during local verification if you want to avoid touching the normal development PostgreSQL volume.

## Frontend Token Storage

The frontend currently stores JWT access tokens in browser storage through the existing auth storage module. This is simple for the MVP, but bearer tokens in browser storage are exposed if an XSS defect exists.

Future hardening direction:

- consider a backend-for-frontend session or short-lived access token with secure `HttpOnly`, `Secure`, `SameSite` cookies,
- add CSRF protection if authentication moves to cookies,
- define token revocation and refresh-token rotation before long-lived sessions.

This task does not redesign authentication.

## Rotation Guidance

JWT secret rotation:

- Replace the secret value in the secret manager or `secrets/jwt_secret.txt`.
- Restart backend and scheduler services.
- Existing JWTs become invalid immediately because multi-key JWT verification is not implemented.
- Verify login and `/auth/me` after restart.

Database password rotation:

- Create or rotate the database user's password in PostgreSQL.
- Update the platform secret or `secrets/postgres_password.txt`.
- Restart backend and scheduler services after the database accepts the new password.
- Verify migrations/current revision and backend health.

TLS certificate/key replacement:

- Replace certificate and private key secret values together.
- Restart or reload the proxy.
- Verify HTTPS, certificate chain, HTTP redirect, frontend routes, `/api/health`, and security headers.
- Enable or keep HSTS only after the real domain is verified.

Troubleshooting:

- Check whether the expected secret file exists and is readable.
- Do not print secret file contents.
- Use backend validation errors to identify the setting name.
- Use `docker-compose config` cautiously because rendered configs can include local environment values.
