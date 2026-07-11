# PostgreSQL Backup and Restore Runbook

This runbook documents logical PostgreSQL backup and restore operations for the Parking Management App. It is written for Docker Compose based local/staging operations and can be adapted to production platforms. Volume persistence is not a backup.

## Scope

- Backup type: logical `pg_dump` custom-format archives (`-Fc`) created from the PostgreSQL container.
- Restore type: `pg_restore` into a fresh database by default, with an explicit destructive mode for replacing an existing database.
- Metadata: every created backup receives a sidecar `.metadata.json` file with non-secret operational metadata and a SHA-256 checksum.
- Automation: scripts are safe to run manually or from a scheduler, but production scheduling, encryption storage, and offsite replication must be provided by the deployment platform.

## Files

- `scripts/backup_postgres.ps1`: creates a custom-format backup and metadata sidecar.
- `scripts/verify_postgres_backup.ps1`: validates file readability, checksum metadata, optional expected checksum, and `pg_restore --list`.
- `scripts/restore_postgres.ps1`: restores a verified backup into a fresh database or, with explicit confirmation, replaces an existing database.
- `scripts/postgres_backup_common.ps1`: shared PowerShell helpers.
- `backups/.gitkeep`: keeps the local backup directory present while actual backup files remain ignored.

Generated files under `backups/` are ignored by Git and by the root Docker build context.

## Prerequisites

- Docker Desktop is running.
- Either `docker-compose` or `docker compose` is available.
- The `db` service is running and healthy.
- The database user has permission to run `pg_dump`, create restore databases, and run `pg_restore`.
- Alembic migrations have been applied before taking release-candidate backups.

The scripts default to:

- Compose file: `docker-compose.yml`
- Compose project: current directory default, unless `-ProjectName` is provided
- Database service: `db`
- Database name: `$env:POSTGRES_DB`, otherwise `parking_app`
- Database user: `$env:POSTGRES_USER`, otherwise `parking_app`
- Backup output directory: `backups/postgres`

## Local Backup

Start the stack and apply migrations:

```powershell
docker-compose config
docker-compose up -d db backend frontend
docker-compose exec -T backend alembic -c alembic.ini upgrade head
```

Create a backup:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_postgres.ps1
```

Create a backup for a named Compose project:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_postgres.ps1 `
  -ProjectName parkingapp `
  -OutputDirectory .\backups\postgres
```

The backup file name is generated as:

```text
<database>_yyyyMMddTHHmmssZ.pgdump
```

The sidecar metadata file is generated as:

```text
<database>_yyyyMMddTHHmmssZ.pgdump.metadata.json
```

Metadata intentionally excludes database passwords, JWT secrets, seed credentials, connection URLs, and private keys. It includes the database name, PostgreSQL server version, Alembic revision, Compose project name, archive format, compression level, size, and SHA-256 checksum.

## Backup Verification

Verify a backup and its metadata:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_postgres_backup.ps1 `
  -BackupFile .\backups\postgres\parking_app_20260620T123456Z.pgdump
```

Verify against a known checksum:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_postgres_backup.ps1 `
  -BackupFile .\backups\postgres\parking_app_20260620T123456Z.pgdump `
  -ExpectedSha256 "<sha256>"
```

Verification fails when the file is missing, empty, checksum metadata does not match, the expected checksum does not match, or `pg_restore --list` cannot read the archive.

## Fresh Restore Drill

Restore into a new database. This is the safest default because it does not overwrite the source database:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\restore_postgres.ps1 `
  -BackupFile .\backups\postgres\parking_app_20260620T123456Z.pgdump `
  -TargetDatabase parking_app_restore_verify
```

Check the restored Alembic revision:

```powershell
docker-compose exec -T db psql -U parking_app -d parking_app_restore_verify -At -c "SELECT version_num FROM alembic_version LIMIT 1;"
```

Check representative table counts:

```powershell
docker-compose exec -T db psql -U parking_app -d parking_app_restore_verify -At -c "SELECT count(*) FROM users; SELECT count(*) FROM teams;"
```

After a restore drill, drop only the disposable restore database:

```powershell
docker-compose exec -T db dropdb -U parking_app parking_app_restore_verify
```

## Destructive Restore

Replacing an existing database is intentionally guarded. It requires `-Mode ExistingDatabase` and `-ConfirmDestructive`.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\restore_postgres.ps1 `
  -BackupFile .\backups\postgres\parking_app_20260620T123456Z.pgdump `
  -Mode ExistingDatabase `
  -TargetDatabase parking_app_restore_verify `
  -ConfirmDestructive
```

Production-like environments also require `-AllowProductionRestore`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\restore_postgres.ps1 `
  -BackupFile .\backups\postgres\parking_app_20260620T123456Z.pgdump `
  -Environment production `
  -Mode ExistingDatabase `
  -TargetDatabase parking_app_restore_verify `
  -ConfirmDestructive `
  -AllowProductionRestore
```

Do not run a destructive restore against production until the backup checksum, target database name, maintenance window, and rollback plan have been reviewed.

## Retention

Delete generated backup files older than the configured retention period:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_postgres.ps1 `
  -RetentionOnly `
  -RetentionDays 14 `
  -OutputDirectory .\backups\postgres
```

Preview retention deletion without removing files:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_postgres.ps1 `
  -RetentionOnly `
  -RetentionDays 14 `
  -DryRunRetention `
  -OutputDirectory .\backups\postgres
```

Retention deletes only generated backup names matching `<database>_yyyyMMddTHHmmssZ.pgdump` and their sidecar metadata. It does not delete manually named files.

## Production Guidance

For production, keep the scripts as operational groundwork and add platform controls:

- Store backups outside the application host and outside the Docker volume.
- Encrypt backups at rest and in transit.
- Restrict backup storage access to least privilege.
- Schedule backups through the platform scheduler or backup service.
- Monitor backup completion, checksum generation, upload completion, and restore drills.
- Test restore on a separate database or staging environment on a fixed cadence.
- Record the expected recovery point objective and recovery time objective for the deployment.
- Keep PostgreSQL major versions compatible between backup and restore. Prefer restoring with the same or newer PostgreSQL major version supported by PostgreSQL tooling.
- Run Alembic `current` after restore and compare it with the application version to be deployed.

Example production Compose-oriented command shape:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_postgres.ps1 `
  -ComposeFiles docker-compose.production.yml `
  -ProjectName parkingapp-prod `
  -OutputDirectory D:\parking-backups\postgres `
  -RetentionDays 14
```

Production database credentials must come from the deployment secret mechanism. Do not put production passwords in `.env.example`, script arguments, command history, logs, or source control.

## Troubleshooting

- `Neither docker-compose nor docker compose is available.`: install Docker Compose or use a shell where Docker is on PATH.
- `Backup file does not exist` or `Backup file is empty`: confirm the path and rerun the backup command.
- `Backup checksum does not match metadata`: treat the backup as corrupted or moved incorrectly. Recreate or retrieve a known-good copy.
- `pg_restore --list` fails: the file is not a readable PostgreSQL custom-format archive for this PostgreSQL tooling version.
- Restore target identifier is rejected: use letters, numbers, and underscores only, and do not start with a number.
- `Production restore requires -AllowProductionRestore`: pass `-AllowProductionRestore` only after completing the production restore review.
