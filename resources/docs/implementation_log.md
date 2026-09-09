# Implementation Log

## Task 1: Backend Foundation and Health Check

### Files Changed

- `.gitignore`
- `backend/.env.example`
- `backend/pyproject.toml`
- `backend/requirements.txt`
- `backend/requirements-dev.txt`
- `backend/app/__init__.py`
- `backend/app/core/__init__.py`
- `backend/app/core/config.py`
- `backend/app/db/__init__.py`
- `backend/app/db/base.py`
- `backend/app/db/session.py`
- `backend/app/models/__init__.py`
- `backend/app/repositories/__init__.py`
- `backend/app/routers/__init__.py`
- `backend/app/routers/health.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/health.py`
- `backend/app/services/__init__.py`
- `backend/app/main.py`
- `backend/tests/test_health.py`

### What Was Implemented

- Added the initial FastAPI backend package structure from the project plan.
- Added app factory setup in `backend/app/main.py`.
- Added CORS middleware configuration using application settings.
- Added Pydantic settings in `backend/app/core/config.py`.
- Added SQLAlchemy base metadata and session scaffolding.
- Added a health router with `GET /health`.
- Added dependency manifests for runtime and development/test dependencies.
- Added a focused API test for the health endpoint.
- Added `.gitignore` entries for Python caches, local dependency folders, and local env files.

### Review Notes

- Architecture matches the planned separation of routers, schemas, core config, database config, services, repositories, and models.
- Naming is consistent with the plan and uses clear module boundaries.
- The health response uses a Pydantic schema with `extra="forbid"` to keep response shape strict.
- The health endpoint does not expose secrets or database connection details.
- JWT settings are present for future auth work, but authentication is not implemented in this task.
- Database session setup is scaffolded only; no database connection is opened by the health endpoint.
- The default JWT secret is suitable only for local development and is marked as changeable through environment configuration.
- No frontend or Docker files were changed in this task.

### Tests Added

- `backend/tests/test_health.py`
  - Verifies `GET /health` returns HTTP 200.
  - Verifies the expected health response payload.

### Test Results

- Dependencies were installed into the ignored local folder `backend/.test-deps` because the bundled Python runtime did not include FastAPI, SQLAlchemy, Alembic, pytest, or related backend packages.
- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `1 passed, 1 warning`
- Backend build/parsing verification:
  - Command: `python -m compileall -q backend/app`
  - Result: passed
- Warning observed:
  - `StarletteDeprecationWarning` from the currently resolved FastAPI/TestClient dependency stack.
  - This does not fail the test suite and does not affect the implemented endpoint behavior.
- Frontend verification:
  - Not applicable; no frontend code exists yet and no frontend files were changed.
- Docker verification:
  - Not applicable; Docker files have not been added yet.

### Next Suggested Task

Configure Alembic and create the initial database migration scaffold so future SQLAlchemy models can be migrated through a consistent PostgreSQL migration workflow.

## Task 2: Alembic Configuration and Initial Migration Scaffold

### Files Changed

- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/script.py.mako`
- `backend/alembic/versions/0001_initial_migration_scaffold.py`
- `backend/tests/test_alembic_config.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added a conventional Alembic setup inside the backend project.
- Configured `backend/alembic.ini` with `script_location = %(here)s/alembic` so commands work from the repository root with `-c backend/alembic.ini` and from the backend directory with `-c alembic.ini`.
- Configured `prepend_sys_path = %(here)s` so Alembic can import the backend `app` package.
- Configured `backend/alembic/env.py` to use `app.core.config.get_settings().database_url`.
- Configured Alembic target metadata to use `app.db.base.Base.metadata`.
- Imported `app.models` in `env.py` so future model modules can register SQLAlchemy metadata for autogeneration.
- Added an empty initial migration revision `0001` because no business domain models exist yet.
- Added tests that verify Alembic configuration, revision metadata, and offline SQL generation.

### Developer Migration Commands

From the repository root:

```powershell
python -m alembic -c backend/alembic.ini revision --autogenerate -m "describe change"
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini downgrade -1
python -m alembic -c backend/alembic.ini current
python -m alembic -c backend/alembic.ini heads
python -m alembic -c backend/alembic.ini history
```

From the `backend` directory:

```powershell
python -m alembic -c alembic.ini revision --autogenerate -m "describe change"
python -m alembic -c alembic.ini upgrade head
python -m alembic -c alembic.ini downgrade -1
python -m alembic -c alembic.ini current
python -m alembic -c alembic.ini heads
python -m alembic -c alembic.ini history
```

In this Codex environment, the bundled Python runtime is invoked by absolute path and dependencies are loaded from the ignored local folder `backend/.test-deps`.

### Review Notes

- Alembic reads the database URL from the existing backend settings rather than duplicating runtime configuration in migration code.
- `sqlalchemy.url` remains present in `alembic.ini` only as a structurally valid placeholder; `env.py` overrides it from settings at runtime.
- The migration setup is synchronous, matching the current SQLAlchemy session configuration. No async SQLAlchemy setup exists yet, so async Alembic configuration is not needed.
- The URL scheme remains PostgreSQL-compatible through the existing `postgresql+psycopg` default.
- The initial revision intentionally does not create domain tables because no domain models have been implemented.
- Offline migration generation uses PostgreSQL dialect behavior, confirmed by Alembic reporting `PostgresqlImpl`.
- No secrets were added to source files beyond local-development placeholders already present in `.env.example` and `alembic.ini`.

### Tests Added

- `backend/tests/test_alembic_config.py`
  - Verifies the Alembic script directory resolves to `backend/alembic`.
  - Verifies revision `0001` is the current head and has callable upgrade/downgrade functions.
  - Verifies offline `upgrade head --sql` loads the Alembic environment without a database connection.

### Test Results

- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `4 passed, 1 warning`
- Alembic heads from repository root:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0001 (head)`
- Alembic history from repository root:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result: `<base> -> 0001 (head), Initial migration scaffold.`
- Alembic heads from backend directory:
  - Command: `python -m alembic -c alembic.ini heads`
  - Result: `0001 (head)`
- Alembic offline upgrade SQL:
  - Command: `python -m alembic -c backend/alembic.ini upgrade head --sql`
  - Result: passed; generated PostgreSQL-style SQL for creating `alembic_version` and inserting revision `0001`.
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed

### Known Limitations

- Online migration commands such as `upgrade head`, `downgrade -1`, and `current` were not executed against a live PostgreSQL database because no PostgreSQL service is running yet in this workspace.
- Manual verification still needed after Docker/PostgreSQL setup:
  - Start PostgreSQL.
  - Run `python -m alembic -c backend/alembic.ini upgrade head`.
  - Run `python -m alembic -c backend/alembic.ini current`.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Add local infrastructure for the backend and database: create the backend Dockerfile, add PostgreSQL and backend services to `docker-compose.yml`, and document how to run the API and apply migrations against PostgreSQL.

## Task 3: Local Backend and PostgreSQL Docker Infrastructure

### Files Changed

- `.env.example`
- `docker-compose.yml`
- `backend/.dockerignore`
- `backend/.env.example`
- `backend/Dockerfile`
- `backend/app/core/config.py`
- `backend/tests/test_infrastructure_files.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added a backend Dockerfile using `python:3.12-slim`.
- Installed backend dependencies from `backend/requirements.txt`.
- Copied the backend application and Alembic files into the image.
- Exposed port `8000`.
- Added a Uvicorn default command for `app.main:app`.
- Added root `docker-compose.yml` with:
  - `db` service using `postgres:16-alpine`.
  - Persistent `postgres_data` volume.
  - PostgreSQL healthcheck using `pg_isready`.
  - `backend` service built from `backend/Dockerfile`.
  - Backend dependency on database health.
  - Backend port mapping from `${BACKEND_PORT:-8000}` to container port `8000`.
  - Database component environment variables and full `DATABASE_URL`.
- Added root `.env.example` for Docker Compose local defaults.
- Updated `backend/.env.example` for local backend execution outside Docker.
- Added database component settings fields while keeping `DATABASE_URL` as the value used by SQLAlchemy and Alembic.
- Added `backend/.dockerignore` to exclude local test dependencies, caches, virtual environments, and tests from the backend image context.
- Added static infrastructure tests for Dockerfile, Compose structure, and settings compatibility.

### Docker Compose Developer Commands

Build services:

```powershell
docker-compose build backend
```

Start PostgreSQL only:

```powershell
docker-compose up -d db
```

Start PostgreSQL and backend:

```powershell
docker-compose up -d backend
```

Run Alembic migrations from inside the backend container:

```powershell
docker-compose run --rm backend alembic -c alembic.ini upgrade head
```

Check current Alembic revision from inside the backend container:

```powershell
docker-compose run --rm backend alembic -c alembic.ini current
```

Check backend health endpoint:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

Inspect Compose configuration:

```powershell
docker-compose config
```

Stop services while preserving the PostgreSQL named volume:

```powershell
docker-compose down
```

Stop services and remove the PostgreSQL named volume:

```powershell
docker-compose down -v
```

Use `docker-compose` on this machine. The `docker compose` subcommand was not available in the current Docker CLI.

### Review Notes

- Service naming is consistent and simple: `db` for PostgreSQL and `backend` for the FastAPI service.
- Backend database connectivity uses the Docker network hostname `db`.
- Compose passes both database component variables and the full `DATABASE_URL`; the backend still uses `DATABASE_URL` for SQLAlchemy and Alembic.
- Settings now accept database component environment variables, which avoids rejecting or ignoring useful Compose configuration.
- PostgreSQL credentials are local-development defaults only and are kept in `.env.example`/Compose variable defaults, not real secrets.
- The PostgreSQL data volume is persistent and is not removed by the normal `docker-compose down` command.
- The backend Docker image does not include local `.test-deps`, virtual environments, pytest caches, or tests.
- No frontend service was added because the frontend project does not exist yet.
- No parking domain models or business tables were added.

### Tests Added or Updated

- Added `backend/tests/test_infrastructure_files.py`
  - Verifies the backend Dockerfile base image, dependency install step, exposed port, and Uvicorn command.
  - Verifies `docker-compose.yml` defines the expected `db` and `backend` services, PostgreSQL volume, healthcheck, backend dependency on database health, port mapping, and database URL host.
  - Verifies backend settings accept database component values and the full Docker-network database URL.

### Verification Results

- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `7 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic local load/head check:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0001 (head)`
- Docker availability:
  - Command: `docker --version`
  - Result: `Docker version 28.5.1, build e180ab8`
  - Command: `docker-compose --version`
  - Result: `Docker Compose version v2.40.0-desktop.1`
  - Command: `docker compose version`
  - Result: failed; this Docker CLI does not expose the `docker compose` subcommand.
- Docker Compose configuration:
  - Command: `docker-compose config`
  - Result: passed and rendered valid `db`, `backend`, `postgres_data`, and default network configuration.
  - Note: under the sandbox, Docker emitted a warning about reading `C:\Users\nikola.milosevic\.docker\config.json`; the Compose config still rendered successfully.
- Backend Docker image build:
  - Command: `docker-compose build backend`
  - Result: passed; image `parkingapp-backend:latest` built successfully.
- PostgreSQL startup:
  - Command: `docker-compose up -d db`
  - Result: passed; `parkingapp-db-1` started.
- PostgreSQL health:
  - Command: `docker-compose ps`
  - Result: `parkingapp-db-1` was `Up` and `healthy`.
- Migration execution against PostgreSQL:
  - Command: `docker-compose run --rm backend alembic -c alembic.ini upgrade head`
  - Result: passed; Alembic used `PostgresqlImpl` and ran revision `0001`.
- Migration current revision:
  - Command: `docker-compose run --rm backend alembic -c alembic.ini current`
  - Result: `0001 (head)`
- Backend startup:
  - Command: `docker-compose up -d backend`
  - Result: passed; backend container started after the database became healthy.
- Backend health endpoint:
  - Command: `Invoke-RestMethod -Uri "http://localhost:8000/health"`
  - Result: returned `status=ok`, `service=Parking Management API`, `environment=local`.
- Service shutdown:
  - Command: `docker-compose down`
  - Result: passed; backend and database containers and the Compose network were removed. The named PostgreSQL volume was preserved.
- ASCII check:
  - Result: passed for the newly added infrastructure and test files.

### Known Limitations

- Docker commands required elevated Docker Desktop access because the sandbox could not access the Docker engine pipe or Docker config files.
- The current infrastructure is backend and database only. Frontend Docker configuration will be added after the frontend project exists.
- The backend health endpoint does not check database connectivity yet; it only verifies that the API process is running.
- The PostgreSQL named volume remains after `docker-compose down` by design. Use `docker-compose down -v` only when local database data should be removed.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Start Phase 2 authentication groundwork: implement the initial `Team` and `User` SQLAlchemy models, Pydantic schemas, first real Alembic migration for those tables, and focused model/schema tests without adding full authentication endpoints yet.

## Task 4: Initial Team and User Models, Schemas, and Migration

### Files Changed

- `backend/requirements.txt`
- `backend/app/db/base.py`
- `backend/app/models/mixins.py`
- `backend/app/models/team.py`
- `backend/app/models/user.py`
- `backend/app/models/__init__.py`
- `backend/app/schemas/team.py`
- `backend/app/schemas/user.py`
- `backend/app/schemas/__init__.py`
- `backend/alembic/versions/0002_add_teams_and_users.py`
- `backend/tests/test_alembic_config.py`
- `backend/tests/test_models.py`
- `backend/tests/test_schemas.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added SQLAlchemy `Team` and `User` models.
- Added `UserRole` enum with `admin`, `employee`, and `parking_owner` values.
- Added shared timestamp mixin with timezone-aware `created_at` and `updated_at` columns.
- Added SQLAlchemy naming convention metadata for consistent constraint and index names.
- Added relationships:
  - `Team.users`
  - `User.team`
- Added Pydantic v2 schemas:
  - `TeamBase`
  - `TeamCreate`
  - `TeamUpdate`
  - `TeamRead`
  - `UserBase`
  - `UserCreate`
  - `UserUpdate`
  - `UserRead`
- Added `email-validator` dependency so Pydantic `EmailStr` works reliably.
- Added Alembic migration `0002_add_teams_and_users.py`.
- Updated Alembic tests to expect `0002` as the current head.
- Added focused model and schema tests.

### Review Notes

- The implementation is limited to Team and User groundwork only.
- No authentication endpoints, parking spot models, parking availability logic, frontend code, or reservation logic were added.
- `hashed_password` exists only on the SQLAlchemy `User` model and is not exposed by `UserRead`.
- `UserCreate` and `UserUpdate` accept `password`, not `hashed_password`, leaving password hashing to the future auth/service task.
- `EmailStr` is used for user email validation.
- Pydantic schemas use `ConfigDict` and are compatible with Pydantic v2.
- Read schemas use `from_attributes=True` for ORM serialization.
- Role values are represented by a clean Python enum and a PostgreSQL enum in the migration.
- `team_id` is nullable and uses `ON DELETE SET NULL`, so users can remain valid if a team is removed later.
- Email, username, and team name are implemented as unique indexes. This enforces uniqueness and provides indexes while matching SQLAlchemy model metadata and avoiding duplicate PostgreSQL indexes.
- Timestamps use timezone-aware SQLAlchemy column types and Python UTC defaults. Database-side `updated_at` auto-update triggers are not implemented yet; ORM updates will refresh `updated_at` through `onupdate`.
- The migration was reviewed after offline SQL generation exposed duplicate enum creation. The enum configuration was fixed and a regression assertion was added.

### Tests Added or Updated

- Updated `backend/tests/test_alembic_config.py`
  - Expects `0002` as the current Alembic head.
  - Verifies offline SQL includes one `CREATE TYPE user_role AS ENUM`, `teams`, `users`, and revision `0002`.
- Added `backend/tests/test_models.py`
  - Verifies metadata contains `teams` and `users`.
  - Verifies important columns, indexes, enum values, foreign key, and relationships.
  - Verifies lightweight SQLite table creation and basic persistence for one team/user relationship.
- Added `backend/tests/test_schemas.py`
  - Verifies Team schema validation and ORM serialization.
  - Verifies User schema validation, email validation, enum serialization, partial updates, and that `UserRead` does not expose `hashed_password` or `password`.

### Verification Results

- Local test dependency update:
  - Command: `python -m pip install "email-validator>=2.2,<3.0" --target backend/.test-deps --upgrade`
  - Result: passed; installed `email-validator`, `dnspython`, and `idna` into the ignored local dependency folder.
- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `17 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0002 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0001 -> 0002 (head), Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`
- Alembic offline SQL generation:
  - Command: `python -m alembic -c backend/alembic.ini upgrade head --sql`
  - Result: passed; generated PostgreSQL SQL with one `CREATE TYPE user_role AS ENUM`, `CREATE TABLE teams`, `CREATE TABLE users`, and unique indexes for team name, user email, and username.
- Docker Compose configuration:
  - Command: `docker-compose config`
  - Result: passed; Compose rendered valid backend/database configuration.
  - Note: Docker emitted the same sandbox warning about reading `C:\Users\nikola.milosevic\.docker\config.json`.
- Backend Docker image build:
  - Command: `docker-compose build backend`
  - Result: passed; rebuilt image with `email-validator` and the `0002` migration.
- PostgreSQL startup:
  - Command: `docker-compose up -d db`
  - Result: passed.
- PostgreSQL health:
  - Command: `docker-compose ps`
  - Result: `parkingapp-db-1` was `Up` and `healthy`.
- Migration execution against PostgreSQL:
  - Command: `docker-compose run --rm backend alembic -c alembic.ini upgrade head`
  - Result: passed; Alembic ran `0001 -> 0002`.
- Migration current revision:
  - Command: `docker-compose run --rm backend alembic -c alembic.ini current`
  - Result: `0002 (head)`
- Backend startup:
  - Command: `docker-compose up -d backend`
  - Result: passed.
- Backend health endpoint:
  - Command: `Invoke-RestMethod -Uri "http://localhost:8000/health"`
  - Result: returned `status=ok`, `service=Parking Management API`, `environment=local`.
- Service shutdown:
  - Command: `docker-compose down`
  - Result: passed; containers and network were removed. The PostgreSQL named volume was preserved.
- ASCII check:
  - Result: passed for the newly added and changed source files.

### Known Limitations

- Docker commands required elevated Docker Desktop access because the sandbox cannot access Docker engine and Docker Desktop config paths directly.
- The local PostgreSQL named volume is now migrated to `0002`; use `docker-compose down -v` only when a clean local database is needed.
- Authentication services, password hashing, JWT validation, repositories, and API endpoints are not implemented yet.
- `updated_at` has ORM-level update behavior, but no database trigger for direct SQL updates.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement authentication security primitives: password hashing, password verification, JWT access-token creation/validation helpers, auth schemas, and focused tests. Do not add login endpoints yet.

## Task 5: Authentication Security Primitives

### Files Changed

- `backend/requirements.txt`
- `backend/app/core/security.py`
- `backend/app/schemas/auth.py`
- `backend/app/schemas/user.py`
- `backend/app/schemas/__init__.py`
- `backend/tests/test_auth_schemas.py`
- `backend/tests/test_security.py`
- `backend/tests/test_schemas.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added reusable password hashing and verification helpers in `backend/app/core/security.py`.
- Added JWT access-token creation helper.
- Added JWT decode/validation helper.
- Added auth schemas:
  - `LoginRequest`
  - `Token`
  - `TokenPayload`
- Exported auth schemas from `backend/app/schemas/__init__.py`.
- Pinned `bcrypt>=4.0,<4.1` for compatibility with `passlib[bcrypt]`.
- Tightened password schema max length to 72 characters to align with bcrypt's limit.
- Configured passlib bcrypt with `bcrypt__truncate_error=True` to avoid silent password truncation.

### Error Handling Design

- Low-level token decoding returns `None` for expired, invalid, malformed, or schema-invalid tokens.
- `backend/app/core/security.py` intentionally does not raise `HTTPException`.
- Future FastAPI dependencies such as `get_current_user` can translate `None` into the appropriate HTTP 401 response at the API boundary.

### Review Notes

- Password hashing uses passlib with bcrypt, which is suitable for web application password storage.
- Plain-text passwords are never stored or returned by the security helpers.
- `hash_password` returns only the generated hash.
- `verify_password` compares a plain password to an existing stored hash and returns a boolean.
- JWT helpers read secret key, algorithm, and expiry settings from `Settings`; secrets are not hardcoded in utility code.
- JWT payload includes `sub`, `role`, `iat`, and `exp`.
- Token timestamps are generated with timezone-aware UTC datetimes.
- Expired and invalid tokens are handled cleanly by returning `None`.
- `TokenPayload` validates decoded role values against `UserRole`.
- `Token` response schema defaults `token_type` to `bearer`.
- `LoginRequest` is only a schema for future endpoint use; no login endpoint was added.
- No user repository, auth service, route authorization, frontend, or parking functionality was added.

### Tests Added or Updated

- Added `backend/tests/test_security.py`
  - Verifies password hashes differ from the plain password.
  - Verifies correct password verification succeeds.
  - Verifies wrong password verification fails.
  - Verifies access-token creation returns a JWT-shaped string.
  - Verifies decoded token payload contains expected subject and role.
  - Verifies expired tokens return `None`.
  - Verifies invalid tokens return `None`.
- Added `backend/tests/test_auth_schemas.py`
  - Verifies token schema serialization and default token type.
  - Verifies token payload role and timestamp validation.
  - Verifies login request validation.
  - Verifies passwords over the bcrypt schema limit are rejected.
- Updated `backend/tests/test_schemas.py`
  - Verifies `UserCreate` rejects passwords over the bcrypt schema limit.

### Verification Results

- Local test dependency update:
  - Command: `python -m pip install "bcrypt>=4.0,<4.1" --target backend/.test-deps --upgrade`
  - Result: passed; installed `bcrypt-4.0.1` into the ignored local dependency folder.
- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `31 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0002 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0001 -> 0002 (head), Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`
- ASCII check:
  - Result: passed for the newly added and changed source files.

### Known Limitations

- Docker/PostgreSQL verification was not run for this task because no database schema, migration, Dockerfile, or Compose changes were made.
- The backend Docker image will pick up the bcrypt pin on the next image rebuild.
- No login endpoint exists yet.
- No route protection or current-user dependency exists yet.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement initial `UserRepository`, `TeamRepository`, and focused repository tests so future auth and admin services have a clean database-access layer. Do not add API endpoints yet.

## Task 6: Initial Team and User Repositories

### Files Changed

- `backend/app/repositories/__init__.py`
- `backend/app/repositories/teams.py`
- `backend/app/repositories/users.py`
- `backend/tests/test_repositories.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `TeamRepository` with:
  - `create`
  - `get_by_id`
  - `get_by_name`
  - `list`
  - `update`
  - `delete`
- Added `UserRepository` with:
  - `create`
  - `get_by_id`
  - `get_by_email`
  - `get_by_username`
  - `list`
  - `list_by_team_id`
  - `update`
  - `delete`
- Exported repositories from `backend/app/repositories/__init__.py`.
- Added focused SQLite repository tests.

### Review Notes

- Repositories are database-focused only and contain no business rules.
- No API endpoints, service layer, auth endpoints, route protection, frontend code, or parking logic was added.
- Repository methods use the existing synchronous SQLAlchemy `Session` style.
- `create`, `update`, and `delete` call `flush` but do not commit. This keeps transaction control with future services.
- `create` and `update` refresh the model before returning it.
- `list` methods support `skip` and `limit` pagination.
- `get_by_id`, `get_by_email`, `get_by_username`, `get_by_name`, `list`, and `list_by_team_id` return model instances or `None` where appropriate.
- Relationship queries use `selectinload` for `User.team` and `Team.users` to avoid avoidable lazy-loading surprises.
- `get_by_id` uses explicit `select` queries with `populate_existing=True` so relationship loading is consistent even when the object is already present in the session.
- `update` methods accept explicit update mappings. Omitted fields are untouched; `None` is written only when the caller includes that field.
- Unknown update fields are ignored by the repository.
- Password hashing is intentionally not implemented in `UserRepository`; callers must provide `hashed_password`.
- Simple hard delete was chosen for this groundwork task. Soft delete can be introduced later at the service/API policy level if needed.

### Tests Added or Updated

- Added `backend/tests/test_repositories.py`
  - Verifies team create, get by ID, get by name, list pagination, update, explicit `None` update, delete, and unique name constraint.
  - Verifies user create with team, get by ID, get by email, get by username, list pagination, list by team ID, relationship loading, update, explicit `None` team update, delete, and unique email/username constraints.
  - Verifies missing lookups return `None`.
  - Uses isolated in-memory SQLite databases per test.

### Verification Results

- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `45 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0002 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0001 -> 0002 (head), Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`
- ASCII check:
  - Result: passed for the newly added and changed repository/test files.

### Known Limitations

- Docker/PostgreSQL verification was not run for this task because no database schema, migration, Dockerfile, or Compose changes were made.
- Repository tests use SQLite for speed and isolation. PostgreSQL-specific behavior remains covered by Alembic and migration verification from earlier schema tasks.
- Delete methods currently perform hard deletes.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement initial authentication service groundwork: authenticate a user by email and password using `UserRepository`, verify stored password hashes, issue JWT access tokens through the security helpers, and add focused service tests. Do not add API endpoints yet.

## Task 7: Initial Authentication Service Groundwork

### Files Changed

- `backend/app/services/__init__.py`
- `backend/app/services/auth.py`
- `backend/tests/test_auth_service.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `AuthService` in `backend/app/services/auth.py`.
- Exported `AuthService` from `backend/app/services/__init__.py`.
- Added `authenticate_user`.
- Added `create_access_token_for_user`.
- Added focused service tests using the existing repository layer, password hashing helper, and JWT helper.

### Failure Behavior

- `authenticate_user` returns `None` for all authentication failures.
- Failure cases intentionally do not distinguish between:
  - unknown username/email,
  - wrong password,
  - inactive user,
  - blank identifier.
- The service does not raise `HTTPException`; future routers can translate `None` into a 401 response at the API boundary.

### Review Notes

- The implementation is limited to the service layer only.
- No API endpoints, login routes, current-user dependencies, route protection, frontend code, or parking logic was added.
- `AuthService` depends on `UserRepository`, `verify_password`, and `create_access_token`.
- The service accepts either username or email as the login identifier.
- Email-like identifiers are checked by email first, then username. Non-email identifiers are checked by username first, then email.
- Blank identifiers fail before repository lookup.
- Inactive users cannot authenticate.
- Password verification uses the stored `hashed_password`, but the service never returns or exposes password data.
- `create_access_token_for_user` returns the existing `Token` schema with `token_type="bearer"`.
- Token creation includes the user ID as `sub` and the user role. Username/email are not included because the current token helper does not support additional non-sensitive profile claims yet.
- Service tests decode tokens and assert password fields are not present in the raw payload.

### Tests Added or Updated

- Added `backend/tests/test_auth_service.py`
  - Authenticates active user by username with correct password.
  - Authenticates active user by email with correct password.
  - Fails for wrong password.
  - Fails for unknown identifier.
  - Fails for blank identifier.
  - Fails for inactive user.
  - Creates access token as a `Token` schema.
  - Verifies decoded token contains expected subject and role.
  - Verifies raw token payload does not expose `hashed_password` or `password`.

### Verification Results

- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `54 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0002 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0001 -> 0002 (head), Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`
- ASCII check:
  - Result: passed for the newly added and changed service/test files.

### Known Limitations

- Docker/PostgreSQL verification was not run for this task because no database schema, migration, Dockerfile, or Compose changes were made.
- The service currently issues access tokens only; refresh tokens are not implemented.
- Token payloads currently include only `sub`, `role`, `iat`, and `exp`.
- No login endpoint exists yet.
- No current-user dependency or route protection exists yet.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement the initial auth API router with `POST /auth/login` using `AuthService`, dependency-injected database sessions, and focused API tests. Do not add current-user route protection or frontend yet.

## Task 8: Initial Auth Login API Route

### Files Changed

- `backend/app/main.py`
- `backend/app/routers/auth.py`
- `backend/app/schemas/auth.py`
- `backend/tests/test_auth_api.py`
- `backend/tests/test_auth_schemas.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added an auth router in `backend/app/routers/auth.py`.
- Registered the auth router in the FastAPI app.
- Added `POST /auth/login`.
- Added route-local dependency wiring for:
  - injected SQLAlchemy session through `get_db`,
  - `UserRepository`,
  - `AuthService`.
- Updated `LoginRequest` to use a neutral `identifier` field and accept `identifier`, `email`, or `username` input aliases.
- Added focused API tests for the login endpoint.

### Review Notes

- The implementation is limited to the initial login API endpoint.
- No registration endpoint, current-user endpoint, route protection, role authorization, frontend code, or parking logic was added.
- The route is intentionally thin and delegates credential validation/token creation to `AuthService`.
- Login supports username or email through `AuthService.authenticate_user`.
- Authentication failure always returns HTTP 401 with the generic message `Invalid credentials`.
- The route does not reveal whether the identifier, password, or active-user status caused the failure.
- No plain-text password or password hash is logged or returned.
- The route uses `response_model=Token`, so OpenAPI shows the token response shape clearly.
- `LoginRequest` no longer validates the identifier as strictly an email because username login is now supported. Email strings are still accepted as identifiers.
- Dependency wiring uses the existing database dependency and does not introduce global sessions or hardcoded connections.

### Tests Added or Updated

- Added `backend/tests/test_auth_api.py`
  - Successful login with username returns a bearer token.
  - Successful login with email returns a bearer token.
  - Wrong password returns HTTP 401.
  - Unknown identifier returns HTTP 401.
  - Inactive user returns HTTP 401.
  - Response body does not include `hashed_password` or `password`.
  - Raw JWT payload does not include `hashed_password` or `password`.
  - Decoded token contains expected user subject and role.
  - `/auth/login` is listed in OpenAPI.
- Updated `backend/tests/test_auth_schemas.py`
  - Verifies `LoginRequest` accepts `identifier`, `email`, and `username` aliases.
  - Verifies blank identifiers are rejected.
  - Keeps bcrypt password-length validation coverage.

### Verification Results

- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `63 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0002 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0001 -> 0002 (head), Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`
- ASCII check:
  - Result: passed for the newly added and changed router/schema/test files.

### Known Limitations

- Docker/PostgreSQL verification was not run for this task because no database schema, migration, Dockerfile, or Compose changes were made.
- API tests use in-memory SQLite with FastAPI dependency overrides for isolated login-route behavior.
- No current-user dependency exists yet.
- No protected routes or role authorization exist yet.
- No refresh-token support exists yet.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement the current-user authentication dependency and `GET /auth/me`, including bearer-token decoding, database user lookup, inactive-user rejection, and focused API tests. Do not add role authorization or parking logic yet.

## Task 9: Current-User Dependency and Auth Me Endpoint

### Files Changed

- `backend/app/dependencies/__init__.py`
- `backend/app/dependencies/auth.py`
- `backend/app/routers/auth.py`
- `backend/tests/test_current_user_api.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added reusable auth dependency package under `backend/app/dependencies`.
- Added `get_current_user`.
- Added `OAuth2PasswordBearer` bearer-token parsing with `tokenUrl="/auth/login"`.
- Added `GET /auth/me` under the existing auth router.
- Returned the current authenticated user through the existing `UserRead` response schema.
- Added focused API tests for valid and invalid bearer-token behavior.

### Dependency Behavior

- `get_current_user` reads the bearer token from the `Authorization` header.
- It decodes and validates the JWT through `decode_access_token`.
- It converts the token subject to an integer user ID.
- It loads the user through `UserRepository`.
- It returns the user only when the token is valid, the user exists, and the user is active.
- It raises HTTP 401 with `Could not validate credentials` for:
  - missing bearer token,
  - malformed token,
  - expired token,
  - invalid token payload,
  - non-integer subject,
  - missing user,
  - inactive user.

### Review Notes

- The implementation is limited to the current-user dependency and `GET /auth/me`.
- No role authorization, admin CRUD, registration, frontend code, or parking logic was added.
- The dependency is reusable for future protected routes.
- The dependency uses the existing database session dependency and does not create global sessions.
- The endpoint code is thin and only returns the dependency-injected current user.
- `UserRead` prevents `hashed_password` from being exposed.
- All auth failures use the same generic HTTP 401 message and do not expose token internals.
- OpenAPI shows `/auth/me` as requiring bearer authentication through `OAuth2PasswordBearer`.

### Tests Added or Updated

- Added `backend/tests/test_current_user_api.py`
  - Valid token returns the current user.
  - Response does not include `hashed_password` or `password`.
  - Missing token returns HTTP 401.
  - Malformed token returns HTTP 401.
  - Expired token returns HTTP 401.
  - Token for missing user returns HTTP 401.
  - Token for inactive user returns HTTP 401.
  - Token subject that is not a valid user ID returns HTTP 401.
  - `/auth/me` is listed in OpenAPI with bearer security.

### Verification Results

- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `72 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0002 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0001 -> 0002 (head), Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`
- ASCII check:
  - Result: passed for the newly added and changed dependency/router/test files.

### Known Limitations

- Docker/PostgreSQL verification was not run for this task because no database schema, migration, Dockerfile, or Compose changes were made.
- API tests use in-memory SQLite with FastAPI dependency overrides for isolated current-user behavior.
- Role-based authorization does not exist yet.
- Admin CRUD does not exist yet.
- Refresh-token support does not exist yet.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement role authorization groundwork: add reusable admin-role dependency helpers based on `get_current_user`, with focused tests for admin access, non-admin rejection, inactive-user rejection through the existing dependency, and OpenAPI behavior where applicable. Do not add admin CRUD endpoints yet.

## Task 10: Role Authorization Dependency Groundwork

### Files Changed

- `backend/app/dependencies/__init__.py`
- `backend/app/dependencies/auth.py`
- `backend/tests/test_role_dependencies.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `require_roles`.
- Added `require_admin`.
- Added reusable 403 permissions exception behavior.
- Exported `get_current_user`, `require_roles`, and `require_admin` from `backend/app/dependencies/__init__.py`.
- Added focused role dependency tests using test-only routes.

### Authorization Behavior

- `require_roles(*allowed_roles)` builds on `get_current_user`.
- Authenticated users whose role is in the allowed role set are returned unchanged.
- Authenticated users whose role is not allowed receive HTTP 403 with `Not enough permissions`.
- Missing, invalid, expired, missing-user, and inactive-user cases remain handled by `get_current_user` and return HTTP 401 with `Could not validate credentials`.
- `require_admin` is a convenience dependency based on `require_roles(UserRole.ADMIN)`.

### Review Notes

- The implementation is limited to reusable authorization helpers.
- No admin CRUD endpoints, registration, frontend code, parking logic, or production test-only routes were added.
- Role checks use the existing `UserRole` enum and avoid duplicate role string literals.
- The helpers are compatible with future role-specific dependencies for employees or parking owners.
- `require_roles` returns a dependency callable, which keeps route usage concise and composable.
- 401 and 403 behavior is separated cleanly: authentication failures stay in `get_current_user`; authorization failures stay in role helpers.
- OpenAPI bearer security is preserved for routes that use the role helpers because they depend on `get_current_user`.

### Tests Added or Updated

- Added `backend/tests/test_role_dependencies.py`
  - Admin user passes `require_admin`.
  - Employee user fails `require_admin` with HTTP 403.
  - Parking owner user fails `require_admin` with HTTP 403.
  - `require_roles` allows one of multiple permitted roles.
  - `require_roles` rejects a role not in the permitted set with HTTP 403.
  - Missing token still returns HTTP 401 through `get_current_user`.
  - Invalid token still returns HTTP 401 through `get_current_user`.
  - Inactive user still returns HTTP 401 through `get_current_user`.
  - Test-only role-protected route keeps bearer security metadata in OpenAPI.

### Verification Results

- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `81 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0002 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0001 -> 0002 (head), Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`
- ASCII check:
  - Result: passed for the newly added and changed dependency/test files.

### Known Limitations

- Docker/PostgreSQL verification was not run for this task because no database schema, migration, Dockerfile, or Compose changes were made.
- Role authorization helpers exist, but no production admin endpoints consume them yet.
- No fine-grained permissions model exists yet.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement initial admin team-management API endpoints using `TeamRepository` and `require_admin`: create, list, get, update, and delete teams with focused API tests. Do not implement user admin CRUD or parking logic yet.

## Task 11: Initial Admin Team Management API

### Files Changed

- `backend/app/main.py`
- `backend/app/routers/admin_teams.py`
- `backend/app/schemas/team.py`
- `backend/tests/test_admin_teams_api.py`
- `backend/tests/test_schemas.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added an admin team-management router under `backend/app/routers/admin_teams.py`.
- Registered the admin team router in the FastAPI application factory.
- Added admin-protected endpoints:
  - `GET /admin/teams`
  - `GET /admin/teams/{team_id}`
  - `POST /admin/teams`
  - `PATCH /admin/teams/{team_id}`
  - `DELETE /admin/teams/{team_id}`
- Applied the existing `require_admin` dependency to the admin team router.
- Used `TeamRepository` directly in the router to keep this task scoped to API wiring and repository usage.
- Added transaction handling at the API boundary for create, update, and delete operations.
- Added duplicate team-name handling with HTTP 409.
- Added missing team handling with HTTP 404.
- Added pagination validation for list requests.
- Tightened `TeamUpdate` validation so omitted `name` remains valid for partial updates, while explicit `null` names are rejected.

### Review Notes

- The implementation is limited to initial admin team CRUD only.
- No admin user CRUD, registration, frontend code, parking models, parking spot logic, or service layer changes were added.
- Router code stays thin and delegates database operations to `TeamRepository`.
- A service layer was not added for teams in this task because there are no team business rules beyond API-level authorization, validation, and transaction/error handling yet.
- All admin team endpoints are protected by `require_admin`; missing or invalid tokens still return HTTP 401 through `get_current_user`, while non-admin users receive HTTP 403.
- Create and update use a duplicate-name pre-check and still catch `IntegrityError` to handle database-enforced uniqueness.
- The router rolls back failed write transactions before raising API errors.
- Successful writes commit at the route boundary, preserving the existing repository behavior where repositories flush but do not commit.
- `DELETE /admin/teams/{team_id}` performs a hard delete for now, matching the current repository behavior. The existing user `team_id` foreign key is nullable with `ON DELETE SET NULL` in the PostgreSQL migration.
- `TeamUpdate` now rejects an explicit `name: null` payload so a required database column cannot fail later as a misleading duplicate/conflict error.

### Tests Added or Updated

- Added `backend/tests/test_admin_teams_api.py`
  - Admin can create a team.
  - Admin can list teams.
  - Admin can list teams with pagination.
  - Admin can get a team by ID.
  - Missing team lookup returns HTTP 404.
  - Admin can update a team.
  - Missing team update returns HTTP 404.
  - Null team name update returns HTTP 422.
  - Admin can delete a team.
  - Missing team delete returns HTTP 404.
  - Duplicate create returns HTTP 409.
  - Duplicate update returns HTTP 409.
  - Employee user receives HTTP 403.
  - Parking owner user receives HTTP 403.
  - Missing token receives HTTP 401.
  - Invalid token receives HTTP 401.
- Updated `backend/tests/test_schemas.py`
  - Added coverage that `TeamUpdate(name=None)` is rejected.

### Verification Results

- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `98 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0002 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0001 -> 0002 (head), Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`

### Known Limitations

- Docker/PostgreSQL verification was not run for this task because no database schema, migration, Dockerfile, or Compose files were changed.
- API tests use in-memory SQLite with FastAPI dependency overrides for isolated endpoint behavior.
- Team deletion is currently hard delete. If the product later requires deactivation instead, the repository/API behavior should be changed before frontend admin workflows depend on it.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement initial admin user-management API endpoints using `UserRepository` and `require_admin`: create, list, get, update, and deactivate or delete users with password hashing, duplicate email/username handling, team assignment validation, and focused API tests. Do not implement parking domain models or frontend yet.

## Task 12: Initial Admin User Management API

### Files Changed

- `backend/app/main.py`
- `backend/app/routers/admin_users.py`
- `backend/app/schemas/user.py`
- `backend/tests/test_admin_users_api.py`
- `backend/tests/test_schemas.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added an admin user-management router under `backend/app/routers/admin_users.py`.
- Registered the admin user router in the FastAPI application factory.
- Added admin-protected endpoints:
  - `GET /admin/users`
  - `GET /admin/users/{user_id}`
  - `POST /admin/users`
  - `PATCH /admin/users/{user_id}`
  - `DELETE /admin/users/{user_id}`
- Added pagination validation to `GET /admin/users`.
- Added optional `team_id` filtering to `GET /admin/users`.
- Used `UserRepository` for user persistence and `TeamRepository` for team existence checks.
- Hashed plain-text passwords before create and password-update persistence.
- Added duplicate email and duplicate username checks with HTTP 409.
- Added team existence checks with HTTP 404 when assigning a `team_id`.
- Added self-delete protection so an admin cannot hard-delete their own account.
- Added transaction commit/rollback handling for write endpoints.
- Tightened `UserUpdate` validation so only `team_id` can intentionally be set to `null`; non-null database fields reject explicit nulls before repository/database writes.

### Service Layer Decision

- No new `UserService` was added in this task.
- The router uses repositories directly because the current behavior is API-level authorization, validation, password hashing, transaction handling, and simple persistence.
- A service layer should be introduced later if user-management rules become more complex, such as invite flows, audit logging, notification side effects, or soft-delete/deactivation policy.

### Review Notes

- The implementation is limited to initial admin user CRUD only.
- No parking models, parking availability logic, reservations, frontend code, or user self-service/profile endpoints were added.
- Every admin user endpoint uses the existing `require_admin` dependency.
- Missing and invalid tokens still return HTTP 401 through `get_current_user`.
- Authenticated non-admin users receive HTTP 403 through role authorization.
- Missing users and missing teams return HTTP 404.
- Duplicate email and username pre-checks return specific HTTP 409 messages.
- `IntegrityError` is still caught and rolled back as a defensive fallback for database-enforced uniqueness.
- Passwords are accepted only through `UserCreate.password` and `UserUpdate.password`, immediately hashed, and never returned.
- `UserRead` remains the response model, so `hashed_password` is not exposed by create, list, get, update, or delete behavior.
- Self-delete protection returns HTTP 400 with a clear message before deletion is attempted.
- Hard delete is used for now, matching the current repository behavior and task scope.
- Explicit null handling is intentional: `team_id: null` clears the team assignment, while null values for email, username, names, password, role, and active status are rejected.

### Tests Added or Updated

- Added `backend/tests/test_admin_users_api.py`
  - Admin can create a user without a team.
  - Admin can create a user with an existing team.
  - Creating a user with a missing `team_id` returns HTTP 404.
  - Duplicate email returns HTTP 409.
  - Duplicate username returns HTTP 409.
  - Admin can list users.
  - Admin can list users by `team_id`.
  - Admin can get a user by ID.
  - Missing user lookup returns HTTP 404.
  - Admin can update basic user fields.
  - Admin can update `team_id`.
  - Admin can clear `team_id`.
  - Updating with a missing `team_id` returns HTTP 404.
  - Updating a missing user returns HTTP 404.
  - Duplicate update email returns HTTP 409.
  - Duplicate update username returns HTTP 409.
  - Admin can update a user's password and the stored value is hashed.
  - Admin can delete another user.
  - Deleting a missing user returns HTTP 404.
  - Admin cannot delete their own account.
  - Employee user receives HTTP 403.
  - Parking owner user receives HTTP 403.
  - Missing token receives HTTP 401.
  - Invalid token receives HTTP 401.
  - Created user password is hashed and verifies against the plain password.
  - API responses do not include `password` or `hashed_password`.
- Updated `backend/tests/test_schemas.py`
  - Added coverage for clearing `team_id`.
  - Added coverage that explicit nulls are rejected for non-nullable `UserUpdate` fields.

### Verification Results

- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `131 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0002 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0001 -> 0002 (head), Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`

### Known Limitations

- Docker/PostgreSQL verification was not run for this task because no database schema, migration, Dockerfile, or Compose files were changed.
- API tests use in-memory SQLite with FastAPI dependency overrides for isolated endpoint behavior.
- User deletion is currently hard delete. If the product should preserve historical user records, this should move to deactivate/soft-delete behavior before parking ownership and audit workflows are added.
- Admins can update their own profile fields through the admin endpoint, including role or active status. Only self-delete is blocked in this task because that was the explicit requirement.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Start frontend Phase 2 groundwork: scaffold the Vue frontend structure, add routing and an auth API service for `POST /auth/login` and `GET /auth/me`, and build the initial login page. Do not implement parking workflows yet.

## Task 13: Frontend Phase 2 Groundwork

### Files Changed

- `.gitignore`
- `frontend/.env.example`
- `frontend/index.html`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/vite.config.js`
- `frontend/src/App.vue`
- `frontend/src/main.js`
- `frontend/src/router/index.js`
- `frontend/src/services/apiClient.js`
- `frontend/src/services/authService.js`
- `frontend/src/services/authStorage.js`
- `frontend/src/components/common/AlertMessage.vue`
- `frontend/src/components/common/BaseButton.vue`
- `frontend/src/components/common/BaseInput.vue`
- `frontend/src/components/dashboard/DashboardCard.vue`
- `frontend/src/layouts/AppLayout.vue`
- `frontend/src/views/DashboardView.vue`
- `frontend/src/views/LoginView.vue`
- `frontend/src/views/NotFoundView.vue`
- `frontend/src/styles/main.css`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Created a Vue 3 frontend project under `frontend/`.
- Added Vite and Vue Router configuration.
- Added a configurable API base URL through `frontend/.env.example`:
  - `VITE_API_BASE_URL=http://localhost:8000`
- Added route structure:
  - `/login`
  - `/dashboard`
  - `/` redirecting based on local token presence
  - fallback not-found route
- Added simple route guards:
  - protected dashboard redirects to login when no token exists
  - login redirects to dashboard when a token exists
- Added reusable frontend auth services:
  - `apiClient.js` for Axios configuration and bearer-token attachment
  - `authService.js` for `POST /auth/login`, `GET /auth/me`, and logout
  - `authStorage.js` for access-token and current-user local storage
- Added a login page with username/email and password fields, clean validation, token storage, current-user loading, and dashboard navigation.
- Added a dashboard shell that loads `GET /auth/me`, displays the current user, and exposes logout.
- Added dashboard placeholder cards for:
  - available parking spots
  - my applications
  - my parking spot availability
  - admin management
- Added reusable starter components:
  - `BaseButton`
  - `BaseInput`
  - `AlertMessage`
  - `DashboardCard`
  - `AppLayout`
- Added a modern blue/white CSS foundation with design tokens for colors, spacing, border radius, shadows, and typography.
- Updated `.gitignore` for frontend local artifacts:
  - `frontend/node_modules/`
  - `frontend/.npm-cache/`
  - `frontend/dist/`
  - `frontend/.env`

### Architecture Decisions

- Used Vue 3 with Vite, matching the project plan.
- Used plain JavaScript for this scaffold to keep the initial frontend low-friction.
- Used Axios for the API client.
- Did not add Pinia yet. Current auth state is simple token/current-user local storage; Pinia should be introduced when shared frontend state grows beyond the login/dashboard shell.
- Did not add frontend tests yet. The project does not have a component-test framework configured, and adding one before reusable workflows exist would be premature for this scaffold task.
- Configured Vite scripts with `--configLoader runner` and `optimizeDeps.noDiscovery=true` because the restricted Windows workspace caused esbuild-based config/dependency scanning to attempt parent-directory access outside the allowed workspace.

### Review Notes

- The implementation is limited to frontend scaffold and authentication UI groundwork.
- No parking domain UI, admin CRUD screens, advanced state management, role-based frontend authorization, or frontend Docker integration was added.
- API calls are kept outside page components.
- The backend URL is configurable through `VITE_API_BASE_URL`.
- The bearer token is attached only by the shared API client interceptor.
- HTTP 401 responses clear stored auth state.
- Password and token values are not logged.
- `LoginView` sends the backend-compatible `identifier` and `password` request body.
- `DashboardView` loads the current user through `GET /auth/me` and clears auth state on session failure.
- `UserRead` data displayed by the frontend does not include password fields from the backend.
- The blue/white visual system is centralized in CSS variables and stays suitable for an internal company application.
- The layout is responsive and avoids parking/admin functionality beyond requested placeholders.

### Tests and Build Verification

- Frontend dependency install:
  - Command: `npm.cmd install --cache '.\.npm-cache'`
  - Result: passed; installed 63 packages and reported `found 0 vulnerabilities`
- Frontend build:
  - Command: `npm.cmd run build`
  - Result: passed; Vite transformed 90 modules and built `frontend/dist`
- Frontend dev server startup check:
  - Command: `npm.cmd run dev -- --host 127.0.0.1`
  - Result: Vite reported ready at `http://127.0.0.1:5173/`
- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `131 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0002 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0001 -> 0002 (head), Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`

### Known Limitations

- PowerShell blocks `npm.ps1` in this environment, so frontend commands were run through `npm.cmd`.
- The first `npm.cmd install` attempt failed because npm tried to write cache files under the user profile. Re-running with `--cache '.\.npm-cache'` kept cache writes inside the workspace and succeeded.
- Persistent background dev-server verification was limited by this execution environment. Vite starts successfully in the foreground, but detached child processes did not remain available across shell tool calls.
- The in-app browser tool was not callable in this thread, and the Node REPL sandbox failed while attempting to host the built static assets. Visual browser verification remains a manual check.
- Frontend tests and linting are not configured yet.
- Frontend Docker integration was intentionally not added in this task.
- Docker/PostgreSQL verification was not run because no backend schema, migration, Dockerfile, or Compose files changed.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Developer Commands

From `frontend/`:

```powershell
npm.cmd install --cache '.\.npm-cache'
npm.cmd run dev -- --host 127.0.0.1
npm.cmd run build
```

The local frontend dev URL is:

```text
http://127.0.0.1:5173/
```

### Next Suggested Task

Add frontend Docker integration now that the Vue project exists: create a frontend Dockerfile, add a frontend service to `docker-compose.yml`, pass `VITE_API_BASE_URL`, and document local Docker Compose startup for backend, frontend, and PostgreSQL. Do not implement parking UI yet.

## Task 14: Frontend Docker Integration and Full Compose Startup

### Files Changed

- `.env.example`
- `.gitignore`
- `backend/.env.example`
- `backend/app/core/config.py`
- `backend/tests/test_infrastructure_files.py`
- `docker-compose.yml`
- `frontend/.dockerignore`
- `frontend/.env.example`
- `frontend/Dockerfile`
- `frontend/nginx.conf`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `frontend/Dockerfile` with a multi-stage build:
  - `node:22-alpine` builds the Vue/Vite production bundle.
  - `nginx:1.27-alpine` serves the built static assets.
- Added `frontend/nginx.conf` with Vue Router history fallback:
  - `try_files $uri $uri/ /index.html`
- Added `frontend/.dockerignore` to exclude local dependencies, build output, cache, env files, and logs from the Docker build context.
- Added a `frontend` service to `docker-compose.yml`.
- Configured the frontend image build with:
  - `VITE_API_BASE_URL=${VITE_API_BASE_URL:-http://localhost:8000}`
- Exposed the frontend through:
  - `${FRONTEND_PORT:-8080}:80`
- Kept backend exposed at:
  - `${BACKEND_PORT:-8000}:8000`
- Kept PostgreSQL healthcheck and backend dependency on healthy database intact.
- Made the frontend depend on backend service startup.
- Updated root `.env.example` with:
  - `FRONTEND_PORT=8080`
  - `VITE_API_BASE_URL=http://localhost:8000`
  - CORS origins for both Vite dev and Dockerized frontend.
- Updated `backend/.env.example` and backend settings defaults to allow:
  - `http://localhost:5173`
  - `http://localhost:8080`
- Updated `frontend/.env.example` to document that `VITE_API_BASE_URL` is the browser-visible backend URL.
- Added infrastructure tests for frontend Dockerfile, nginx fallback, Compose frontend service wiring, env examples, and CORS defaults.

### Docker Compose Developer Commands

Build all services:

```powershell
docker-compose build
```

Build a single service:

```powershell
docker-compose build frontend
docker-compose build backend
```

Start PostgreSQL, backend, and frontend:

```powershell
docker-compose up -d db backend frontend
```

Apply migrations from inside the backend container:

```powershell
docker-compose run --rm backend alembic -c alembic.ini upgrade head
```

Check backend health:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

Open the frontend:

```text
http://localhost:8080/
```

Check Vue Router history fallback:

```powershell
Invoke-WebRequest -Uri "http://localhost:8080/login" -UseBasicParsing
Invoke-WebRequest -Uri "http://localhost:8080/dashboard" -UseBasicParsing
```

Stop services while preserving PostgreSQL data:

```powershell
docker-compose down
```

Stop services and delete the PostgreSQL named volume:

```powershell
docker-compose down -v
```

### Review Notes

- The implementation is limited to frontend Docker integration and full local Compose startup.
- No parking domain models, parking UI, admin CRUD UI, or additional backend business logic was added.
- The frontend container is production-style static serving through nginx, not a Vite dev-server container.
- `VITE_API_BASE_URL` is intentionally set to `http://localhost:8000` because the compiled frontend runs in the user's browser and must call the host-exposed backend URL, not the Compose-internal `backend:8000` hostname.
- Backend-to-database traffic still uses the Compose-internal hostname `db`.
- CORS defaults now allow the local Vite dev frontend on `localhost:5173` and Dockerized frontend on `localhost:8080`.
- The nginx fallback supports direct refreshes of `/login` and `/dashboard`.
- Existing backend/database Compose behavior remains intact.
- No real secrets were added.
- Frontend logs are ignored through `.gitignore`.

### Tests and Verification Results

- Frontend build:
  - Command: `npm.cmd run build`
  - Result: passed; Vite transformed 90 modules and built `frontend/dist`
- Docker Compose config:
  - Command: `docker-compose config`
  - Result: passed; rendered `db`, `backend`, `frontend`, `postgres_data`, and default network configuration.
  - Rendered backend CORS value: `["http://localhost:5173","http://localhost:8080"]`
  - Rendered frontend build arg: `VITE_API_BASE_URL=http://localhost:8000`
- Frontend Docker image build:
  - Command: `docker-compose build frontend`
  - Result: passed; image `parkingapp-frontend:latest` built successfully.
- Backend Docker image build:
  - Command: `docker-compose build backend`
  - Result: passed; image `parkingapp-backend:latest` built successfully.
- Full Compose startup:
  - Command: `docker-compose up -d db backend frontend`
  - Result: passed; `db` became healthy, backend started, frontend started.
- Migration execution against PostgreSQL:
  - Command: `docker-compose run --rm backend alembic -c alembic.ini upgrade head`
  - Result: passed; Alembic used `PostgresqlImpl` and completed without errors.
- Backend health endpoint:
  - Command: `Invoke-RestMethod -Uri "http://localhost:8000/health"`
  - Result: returned `status=ok`, `service=Parking Management API`, `environment=local`.
- Frontend HTTP response:
  - Command: `Invoke-WebRequest -Uri "http://localhost:8080/" -UseBasicParsing`
  - Result: HTTP 200.
- Vue Router history fallback:
  - Command: `Invoke-WebRequest -Uri "http://localhost:8080/login" -UseBasicParsing`
  - Result: HTTP 200.
  - Command: `Invoke-WebRequest -Uri "http://localhost:8080/dashboard" -UseBasicParsing`
  - Result: HTTP 200.
- Backend CORS preflight from Dockerized frontend origin:
  - Command: `OPTIONS http://localhost:8000/auth/me` with origin `http://localhost:8080`, method `GET`, and header `Authorization`.
  - Result: HTTP 200 with `Access-Control-Allow-Origin=http://localhost:8080` and `Access-Control-Allow-Headers=Authorization`.
- Docker Compose service status:
  - Command: `docker-compose ps`
  - Result:
    - `parkingapp-db-1` healthy on host port `5432`.
    - `parkingapp-backend-1` running on host port `8000`.
    - `parkingapp-frontend-1` running on host port `8080`.
- Service shutdown:
  - Command: `docker-compose down`
  - Result: passed; containers and network removed while preserving the PostgreSQL named volume.
- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `134 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0002 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0001 -> 0002 (head), Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`

### Known Limitations

- Docker commands needed elevated Docker Desktop access because the sandbox could not access Docker config/buildx files under the user profile.
- Browser visual verification was not performed in this task. The frontend was verified through production build, nginx HTTP 200 responses, and Vue Router fallback HTTP checks.
- The frontend image uses a build-time `VITE_API_BASE_URL`. Changing the browser-visible backend URL requires rebuilding the frontend image.
- The frontend service depends on backend startup, not backend health, because the backend service does not currently define a container healthcheck.
- Frontend tests and linting are still not configured.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement frontend admin-management groundwork: add reusable admin API service modules for users and teams, create protected admin routes/pages for listing users and teams, and wire navigation placeholders to real admin pages. Do not implement parking domain UI yet.

## Task 15: Parking Spot Domain Groundwork

### Files Changed

- `backend/alembic/versions/0003_add_parking_spots.py`
- `backend/app/models/__init__.py`
- `backend/app/models/parking_spot.py`
- `backend/app/models/user.py`
- `backend/app/repositories/__init__.py`
- `backend/app/repositories/parking_spots.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/parking_spot.py`
- `backend/tests/test_alembic_config.py`
- `backend/tests/test_models.py`
- `backend/tests/test_repositories.py`
- `backend/tests/test_schemas.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `ParkingSpot` SQLAlchemy model with:
  - `id`
  - unique indexed `code`
  - optional `location`
  - optional `description`
  - nullable indexed `owner_id`
  - `is_active`
  - `created_at`
  - `updated_at`
- Added direct owner relationship:
  - `ParkingSpot.owner`
  - `User.owned_parking_spots`
- Added Pydantic v2 schemas:
  - `ParkingSpotBase`
  - `ParkingSpotCreate`
  - `ParkingSpotUpdate`
  - `ParkingSpotRead`
- Added `ParkingSpotRepository` with:
  - `create`
  - `get_by_id`
  - `get_by_code`
  - `list`
  - `list_by_owner_id`
  - `update`
  - `delete`
- Added Alembic migration `0003_add_parking_spots.py`.
- Updated model, schema, and repository package exports.
- Updated Alembic tests to expect `0003` as head.
- Added focused model, schema, and repository tests.

### Ownership Decision

- Ownership is modeled as a nullable direct `owner_id` on `parking_spots` for this MVP groundwork task.
- This keeps the initial parking domain simple and gives admin APIs a direct way to assign or unassign a spot owner.
- The original plan mentions ownership history. That can be introduced later with a dedicated ownership-history table before audit-heavy workflows depend on it.
- `owner_id` uses `ON DELETE SET NULL`, so deleting a user does not force-delete parking spots.

### Review Notes

- The implementation is limited to parking spot domain groundwork.
- No parking availability, applications, reservations, fairness logic, parking frontend UI, or admin parking UI was added.
- Model naming follows the existing table style: `parking_spots`.
- `code` is unique and indexed for stable spot lookup.
- `owner_id` is nullable to allow unassigned parking spots.
- Repository methods are database-focused only and do not validate owner existence as a business rule.
- Repository write methods flush but do not commit, matching existing repository behavior.
- Relationship queries use `selectinload` to avoid avoidable lazy-loading surprises.
- `ParkingSpotRead` exposes only parking spot fields and `owner_id`; it does not expose owner details or password fields.
- `ParkingSpotUpdate` intentionally allows explicit null for `location`, `description`, and `owner_id`; explicit null for `code` and `is_active` is rejected.
- The migration is PostgreSQL-compatible and uses the existing naming convention for PK, FK, and indexes.
- Simple hard delete is used for now, matching existing repository behavior.

### Tests Added or Updated

- Updated `backend/tests/test_models.py`
  - Verifies metadata contains `parking_spots`.
  - Verifies columns, indexes, FK, timestamps, and relationships.
  - Verifies SQLite table creation and basic parking spot owner persistence.
- Updated `backend/tests/test_schemas.py`
  - Verifies create/update/read schema behavior.
  - Verifies blank code rejection.
  - Verifies explicit null behavior for update fields.
  - Verifies `ParkingSpotRead` does not expose owner details or password fields.
- Updated `backend/tests/test_repositories.py`
  - Verifies create with owner and get by ID.
  - Verifies get by code and missing lookups.
  - Verifies list pagination and list by owner ID.
  - Verifies partial update behavior.
  - Verifies explicit null updates for optional fields.
  - Verifies delete.
  - Verifies duplicate code constraint.
- Updated `backend/tests/test_alembic_config.py`
  - Expects `0003` as current head.
  - Verifies offline SQL includes `parking_spots` and indexes.

### Verification Results

- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `148 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0003 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0002 -> 0003 (head), Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`
- Alembic offline SQL generation:
  - Command: `python -m alembic -c backend/alembic.ini upgrade head --sql`
  - Result: passed; generated PostgreSQL SQL for `parking_spots`, `ix_parking_spots_code`, and `ix_parking_spots_owner_id`.
- Backend Docker image build:
  - Command: `docker-compose build backend`
  - Result: passed; image `parkingapp-backend:latest` rebuilt with migration `0003`.
- PostgreSQL/backend startup:
  - Command: `docker-compose up -d db backend`
  - Result: passed; PostgreSQL became healthy and backend started.
- Migration execution against PostgreSQL:
  - Command: `docker-compose run --rm backend alembic -c alembic.ini upgrade head`
  - Result: passed; Alembic ran `0002 -> 0003, Add parking spots table.`
- Backend health endpoint:
  - Command: `Invoke-RestMethod -Uri "http://localhost:8000/health"`
  - Result: returned `status=ok`, `service=Parking Management API`, `environment=local`.
- PostgreSQL current revision:
  - Command: `docker-compose run --rm backend alembic -c alembic.ini current`
  - Result: `0003 (head)`
- Service shutdown:
  - Command: `docker-compose down`
  - Result: passed; containers and network removed while preserving the PostgreSQL named volume.

### Known Limitations

- Docker commands needed elevated Docker Desktop access because the sandbox could not access Docker config/buildx files under the user profile.
- Parking spot owner existence is not validated in the repository. That should be handled in a future service/API layer.
- Ownership history is not implemented yet.
- Parking spot admin API endpoints do not exist yet.
- Parking availability, applications, reservations, and fairness logic are not implemented yet.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement initial admin parking spot-management API endpoints using `ParkingSpotRepository`, `UserRepository`, and `require_admin`: create, list, get, update, assign/unassign owner through `owner_id`, and delete parking spots with focused API tests. Do not implement parking availability, applications, reservations, fairness logic, or parking frontend UI yet.

## Task 16: Initial Admin Parking Spot Management API

### Files Changed

- `backend/app/main.py`
- `backend/app/repositories/parking_spots.py`
- `backend/app/routers/admin_parking_spots.py`
- `backend/tests/test_admin_parking_spots_api.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added an admin parking spot-management router under `backend/app/routers/admin_parking_spots.py`.
- Registered the admin parking spot router in the FastAPI application factory.
- Added admin-protected endpoints:
  - `GET /admin/parking-spots`
  - `GET /admin/parking-spots/{parking_spot_id}`
  - `POST /admin/parking-spots`
  - `PATCH /admin/parking-spots/{parking_spot_id}`
  - `DELETE /admin/parking-spots/{parking_spot_id}`
- Added pagination validation to `GET /admin/parking-spots`.
- Added optional list filters:
  - `owner_id`
  - `is_active`
- Extended `ParkingSpotRepository.list` and `list_by_owner_id` to support database-level filtering.
- Used `ParkingSpotRepository` for parking spot persistence.
- Used `UserRepository` to validate `owner_id` assignments.
- Added owner assignment validation:
  - missing owner returns HTTP 404,
  - inactive owner returns HTTP 400,
  - `owner_id: null` is allowed on update to unassign a spot.
- Added duplicate parking spot code checks with HTTP 409.
- Added transaction commit/rollback handling for write endpoints.

### Service Layer Decision

- No new `ParkingSpotService` was added in this task.
- This matches the existing admin team and admin user endpoint style, where routes coordinate authorization, validation, transactions, and repositories for simple CRUD behavior.
- A service layer should be introduced later if parking spot rules grow to include ownership history, audit logs, notifications, or validation tied to future availability/reservation records.

### Review Notes

- The implementation is limited to admin parking spot CRUD only.
- No parking availability, applications, reservations, fairness logic, parking frontend UI, or admin frontend UI was added.
- Every endpoint uses the existing `require_admin` dependency.
- Missing and invalid tokens still return HTTP 401 through `get_current_user`.
- Authenticated non-admin users receive HTTP 403 through role authorization.
- Missing parking spots and owner users return HTTP 404.
- Inactive owner assignment returns HTTP 400 with `Owner is inactive`.
- Duplicate `code` pre-checks return HTTP 409 with `Parking spot code already exists`.
- `IntegrityError` is caught and rolled back as a defensive fallback for database-enforced uniqueness.
- Parking spot responses use `ParkingSpotRead`, which exposes only parking spot fields and `owner_id`; no sensitive user details are returned.
- Hard delete is acceptable for this MVP stage because availability, reservation, and audit tables do not exist yet. This should be revisited when those references are introduced.
- Active users of any role may currently be assigned as a parking spot owner. Role/capability policy can be tightened later when ownership workflows are introduced.

### Tests Added or Updated

- Added `backend/tests/test_admin_parking_spots_api.py`
  - Admin can create a parking spot without an owner.
  - Admin can create a parking spot with an active owner.
  - Creating with missing `owner_id` returns HTTP 404.
  - Creating with inactive owner returns HTTP 400.
  - Duplicate parking spot code returns HTTP 409.
  - Admin can list parking spots.
  - Admin can filter parking spots by `owner_id`.
  - Admin can filter parking spots by `is_active`.
  - Admin can get a parking spot by ID.
  - Missing parking spot lookup returns HTTP 404.
  - Admin can update basic fields.
  - Admin can assign an owner.
  - Admin can unassign an owner with `owner_id: null`.
  - Updating with missing `owner_id` returns HTTP 404.
  - Updating with inactive owner returns HTTP 400.
  - Updating a missing parking spot returns HTTP 404.
  - Updating to a duplicate code returns HTTP 409.
  - Admin can delete a parking spot.
  - Deleting a missing parking spot returns HTTP 404.
  - Employee user receives HTTP 403.
  - Parking owner user receives HTTP 403.
  - Missing token receives HTTP 401.
  - Invalid token receives HTTP 401.
  - Parking spot API responses do not expose owner details, passwords, or password hashes.

### Verification Results

- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `171 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0003 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0002 -> 0003 (head), Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`

### Known Limitations

- Docker/PostgreSQL verification was not run for this task because no schema, migration, Dockerfile, or Compose files changed.
- API tests use in-memory SQLite with FastAPI dependency overrides for isolated endpoint behavior.
- Parking spot hard delete remains temporary MVP behavior and should be revisited once availability/reservation records reference parking spots.
- Ownership history is not implemented yet.
- Owner assignment currently rejects inactive users but does not restrict ownership to a specific role.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement parking availability domain groundwork: add parking availability model, schemas, repository, Alembic migration, and focused tests for owner-published availability windows. Do not implement applications, reservations, fairness selection, background assignment, or frontend parking UI yet.

## Task 17: Parking Availability Domain Groundwork

### Files Changed

- `backend/alembic/versions/0004_add_parking_availabilities.py`
- `backend/app/models/__init__.py`
- `backend/app/models/parking_availability.py`
- `backend/app/models/parking_spot.py`
- `backend/app/models/user.py`
- `backend/app/repositories/__init__.py`
- `backend/app/repositories/parking_availabilities.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/parking_availability.py`
- `backend/tests/test_alembic_config.py`
- `backend/tests/test_models.py`
- `backend/tests/test_repositories.py`
- `backend/tests/test_schemas.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added the `ParkingAvailability` SQLAlchemy model with required parking spot and owner foreign keys, timezone-aware datetime columns, status enum, optional note, optional `priority_until`, timestamps, and relationships to `ParkingSpot` and `User`.
- Added reverse relationships on `ParkingSpot.availabilities` and `User.published_availabilities`.
- Added Pydantic v2 schemas for create, update, read, and base availability payloads.
- Added structural schema validation for timezone-aware datetimes and `end_at > start_at`.
- Added intentional explicit-null behavior: `note` can be null, while update `start_at`, `end_at`, and `status` reject explicit null.
- Added `ParkingAvailabilityRepository` with create, get, list, list-by-spot, list-by-owner, list-open, overlap lookup, update, and delete methods.
- Added Alembic migration `0004` for the `parking_availabilities` table, PostgreSQL enum, foreign keys, and indexes.

### Review Notes

- The implementation stays within domain groundwork only. No availability API endpoints, services, parking applications, reservations, fairness logic, background jobs, or frontend parking screens were added.
- Repository methods are database-focused and do not enforce ownership, overlap prevention, assignment, or same-team priority rules.
- Schema validation handles only structural request validation that is safe to enforce before service-layer business rules.
- The status enum is stored with PostgreSQL-compatible values: `open`, `assigned`, `cancelled`, and `expired`.
- `priority_until` is stored as nullable because priority-window calculation belongs in a later service/API task.
- Foreign keys reference `parking_spots.id` and `users.id`; delete behavior is intentionally not cascaded until application/reservation lifecycle rules are defined.
- Indexes cover spot lookup, owner lookup, status lookup, datetime filtering, and spot/time overlap-style queries.
- Test comparisons account for SQLite dropping timezone info on datetime round-trips; production PostgreSQL migration uses timezone-aware columns.

### Tests Added or Updated

- Updated `backend/tests/test_models.py`
  - Verifies metadata contains `parking_availabilities`.
  - Verifies important availability columns, indexes, constraints, enum metadata, and relationships.
  - Extends SQLite table creation/persistence coverage with availability relationships.
- Updated `backend/tests/test_schemas.py`
  - Verifies availability create/read schemas validate and serialize.
  - Verifies `end_at <= start_at` is rejected.
  - Verifies naive datetimes are rejected.
  - Verifies update explicit-null behavior.
  - Verifies nullable `note` behavior.
- Updated `backend/tests/test_repositories.py`
  - Verifies create/get, missing record, list, list by parking spot, list by owner, list open, update, overlap lookup, and delete behavior.
  - Verifies loaded parking spot and owner relationships.
- Updated `backend/tests/test_alembic_config.py`
  - Verifies Alembic head is `0004`.
  - Verifies migration history includes `0004`.
  - Verifies offline SQL contains the availability table, enum, and key indexes.

### Verification Results

- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `187 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0004 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0003 -> 0004 (head), Add parking availabilities table.`
    - `0002 -> 0003, Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`
- Alembic offline SQL generation:
  - Command: `python -m alembic -c backend/alembic.ini upgrade head --sql`
  - Result: generated successfully and contained `CREATE TYPE parking_availability_status AS ENUM`, `CREATE TABLE parking_availabilities`, `ix_parking_availabilities_spot_start_end`, `ix_parking_availabilities_status_start_at`, and `0004`.
- Docker Compose configuration:
  - Command: `docker-compose config`
  - Result: passed; Docker emitted a Windows access warning for `C:\Users\nikola.milosevic\.docker\config.json`, but the rendered Compose configuration was valid.
- Backend Docker build:
  - Command: `docker-compose build backend`
  - Result: passed after approved Docker access.
- Docker PostgreSQL/backend startup:
  - Command: `docker-compose up -d db backend`
  - Result: passed after approved Docker Engine access; PostgreSQL became healthy and backend started.
- Docker PostgreSQL migration:
  - Command: `docker-compose run --rm backend alembic -c alembic.ini upgrade head`
  - Result: passed; Alembic ran `0003 -> 0004`.
- Docker PostgreSQL current revision:
  - Command: `docker-compose run --rm backend alembic -c alembic.ini current`
  - Result: `0004 (head)`.
- Backend health endpoint:
  - Command: `Invoke-RestMethod -Uri http://localhost:8000/health`
  - Result: `{"status":"ok","service":"Parking Management API","environment":"local"}`.
- Docker shutdown:
  - Command: `docker-compose down`
  - Result: passed; services stopped and volumes were preserved.

### Known Limitations

- No availability ownership validation is implemented yet; the future service/API layer should confirm that the authenticated owner can publish availability for the selected parking spot.
- No overlap prevention is enforced yet; the repository only exposes a helper query for future service validation.
- No application, reservation, same-team priority, or fairness assignment logic exists yet.
- No availability endpoints or frontend parking screens were added.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement parking availability service and API endpoints for owners to publish, list, inspect, update, and cancel their own availability windows. Add ownership validation and overlap checks in the service layer, but do not implement parking applications, reservations, fairness assignment, or frontend parking screens yet.

## Task 18: Parking Availability Service and Owner-Facing API

### Files Changed

- `.env.example`
- `backend/.env.example`
- `docker-compose.yml`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/repositories/parking_availabilities.py`
- `backend/app/routers/parking_availabilities.py`
- `backend/app/services/__init__.py`
- `backend/app/services/parking_availabilities.py`
- `backend/tests/test_infrastructure_files.py`
- `backend/tests/test_parking_availabilities_api.py`
- `backend/tests/test_parking_availability_service.py`
- `backend/tests/test_repositories.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `ParkingAvailabilityService` for owner-facing availability business rules.
- Added service-level exceptions so routers can map business failures to HTTP without raising `HTTPException` in the service layer.
- Added authenticated availability endpoints:
  - `POST /parking-availabilities`
  - `GET /parking-availabilities`
  - `GET /parking-availabilities/my`
  - `GET /parking-availabilities/{availability_id}`
  - `PATCH /parking-availabilities/{availability_id}/cancel`
- Added ownership validation for publishing availability:
  - parking spot must exist,
  - parking spot must be active,
  - current user must own the parking spot.
- Added business time validation:
  - `end_at` cannot be in the past,
  - `start_at` cannot be in the past.
- Added overlap prevention for blocking statuses:
  - `open` blocks overlapping availability,
  - `assigned` blocks overlapping availability,
  - `cancelled` and `expired` do not block.
- Added automatic `priority_until` calculation using `SAME_TEAM_PRIORITY_WINDOW_HOURS`, defaulting to 2 hours.
- Extended `ParkingAvailabilityRepository` with filtered open listing and blocking-overlap lookup.
- Registered the new availability router in the FastAPI application.

### Review Notes

- The task stayed within owner-facing availability publishing/listing/viewing/cancellation.
- No parking applications, reservations, fairness assignment, admin availability management, or frontend parking screens were added.
- Service methods own business rules; repositories remain database-focused.
- Routers translate service errors into generic HTTP responses:
  - 400 for invalid time windows,
  - 403 for permission failures,
  - 404 for missing parking spots or availabilities,
  - 409 for inactive parking spots, overlaps, and invalid cancel transitions.
- Missing and invalid bearer tokens still return 401 through the existing `get_current_user` dependency.
- Open availabilities are visible to any authenticated user.
- Non-open availabilities are visible only to the owner or an admin.
- Only the owner or an admin can cancel an open availability.
- The general update endpoint was intentionally not added because changing availability windows safely requires additional overlap/status rules and can be implemented as a separate focused task if needed.
- PostgreSQL schema and Alembic migrations were not changed in this task.

### Tests Added or Updated

- Added `backend/tests/test_parking_availability_service.py`
  - Owner can create availability for own active parking spot.
  - Non-owner cannot create availability for another user's spot.
  - Missing parking spot raises a clean service error.
  - Inactive parking spot cannot be published.
  - Overlapping open availability is rejected.
  - Overlapping assigned availability is rejected.
  - Overlapping cancelled availability does not block.
  - Past availability end time is rejected.
  - `priority_until` is set automatically.
  - Open availability can be viewed by any authenticated user.
  - Non-owner cannot view non-open availability, while admin can.
  - Owner and admin can cancel open availability.
  - Non-owner cannot cancel availability.
  - Cancelled availability cannot be cancelled again.
- Added `backend/tests/test_parking_availabilities_api.py`
  - API coverage for create/list/my/get/cancel endpoints and 400/403/404/409 mappings.
  - Missing and invalid tokens return 401.
  - Responses do not expose password or nested owner/parking spot objects.
- Updated `backend/tests/test_repositories.py`
  - Added filtered availability listing assertions.
  - Added blocking-overlap status behavior coverage.
- Updated `backend/tests/test_infrastructure_files.py`
  - Verifies `SAME_TEAM_PRIORITY_WINDOW_HOURS` in settings, env examples, and Docker Compose backend environment.

### Verification Results

- Focused tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests/test_parking_availability_service.py backend/tests/test_parking_availabilities_api.py backend/tests/test_repositories.py backend/tests/test_infrastructure_files.py`
  - Result: `65 passed, 1 warning`
- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `219 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0004 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0003 -> 0004 (head), Add parking availabilities table.`
    - `0002 -> 0003, Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`
- Docker Compose configuration:
  - Command: `docker-compose config`
  - Result: passed and rendered `SAME_TEAM_PRIORITY_WINDOW_HOURS: "2"` for the backend service. Docker emitted the existing Windows warning for `C:\Users\nikola.milosevic\.docker\config.json`, but the rendered Compose configuration was valid.

### Known Limitations

- Docker/PostgreSQL migration execution was not run because this task did not change schema or migrations.
- The API does not expose a general availability update endpoint yet.
- There is no parking application model or apply/cancel-application flow yet.
- There is no reservation or automatic assignment/fairness logic yet.
- The priority window is stored but not used for applicant selection yet.
- Availability date/times are validated by schema/service, but frontend date/time handling is not implemented yet.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement parking application domain groundwork: add `ParkingApplication` model, schemas, repository, Alembic migration, and focused tests for employees applying to open availabilities. Do not implement reservation assignment, fairness ranking, scheduled workers, or frontend parking screens yet.

## Task 19: Parking Application Domain Groundwork

### Files Changed

- `backend/alembic/versions/0005_add_parking_applications.py`
- `backend/app/models/__init__.py`
- `backend/app/models/parking_application.py`
- `backend/app/models/parking_availability.py`
- `backend/app/models/user.py`
- `backend/app/repositories/__init__.py`
- `backend/app/repositories/parking_applications.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/parking_application.py`
- `backend/tests/test_alembic_config.py`
- `backend/tests/test_models.py`
- `backend/tests/test_repositories.py`
- `backend/tests/test_schemas.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `ParkingApplication` SQLAlchemy model.
- Added `ParkingApplicationStatus` enum with `pending`, `selected`, `cancelled`, and `rejected`.
- Added relationships:
  - `ParkingApplication.availability`
  - `ParkingApplication.applicant`
  - `ParkingAvailability.applications`
  - `User.parking_applications`
- Added database uniqueness constraint on `(availability_id, applicant_id)`.
- Added Pydantic v2 schemas:
  - `ParkingApplicationBase`
  - `ParkingApplicationCreate`
  - `ParkingApplicationUpdate`
  - `ParkingApplicationRead`
- Added `ParkingApplicationRepository` with create, get, list, filtered list, update, and delete methods.
- Added Alembic migration `0005` for the `parking_applications` table, enum, foreign keys, unique constraint, and indexes.

### Review Notes

- The implementation is limited to domain groundwork only.
- No parking application API endpoints, services, reservation/assignment logic, fairness/priority selection, admin application management, or frontend parking screens were added.
- The repository remains database-focused and does not check whether an availability is open, whether the applicant is the owner, or whether fairness rules allow the application.
- Applicant identity is not accepted by the client-facing create schema; it is expected to come from the authenticated user in a later service/API task.
- `note` is nullable in create/update schemas.
- Update schema rejects explicit `null` for `status`.
- The uniqueness constraint prevents the same applicant from applying more than once for the same availability while still allowing:
  - the same applicant to apply to different availabilities,
  - different applicants to apply to the same availability.
- PostgreSQL enum values and SQLAlchemy enum values are aligned.
- Migration `0005` applies after `0004`.

### Tests Added or Updated

- Updated `backend/tests/test_models.py`
  - Verifies metadata contains `parking_applications`.
  - Verifies columns, enum values, indexes, unique constraint, foreign keys, and relationships.
  - Extends SQLite persistence coverage to include application relationships.
- Updated `backend/tests/test_schemas.py`
  - Verifies create/update/read schema behavior.
  - Verifies create schema does not include `applicant_id`.
  - Verifies update schema rejects explicit `null` for `status`.
  - Verifies nullable `note` behavior.
- Updated `backend/tests/test_repositories.py`
  - Verifies create/get/get-by-availability-and-applicant/list/list-by-availability/list-by-applicant/list-pending/update/delete.
  - Verifies duplicate applicant for the same availability fails.
  - Verifies the same applicant can apply to different availabilities.
  - Verifies different applicants can apply to the same availability.
  - Verifies missing records return `None`.
- Updated `backend/tests/test_alembic_config.py`
  - Verifies Alembic head is `0005`.
  - Verifies offline SQL includes the application enum, table, unique constraint, indexes, and revision marker.

### Verification Results

- Focused tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests/test_models.py backend/tests/test_schemas.py backend/tests/test_repositories.py backend/tests/test_alembic_config.py`
  - Result: `82 passed`
- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `233 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0005 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0004 -> 0005 (head), Add parking applications table.`
    - `0003 -> 0004, Add parking availabilities table.`
    - `0002 -> 0003, Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`
- Alembic offline SQL generation:
  - Command: `python -m alembic -c backend/alembic.ini upgrade head --sql`
  - Result: generated successfully and contained `CREATE TYPE parking_application_status AS ENUM`, `CREATE TABLE parking_applications`, `uq_parking_applications_availability_id_applicant_id`, `ix_parking_applications_availability_status`, and `0005`.
- Backend Docker build:
  - Command: `docker-compose build backend`
  - Result: passed after approved Docker access.
- Docker PostgreSQL/backend startup:
  - Command: `docker-compose up -d db backend`
  - Result: passed after approved Docker Engine access; PostgreSQL became healthy and backend started.
- Docker PostgreSQL migration:
  - Command: `docker-compose run --rm backend alembic -c alembic.ini upgrade head`
  - Result: passed; Alembic ran `0004 -> 0005`.
- Docker PostgreSQL current revision:
  - Command: `docker-compose run --rm backend alembic -c alembic.ini current`
  - Result: `0005 (head)`.
- Backend health endpoint:
  - Command: `Invoke-RestMethod -Uri http://localhost:8000/health`
  - Result: `{"status":"ok","service":"Parking Management API","environment":"local"}`.
- Docker shutdown:
  - Command: `docker-compose down`
  - Result: passed; services stopped and volumes were preserved.

### Known Limitations

- No parking application API endpoints were added yet.
- No service-layer validation exists yet for open availability, owner-cannot-apply, inactive applicants, duplicate application error mapping, or cancellation.
- No reservation, assignment, fairness ranking, scheduled worker, or frontend parking screen exists yet.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement parking application service and API endpoints for employees to apply to open availabilities, list their own applications, and cancel pending applications. Add service-layer validation for open availability, owner-cannot-apply, duplicate applications, inactive users, and pending-only cancellation. Do not implement reservation assignment, fairness ranking, scheduled workers, or frontend parking screens yet.

## Task 20: Parking Application Service and Employee-Facing API

### Files Changed

- `backend/app/main.py`
- `backend/app/repositories/parking_applications.py`
- `backend/app/routers/parking_applications.py`
- `backend/app/services/__init__.py`
- `backend/app/services/parking_applications.py`
- `backend/tests/test_parking_application_service.py`
- `backend/tests/test_parking_applications_api.py`
- `backend/tests/test_repositories.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `ParkingApplicationService` for employee application business rules.
- Added service-level exceptions so routers can map domain failures to HTTP without raising `HTTPException` in service code.
- Added employee-facing authenticated application endpoints:
  - `POST /parking-applications`
  - `GET /parking-applications/my`
  - `GET /parking-applications/{application_id}`
  - `PATCH /parking-applications/{application_id}/cancel`
- Added apply validation:
  - availability must exist,
  - availability must be `open`,
  - availability `end_at` must be in the future,
  - applicant must be active,
  - applicant must not be the availability owner,
  - applicant must not already have an application for that availability,
  - inactive parking spots are rejected when the availability relationship exposes the spot.
- Added cancel validation:
  - application must exist,
  - current user must be the applicant,
  - only `pending` applications can be cancelled,
  - cancellation updates status to `cancelled` instead of deleting the row.
- Added view/list behavior:
  - users can list their own applications,
  - `GET /parking-applications/my` supports optional `status` filtering,
  - users can view their own application,
  - admins can view any application.
- Extended `ParkingApplicationRepository.list_by_applicant_id` with an optional status filter.

### Review Notes

- The implementation stayed within employee-facing application submission/listing/viewing/cancellation.
- No reservation/winner assignment, fairness/priority selection, owner/admin application management, scheduled worker, or frontend parking screen was added.
- Repository changes remain database-focused; all application rules live in `ParkingApplicationService`.
- Routers map service errors to generic HTTP responses:
  - 403 for owner-cannot-apply, inactive applicant, and permission failures,
  - 404 for missing availability or application,
  - 409 for duplicate application, non-open availability, expired availability, inactive parking spot, and invalid cancel transition.
- `IntegrityError` is handled defensively in the create endpoint and returned as duplicate application conflict.
- The service normalizes datetimes to UTC before expiration checks so SQLite test round-trips and PostgreSQL timezone-aware values behave consistently.
- Priority window behavior is intentionally permissive for this task: non-team applicants may apply during the priority window. Team priority affects later selection/assignment, not application submission.

### Tests Added or Updated

- Added `backend/tests/test_parking_application_service.py`
  - Authenticated user can apply for an open future availability.
  - Missing availability raises a clean service error.
  - Non-open availability is rejected.
  - Expired availability is rejected.
  - Owner cannot apply to own availability.
  - Duplicate application is rejected.
  - Inactive applicant is rejected at service level.
  - Non-team applicant can apply during the priority window.
  - User can list own applications with status filter.
  - User and admin can view allowed applications.
  - Non-applicant cannot view another user's application.
  - Applicant can cancel pending application.
  - Cancellation updates status instead of deleting the row.
  - Applicant cannot cancel non-pending application.
  - User cannot cancel another user's application.
- Added `backend/tests/test_parking_applications_api.py`
  - API coverage for apply, list-my, get, cancel, and 401/403/404/409 mappings.
  - Inactive user receives 401 through the existing current-user dependency.
  - Responses do not expose nested applicant/availability objects or password fields.
- Updated `backend/tests/test_repositories.py`
  - Verifies `list_by_applicant_id` supports status filtering.

### Verification Results

- Focused tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests/test_parking_application_service.py backend/tests/test_parking_applications_api.py backend/tests/test_repositories.py`
  - Result: `69 passed, 1 warning`
- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `265 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0005 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0004 -> 0005 (head), Add parking applications table.`
    - `0003 -> 0004, Add parking availabilities table.`
    - `0002 -> 0003, Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`

### Known Limitations

- Docker/PostgreSQL migration execution was not run because this task did not change schema, migrations, Docker, or Compose.
- There is no reservation/winner assignment yet.
- There is no fairness ranking or scheduled assignment worker yet.
- There is no owner/admin application management endpoint yet.
- There are no frontend parking screens yet.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement parking reservation domain groundwork: add `ParkingReservation` model, schemas, repository, Alembic migration, and focused tests for assigned parking reservations. Do not implement automatic winner selection, fairness ranking, scheduled workers, admin override flows, or frontend reservation screens yet.

## Task 21: Parking Reservation Domain Groundwork

### Files Changed

- `backend/alembic/versions/0006_add_parking_reservations.py`
- `backend/app/models/__init__.py`
- `backend/app/models/parking_application.py`
- `backend/app/models/parking_availability.py`
- `backend/app/models/parking_reservation.py`
- `backend/app/models/parking_spot.py`
- `backend/app/models/user.py`
- `backend/app/repositories/__init__.py`
- `backend/app/repositories/parking_reservations.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/parking_reservation.py`
- `backend/tests/test_alembic_config.py`
- `backend/tests/test_models.py`
- `backend/tests/test_repositories.py`
- `backend/tests/test_schemas.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `ParkingReservation` SQLAlchemy model.
- Added `ParkingReservationStatus` enum with `active`, `cancelled`, and `completed`.
- Added reservation relationships:
  - `ParkingReservation.availability`
  - `ParkingReservation.application`
  - `ParkingReservation.parking_spot`
  - `ParkingReservation.reserved_for_user`
  - `ParkingAvailability.reservation`
  - `ParkingApplication.reservation`
  - `ParkingSpot.reservations`
  - `User.parking_reservations`
- Added MVP cardinality constraints:
  - one reservation per availability through unique `availability_id`,
  - one reservation per application through unique nullable `application_id`.
- Kept `application_id` nullable to support future admin/manual assignment without an application.
- Added Pydantic v2 schemas:
  - `ParkingReservationBase`
  - `ParkingReservationCreate`
  - `ParkingReservationUpdate`
  - `ParkingReservationRead`
- Added schema validation for timezone-aware datetimes and `end_at > start_at`.
- Added `ParkingReservationRepository` with create, get, list, active-filtered list, update, and delete methods.
- Added Alembic migration `0006` for the `parking_reservations` table, enum, foreign keys, unique constraints, and indexes.

### Review Notes

- The implementation is limited to reservation domain groundwork only.
- No reservation assignment service, winner/fairness selection, scheduled worker, owner/admin reservation APIs, admin override flow, notification logic, or frontend screens were added.
- The repository remains database-focused and does not select winners, update applications, update availability status, check fairness, or prevent overlapping reservations beyond the declared constraints.
- The one-reservation-per-availability rule is enforced with `uq_parking_reservations_availability_id`.
- `application_id` is nullable for future manual/admin reservations, while `uq_parking_reservations_application_id` prevents a non-null application from producing more than one reservation.
- Reservation intervals are stored as timezone-aware datetimes and validated in schemas.
- Indexes cover user, spot, status, start/end, and composite lookup patterns needed by future reservation queries.

### Tests Added or Updated

- Updated `backend/tests/test_models.py`
  - Verifies metadata contains `parking_reservations`.
  - Verifies reservation columns, enum values, indexes, unique constraints, foreign keys, and relationships.
  - Extends SQLite persistence coverage to include reservation relationships.
- Updated `backend/tests/test_schemas.py`
  - Verifies reservation create/update/read schema behavior.
  - Verifies nullable `application_id`.
  - Verifies `end_at <= start_at` is rejected.
  - Verifies naive datetimes are rejected.
  - Verifies invalid identifiers are rejected.
  - Verifies update schema rejects explicit `null` for `status`.
- Updated `backend/tests/test_repositories.py`
  - Verifies create/get/get-by-availability/get-by-application/list/list-by-spot/list-by-user/list-active-by-user/list-active-by-spot/update/delete.
  - Verifies duplicate reservation for the same availability fails.
  - Verifies duplicate reservation for the same application fails.
  - Verifies missing records return `None`.
- Updated `backend/tests/test_alembic_config.py`
  - Verifies Alembic head is `0006`.
  - Verifies offline SQL includes the reservation enum, table, unique constraints, indexes, and revision marker.

### Verification Results

- Focused tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests/test_models.py backend/tests/test_schemas.py backend/tests/test_repositories.py backend/tests/test_alembic_config.py`
  - Result: `97 passed`
- Backend tests:
  - Command: `python -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `280 passed, 1 warning`
- Backend compile check:
  - Command: `python -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `python -m alembic -c backend/alembic.ini heads`
  - Result: `0006 (head)`
- Alembic history:
  - Command: `python -m alembic -c backend/alembic.ini history`
  - Result:
    - `0005 -> 0006 (head), Add parking reservations table.`
    - `0004 -> 0005, Add parking applications table.`
    - `0003 -> 0004, Add parking availabilities table.`
    - `0002 -> 0003, Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`
- Alembic offline SQL generation:
  - Command: `python -m alembic -c backend/alembic.ini upgrade head --sql`
  - Result: generated successfully and contained `CREATE TYPE parking_reservation_status AS ENUM`, `CREATE TABLE parking_reservations`, `uq_parking_reservations_availability_id`, `uq_parking_reservations_application_id`, `ix_parking_reservations_spot_start_end`, `ix_parking_reservations_user_status`, and `0006`.
- Backend Docker build:
  - Command: `docker-compose build backend`
  - Result: passed after approved Docker access.
- Docker PostgreSQL/backend startup:
  - Command: `docker-compose up -d db backend`
  - Result: passed after approved Docker Engine access; PostgreSQL became healthy and backend started.
- Docker PostgreSQL migration:
  - Command: `docker-compose run --rm backend alembic -c alembic.ini upgrade head`
  - Result: passed; Alembic ran `0005 -> 0006`.
- Docker PostgreSQL current revision:
  - Command: `docker-compose run --rm backend alembic -c alembic.ini current`
  - Result: `0006 (head)`.
- Backend health endpoint:
  - Command: `Invoke-RestMethod -Uri http://localhost:8000/health`
  - Result: `{"status":"ok","service":"Parking Management API","environment":"local"}`.
- Docker shutdown:
  - Command: `docker-compose down`
  - Result: passed; services stopped and volumes were preserved.

### Known Limitations

- No reservation assignment service exists yet.
- No automatic winner selection, fairness ranking, or scheduled worker exists yet.
- Creating a reservation does not yet update application or availability status.
- There are no owner/admin reservation endpoints or admin override flows yet.
- There are no frontend reservation screens yet.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement initial reservation assignment service groundwork: create a reservation from a selected/pending application, update the selected application and availability statuses, reject other pending applications, and add focused service tests. Do not implement fairness ranking, scheduled workers, admin override flows, reservation APIs, or frontend screens yet.

## Task 22: Initial Reservation Assignment Service Groundwork

### Files Changed

- `backend/app/repositories/parking_applications.py`
- `backend/app/services/__init__.py`
- `backend/app/services/parking_reservation_assignment.py`
- `backend/tests/test_parking_reservation_assignment_service.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `ParkingReservationAssignmentService` with `assign_availability(availability_id)`.
- Added service-level assignment exceptions without using `HTTPException`.
- Added `ParkingReservationAssignmentResult` to return the created reservation, selected application, rejected applications, and updated availability.
- Implemented MVP deterministic assignment behavior:
  - load availability,
  - require `open` availability status,
  - reject assignment when a reservation already exists for the availability,
  - load pending applications ordered by `created_at, id`,
  - select the oldest pending application,
  - create a `ParkingReservation`,
  - set selected application to `selected`,
  - set remaining pending applications to `rejected`,
  - set availability to `assigned`.
- Updated pending application repository ordering to `created_at, id` for deterministic assignment selection.
- Added rollback handling for SQLAlchemy `IntegrityError` during assignment writes.

### Review Notes

- The implementation is limited to reservation assignment service groundwork only.
- No fairness ranking, same-team priority, scheduled workers, reservation APIs, admin override endpoints, parking UI, or frontend screens were added.
- The service keeps business orchestration out of repositories and keeps HTTP concerns out of the service layer.
- Repository methods remain database-focused.
- The selected application and rejected applications are updated only after reservation creation succeeds.
- A pre-check uses `ParkingReservationRepository.get_by_availability_id`, and the existing unique `availability_id` constraint remains the final concurrency safety net.
- `IntegrityError` is caught and rolled back, then re-raised as a service-level `ParkingReservationAssignmentIntegrityError`.
- Row-level locking is not implemented yet; concurrent assignments against PostgreSQL should later use a transaction and locking strategy around availability/application selection.
- The temporary MVP assignment rule is explicitly documented as oldest pending application wins by `created_at, id`.

### Tests Added or Updated

- Added `backend/tests/test_parking_reservation_assignment_service.py`
  - Verifies one pending application creates a reservation with mirrored availability fields.
  - Verifies selected application becomes `selected`.
  - Verifies availability becomes `assigned`.
  - Verifies multiple pending applications choose the oldest `created_at`.
  - Verifies same-`created_at` applications use `id` as a deterministic tie-breaker.
  - Verifies non-selected pending applications become `rejected`.
  - Verifies cancelled, rejected, and selected applications are ignored.
  - Verifies missing availability, non-open availability, no pending applications, and existing reservation failures.
  - Verifies simulated reservation `IntegrityError` triggers rollback and preserves persisted availability/application state.

### Verification Results

- Focused tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_parking_reservation_assignment_service.py`
  - Result: `9 passed`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `289 passed, 1 warning`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads`
  - Result: `0006 (head)`
- Alembic history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result:
    - `0005 -> 0006 (head), Add parking reservations table.`
    - `0004 -> 0005, Add parking applications table.`
    - `0003 -> 0004, Add parking availabilities table.`
    - `0002 -> 0003, Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`

### Known Limitations

- Docker/PostgreSQL verification was not run for this task because no schema, migration, Docker, Compose, or PostgreSQL-specific SQL behavior changed.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.
- Concurrent assignment still needs a PostgreSQL transaction/locking design in a later task; this service currently relies on the existing unique reservation constraint as the final conflict guard.
- The assignment rule is intentionally simple and does not include fairness ranking or same-team priority yet.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement an initial reservation assignment API endpoint for authorized users/admins using `ParkingReservationAssignmentService`, dependency-injected database sessions, and focused API tests. Do not implement fairness ranking, scheduled workers, admin override flows, parking UI, or frontend screens yet.

## Task 23: Initial Reservation Assignment API Endpoint

### Files Changed

- `backend/app/routers/parking_availabilities.py`
- `backend/tests/test_parking_availabilities_api.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `POST /parking-availabilities/{availability_id}/assign`.
- Kept the endpoint in the existing parking availability router because assignment is triggered from an availability.
- Added dependency wiring for `ParkingReservationAssignmentService`.
- Added route-level owner/admin authorization:
  - admins can assign any availability,
  - availability owners can assign their own availability,
  - other authenticated users receive `403`.
- Added service error to HTTP mapping:
  - missing availability -> `404`,
  - non-open availability -> `409`,
  - no pending applications -> `409`,
  - existing reservation -> `409`,
  - integrity conflict -> `409`.
- Returned `ParkingReservationRead` with `201 Created` for successful assignments.
- Followed existing write endpoint transaction style:
  - commit after service success,
  - rollback on service failure,
  - refresh returned reservation before response serialization.

### Review Notes

- Router placement is consistent with existing `parking_availabilities` endpoint organization.
- The permission check runs before the assignment service mutates state.
- Missing/invalid token behavior remains delegated to `get_current_user` and returns `401`.
- Owner/admin permission failure returns `403` with the existing generic message.
- The route remains thin: permission and HTTP mapping are in the router; assignment mutation stays in `ParkingReservationAssignmentService`.
- No fairness ranking, same-team priority ranking, scheduled workers, admin override flows, notification logic, frontend screens, or parking UI were added.
- No migration, schema, Docker, or Compose changes were made.

### Tests Added or Updated

- Updated `backend/tests/test_parking_availabilities_api.py`
  - Verifies owner can assign an availability with one pending application.
  - Verifies admin can assign an availability owned by another user.
  - Verifies non-owner/non-admin receives `403`.
  - Verifies missing availability returns `404`.
  - Verifies non-open availability returns `409`.
  - Verifies open availability with no pending applications returns `409`.
  - Verifies existing reservation returns `409`.
  - Verifies successful assignment returns reservation payload without sensitive fields.
  - Verifies successful assignment changes availability status to `assigned`.
  - Verifies successful assignment changes selected application status to `selected`.
  - Verifies successful assignment rejects other pending applications.
  - Verifies cancelled/rejected applications are ignored.
  - Verifies oldest pending application wins using deterministic `created_at`.
  - Verifies missing token returns `401`.
  - Verifies invalid token returns `401`.

### Verification Results

- Focused assignment API tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_parking_availabilities_api.py`
  - Result: `29 passed, 1 warning`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `299 passed, 1 warning`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads`
  - Result: `0006 (head)`
- Alembic history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result:
    - `0005 -> 0006 (head), Add parking reservations table.`
    - `0004 -> 0005, Add parking applications table.`
    - `0003 -> 0004, Add parking availabilities table.`
    - `0002 -> 0003, Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`

### Known Limitations

- Docker/PostgreSQL verification was not run for this task because no schema, migration, Docker, Compose, or PostgreSQL-specific SQL behavior changed.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.
- The endpoint uses the current MVP oldest-pending assignment rule from the service; fairness ranking and same-team priority are still deferred.
- Concurrent assignment still needs a PostgreSQL transaction/row-locking design in a later task.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement initial reservation read API groundwork: add authenticated reservation listing/detail endpoints such as `GET /parking-reservations/my` and `GET /parking-reservations/{reservation_id}` using `ParkingReservationRepository`, with owner/applicant/admin visibility rules and focused API tests. Do not implement cancellation, overrides, fairness ranking, scheduled workers, or frontend screens yet.

## Task 24: Reservation Read API Groundwork

### Files Changed

- `backend/app/main.py`
- `backend/app/repositories/parking_reservations.py`
- `backend/app/routers/admin_parking_reservations.py`
- `backend/app/routers/parking_reservations.py`
- `backend/tests/test_parking_reservations_api.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added authenticated reservation read endpoints:
  - `GET /parking-reservations/my`
  - `GET /parking-reservations/{reservation_id}`
- Added admin-only reservation list endpoint:
  - `GET /admin/parking-reservations`
- Registered the new routers in `backend/app/main.py`.
- Added user reservation list pagination with `skip` and `limit`.
- Added optional reservation `status` filter for the current user's reservation list.
- Added admin list pagination and filters:
  - `status`
  - `reserved_for_user_id`
  - `parking_spot_id`
- Added repository-level list filters for `reserved_for_user_id` and `parking_spot_id`.
- Implemented read visibility rules for reservation detail:
  - reserved user can view their reservation,
  - availability owner can view the reservation for their published availability,
  - admin can view any reservation,
  - unrelated authenticated users receive `403`.

### Review Notes

- Router placement follows the current backend convention:
  - public authenticated reservation reads in `parking_reservations.py`,
  - admin-only reservation listing in `admin_parking_reservations.py`.
- Relationship loading is handled by `ParkingReservationRepository.get_by_id` through existing `selectinload` loaders, so availability owner checks do not rely on lazy loading.
- Repository changes remain database-focused and contain no business assignment, fairness, cancellation, or override logic.
- Pagination and filters are applied at the query level.
- Error handling uses generic responses:
  - missing/invalid token -> `401` through `get_current_user`,
  - forbidden visibility -> `403`,
  - missing reservation -> `404`.
- Response models use `ParkingReservationRead`, so related models and sensitive user fields are not exposed.
- No reservation cancellation, admin override flows, fairness ranking, scheduled workers, notifications, frontend screens, migrations, Docker, or Compose changes were added.

### Tests Added or Updated

- Added `backend/tests/test_parking_reservations_api.py`
  - Verifies authenticated users can list their own reservations.
  - Verifies own-reservations list does not return another user's reservations.
  - Verifies `status` filter works for `GET /parking-reservations/my`.
  - Verifies a reserved user can view their own reservation.
  - Verifies an availability owner can view the reservation for their published availability.
  - Verifies an admin can view any reservation.
  - Verifies an unrelated user receives `403`.
  - Verifies missing reservation returns `404`.
  - Verifies missing token returns `401`.
  - Verifies invalid token returns `401`.
  - Verifies admin reservation list works with `status`, `reserved_for_user_id`, and `parking_spot_id` filters.
  - Verifies non-admin users cannot access the admin reservation list.

### Verification Results

- Focused reservation API tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_parking_reservations_api.py`
  - Result: `11 passed, 1 warning`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `310 passed, 1 warning`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads`
  - Result: `0006 (head)`
- Alembic history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result:
    - `0005 -> 0006 (head), Add parking reservations table.`
    - `0004 -> 0005, Add parking applications table.`
    - `0003 -> 0004, Add parking availabilities table.`
    - `0002 -> 0003, Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`

### Known Limitations

- Docker/PostgreSQL verification was not run for this task because no schema, migration, Docker, Compose, or PostgreSQL-specific SQL behavior changed.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.
- Reservation cancellation and admin override flows are not implemented yet.
- Fairness ranking, same-team priority ranking, scheduled workers, notifications, and frontend screens remain deferred.
- Concurrent assignment row locking remains a future assignment-service concern and was not changed by this read-only API task.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement assignment ranking groundwork: add a reusable candidate ranking component for same-team priority and recent-win fairness inputs, with focused service tests, but do not wire it into scheduled workers, admin overrides, reservation cancellation, or frontend screens yet.

## Task 25: Assignment Ranking Groundwork

### Files Changed

- `backend/app/services/__init__.py`
- `backend/app/services/parking_application_ranking.py`
- `backend/app/services/parking_reservation_assignment.py`
- `backend/tests/test_parking_application_ranking_service.py`
- `backend/tests/test_parking_reservation_assignment_service.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `ParkingApplicationRankingService` as a reusable ranking boundary for assignment candidate selection.
- Replaced the temporary oldest-pending-only selection in `ParkingReservationAssignmentService` with ranking-service selection.
- Implemented the MVP ranking policy:
  - while `now <= availability.priority_until`, applicants from the same team as the availability owner rank before non-same-team applicants,
  - after `priority_until`, all pending applicants are treated equally regardless of team,
  - `priority_until = None` means no active same-team priority window,
  - within the same priority group, oldest `created_at` wins,
  - equal `created_at` falls back to lowest application `id`.
- Added injectable `now_provider` to the ranking service for deterministic tests.
- Added timezone normalization for ranking comparisons, including SQLite-style naive datetime values.
- Kept future fairness extensibility documented in the ranking service docstring:
  - fewer recent wins,
  - cooldown after winning,
  - weighted random among eligible candidates,
  - richer team-priority window rules.
- Updated assignment rejection behavior to reject every pending application except the ranked winner, instead of assuming the first repository row is always the winner.

### Review Notes

- Ranking logic is separate from reservation creation and status mutation.
- Assignment service still owns orchestration and preserves existing service-level exceptions and `IntegrityError` rollback behavior.
- Repository queries already load the required relationships:
  - `ParkingAvailabilityRepository.get_by_id` loads the availability owner,
  - `ParkingApplicationRepository.list_pending_by_availability_id` loads applicants.
- Ranking only requires scalar `team_id` values from loaded owner/applicant records; no team relationship loading or async lazy loading is needed.
- Same-team priority is active at the exact `priority_until` boundary because the rule is `now <= priority_until`.
- Owner without a team does not create a same-team priority group.
- No fairness history tables, scheduled workers, admin override flows, notification logic, frontend screens, Docker changes, Compose changes, schema changes, or migrations were added.

### Tests Added or Updated

- Added `backend/tests/test_parking_application_ranking_service.py`
  - Verifies same-team applicant beats an earlier non-team applicant before `priority_until`.
  - Verifies same-team priority remains active at exactly `priority_until`.
  - Verifies oldest same-team applicant wins among same-team applicants.
  - Verifies oldest pending applicant wins during the priority window when no same-team applicants exist.
  - Verifies oldest pending applicant wins after `priority_until` regardless of team.
  - Verifies `priority_until = None` disables same-team priority.
  - Verifies equal `created_at` falls back to lowest application `id`.
  - Verifies cancelled/rejected/selected applications are excluded by the pending repository filter before ranking.
- Updated `backend/tests/test_parking_reservation_assignment_service.py`
  - Injects deterministic ranking time for assignment service tests.
  - Verifies assignment uses same-team priority before `priority_until`.
  - Verifies assignment uses first-applied ordering after `priority_until`.
  - Preserves existing reservation payload/status/rejection/error coverage.

### Verification Results

- Focused ranking and assignment tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_parking_application_ranking_service.py backend/tests/test_parking_reservation_assignment_service.py`
  - Result: `19 passed`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `320 passed, 1 warning`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads`
  - Result: `0006 (head)`
- Alembic history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result:
    - `0005 -> 0006 (head), Add parking reservations table.`
    - `0004 -> 0005, Add parking applications table.`
    - `0003 -> 0004, Add parking availabilities table.`
    - `0002 -> 0003, Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`

### Known Limitations

- Docker/PostgreSQL verification was not run for this task because no schema, migration, Docker, Compose, or PostgreSQL-specific SQL behavior changed.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.
- The ranking policy is still MVP-level and does not count recent wins or apply cooldown limits.
- No fairness history/audit tables exist yet.
- Concurrent assignment row locking remains a future assignment-service concern.
- Scheduled workers, admin override flows, notifications, reservation cancellation, and frontend screens remain deferred.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement assignment transaction and PostgreSQL row-locking groundwork: add a repository/service path that can lock an availability during assignment and document/test duplicate-assignment behavior where feasible. Do not add scheduled workers, admin override flows, reservation cancellation, notifications, or frontend screens yet.

## Task 26: Assignment Transaction and PostgreSQL Row-Locking Groundwork

### Files Changed

- `backend/app/repositories/parking_applications.py`
- `backend/app/repositories/parking_availabilities.py`
- `backend/app/services/parking_reservation_assignment.py`
- `backend/tests/test_parking_reservation_assignment_service.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `ParkingAvailabilityRepository.get_by_id_for_update`.
- Added `ParkingApplicationRepository.list_pending_by_availability_id_for_update`.
- Added shared pending-application statement construction so normal and lock-enabled queries preserve the same pending filter and deterministic ordering.
- Updated `ParkingReservationAssignmentService.assign_availability` to:
  - lock the availability row before validating assignment state,
  - check for an existing reservation after acquiring the availability lock,
  - lock all pending application rows used by the assignment,
  - preserve the existing ranking policy,
  - preserve reservation/application/availability status mutation behavior.
- Improved duplicate assignment conflict handling:
  - existing reservation before assignment still raises `ParkingReservationAssignmentReservationExistsError`,
  - the unique reservation constraint remains the final duplicate protection,
  - after an `IntegrityError`, the service rolls back the failed transaction,
  - if a reservation now exists for the availability, the conflict maps to `ParkingReservationAssignmentReservationExistsError`,
  - other integrity conflicts map to `ParkingReservationAssignmentIntegrityError`.

### Transaction Boundary

- The assignment API route remains the owner of the successful transaction boundary.
- The route commits only after the complete assignment service flow succeeds.
- Repositories perform flush/refresh operations but do not commit.
- All reservation creation, application status updates, and availability status updates therefore occur in one database transaction.
- The route rolls back service-level assignment failures.
- The assignment service performs an immediate rollback only after `IntegrityError`, because SQLAlchemy sessions cannot be queried safely until the failed transaction is rolled back. This also allows the service to determine whether the integrity conflict represents a duplicate reservation race.

### Review Notes

- PostgreSQL `FOR UPDATE OF parking_availabilities` serializes assignment attempts for the same availability.
- Pending application rows are locked with `FOR UPDATE OF parking_applications` while their statuses are selected/rejected.
- Lock scope is limited to the availability and pending application rows needed by assignment.
- SQLite safely executes the lock-enabled repository methods but does not enforce real row-level locks.
- The existing `uq_parking_reservations_availability_id` unique constraint remains the final duplicate-assignment safety net.
- Ranking behavior was not changed.
- No scheduled workers, admin override flows, reservation cancellation, notifications, frontend screens, new tables, schema changes, migrations, Docker changes, or Compose changes were added.

### Tests Added or Updated

- Updated `backend/tests/test_parking_reservation_assignment_service.py`
  - Verifies successful assignment uses the lock-enabled availability and pending-application repository paths.
  - Verifies lock-enabled methods execute successfully with SQLite.
  - Verifies generated PostgreSQL SQL contains:
    - `FOR UPDATE OF parking_availabilities`
    - `FOR UPDATE OF parking_applications`
  - Verifies an `IntegrityError` after reservation creation and selected-application mutation rolls back all assignment changes.
  - Verifies rollback leaves availability `open`, applications `pending`, and no reservation persisted after simulated partial failure.
  - Verifies a simulated duplicate-reservation race maps to `ParkingReservationAssignmentReservationExistsError`.
  - Preserves existing successful assignment, ranking, existing reservation, and generic integrity conflict coverage.

### Verification Results

- Focused transaction/ranking/assignment tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_parking_reservation_assignment_service.py backend/tests/test_parking_application_ranking_service.py`
  - Result: `23 passed`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `324 passed, 1 warning`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads`
  - Result: `0006 (head)`
- Alembic history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result:
    - `0005 -> 0006 (head), Add parking reservations table.`
    - `0004 -> 0005, Add parking applications table.`
    - `0003 -> 0004, Add parking availabilities table.`
    - `0002 -> 0003, Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`

### Known Limitations

- A live two-session PostgreSQL concurrency test was not added or run in this task.
- PostgreSQL row-lock SQL was verified by compiling the lock-enabled SQLAlchemy statements with the PostgreSQL dialect.
- SQLite tests verify method compatibility and rollback behavior but cannot enforce or prove real row-level lock contention.
- A concurrent application submission that races with assignment may need additional locking/validation work in a later task.
- Docker/PostgreSQL runtime verification was not run because no schema, migration, Docker, or Compose files changed, and the requested PostgreSQL lock syntax was verified through dialect compilation.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.
- Scheduled workers, admin override flows, notifications, reservation cancellation, and frontend screens remain deferred.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement recent-win fairness ranking and soft-win-limit groundwork using existing reservation history, with focused repository/ranking/assignment tests. Do not add scheduled workers, admin override flows, reservation cancellation, notifications, frontend screens, or new fairness tables yet.

## Task 27: Scheduled Assignment Groundwork

### Files Changed

- `backend/app/commands/__init__.py`
- `backend/app/commands/assign_due_availabilities.py`
- `backend/app/repositories/parking_availabilities.py`
- `backend/app/services/__init__.py`
- `backend/app/services/parking_assignment_scheduler.py`
- `backend/tests/test_parking_assignment_scheduler.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `ParkingAvailabilityRepository.list_assignable` to identify assignment candidates that:
  - are open,
  - have a non-null `priority_until` at or before the supplied current time,
  - have an `end_at` still in the future,
  - have at least one pending application,
  - do not already have a reservation.
- Used correlated `EXISTS` and `NOT EXISTS` queries so candidate filtering remains database-focused without duplicating assignment business rules.
- Added `ParkingAssignmentSchedulerService.assign_due_availabilities`:
  - accepts an injectable current time and batch limit,
  - calls the existing `ParkingReservationAssignmentService` for every candidate,
  - commits each successful assignment independently,
  - rolls back and continues after a stale/skipped or failed assignment,
  - returns deterministic processed, assigned, skipped, failed, and generic issue details.
- Added the import-safe, one-shot command:
  - `python -m app.commands.assign_due_availabilities`
  - optional batch limit: `python -m app.commands.assign_due_availabilities --limit 100`
- The command prints a concise batch summary and returns a non-zero exit status only when the batch cannot start or complete because of a fatal error.

### Manual Docker Command

- Run one assignment batch:
  - `docker compose exec backend python -m app.commands.assign_due_availabilities`
- Run one limited assignment batch:
  - `docker compose exec backend python -m app.commands.assign_due_availabilities --limit 100`

### Review Notes

- The repository method only identifies assignable candidates; it does not rank applicants, create reservations, or mutate statuses.
- The scheduler reuses the existing assignment service and therefore preserves its ranking policy, validation, row locking, duplicate-reservation protection, and status transitions.
- Candidate IDs are copied before processing so per-candidate commits and rollbacks do not invalidate the candidate iteration.
- Each candidate is reloaded, locked, and revalidated by the assignment service, allowing candidates that become stale after the initial query to be skipped safely.
- Known stale-state assignment errors are counted as skipped. Other assignment-service errors and unexpected per-candidate errors are counted as failed.
- Failure details expose only stable generic codes and do not leak exception messages or internal database information.
- No ranking changes, long-running worker framework, scheduler container, frontend work, notifications, admin overrides, schema changes, migrations, Docker changes, or Compose changes were added.

### Tests Added or Updated

- Added `backend/tests/test_parking_assignment_scheduler.py`
  - Verifies the assignable repository query includes only due, open, future-ending availabilities with pending applications and no reservation.
  - Verifies availabilities before `priority_until`, with `priority_until = None`, with past `end_at`, without pending applications, or with an existing reservation are excluded.
  - Verifies a due candidate is assigned with correct reservation, availability, and application state.
  - Verifies assignment ranking is reused at the priority-window boundary rather than duplicated in the scheduler.
  - Verifies multiple candidates are processed in deterministic batches with a limit.
  - Verifies one unexpected assignment failure rolls back and does not stop later candidates.
  - Verifies a candidate that becomes stale is skipped and does not stop later candidates.
  - Verifies the command is safe to import, passes the requested limit, prints the concise summary, and returns non-zero for a fatal error.

### Verification Results

- Focused scheduled-assignment tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_parking_assignment_scheduler.py`
  - Result: `8 passed in 1.77s`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `332 passed, 1 warning in 90.94s`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads`
  - Result: `0006 (head)`
- Alembic history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result:
    - `0005 -> 0006 (head), Add parking reservations table.`
    - `0004 -> 0005, Add parking applications table.`
    - `0003 -> 0004, Add parking availabilities table.`
    - `0002 -> 0003, Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`

### Known Limitations

- The command is one-shot and must be invoked manually or by an external scheduler such as cron; no daemon or background worker framework was added.
- The initial candidate-list query does not lock the entire batch. Each candidate is instead locked and revalidated by the assignment service immediately before assignment.
- Candidates can become stale between the list query and assignment; these are rolled back, reported with a generic skip code, and do not stop the batch.
- Unexpected per-candidate exceptions are intentionally converted to a generic failure issue so remaining candidates can be processed.
- Docker/PostgreSQL runtime verification was not run because this task did not change schema, migrations, Docker, Compose, or PostgreSQL-specific SQL behavior.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.
- Notifications, admin override flows, reservation cancellation, frontend screens, and long-running scheduling remain deferred.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement recent-win fairness ranking and soft-win-limit groundwork using existing reservation history, with focused repository/ranking/assignment tests. Do not add a long-running worker framework, admin override flows, reservation cancellation, notifications, frontend screens, or new fairness tables yet.

## Task 28: Recent-Win Fairness Ranking Groundwork

### Files Changed

- `.env.example`
- `backend/.env.example`
- `docker-compose.yml`
- `backend/app/core/config.py`
- `backend/app/repositories/parking_reservations.py`
- `backend/app/services/parking_application_ranking.py`
- `backend/app/services/parking_reservation_assignment.py`
- `backend/tests/test_infrastructure_files.py`
- `backend/tests/test_parking_application_ranking_service.py`
- `backend/tests/test_parking_assignment_scheduler.py`
- `backend/tests/test_parking_reservation_assignment_service.py`
- `backend/tests/test_parking_reservation_fairness_repository.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added configurable `RECENT_WIN_FAIRNESS_WINDOW_DAYS`:
  - default: `30`,
  - validated as at least one day,
  - included in root/backend environment examples and the backend Compose environment.
- Added `ParkingReservationRepository.count_recent_wins_by_user_ids`:
  - performs one grouped query for all requested applicants,
  - counts only `active` and `completed` reservations,
  - ignores `cancelled` reservations,
  - uses inclusive `start_at >= since` filtering,
  - returns zero for requested users without recent wins,
  - removes duplicate requested user IDs.
- Integrated recent-win counts into `ParkingApplicationRankingService`.
- Updated ranking order to:
  1. same-team priority group while `now <= priority_until`,
  2. recent win count ascending,
  3. application `created_at` ascending,
  4. application ID ascending.
- Added injectable recent-win count provider and settings dependency so ranking tests remain deterministic.
- Updated the default `ParkingReservationAssignmentService` construction path to use the reservation repository's recent-win count provider automatically.
- Preserved all existing assignment status transitions, row locking, reservation creation, and duplicate-assignment behavior.

### Recent-Win Definition

- Fairness counts use reservation `start_at`, because it represents the actual reserved parking period more directly than record creation time.
- A reservation counts when:
  - its status is `active` or `completed`, and
  - its `start_at` is at or after `now - RECENT_WIN_FAIRNESS_WINDOW_DAYS`.
- Active upcoming reservations also count as committed wins because the query intentionally uses an inclusive lower-bound lookback without an upper-bound date.

### Review Notes

- Same-team priority remains the first ranking key and cannot be overridden by a lower recent-win count from another team while the priority window is active.
- After the priority window, team membership no longer affects ranking.
- The reservation repository remains database-focused and returns only aggregate counts.
- The grouped count query avoids one query per applicant and remains compatible with SQLite and PostgreSQL.
- The ranking service calls the count provider once per candidate pool and defaults missing provider-map entries to zero.
- The assignment service's normal API and scheduled-command construction paths receive fairness behavior automatically through the default ranking service.
- Custom ranking services can still be injected for deterministic or alternative policies.
- No status transitions, database schema, migrations, new tables, scheduled-worker behavior, admin overrides, frontend screens, notifications, or random/weighted selection were added.

### Tests Added or Updated

- Added `backend/tests/test_parking_reservation_fairness_repository.py`
  - Verifies recent active and completed reservations count.
  - Verifies cancelled reservations and reservations outside the lookback window do not count.
  - Verifies users without wins receive zero and duplicate input IDs are handled.
  - Verifies empty input avoids unnecessary query behavior and returns an empty map.
- Updated `backend/tests/test_parking_application_ranking_service.py`
  - Verifies same-team priority still beats a non-team applicant with fewer wins.
  - Verifies fewer recent wins wins among same-team applicants.
  - Verifies fewer recent wins wins among non-team applicants when no same-team applicants exist.
  - Verifies fewer recent wins wins regardless of team after the priority window.
  - Verifies equal win counts fall back to oldest application time.
  - Verifies equal win counts and application times fall back to lowest application ID.
  - Verifies missing count-map entries default to zero.
  - Verifies the count provider receives the configured lookback boundary.
- Updated `backend/tests/test_parking_reservation_assignment_service.py`
  - Verifies the normal default assignment-service path selects the candidate with fewer recent wins.
  - Verifies reservation creation, selected/rejected application states, and assigned availability state remain correct.
- Updated scheduler and infrastructure tests to use and verify the new fairness provider/configuration.

### Verification Results

- Focused fairness, ranking, assignment, scheduler, and infrastructure tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_parking_reservation_fairness_repository.py backend/tests/test_parking_application_ranking_service.py backend/tests/test_parking_reservation_assignment_service.py backend/tests/test_parking_assignment_scheduler.py backend/tests/test_infrastructure_files.py`
  - Result: `46 passed in 2.73s`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `341 passed, 1 warning in 83.30s`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads`
  - Result: `0006 (head)`
- Alembic history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result:
    - `0005 -> 0006 (head), Add parking reservations table.`
    - `0004 -> 0005, Add parking applications table.`
    - `0003 -> 0004, Add parking availabilities table.`
    - `0002 -> 0003, Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`
- Docker Compose configuration:
  - Command: `docker compose config`
  - Result: unavailable because the installed Docker CLI does not support the `docker compose` subcommand and cannot read `C:\Users\nikola.milosevic\.docker\config.json`.
  - Fallback command: `docker-compose config`
  - Result: passed and resolved `RECENT_WIN_FAIRNESS_WINDOW_DAYS` to `"30"`; the Docker config-file access warning remained.

### Known Limitations

- The recent-win rule is a ranking input only; a configurable soft win limit is not implemented yet.
- Ranking inputs and candidate counts are not persisted as assignment audit details.
- Active upcoming reservations count as committed wins even when their `start_at` is in the future.
- The fairness window is process/environment configuration rather than database-managed configuration.
- No live Docker/PostgreSQL runtime test was run. Compose syntax was verified with `docker-compose config`, and the grouped query was exercised with SQLite.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.
- Admin override flows, audit logs, notifications, frontend screens, reservation cancellation, and random/weighted selection remain deferred.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement configurable soft recent-win-limit groundwork: within each existing priority group, prefer applicants below the soft limit when at least one is below it, but fall back to the normal recent-win/application-time ranking when every applicant in that group has reached the limit. Add focused ranking and assignment tests without adding audit tables, admin overrides, frontend screens, notifications, or random selection.

## Task 29: Configurable Soft Recent-Win-Limit Groundwork

### Files Changed

- `.env.example`
- `backend/.env.example`
- `docker-compose.yml`
- `backend/app/core/config.py`
- `backend/app/services/parking_application_ranking.py`
- `backend/tests/test_infrastructure_files.py`
- `backend/tests/test_parking_application_ranking_service.py`
- `backend/tests/test_parking_assignment_scheduler.py`
- `backend/tests/test_parking_reservation_assignment_service.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added configurable `RECENT_WIN_SOFT_LIMIT`:
  - default: `2`,
  - validated as at least one,
  - included in root/backend environment examples and the backend Compose environment.
- Added an explicit soft-limit bucket to `ParkingApplicationRankingService`.
- Updated ranking order to:
  1. same-team priority group while `now <= priority_until`,
  2. below-soft-limit applicants before applicants at or above the soft limit,
  3. recent win count ascending,
  4. application `created_at` ascending,
  5. application ID ascending.
- An applicant is in the lower-priority soft-limit bucket when:
  - `recent_win_count >= RECENT_WIN_SOFT_LIMIT`.
- Preserved existing assignment and scheduler integration because both already delegate selection to the shared ranking service.
- Preserved all application eligibility, reservation creation, locking, and status-transition behavior.

### Soft-Limit Behavior

- The soft limit never blocks, rejects, or removes an application from the candidate pool.
- A candidate at or above the soft limit can still win when:
  - the candidate is the only applicant,
  - every applicant in the same team-priority group is at or above the limit,
  - the candidate is in a stronger same-team priority group than lower-win non-team applicants during the priority window.
- When every applicant in a team-priority group is at or above the limit, the shared bucket value ties and ranking falls back to recent win count, application time, and application ID.

### Review Notes

- Same-team priority remains the first and strongest ranking key during the priority window.
- After the priority window, all candidates share the same team-priority rank and the soft-limit bucket applies globally.
- The exact threshold boundary is explicit: a count equal to the configured limit is in the lower-priority bucket.
- The soft-limit bucket is intentionally a ranking-only policy and does not introduce hard application blocking.
- With the current ascending recent-win-count tie-breaker, the threshold bucket is mathematically consistent with and does not reverse the previous count-based ordering. It makes the soft-limit policy explicit and provides a stable extension boundary without changing eligibility.
- The scheduler continues to reuse the assignment service and ranking service; no fairness logic was duplicated in scheduler code.
- No repository changes, database schema changes, migrations, new tables, status-transition changes, scheduled-worker changes, admin overrides, frontend screens, notifications, or random/weighted selection were added.

### Tests Added or Updated

- Updated `backend/tests/test_parking_application_ranking_service.py`
  - Verifies an applicant below the soft limit ranks before an applicant exactly at the limit.
  - Verifies an applicant below the soft limit ranks before an applicant above the limit.
  - Verifies fewer recent wins still wins when both applicants are below the limit.
  - Verifies fewer recent wins still wins when both applicants are at or above the limit.
  - Verifies an applicant at the soft limit can still win as the only candidate.
  - Verifies a custom soft-limit setting changes the threshold boundary.
  - Preserves coverage proving:
    - equal recent wins fall back to oldest application time,
    - equal wins and time fall back to lowest application ID,
    - same-team priority remains stronger than soft-limit status,
    - team membership no longer matters after the priority window.
- Updated `backend/tests/test_parking_reservation_assignment_service.py`
  - Verifies the normal assignment-service path selects a below-limit candidate over an earlier candidate exactly at the default limit.
  - Verifies reservation creation, selected/rejected application states, and assigned availability state remain correct.
- Updated `backend/tests/test_parking_assignment_scheduler.py`
  - Verifies the scheduler delegates soft-limit selection to the existing assignment/ranking services.
- Updated `backend/tests/test_infrastructure_files.py`
  - Verifies the default and custom setting values, environment examples, and Compose environment.

### Verification Results

- Focused soft-limit ranking, assignment, scheduler, and infrastructure tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_parking_application_ranking_service.py backend/tests/test_parking_reservation_assignment_service.py backend/tests/test_parking_assignment_scheduler.py backend/tests/test_infrastructure_files.py`
  - Result: `52 passed in 3.39s`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `349 passed, 1 warning in 90.27s`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads`
  - Result: `0006 (head)`
- Alembic history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result:
    - `0005 -> 0006 (head), Add parking reservations table.`
    - `0004 -> 0005, Add parking applications table.`
    - `0003 -> 0004, Add parking availabilities table.`
    - `0002 -> 0003, Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`
- Docker Compose configuration:
  - Command: `docker compose config`
  - Result: unavailable because the installed Docker CLI does not support the `docker compose` subcommand and cannot read `C:\Users\nikola.milosevic\.docker\config.json`.
  - Fallback command: `docker-compose config`
  - Result: passed and resolved `RECENT_WIN_SOFT_LIMIT` to `"2"`; the Docker config-file access warning remained.

### Known Limitations

- Because the soft-limit bucket is followed by ascending recent-win count, it currently makes the threshold policy explicit without changing winners compared with pure ascending recent-win-count ordering.
- Soft-limit status and fairness ranking inputs are not persisted as assignment audit details.
- The soft limit and fairness window are process/environment configuration rather than database-managed configuration.
- No live Docker/PostgreSQL runtime test was run because no schema, migration, or PostgreSQL-specific SQL behavior changed.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.
- Admin override flows, audit logs, notifications, frontend screens, reservation cancellation, and random/weighted selection remain deferred.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement assignment audit-details groundwork: define and persist the assignment method and enough deterministic fairness decision context to explain automatic selections, with focused model/repository/service tests. Do not implement admin override endpoints, frontend screens, notifications, or random selection yet.

## Task 30: Assignment Audit-Details Groundwork

### Files Changed

- `backend/app/services/parking_application_ranking.py`
- `backend/app/services/parking_reservation_assignment.py`
- `backend/tests/test_parking_application_ranking_service.py`
- `backend/tests/test_parking_availabilities_api.py`
- `backend/tests/test_parking_reservation_assignment_service.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added immutable internal ranking audit result types:
  - `ParkingApplicationRankingAuditDetail`,
  - `ParkingApplicationRankingResult`.
- Added `ParkingApplicationRankingService.rank_applications_with_audit`.
- Ranking now produces the selected application, complete ordered candidate pool, and deterministic audit details in one computation.
- Each candidate audit detail includes:
  - application ID,
  - applicant ID,
  - applicant team ID,
  - owner team ID,
  - same-team flag,
  - team-priority-active flag,
  - recent win count,
  - at-or-over-soft-limit flag,
  - application creation time,
  - full ranking-order values,
  - final one-based rank position,
  - selected flag.
- Existing ranking convenience methods now delegate to the audited ranking path:
  - `select_winning_application` returns the audited result's winner,
  - `rank_applications_for_availability` returns the audited ordered candidate pool while preserving empty-list behavior.
- Added internal assignment audit types:
  - `ParkingReservationAssignmentMethod`,
  - `ParkingReservationAssignmentAuditDetails`.
- Extended `ParkingReservationAssignmentResult` with:
  - automatic assignment method,
  - selected application ID,
  - rejected application IDs,
  - complete candidate ranking audit details.
- Preserved the public assignment API response shape. The endpoint still returns only `ParkingReservationRead`.

### Audit Design Decision

- Audit details are computed during assignment and returned through the internal service result.
- No database table, reservation column, schema change, migration, or public audit endpoint was added.
- This keeps assignment decisions explainable to internal callers now while leaving persistent audit logs and optional API exposure for a later task.
- The internal ranking-order tuple records the exact sort inputs in policy order:
  1. team-priority rank,
  2. soft-limit bucket rank,
  3. recent win count,
  4. application creation time,
  5. application ID.

### Review Notes

- Winner selection and candidate audit details are generated from the same sorted candidate list, preventing audit/selection divergence.
- The ranking policy did not change.
- The assignment service still creates the same reservation and performs the same selected/rejected/assigned status transitions.
- Audit details include every pending application considered during assignment and exclude non-pending applications.
- Audit details do not include passwords, password hashes, emails, usernames, names, free-text notes, tokens, or database exception details.
- `is_same_team_as_owner` is true only when the owner has a team and the applicant's team matches it.
- `team_priority_active` records the window state independently from the candidate's same-team flag.
- A recent win count equal to the soft limit is recorded as `is_over_soft_limit = true`, matching the existing soft-limit bucket rule.
- Scheduler callers continue to ignore the assignment result and therefore remain compatible without exposing audit details.
- No persistent audit storage, API response changes, scheduler behavior changes, migrations, admin overrides, frontend screens, notifications, or fairness policy changes were added.

### Tests Added or Updated

- Updated `backend/tests/test_parking_application_ranking_service.py`
  - Verifies audit details include every considered candidate in final rank order.
  - Verifies selected and rejected candidate flags and deterministic rank positions.
  - Verifies team-priority-active behavior at the exact priority boundary and after the window.
  - Verifies same-team flags, owner/applicant team IDs, recent win counts, soft-limit flags, creation times, and full ranking-order values.
  - Verifies the audited ranking order matches the actual selected application.
- Updated `backend/tests/test_parking_reservation_assignment_service.py`
  - Verifies automatic assignment method, selected application ID, rejected application IDs, complete candidate rankings, rank positions, and selected flags.
  - Preserves existing reservation and status-transition assertions.
- Updated `backend/tests/test_parking_availabilities_api.py`
  - Verifies the assignment endpoint still returns exactly the existing reservation response fields and does not expose internal audit details.
- Existing focused scheduler tests verify assignment still succeeds and selects the expected candidate with the updated internal assignment result.

### Verification Results

- Focused audit, ranking, assignment, scheduler, and API compatibility tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_parking_application_ranking_service.py backend/tests/test_parking_reservation_assignment_service.py backend/tests/test_parking_assignment_scheduler.py backend/tests/test_parking_availabilities_api.py`
  - Result: `76 passed, 1 warning in 21.38s`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `351 passed, 1 warning in 88.77s`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads`
  - Result: `0006 (head)`
- Alembic history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result:
    - `0005 -> 0006 (head), Add parking reservations table.`
    - `0004 -> 0005, Add parking applications table.`
    - `0003 -> 0004, Add parking availabilities table.`
    - `0002 -> 0003, Add parking spots table.`
    - `0001 -> 0002, Add teams and users tables.`
    - `<base> -> 0001, Initial migration scaffold.`

### Known Limitations

- Audit details are ephemeral and are not persisted after the assignment service call completes.
- No endpoint exposes audit details yet; future admin or audit endpoints can map the internal immutable result to dedicated response schemas.
- The internal ranking-order values include a datetime and would require explicit JSON serialization before persistent JSON storage or API exposure.
- Only the `automatic` assignment method exists; manual and admin-override methods remain deferred.
- Docker/PostgreSQL runtime verification was not run because this task did not change schema, migrations, Docker, Compose, or PostgreSQL-specific SQL behavior.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.
- Persistent audit logs, admin override flows, frontend screens, notifications, and random/weighted selection remain deferred.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.

### Next Suggested Task

Implement persistent audit-log groundwork with an `AuditLog` model, migration, repository, and automatic-assignment audit recording that serializes the existing internal decision details. Do not implement admin override endpoints, frontend screens, notifications, or random selection yet.

## Task 31: Persistent Assignment Audit-Log Groundwork

### Files Changed

- `backend/app/models/parking_assignment_audit_log.py`
- `backend/app/models/__init__.py`
- `backend/app/schemas/parking_assignment_audit_log.py`
- `backend/app/schemas/__init__.py`
- `backend/app/repositories/parking_assignment_audit_logs.py`
- `backend/app/repositories/__init__.py`
- `backend/alembic/versions/0007_add_parking_assignment_audit_logs.py`
- `backend/app/services/parking_reservation_assignment.py`
- `backend/app/services/parking_assignment_scheduler.py`
- `backend/app/routers/parking_availabilities.py`
- `backend/tests/test_parking_assignment_audit_log.py`
- `backend/tests/test_models.py`
- `backend/tests/test_alembic_config.py`
- `backend/tests/test_parking_reservation_assignment_service.py`
- `backend/tests/test_parking_assignment_scheduler.py`
- `backend/tests/test_parking_availabilities_api.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `ParkingAssignmentAuditLog` with:
  - availability, reservation, selected application, and selected user foreign keys,
  - rejected application IDs,
  - ranking policy version/name,
  - complete serialized ranking details,
  - assignment trigger source,
  - creation timestamp.
- Added `ParkingAssignmentTriggerSource` values:
  - `system` for direct service calls that do not provide a source,
  - `manual_owner`,
  - `manual_admin`,
  - `scheduled`.
- Added a unique constraint on `reservation_id` to enforce one audit log per reservation assignment.
- Added indexes for availability, reservation, selected application, selected user, and creation time.
- Added Pydantic v2 create/read schemas that expose only non-sensitive audit data and serialize JSON details cleanly.
- Added `ParkingAssignmentAuditLogRepository` with create, lookup, paginated list, and selected-user list operations.
- Added Alembic revision `0007` with the PostgreSQL trigger-source enum, audit-log table, constraints, foreign keys, and indexes.
- Integrated audit creation into `ParkingReservationAssignmentService` after reservation and status changes.
- Audit creation uses the same database session and transaction as the assignment. An audit persistence failure rolls back the reservation and all status changes.
- Serialized the existing internal deterministic ranking details into JSON-safe values without changing the ranking policy.
- Preserved the public assignment API response shape.
- Propagated trigger sources:
  - owner assignment API calls use `manual_owner`,
  - admin assignment API calls use `manual_admin`,
  - scheduler assignments use `scheduled`,
  - direct service calls default to `system`.
- Added a scoped assignment audit-persistence service error and mapped it to a generic HTTP 409 conflict without exposing database details.

### Review Notes

- The table name, model name, repository name, schemas, and enum naming follow the existing parking-domain conventions.
- SQLAlchemy `JSON` is used instead of PostgreSQL-only `JSONB` to preserve SQLite test compatibility; PostgreSQL stores the fields as JSON.
- The trigger-source ORM enum explicitly persists lowercase enum values, matching migration `0007`.
- The audit row is inserted before the transaction is committed by API or scheduler callers. The repository flushes but does not commit.
- A unique reservation audit constraint prevents duplicate assignment audit records. The existing unique reservation-per-availability constraint also makes availability lookup unambiguous.
- Ranking details contain deterministic decision inputs and IDs only. Passwords, hashes, tokens, names, emails, usernames, free-text application notes, and exception details are not persisted.
- API and scheduler behavior remains compatible. The assignment endpoint still returns only `ParkingReservationRead`.
- No audit read endpoint, frontend audit screen, notification, admin override flow, or fairness-policy change was added.

### Tests Added or Updated

- Added `backend/tests/test_parking_assignment_audit_log.py`
  - Verifies model metadata, foreign keys, JSON fields, indexes, timestamp, and unique reservation constraint.
  - Verifies create/read schema validation and JSON serialization.
  - Verifies repository create, get, paginated list, selected-user list, and missing-record behavior.
  - Verifies duplicate audit rows for one reservation are rejected.
- Updated assignment-service tests:
  - Verifies persisted selected IDs, reservation ID, availability ID, rejected IDs, policy name, and complete candidate ranking details.
  - Verifies direct service calls use the `system` trigger.
  - Verifies audit creation failure rolls back the complete assignment transaction.
- Updated assignment API tests:
  - Verifies owner assignments create `manual_owner` audit rows.
  - Verifies admin assignments create `manual_admin` audit rows.
  - Verifies the public reservation response remains unchanged.
- Updated scheduler tests:
  - Verifies scheduled assignments create `scheduled` audit rows.
  - Preserves scheduler failure-isolation test compatibility with the trigger-source argument.
- Updated model and Alembic tests for the new table and revision.

### Verification Results

- Focused audit-log, model, schema, migration, assignment, scheduler, and API tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_parking_assignment_audit_log.py backend/tests/test_models.py backend/tests/test_schemas.py backend/tests/test_alembic_config.py backend/tests/test_parking_reservation_assignment_service.py backend/tests/test_parking_assignment_scheduler.py backend/tests/test_parking_availabilities_api.py`
  - Result: `111 passed, 1 warning in 20.65s`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `356 passed, 1 warning in 94.09s`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads`
  - Result: `0007 (head)`
- Alembic history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result: `0006 -> 0007 (head), Add parking assignment audit logs table.`
- Alembic offline PostgreSQL SQL generation:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini upgrade head --sql`
  - Result: passed; generated the trigger-source enum, audit-log table, unique reservation constraint, foreign keys, and indexes.
- Docker Compose configuration:
  - Command: `docker-compose config --quiet`
  - Result: passed; the existing Docker config-file access warning remained.
- Backend Docker image:
  - Command: `docker-compose build backend`
  - Result: passed. The image was rebuilt because the previous image correctly reported only migration `0006`.
- PostgreSQL migration:
  - Commands:
    - `docker-compose up -d db`
    - `docker-compose run --rm backend alembic -c alembic.ini upgrade head`
    - `docker-compose run --rm backend alembic -c alembic.ini current`
  - Result: migration `0006 -> 0007` applied successfully; PostgreSQL reports `0007 (head)`.
  - Cleanup: `docker-compose stop db` passed and preserved the PostgreSQL volume.

### Known Limitations

- Audit logs are persisted only for reservation assignments. Cancellation, ownership-change, and future admin-override audit events are not implemented.
- No public or admin audit read API exists yet.
- No frontend audit-management or explanation screen exists yet.
- The audit log records deterministic ranking inputs, but it does not snapshot human-readable user or availability labels; future read services can join current domain records where appropriate.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.

### Next Suggested Task

Implement admin-only assignment audit read API groundwork using the existing audit repository and read schema, with filters for reservation, availability, and selected user plus focused authorization/API tests. Do not implement override flows, frontend audit screens, notifications, or fairness-policy changes yet.

## Task 32: Admin-Only Assignment Audit Read API Groundwork

### Files Changed

- `backend/app/repositories/parking_assignment_audit_logs.py`
- `backend/app/routers/admin_assignment_audit_logs.py`
- `backend/app/main.py`
- `backend/tests/test_admin_assignment_audit_logs_api.py`
- `backend/tests/test_parking_assignment_audit_log.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added the read-only admin assignment audit router:
  - `GET /admin/assignment-audit-logs`
  - `GET /admin/assignment-audit-logs/{audit_log_id}`
  - `GET /admin/assignment-audit-logs/by-reservation/{reservation_id}`
- Registered the router in the main FastAPI application.
- Applied the existing `require_admin` dependency to every audit endpoint.
- Added list pagination with validated `skip` and `limit` query parameters.
- Added exact-match list filters for:
  - availability ID,
  - reservation ID,
  - selected user ID,
  - selected application ID,
  - trigger source,
  - ranking policy.
- Extended `ParkingAssignmentAuditLogRepository.list` with the optional filters.
- Changed audit list ordering to deterministic newest-first ordering by `created_at DESC`, then `id DESC`.
- Reused the existing `ParkingAssignmentAuditLogRead` response schema and repository lookup methods.
- Added generic 404 handling for missing audit logs without exposing database details.

### Review Notes

- Router naming, dependency providers, response models, pagination validation, and registration follow the existing admin-router conventions.
- The static `/by-reservation/{reservation_id}` route is declared before the dynamic `/{audit_log_id}` route to prevent route matching conflicts.
- Every endpoint composes through `require_admin`; authentication failures remain 401 and authenticated non-admin failures remain 403 through the existing dependencies.
- List filters are database-focused exact comparisons composed through SQLAlchemy expressions.
- Pagination is applied after filtering and deterministic newest-first ordering.
- The list-by-selected-user repository method delegates to the shared filtered list path so ordering remains consistent.
- Responses contain only the existing audit read schema fields. Related users, passwords, password hashes, access tokens, and authentication details are not exposed.
- The ranking-details and rejected-application JSON fields serialize unchanged through the existing Pydantic v2 read schema.
- No write, update, delete, assignment, ranking, scheduler, migration, database-schema, frontend, notification, or admin-override behavior changed.

### Tests Added or Updated

- Added `backend/tests/test_admin_assignment_audit_logs_api.py`
  - Verifies admins can list audit logs in newest-first order.
  - Verifies pagination.
  - Verifies availability, reservation, selected-user, selected-application, trigger-source, and ranking-policy filters.
  - Verifies detail lookup by audit-log ID.
  - Verifies lookup by reservation ID.
  - Verifies missing audit records return 404.
  - Verifies employees and parking owners receive 403 from every audit endpoint.
  - Verifies missing and invalid bearer tokens return 401.
  - Verifies ranking details and rejected application IDs serialize correctly.
  - Verifies the complete nested response contains no password, hash, or access-token data.
- Updated `backend/tests/test_parking_assignment_audit_log.py`
  - Verifies repository list ordering is newest first.
  - Verifies pagination remains deterministic with the new ordering.

### Verification Results

- Focused admin audit API and audit repository tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_admin_assignment_audit_logs_api.py backend/tests/test_parking_assignment_audit_log.py`
  - Result: `15 passed, 1 warning in 2.10s`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `367 passed, 1 warning in 63.26s`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads`
  - Result: `0007 (head)`
- Alembic history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result: migration history remains unchanged with `0006 -> 0007 (head), Add parking assignment audit logs table.`

### Known Limitations

- Audit read endpoints expose persisted assignment audit records only; cancellation, ownership-change, and override audit events do not exist yet.
- Filtering supports exact matches only. Date ranges, free-text search, aggregate counts, and export are deferred.
- No frontend audit screen or reporting view exists.
- No audit modification or deletion endpoints exist by design.
- Docker/PostgreSQL runtime verification was not run because this task did not change schema, migrations, Docker, Compose, transaction behavior, or PostgreSQL-specific SQL.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.

### Next Suggested Task

Implement admin reservation override service groundwork with a mandatory override reason and transactional audit recording, without adding frontend screens or notifications yet.

## Task 33: Admin Reservation Override Service Groundwork

### Files Changed

- `backend/app/models/parking_assignment_audit_log.py`
- `backend/alembic/versions/0008_add_admin_override_audit_trigger.py`
- `backend/app/services/admin_reservation_override.py`
- `backend/app/services/__init__.py`
- `backend/tests/test_admin_reservation_override_service.py`
- `backend/tests/test_parking_assignment_audit_log.py`
- `backend/tests/test_alembic_config.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `AdminReservationOverrideService` with `override_assign_availability`.
- Added service-level validation for:
  - required non-blank override reason after trimming,
  - existing, active admin actor with the admin role,
  - existing open availability,
  - no existing reservation for the availability,
  - existing application belonging to the requested availability,
  - pending application status,
  - active selected applicant.
- Added focused service-level error types without introducing `HTTPException` into the service layer.
- Reused existing availability and pending-application row-locking repository paths.
- Added transactional manual assignment behavior:
  - creates the reservation for the specifically requested application,
  - marks the requested application selected,
  - rejects every other pending application,
  - marks the availability assigned,
  - creates one persistent assignment audit log.
- Added `admin_override` to `ParkingAssignmentTriggerSource`.
- Added Alembic revision `0008` to extend the existing PostgreSQL enum with the required `admin_override` value.
- Added override audit metadata inside the existing `ranking_details` JSON:
  - assignment method,
  - manual-selection basis,
  - admin user ID,
  - normalized override reason,
  - selected application and user IDs,
  - all pending application IDs considered by the manual decision.
- Added `AdminReservationOverrideResult` containing the reservation, audit log, selected application, rejected applications, and assigned availability.
- Exported the override service through the service package.

### Audit Metadata Design Decision

- The existing audit table has no dedicated override-reason or actor columns.
- Override reason and `admin_user_id` are stored in the existing `ranking_details` JSON to avoid adding table columns or a new table.
- The service validates that the recorded actor exists, is active, and has the admin role before recording the JSON actor ID.
- The audit policy name is `admin_override_manual_selection_v1`.
- The automatic ranking policy and ranking service are not called or changed by the override service.
- A narrow migration was unavoidable because the existing PostgreSQL enum could not persist the explicitly required `admin_override` trigger value.

### Review Notes

- The override service follows the existing service/repository transaction boundary: repositories flush without committing, and the future API caller will own the successful commit.
- Reservation creation, application status changes, availability status change, and audit creation use the same SQLAlchemy session.
- Audit persistence failures roll back the complete override and raise a scoped audit-persistence service error.
- Reservation or other integrity failures roll back and map to reservation-exists or generic integrity-conflict service errors without exposing database details.
- Unexpected mutation-phase failures also roll back before propagating.
- Validation failures occur before mutation and leave domain state unchanged.
- The availability row and pending application rows use the existing `FOR UPDATE` repository paths for PostgreSQL concurrency protection.
- Manual override deliberately selects the requested pending application even when automatic ranking would choose another applicant.
- Override reasons are normalized by trimming leading and trailing whitespace before persistence.
- No admin override API endpoint, frontend screen, notification, scheduled-worker change, or automatic-ranking change was added.

### Tests Added or Updated

- Added `backend/tests/test_admin_reservation_override_service.py`
  - Verifies a valid override creates the correct active reservation.
  - Verifies the requested application is selected even when automatic ranking would select another application.
  - Verifies other pending applications are rejected and the availability becomes assigned.
  - Verifies blank reasons are rejected.
  - Verifies missing, inactive, and non-admin actors are rejected.
  - Verifies missing and non-open availabilities are rejected.
  - Verifies missing, mismatched, and non-pending applications are rejected.
  - Verifies inactive applicants are rejected.
  - Verifies an existing reservation prevents override.
  - Verifies audit trigger, policy, normalized reason, admin actor, selected IDs, rejected IDs, and considered pending IDs.
  - Verifies audit creation failure rolls back reservation and all status changes.
  - Verifies reservation `IntegrityError` rolls back and maps to a clean service error.
  - Verifies the service uses the lock-enabled availability and pending-application repository paths.
- Updated audit model tests to verify the `admin_override` enum value.
- Updated Alembic tests for revision `0008` and the PostgreSQL enum extension SQL.

### Verification Results

- Focused override service, audit model, and Alembic tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_admin_reservation_override_service.py backend/tests/test_parking_assignment_audit_log.py backend/tests/test_alembic_config.py`
  - Result: `24 passed in 1.35s`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `384 passed, 1 warning in 64.67s`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads`
  - Result: `0008 (head)`
- Alembic history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result: `0007 -> 0008 (head), Add admin override assignment audit trigger.`
- Alembic offline PostgreSQL SQL generation:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini upgrade head --sql`
  - Result: passed and generated `ALTER TYPE parking_assignment_trigger_source ADD VALUE IF NOT EXISTS 'admin_override';`
- Backend Docker image:
  - Command: `docker-compose build backend`
  - Result: passed.
- PostgreSQL migration:
  - Commands:
    - `docker-compose up -d db`
    - `docker-compose run --rm backend alembic -c alembic.ini upgrade head`
    - `docker-compose run --rm backend alembic -c alembic.ini current`
  - Result: migration `0007 -> 0008` applied successfully; PostgreSQL reports `0008 (head)`.
  - Cleanup: `docker-compose stop db` passed and preserved the PostgreSQL volume.

### Known Limitations

- No admin override API endpoint exists yet; this task exposes the operation only through the service layer.
- Override reason and admin actor are stored in JSON rather than dedicated indexed columns, so direct reason/actor filtering is deferred.
- The `admin_user_id` JSON value is validated by the service but is not a database foreign key.
- Alembic revision `0008` has a no-op downgrade because removing a PostgreSQL enum value safely requires recreating the enum type and dependent column.
- The service supports manual assignment of an open availability. Replacing or changing an existing reservation remains out of scope.
- Successful service calls require the future caller to commit the shared database session, matching existing assignment-service conventions.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.

### Next Suggested Task

Implement the admin manual-override assignment API endpoint for an open availability using `AdminReservationOverrideService`, with a request schema containing `application_id` and mandatory `reason`, admin-only authorization, service-error-to-HTTP mapping, and focused API tests. Do not implement frontend screens, existing-reservation replacement, or notifications yet.

## Task 34: Admin Manual-Override Assignment API Endpoint

### Files Changed

- `backend/app/schemas/parking_reservation.py`
- `backend/app/schemas/__init__.py`
- `backend/app/routers/admin_reservation_overrides.py`
- `backend/app/main.py`
- `backend/tests/test_admin_reservation_overrides_api.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `AdminReservationOverrideRequest` with:
  - required positive `application_id`,
  - required override `reason`,
  - whitespace trimming,
  - non-blank validation,
  - a 1000-character maximum,
  - rejection of unexpected request fields.
- Added and registered a dedicated admin reservation override router.
- Added:
  - `POST /admin/parking-availabilities/{availability_id}/override-assign`
- The endpoint:
  - requires the existing `require_admin` dependency,
  - derives `admin_user_id` from the authenticated admin rather than the request body,
  - delegates all override business rules and audit persistence to `AdminReservationOverrideService`,
  - commits only after the complete audit-backed override succeeds,
  - rolls back on service-level and unexpected errors,
  - returns `ParkingReservationRead` with HTTP 201.
- Added clean service-error-to-HTTP mappings for:
  - reason validation fallback,
  - missing availability and application,
  - non-open availability,
  - application/availability mismatch,
  - non-pending application,
  - inactive applicant,
  - existing reservation,
  - integrity and audit-persistence conflicts,
  - invalid admin actor fallback.

### Review Notes

- A dedicated router was used because placing this endpoint under the existing `/admin/parking-reservations` router would have produced the wrong required URL.
- The endpoint is registered at exactly `/admin/parking-availabilities/{availability_id}/override-assign`.
- `require_admin` provides the normal 401 behavior for missing/invalid/inactive authentication and 403 behavior for authenticated non-admin users.
- The request schema catches missing, blank, and whitespace-only reasons as HTTP 422 before service execution.
- The service still validates and trims the reason defensively for non-API callers.
- The endpoint owns the successful commit and error rollback, matching existing write-router conventions.
- The public response remains the existing reservation-only shape and does not expose audit metadata, override reason, actor details, passwords, hashes, or tokens.
- The endpoint reuses the existing override service, so audit creation remains transactional with reservation and status updates.
- No ranking, scheduled-worker, migration, database-schema, frontend, audit-read, or notification behavior changed.

### Tests Added or Updated

- Added `backend/tests/test_admin_reservation_overrides_api.py`
  - Verifies an admin can manually assign the specifically requested pending application.
  - Verifies the requested later application is selected and the earlier application is rejected.
  - Verifies the availability becomes assigned.
  - Verifies the response reservation fields and HTTP 201 status.
  - Verifies the override audit log contains `admin_override`, normalized reason, and authenticated admin ID.
  - Verifies the response does not expose audit details, reason, passwords, hashes, or tokens.
  - Verifies missing, blank, and whitespace-only reasons return 422.
  - Verifies non-positive application IDs return 422.
  - Verifies missing availability and application return 404.
  - Verifies non-open availability, mismatched application, non-pending application, inactive applicant, and existing reservation return 409.
  - Verifies employee and parking-owner callers receive 403.
  - Verifies missing and invalid tokens return 401.
  - Verifies every remaining override service error maps to a clean HTTP status and message.

### Verification Results

- Focused override API, override service, and schema tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_admin_reservation_overrides_api.py backend/tests/test_admin_reservation_override_service.py backend/tests/test_schemas.py`
  - Result: `87 passed, 1 warning in 2.79s`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `413 passed, 1 warning in 66.76s`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads`
  - Result: `0008 (head)`
- Alembic history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result: migration history remains unchanged with `0007 -> 0008 (head), Add admin override assignment audit trigger.`
- OpenAPI endpoint verification:
  - Command: load `create_app().openapi()` and inspect `/admin/parking-availabilities/{availability_id}/override-assign`.
  - Result:
    - endpoint exists with POST,
    - request body is required,
    - bearer security is present,
    - documented responses include 201 and 422.

### Known Limitations

- The endpoint manually assigns an open availability only. It does not replace or change an existing reservation.
- No frontend override screen exists.
- Override reason and admin actor remain stored in audit JSON rather than dedicated indexed columns.
- No notifications are sent.
- Docker/PostgreSQL runtime verification was not rerun because this task did not change schema, migrations, Docker, Compose, transaction implementation, or PostgreSQL-specific SQL.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.

### Next Suggested Task

Implement existing-reservation replacement override data-model and service groundwork, preserving immutable audit history and requiring a mandatory reason, without adding frontend screens or notifications yet.

## Task 35: Existing-Reservation Replacement Override Groundwork

### Files Changed

- `backend/app/models/parking_assignment_audit_log.py`
- `backend/alembic/versions/0009_allow_multiple_reservation_audit_events.py`
- `backend/app/repositories/parking_assignment_audit_logs.py`
- `backend/app/repositories/parking_reservations.py`
- `backend/app/services/admin_reservation_override.py`
- `backend/tests/test_admin_reservation_replacement_service.py`
- `backend/tests/test_parking_assignment_audit_log.py`
- `backend/tests/test_alembic_config.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Extended `AdminReservationOverrideService` with `replace_existing_reservation`.
- Added replacement-specific service validation for:
  - required non-blank reason,
  - active admin actor,
  - existing assigned availability,
  - existing active reservation,
  - existing replacement application belonging to the same availability,
  - pending replacement application,
  - active replacement applicant,
  - replacement application differing from the currently reserved application.
- Added replacement-specific service errors and `AdminReservationReplacementResult`.
- Added transactional in-place replacement behavior:
  - keeps the existing reservation row and ID,
  - updates its application and reserved-user fields,
  - keeps its status active,
  - marks the previously selected application rejected,
  - marks the replacement application selected,
  - rejects every other pending application,
  - keeps the availability assigned,
  - creates a new immutable replacement audit event.
- Added replacement audit policy `admin_override_replacement_v1`.
- Added replacement audit metadata:
  - action `replacement`,
  - normalized reason,
  - admin user ID,
  - previous reservation, application, and user IDs,
  - resulting reservation ID,
  - selected replacement application and user IDs,
  - considered pending applications,
  - rejected application IDs.
- Added lock-enabled reservation lookup by availability.
- Extended reservation repository updates to support controlled in-place changes to:
  - `application_id`,
  - `reserved_for_user_id`,
  - `status`.
- Added Alembic revision `0009` to remove the unique audit-log `reservation_id` constraint.
- Updated audit repository singular reservation/availability lookups to return the newest event while filtered list queries preserve complete history.

### Replacement Design Decision

- Replacement updates the existing reservation row in place.
- The reservation ID, availability ID, spot, time range, and active status remain stable.
- This avoids changing the existing one-reservation-per-availability constraint and avoids partial unique indexes for active reservations.
- Previous application/user values are preserved in immutable replacement audit metadata.
- The previous selected application becomes rejected because it is no longer the selected winner after admin replacement.

### Audit Uniqueness Design Decision

- A reservation can now have multiple immutable audit events:
  - the original assignment event,
  - one or more later replacement events.
- Revision `0009` removes `uq_parking_assignment_audit_logs_reservation_id`.
- The existing non-unique reservation index remains for efficient audit-history filtering.
- `get_by_reservation_id` and `get_by_availability_id` now return the newest audit event by `created_at DESC, id DESC`.
- `list(reservation_id=...)` and `list(availability_id=...)` retain the full event history.
- Downgrading revision `0009` can fail after replacement events exist because restoring the unique constraint requires one audit event per reservation.

### Review Notes

- Replacement uses the existing availability and pending-application locks plus a new reservation row lock.
- Reservation update, application status transitions, and audit creation use the same SQLAlchemy session and transaction.
- Audit persistence and integrity failures roll back the reservation values and all application status changes.
- Validation failures occur before mutation.
- The repository update allowlist prevents replacement code from changing availability, spot, or reservation time-range fields.
- The reservation timestamp mixin automatically updates `updated_at` during in-place replacement.
- Replacement does not invoke or modify the automatic ranking service.
- No `HTTPException`, API endpoint, frontend screen, notification, or scheduled-worker change was added.

### Tests Added or Updated

- Added `backend/tests/test_admin_reservation_replacement_service.py`
  - Verifies active reservation replacement succeeds in place.
  - Verifies the reservation ID remains stable while application/user values change.
  - Verifies the previous application becomes rejected, replacement becomes selected, other pending applications become rejected, and availability remains assigned.
  - Verifies replacement audit metadata and full two-event audit history.
  - Verifies blank reason, missing availability, non-assigned availability, missing reservation, non-active reservation, missing/mismatched/non-pending application, inactive applicant, and same currently selected application failures.
  - Verifies audit failure and reservation-update integrity failure roll back the complete replacement.
  - Verifies availability, reservation, and pending-application lock paths are used.
  - Verifies reservation lock SQL compiles to PostgreSQL `FOR UPDATE OF parking_reservations`.
  - Verifies repository replacement updates ignore non-allowlisted fields.
- Updated audit-log tests:
  - Verifies the model no longer has a unique reservation audit constraint.
  - Verifies multiple audit events can be created for one reservation.
  - Verifies singular lookup returns the newest event and list filtering returns full history.
- Updated Alembic tests for revision `0009` and unique-constraint removal SQL.

### Verification Results

- Focused replacement, audit repository, Alembic, and repository tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_admin_reservation_replacement_service.py backend/tests/test_parking_assignment_audit_log.py backend/tests/test_alembic_config.py backend/tests/test_repositories.py`
  - Result: `69 passed in 2.81s`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `430 passed, 1 warning in 85.35s`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads`
  - Result: `0009 (head)`
- Alembic history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result: `0008 -> 0009 (head), Allow multiple audit events for one reservation.`
- Alembic offline PostgreSQL SQL generation:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini upgrade head --sql`
  - Result: passed and generated `ALTER TABLE parking_assignment_audit_logs DROP CONSTRAINT uq_parking_assignment_audit_logs_reservation_id;`
- Docker Compose configuration:
  - Command: `docker-compose config --quiet`
  - Result: passed; the existing Docker config-file access warning remained.
- PostgreSQL migration attempt:
  - Command: `docker-compose build backend`
  - Result: could not run because the Docker Desktop Linux engine was not available at `//./pipe/dockerDesktopLinuxEngine`.

### Known Limitations

- PostgreSQL runtime application of migration `0009` remains to be verified when Docker Desktop is running.
- The replacement operation is service-only; no replacement API endpoint exists yet.
- Replacement preserves history through audit events rather than historical reservation rows.
- The reservation read model exposes only the current application/user assignment; previous values are available through audit history.
- Audit reason and admin actor remain JSON metadata rather than dedicated indexed columns.
- Downgrading `0009` requires removing or consolidating duplicate reservation audit events before restoring the unique constraint.
- No frontend screen or notification exists.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.

### Next Suggested Task

Implement the admin existing-reservation replacement API endpoint using `replace_existing_reservation`, with mandatory reason, admin-only authorization, clean replacement-specific HTTP error mapping, reservation-only response, and focused API tests. Do not implement frontend screens or notifications yet.

## Task 36: Admin Existing-Reservation Replacement API Endpoint

### Files Changed

- `backend/app/routers/admin_reservation_overrides.py`
- `backend/tests/test_admin_reservation_overrides_api.py`
- `backend/tests/test_admin_reservation_replacements_api.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added admin-only endpoint:
  - `POST /admin/parking-availabilities/{availability_id}/replace-reservation`
- Reused `AdminReservationOverrideRequest` because replacement has the same validated request contract:
  - required positive `application_id`,
  - required reason,
  - reason trimming,
  - blank reason rejection,
  - extra-field rejection,
  - no client-supplied admin user ID.
- Added thin endpoint wiring to:
  - resolve the authenticated admin through `require_admin`,
  - use the existing dependency-injected `AdminReservationOverrideService`,
  - call `replace_existing_reservation`,
  - commit on success,
  - roll back on service or unexpected errors,
  - refresh and return only the updated reservation.
- Returns `ParkingReservationRead` with `200 OK` because the existing reservation is updated in place.
- Extended the shared override service-error mapper for replacement-specific failures:
  - availability not assigned -> `409`,
  - existing reservation missing -> `409`,
  - existing reservation not active -> `409`,
  - requested application already reserved -> `409`.
- Kept existing clean mappings for missing availability/application, application mismatch/status, inactive applicant, integrity/audit conflicts, and permission failures.

### Review Notes

- The endpoint is colocated with `override-assign` under the existing admin parking-availability override router; no new router registration was required.
- `require_admin` preserves the intended authentication boundary:
  - missing or invalid credentials remain `401`,
  - authenticated non-admin users receive `403`.
- Request validation produces `422` before service invocation for missing/blank reasons and non-positive application IDs.
- Service-level reason validation remains mapped to `400` as a defensive fallback.
- The route follows the existing write-endpoint transaction pattern and does not create a global or independent database session.
- The response exposes only the stable reservation read schema and does not expose audit metadata, reasons, credentials, tokens, or password hashes.
- Audit creation and all reservation/application/availability mutations remain inside the previously tested replacement service transaction.
- Automatic ranking behavior was not changed or invoked; tests verify that the explicit admin selection wins even when another pending application would rank earlier normally.
- No schema, migration, frontend, notification, or scheduled-worker change was made.

### Tests Added or Updated

- Added `backend/tests/test_admin_reservation_replacements_api.py` covering:
  - successful in-place replacement by an admin,
  - `200 OK` reservation response with updated application and user IDs,
  - manual replacement selecting a later application over the normally earlier-ranked application,
  - previous selected and other pending application rejection,
  - replacement application selection,
  - assigned availability preservation,
  - replacement audit trigger, action, normalized reason, admin ID, previous application ID, and previous user ID,
  - safe public response shape,
  - missing/blank reason and invalid application ID validation,
  - missing availability,
  - availability not assigned,
  - missing/inactive existing reservation,
  - missing/mismatched/non-pending replacement application,
  - inactive replacement applicant,
  - replacement with the currently selected application,
  - employee and parking-owner `403` responses,
  - missing and invalid token `401` responses,
  - OpenAPI registration, required request body, bearer security, and documented `200`/`422` responses.
- Updated override API error-mapping tests for all replacement-specific service errors.

### Verification Results

- Focused replacement API, override API, and replacement service tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_admin_reservation_replacements_api.py backend/tests/test_admin_reservation_overrides_api.py backend/tests/test_admin_reservation_replacement_service.py`
  - Result: `69 passed, 1 warning in 5.13s`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `453 passed, 1 warning in 89.41s`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads and history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result: unchanged at `0009 (head)` with `0008 -> 0009 (head), Allow multiple audit events for one reservation.`
- Alembic offline PostgreSQL SQL:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini upgrade head --sql | Select-String -Pattern 'DROP CONSTRAINT uq_parking_assignment_audit_logs_reservation_id'`
  - Result: passed and emitted the expected revision `0009` constraint-removal SQL.
- Docker Compose static configuration:
  - Command: `docker-compose config --quiet`
  - Result: passed; the existing Docker config-file access warning remained.
- Docker runtime status:
  - Command: `docker-compose ps`
  - Result: could not connect because the Docker daemon pipe `//./pipe/docker_engine` was unavailable.

### Known Limitations

- Docker/PostgreSQL runtime verification remains unavailable because Docker Desktop is not running.
- PostgreSQL runtime application of migration `0009` remains to be verified when Docker Desktop is available.
- No frontend admin reservation/replacement screen exists yet.
- No notification is emitted for replacement.
- The endpoint requires a known replacement application ID; an admin-readable application list filtered by availability/status is not yet exposed for a future UI.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.

### Next Suggested Task

Implement an admin-only parking-application list endpoint with availability and status filters so the future admin reservation view can inspect pending replacement candidates. Add focused repository/API tests, keep the response read-only, and do not implement frontend screens or notifications yet.

## Task 37: Admin Parking-Application List Endpoint

### Scope Decision

- The implementation log contained an explicit next suggested task, so this task implemented the admin parking-application list endpoint.
- The reservation cancellation groundwork supplied as a fallback was not implemented in this task and is now the next suggested task.

### Files Changed

- `backend/app/repositories/parking_applications.py`
- `backend/app/routers/admin_parking_applications.py`
- `backend/app/main.py`
- `backend/tests/test_admin_parking_applications_api.py`
- `backend/tests/test_repositories.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added admin-only read endpoint:
  - `GET /admin/parking-applications`
- Added query parameters:
  - `availability_id` with positive-integer validation,
  - `status` using the existing `ParkingApplicationStatus` enum,
  - `skip` and `limit` pagination using existing admin-list limits.
- Extended `ParkingApplicationRepository.list` with an optional `availability_id` filter.
- Combined availability and status filters are applied at the SQL query level before ordering and pagination.
- Registered the new admin router in the FastAPI application.
- Reused `ParkingApplicationRead` so the endpoint remains read-only and does not expose nested users or sensitive authentication fields.

### Review Notes

- The direct repository dependency matches the existing read-only admin reservation and parking-spot list architecture.
- No service layer was added because this endpoint performs no business transition or authorization rule beyond `require_admin`.
- `require_admin` keeps missing/invalid token behavior at `401` and authenticated non-admin behavior at `403`.
- Repository relationship loading remains unchanged and continues to avoid lazy-loading issues for application relationships.
- Filtering uses the existing enum rather than duplicated status strings.
- Results retain deterministic application-ID ordering.
- The endpoint does not mutate applications, reservations, availability, ranking, audits, or scheduler state.
- No schema, migration, frontend, notification, Docker, or Compose change was made.

### Tests Added or Updated

- Added `backend/tests/test_admin_parking_applications_api.py` covering:
  - admin application listing,
  - stable and safe response shape,
  - combined availability and status filtering,
  - pagination,
  - invalid availability/status/pagination query validation,
  - employee and parking-owner `403` responses,
  - missing and invalid token `401` responses,
  - OpenAPI registration and bearer security.
- Updated repository tests to verify:
  - combined availability/status filtering returns matching applications,
  - combined filters return an empty list when no application matches.

### Verification Results

- Focused admin application API and repository tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_admin_parking_applications_api.py backend/tests/test_repositories.py`
  - Result: `58 passed, 1 warning in 3.04s`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `466 passed, 1 warning in 85.21s`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads and history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result: unchanged at `0009 (head)`.
- Docker Compose static configuration:
  - Command: `docker-compose config --quiet`
  - Result: passed; the existing Docker config-file access warning remained.
- Docker/PostgreSQL runtime verification:
  - Result: not run because this read-only task did not change schema, migrations, Docker, Compose, transactions, or PostgreSQL-specific behavior, and Docker Desktop was unavailable in the preceding task.

### Known Limitations

- The application list response intentionally exposes applicant IDs rather than nested applicant profiles; additional user lookup or a future admin view model may be useful for UI display.
- Reservation cancellation groundwork is not implemented yet.
- No frontend admin application or replacement-candidate view exists.
- No notifications are emitted.
- PostgreSQL runtime application of migration `0009` remains to be verified when Docker Desktop is available.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.

### Next Suggested Task

Implement reservation cancellation groundwork with a transactional cancellation service, reserved-user/availability-owner/admin permission rules, mandatory admin reason, reservation/availability/application status transitions, cancellation audit recording, user and admin API endpoints, and focused service/API tests. Do not automatically assign a replacement applicant, change ranking behavior, add frontend screens, or add notifications.

## Task 38: Reservation Cancellation Groundwork

### Files Changed

- `backend/app/repositories/parking_applications.py`
- `backend/app/repositories/parking_reservations.py`
- `backend/app/schemas/parking_reservation.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/parking_reservation_cancellation.py`
- `backend/app/services/__init__.py`
- `backend/app/routers/parking_reservations.py`
- `backend/app/routers/admin_parking_reservations.py`
- `backend/tests/test_parking_reservation_cancellation_service.py`
- `backend/tests/test_parking_reservation_cancellations_api.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `ParkingReservationCancellationService` with:
  - `cancel_for_user_or_owner`,
  - `cancel_my_reservation`,
  - `cancel_as_owner`,
  - `cancel_as_admin`.
- Added service-level cancellation errors for:
  - missing reservation,
  - non-active reservation,
  - forbidden actor,
  - missing admin reason,
  - integrity conflicts,
  - audit persistence failure.
- Added lock-enabled repository lookups:
  - `ParkingReservationRepository.get_by_id_for_update`,
  - `ParkingApplicationRepository.get_by_id_for_update`.
- Added cancellation request schemas:
  - `ReservationCancellationRequest` with optional trimmed reason,
  - `AdminReservationCancellationRequest` with required non-blank trimmed reason.
- Added endpoints:
  - `PATCH /parking-reservations/{reservation_id}/cancel`,
  - `PATCH /admin/parking-reservations/{reservation_id}/cancel`.
- The public endpoint accepts no request body when no reason is needed.
- Both endpoints return only `ParkingReservationRead`.

### Status Transition Decisions

- Every successful cancellation:
  - changes the reservation from `active` to `cancelled`,
  - preserves the reservation row,
  - preserves all application rows,
  - does not automatically select a replacement applicant.
- Availability status:
  - becomes `open` when `availability.end_at` is in the future,
  - becomes `expired` when `availability.end_at` is not in the future.
- Selected application status:
  - becomes `cancelled` when the reserved user cancels,
  - becomes `rejected` when the availability owner or an admin cancels.
- Other pending applications remain `pending`.

### Audit Recording Decision

- Admin cancellations create an immutable audit event with:
  - `trigger_source = admin_override`,
  - action `cancellation`,
  - normalized reason,
  - admin user ID,
  - reservation and availability IDs,
  - previous application and user IDs,
  - resulting reservation, availability, and application statuses.
- Availability-owner cancellations create an immutable audit event with:
  - `trigger_source = manual_owner`,
  - action `cancellation`,
  - optional normalized reason,
  - owner user ID,
  - previous assignment and resulting status metadata.
- Reserved-user cancellations do not create an assignment audit event in this task because the existing trigger-source enum has no accurate user-action value. Reusing `system` or `manual_owner` would misrepresent the actor.
- No enum or migration change was introduced.

### Review Notes

- Service code remains HTTP-independent; routers map service errors to clean `403`, `404`, `409`, and defensive `400` responses.
- Schema validation returns `422` for missing or blank admin reasons.
- Public permission checks happen before active-status and application-integrity reporting, preventing unrelated users from learning internal reservation state.
- The service validates that the active reservation references the selected application for the same availability and reserved user.
- Cancellation locks the availability, reservation, and selected application rows before mutation.
- Reservation, availability, application, and applicable audit updates use the same SQLAlchemy session and transaction.
- Audit persistence failures roll back all cancellation mutations.
- Admin identity and active-admin role are validated in the service in addition to route-level `require_admin`.
- The service uses timezone-aware comparison for future/open versus expired availability.
- No ranking, replacement, scheduler, frontend, notification, Docker, Compose, schema, or migration behavior was changed.

### Tests Added

- Added focused cancellation service tests covering:
  - reserved-user cancellation,
  - owner cancellation,
  - admin cancellation,
  - actor-specific selected-application status,
  - future availability reopening,
  - elapsed availability expiration,
  - no automatic replacement and unchanged pending applications,
  - owner/admin audit trigger and metadata,
  - no inaccurate user cancellation audit,
  - missing/non-active reservation failures,
  - unrelated-user and non-admin failures,
  - mandatory admin reason,
  - audit-failure rollback,
  - availability/reservation/application lock paths.
- Added focused cancellation API tests covering:
  - public cancellation by reserved user and owner,
  - public cancellation without a request body,
  - admin cancellation with mandatory reason,
  - safe reservation response shape,
  - audit metadata and status transitions,
  - no automatic replacement,
  - missing/blank admin reason `422`,
  - unrelated-user `403`,
  - missing reservation `404`,
  - non-active reservation `409`,
  - permission-before-status behavior,
  - missing/invalid token `401`,
  - non-admin access to admin endpoint `403`,
  - OpenAPI registration and bearer security.

### Verification Results

- Focused cancellation, reservation API, schema, and repository tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_parking_reservation_cancellation_service.py backend/tests/test_parking_reservation_cancellations_api.py backend/tests/test_parking_reservations_api.py backend/tests/test_schemas.py backend/tests/test_repositories.py`
  - Result: `125 passed, 1 warning in 11.91s`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `494 passed, 1 warning in 382.17s`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads and history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result: unchanged at `0009 (head)`.
- Alembic offline SQL:
  - Result: not rerun because this task added no migration.
- Docker Compose static configuration:
  - Command: `docker-compose config --quiet`
  - Result: passed; the existing Docker config-file access warning remained.
- Docker/PostgreSQL runtime status:
  - Command: `docker-compose ps`
  - Result: could not connect because the Docker daemon pipe `//./pipe/docker_engine` was unavailable.

### Known Limitations

- A future availability is reopened after cancellation as required, but the current data model still enforces one reservation row per availability and assignment queries exclude any availability with an existing reservation row. The reopened availability therefore cannot yet be automatically reassigned while its cancelled reservation is preserved.
- Reserved-user cancellations are not audit logged because the current assignment-audit trigger enum lacks an accurate user-action source.
- Cancellation audit events reuse the assignment-audit model, so historical selected-application fields describe the assignment being cancelled rather than a new selection.
- PostgreSQL runtime behavior for the new row-lock paths was not verified because Docker Desktop is unavailable.
- PostgreSQL runtime application of migration `0009` remains to be verified when Docker Desktop is available.
- No frontend cancellation controls or notifications exist.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.

### Next Suggested Task

Implement cancellation-aware reassignment lifecycle groundwork so a future availability reopened after cancellation can be assigned again while preserving immutable cancelled reservation history. Define and migrate the reservation uniqueness strategy, update assignment/replacement queries and services, and add focused PostgreSQL-compatible tests. Do not implement frontend screens or notifications yet.

## Task 39: Explicit Reassignment After Cancellation Groundwork

### Files Changed

- `backend/app/models/parking_availability.py`
- `backend/app/models/parking_reservation.py`
- `backend/app/repositories/parking_reservations.py`
- `backend/app/schemas/parking_reservation.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/admin_reservation_override.py`
- `backend/app/services/parking_reservation_assignment.py`
- `backend/app/services/parking_reassignment.py`
- `backend/app/services/__init__.py`
- `backend/app/routers/parking_availabilities.py`
- `backend/alembic/versions/0010_preserve_cancelled_reservation_history.py`
- `backend/tests/test_admin_reservation_replacement_service.py`
- `backend/tests/test_alembic_config.py`
- `backend/tests/test_models.py`
- `backend/tests/test_parking_assignment_scheduler.py`
- `backend/tests/test_parking_availabilities_api.py`
- `backend/tests/test_parking_reassignment_api.py`
- `backend/tests/test_parking_reassignment_service.py`
- `backend/tests/test_parking_reservation_assignment_service.py`
- `backend/tests/test_repositories.py`
- `backend/tests/test_schemas.py`
- `resources/docs/implementation_log.md`

### Reassignment Design Decision

- Reassignment remains an explicit operation and is not a cancellation side effect.
- Reservation cancellation still reopens a future availability without automatically assigning another applicant.
- Added `ParkingReassignmentService.reassign_open_availability`.
- Added `POST /parking-availabilities/{availability_id}/reassign`.
- The availability owner can reassign their own availability and an admin can reassign any availability.
- The service requires:
  - an open, future availability,
  - no active reservation,
  - the latest reservation history entry to be cancelled,
  - at least one pending application.
- Initial assignment and the scheduler continue to reject any availability with reservation history. This keeps reassignment controlled through the explicit operation.

### Reservation History and Uniqueness Strategy

- Reassignment creates a new active reservation row and preserves the previous cancelled reservation row unchanged.
- Migration `0010` removes the global unique constraint on `parking_reservations.availability_id`.
- Migration `0010` adds a PostgreSQL partial unique index that permits reservation history while enforcing at most one active reservation per availability:
  - `uq_parking_reservations_active_availability_id`
  - unique on `availability_id` where `status = 'active'`.
- SQLAlchemy metadata includes equivalent PostgreSQL and SQLite partial-index predicates.
- `ParkingAvailability.reservation` was replaced with the history-aware `ParkingAvailability.reservations` collection.
- Reservation repository lookups now distinguish:
  - latest reservation history,
  - current active reservation,
  - latest cancelled reservation,
  - complete reservation history for an availability.
- Existing admin replacement continues to update the current active reservation in place and now explicitly looks up that active reservation.

### Reassignment Behavior

- Reuses `ParkingApplicationRankingService` without changing the ranking algorithm or fairness configuration.
- Considers only pending applications.
- Creates a new active reservation for the selected applicant.
- Changes the selected application to `selected`.
- Changes other considered pending applications to `rejected`.
- Changes the availability to `assigned`.
- Preserves previous cancelled reservation and application history.
- Locks the availability, current active reservation lookup, latest history row, and pending applications before mutation.
- Uses one SQLAlchemy session and transaction for reservation, application, availability, and audit mutations.
- Rolls back all mutations on integrity or audit-persistence failures.

### Audit Recording Decision

- Each successful reassignment creates a new immutable `ParkingAssignmentAuditLog`.
- Trigger source is:
  - `manual_owner` for owner-triggered reassignment,
  - `manual_admin` for admin-triggered reassignment,
  - compatible with `scheduled` for a future explicit scheduler integration.
- Audit metadata includes:
  - `action = reassignment`,
  - actor user ID,
  - optional normalized reason,
  - previous reservation, application, and user IDs,
  - selected application and user IDs,
  - rejected application IDs,
  - all candidate ranking details.
- The reassignment ranking-policy identifier is separate, but the underlying ranking behavior is unchanged.

### Review Notes

- The final review tightened history validation so an older cancelled row cannot authorize reassignment when the latest reservation history entry is completed or otherwise non-cancelled.
- The partial unique active-reservation index protects against concurrent duplicate active reservations while preserving immutable cancelled history.
- Availability row locking serializes initial assignment, cancellation, replacement, and explicit reassignment paths.
- Initial assignment, admin initial override, and scheduled assignment still reject any existing reservation history; they cannot silently bypass the explicit reassignment lifecycle.
- Admin replacement now distinguishes no reservation history from cancelled-only history and operates only on an active reservation.
- Service errors remain HTTP-independent. The router maps them to generic `403`, `404`, and `409` responses without exposing database details.
- The endpoint returns only `ParkingReservationRead`; audit details, reasons, credentials, and password hashes are not exposed.
- No cancellation, ranking, scheduled-worker, frontend, notification, Docker, or Compose behavior was changed beyond the required reservation-history compatibility.

### Tests Added or Updated

- Added focused reassignment service tests covering:
  - successful reassignment with preserved cancelled history,
  - current fairness/ranking reuse,
  - ignored cancelled, rejected, and selected applications,
  - owner and admin permission behavior,
  - missing, non-open, and expired availability,
  - active-reservation conflict,
  - no pending applications,
  - required cancelled latest-history state,
  - older cancelled history followed by a non-cancelled row,
  - audit metadata and ranking details,
  - audit-failure rollback.
- Added focused reassignment API tests covering:
  - owner and admin success,
  - optional reason/body,
  - safe response shape,
  - unrelated-user `403`,
  - missing availability `404`,
  - state conflicts `409`,
  - missing and invalid token `401`,
  - OpenAPI bearer-security registration.
- Updated model, repository, Alembic, assignment, replacement, availability API, schema, and scheduler tests for history-aware reservation semantics.
- Added regressions proving:
  - initial assignment rejects cancelled reservation history,
  - scheduled assignment excludes cancelled reservation history,
  - one active reservation per availability is enforced while cancelled plus active history is allowed.

### Verification Results

- Focused reassignment, assignment, scheduler, migration, model, repository, replacement, API, and schema tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_parking_reassignment_service.py backend/tests/test_parking_reassignment_api.py backend/tests/test_parking_reservation_assignment_service.py backend/tests/test_parking_assignment_scheduler.py backend/tests/test_alembic_config.py backend/tests/test_models.py backend/tests/test_repositories.py backend/tests/test_admin_reservation_replacement_service.py backend/tests/test_parking_availabilities_api.py backend/tests/test_schemas.py`
  - Result: `190 passed, 1 warning in 24.13s`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `515 passed, 1 warning in 103.29s`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads and history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result: `0010 (head)` with a linear `0009 -> 0010` history.
- Alembic offline PostgreSQL SQL:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini upgrade head --sql`
  - Result: passed; generated SQL drops `uq_parking_reservations_availability_id` and creates `uq_parking_reservations_active_availability_id ... WHERE status = 'active'`.
- Docker Compose static configuration:
  - Command: `docker-compose config --quiet`
  - Result: passed; the existing Docker config-file access warning remained.
- Docker/PostgreSQL runtime status:
  - Command: `docker-compose ps`
  - Result: could not connect because the Docker daemon pipe `//./pipe/docker_engine` was unavailable.

### Known Limitations

- Migration `0010`, its PostgreSQL partial unique index, and PostgreSQL row-lock behavior still require runtime verification when Docker Desktop is available.
- Downgrading `0010` after multiple reservation-history rows exist for one availability requires consolidating that history first; otherwise restoring the old global unique constraint will fail.
- Reassignment considers only currently pending applications. It does not revive previously cancelled, rejected, or selected applications.
- The scheduler intentionally does not automatically reassign reopened cancelled-history availabilities.
- Reserved-user cancellation audit behavior remains unchanged: no assignment-audit event is created because the trigger-source enum lacks an accurate user-action value.
- No frontend reassignment controls or notifications exist.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.

### Next Suggested Task

Implement an admin reservation-history read API with availability filtering and clear current-active versus historical reservation semantics, then add focused repository/API tests. Do not implement frontend screens or notifications yet.

## Task 40: Admin Reservation-History Read API

### Files Changed

- `backend/app/repositories/parking_reservations.py`
- `backend/app/routers/admin_parking_reservations.py`
- `backend/app/schemas/parking_reservation.py`
- `backend/app/schemas/__init__.py`
- `backend/tests/test_parking_reservations_api.py`
- `backend/tests/test_repositories.py`
- `backend/tests/test_schemas.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added admin-only endpoint:
  - `GET /admin/parking-reservations/history`
- Added `ParkingReservationRepository.list_history` with:
  - newest-first ordering by `created_at`, then `id`,
  - pagination,
  - `availability_id` filtering,
  - reservation-status filtering,
  - `current_active` filtering,
  - reserved-user filtering,
  - parking-spot filtering.
- Added history response primitives:
  - `ParkingReservationHistoryState`,
  - `ParkingReservationHistoryRead`.
- Each history response explicitly classifies the reservation as:
  - `current_active` when its status is `active`,
  - `historical` when its status is `cancelled` or `completed`.
- Kept the existing `GET /admin/parking-reservations` response and ordering unchanged for existing clients.

### API Contract

- Endpoint: `GET /admin/parking-reservations/history`
- Authorization: active admin bearer token required.
- Optional query parameters:
  - `skip`,
  - `limit`,
  - `availability_id`,
  - `status`,
  - `current_active`,
  - `reserved_for_user_id`,
  - `parking_spot_id`.
- Results are newest first.
- `current_active=true` returns active/current reservations.
- `current_active=false` returns cancelled and completed historical reservations.
- Filters compose normally. Contradictory filters, such as `status=active&current_active=false`, return an empty list.

### Review Notes

- A dedicated history endpoint was added instead of changing the existing admin reservation-list response shape.
- The route remains thin and read-only; no service layer was added because the operation contains no business mutation or workflow orchestration.
- Current-versus-historical classification relies on the reservation lifecycle invariant introduced in migration `0010`: at most one active reservation can exist per availability.
- The repository eagerly loads existing reservation relationships consistently with other reservation reads, while the response schema exposes only stable reservation fields and `history_state`.
- The endpoint does not expose nested users, password hashes, tokens, cancellation reasons, audit details, or internal database information.
- Existing reservation assignment, cancellation, replacement, reassignment, ranking, audit, and scheduler behavior was not changed.
- No schema, migration, Docker, Compose, frontend, or notification changes were introduced.

### Tests Added or Updated

- Added schema tests proving:
  - active reservations serialize as `current_active`,
  - cancelled reservations serialize as `historical`,
  - completed reservations serialize as `historical`.
- Added repository tests covering:
  - availability filtering,
  - newest-first reservation history,
  - `current_active=true`,
  - `current_active=false`,
  - combined status, reserved-user, and parking-spot filters.
- Added API tests covering:
  - admin history listing filtered by availability,
  - explicit current-active and historical response states,
  - current-active and status filters,
  - no sensitive response fields,
  - missing and invalid token `401`,
  - non-admin `403`,
  - OpenAPI registration, query parameters, and bearer security.

### Verification Results

- Focused reservation API, repository, and schema tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests/test_parking_reservations_api.py backend/tests/test_repositories.py backend/tests/test_schemas.py`
  - Result: `109 passed, 1 warning in 15.11s`
- Backend tests:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -c backend/pyproject.toml backend/tests`
  - Result: `525 passed, 1 warning in 113.12s`
- Backend compile check:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q backend/app backend/alembic backend/tests`
  - Result: passed
- Alembic heads and history:
  - Command: `$env:PYTHONPATH='backend;backend\.test-deps'; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini heads; & 'C:\Users\nikola.milosevic\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m alembic -c backend/alembic.ini history`
  - Result: unchanged at `0010 (head)`.
- Docker/PostgreSQL verification:
  - Result: not run because this task changed no schema, migrations, Docker, Compose, transactions, row locks, or PostgreSQL-specific query behavior.

### Known Limitations

- History responses intentionally expose IDs rather than nested availability, spot, or user profiles.
- Reservation audit events are available through the separate admin assignment-audit API and are not embedded in history responses.
- `history_state` describes current-active versus historical lifecycle state; it does not separately identify the newest historical row when no active reservation exists.
- No admin reservation-history frontend screen exists.
- The known upstream `StarletteDeprecationWarning` from the FastAPI/TestClient stack remains and does not affect this task.
- The default `python` command is not available on PATH in this shell, so verification used the Codex bundled Python executable with `backend/.test-deps`.

### Next Suggested Task

Implement frontend parking user-flow groundwork: frontend API services and authenticated pages for open availabilities, publishing and cancelling own availabilities, applying and cancelling own applications, and viewing and cancelling own reservations. Do not implement admin frontend screens, audit UI, notifications, or new backend business logic.

## Task 41: Frontend Parking User-Flow Groundwork

### Files Changed

- `frontend/src/components/common/BaseButton.vue`
- `frontend/src/components/common/BaseInput.vue`
- `frontend/src/components/common/BaseTextarea.vue`
- `frontend/src/components/common/DateTimeDisplay.vue`
- `frontend/src/components/common/EmptyState.vue`
- `frontend/src/components/common/LoadingState.vue`
- `frontend/src/components/common/StatusBadge.vue`
- `frontend/src/components/dashboard/DashboardCard.vue`
- `frontend/src/composables/useAuthenticatedPage.js`
- `frontend/src/layouts/AppLayout.vue`
- `frontend/src/router/index.js`
- `frontend/src/services/apiErrors.js`
- `frontend/src/services/applicationService.js`
- `frontend/src/services/availabilityService.js`
- `frontend/src/services/reservationService.js`
- `frontend/src/styles/main.css`
- `frontend/src/views/AvailableSpotsView.vue`
- `frontend/src/views/DashboardView.vue`
- `frontend/src/views/MyApplicationsView.vue`
- `frontend/src/views/MyAvailabilitiesView.vue`
- `frontend/src/views/MyReservationsView.vue`
- `resources/docs/implementation_log.md`

### Frontend API Services

- Added `availabilityService.js` for:
  - listing open availability,
  - listing the current user's published availability,
  - publishing availability,
  - cancelling availability.
- Added `applicationService.js` for:
  - applying for availability,
  - listing the current user's applications,
  - reading one application,
  - cancelling an application.
- Added `reservationService.js` for:
  - listing the current user's reservations,
  - reading one reservation,
  - cancelling a reservation with an optional reason.
- All services reuse the existing authenticated Axios client and do not log tokens, credentials, or payloads.
- Added `apiErrors.js` to map known backend `401`, `403`, `404`, `409`, and `422` responses to stable user-facing messages without exposing raw internal details.

### Routes and Navigation

- Added authenticated routes:
  - `/availabilities`,
  - `/my-availabilities`,
  - `/my-applications`,
  - `/my-reservations`.
- Existing route-guard behavior redirects unauthenticated access to `/login`.
- Updated authenticated navigation to include:
  - Dashboard,
  - Available spots,
  - My availabilities,
  - My applications,
  - My reservations.
- Updated dashboard modules to link directly to the four parking workflows.
- Added `useAuthenticatedPage` to reuse current-user loading and logout behavior across authenticated pages.

### Implemented User Flows

- Available spots:
  - lists open availability,
  - shows spot ID, owner ID, start, end, priority window, status, and note,
  - allows application submission,
  - prevents rapid duplicate submission while a request is active,
  - disables application to the user's own availability,
  - shows clean loading, empty, success, and error states.
- My availabilities:
  - lists published availability,
  - publishes a parking spot with spot ID, start, end, and optional note,
  - converts browser-local date/time input to timezone-aware ISO values,
  - validates required values and end-after-start before submission,
  - cancels open availability,
  - shows status badges and action progress.
- My applications:
  - lists application history,
  - shows availability ID, status, note, and creation time,
  - cancels pending applications,
  - disables cancellation for non-pending applications.
- My reservations:
  - lists reservation history,
  - shows parking spot, start, end, and status,
  - accepts an optional cancellation reason,
  - cancels active reservations,
  - disables cancellation and reason entry for non-active reservations.

### Reusable UI and Styling

- Added:
  - `StatusBadge`,
  - `EmptyState`,
  - `LoadingState`,
  - `DateTimeDisplay`,
  - `BaseTextarea`.
- Extended:
  - `BaseButton` with compact and destructive variants,
  - `BaseInput` with required, minimum, and step support,
  - `DashboardCard` with route-link support.
- Added responsive operational tables, compact forms, action states, full-width workspace sections, and mobile horizontal-table handling.
- Preserved the existing blue/white design system and added restrained green, yellow, and red status/action colors.

### Review Notes

- The four new pages use only existing backend endpoints; no backend compatibility fix was required.
- API payload fields and date/time serialization match existing Pydantic schemas.
- Action buttons track request state to prevent rapid duplicate submissions.
- Only valid lifecycle actions are enabled:
  - open availability can be cancelled,
  - pending applications can be cancelled,
  - active reservations can be cancelled.
- Known backend error details are translated into safe user-facing messages; unknown internal details are not rendered.
- Existing local-storage token behavior remains centralized in the existing auth storage and API client.
- No tokens, passwords, or sensitive payloads are logged.
- Navigation and all new routes retain the existing authentication guard.
- No admin screens, audit UI, override UI, reassignment UI, notifications, ranking changes, backend logic, migrations, Docker, or Compose changes were introduced.

### Verification Results

- Frontend dependency installation:
  - Result: not required because `frontend/node_modules` and `package-lock.json` already existed.
- Frontend production build:
  - Initial command: `npm run build`
  - Result: blocked by the machine PowerShell execution policy for `npm.ps1`.
  - Final command: `npm.cmd run build`
  - Result: passed; Vite transformed `104 modules` and generated the production bundle in `frontend/dist`.
- Frontend lint/type/test scripts:
  - Command: `npm.cmd run`
  - Result: the project currently configures only `dev`, `build`, and `preview`; no lint, type-check, or frontend-test script exists.
- Frontend static route delivery:
  - Commands: HTTP GET requests to `/login`, `/dashboard`, `/availabilities`, `/my-availabilities`, `/my-applications`, and `/my-reservations` on the local Vite server.
  - Result: every route returned HTTP `200`.
- API contract smoke check:
  - Result: a temporary local mock API verified bearer login, current-user loading, and populated availability data contracts. The mock API was stopped and removed after verification.
- Browser visual verification:
  - Result: attempted twice with the in-app browser, but its Windows sandbox failed during startup. Visual screenshots and interactive browser checks remain to be completed manually.
- Backend tests, compile check, and Alembic checks:
  - Result: not run because no backend, schema, migration, Docker, or Compose files were changed.
- Local development server:
  - Result: running at `http://127.0.0.1:5173` with the normal `http://localhost:8000` backend configuration.

### Known Limitations

- Backend user-flow responses expose IDs rather than nested parking spot, owner, or availability details, so the frontend currently displays those IDs.
- Publishing availability requires manually entering a parking spot ID because there is no owner-facing spot-selector endpoint in the current backend API.
- The available-spots page does not yet include an application note field or advanced filtering.
- No availability-detail page or owner reassignment control exists.
- No frontend test runner, component tests, route-guard tests, or end-to-end tests are configured yet.
- Browser visual verification was blocked by the in-app browser Windows sandbox startup failure.
- Admin screens, audit UI, override UI, and notifications remain out of scope.

### Next Suggested Task

Add frontend testing groundwork with Vitest and Vue Test Utils, then add focused tests for status/date components, authenticated route guards, parking API services, publish-availability validation, application submission, and cancellation action-state behavior. Do not implement admin screens, audit UI, notifications, or new backend business logic yet.

## Task 42: Frontend Testing Groundwork

### Files Changed

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/vite.config.js`
- `frontend/src/router/index.js`
- `frontend/src/test/setup.js`
- `frontend/src/components/common/StatusBadge.spec.js`
- `frontend/src/components/common/DateTimeDisplay.spec.js`
- `frontend/src/router/index.spec.js`
- `frontend/src/services/parkingServices.spec.js`
- `frontend/src/views/MyAvailabilitiesView.spec.js`
- `frontend/src/views/AvailableSpotsView.spec.js`
- `frontend/src/views/MyReservationsView.spec.js`
- `resources/docs/implementation_log.md`

### Implemented

- Added Vitest, Vue Test Utils, and jsdom as frontend development dependencies.
- Added a frontend `test` script using Vitest's runner config loader for compatibility with the current Windows environment.
- Added shared test setup that clears local storage before tests and restores mocks after tests.
- Refactored router creation into a reusable `createAppRouter` factory while preserving the existing default production router and guard behavior.
- Added focused tests for:
  - status badge labels and lifecycle classes,
  - date/time rendering and fallback behavior,
  - authenticated route guards and login redirects,
  - availability, application, and reservation API service contracts,
  - publish-availability validation and payload normalization,
  - duplicate application-submission prevention,
  - reservation cancellation eligibility, optional reason handling, and duplicate-action prevention.

### Review Notes

- The router factory preserves the existing production router behavior while allowing isolated route-guard tests.
- Tests use jsdom and mock service boundaries rather than changing production workflow behavior.
- API service tests verify endpoint paths and payloads without logging tokens, passwords, or sensitive values.
- Lifecycle workflow tests verify invalid actions are disabled and rapid duplicate requests are prevented.
- No backend, schema, migration, Docker, Compose, admin UI, audit UI, override UI, notification, or parking business-logic changes were introduced.

### Tests Added

- `StatusBadge.spec.js`
- `DateTimeDisplay.spec.js`
- `router/index.spec.js`
- `parkingServices.spec.js`
- `MyAvailabilitiesView.spec.js`
- `AvailableSpotsView.spec.js`
- `MyReservationsView.spec.js`

### Verification Results

- Frontend test dependency installation:
  - Command: `npm.cmd install --save-dev vitest @vue/test-utils jsdom`
  - Result: passed; added `118 packages`, audited `182 packages`, and found `0 vulnerabilities`.
- Frontend tests:
  - Initial command: `npm.cmd test`
  - Initial result: failed because Vitest's default config loader could not read the Vite config through the current Windows sandbox.
  - Fix: configured the test script with `--configLoader runner`.
  - Final command: `npm.cmd test`
  - Final result: passed; `7 test files` and `13 tests` passed.
- Frontend production build:
  - Command: `npm.cmd run build`
  - Result: passed; Vite transformed `104 modules` and generated the production bundle.
- Frontend script review:
  - Command: `npm.cmd run`
  - Result: confirmed the `test` script is available; no lint or type-check scripts are currently configured.
- Dependency audit:
  - Command: `npm.cmd audit --omit=optional`
  - Result: passed; found `0 vulnerabilities`.
- Backend tests, backend compile check, Alembic checks, and Docker/PostgreSQL verification:
  - Result: not run because this task changed only frontend test infrastructure, frontend tests, and the router's testability structure.
- Browser visual verification:
  - Result: not required because this task made no visual UI changes.

### Known Limitations

- The new tests are focused component, router, service, and workflow tests; full browser end-to-end coverage is not configured.
- Coverage reporting and minimum coverage thresholds are not configured.
- jsdom does not verify behavior in a real browser runtime.
- The frontend still has no lint or type-check scripts.
- Admin role guards and admin management views are not implemented yet.

### Next Suggested Task

Implement frontend admin management groundwork: add admin API services, an admin-only route guard and navigation, and pages for teams, users, parking spots, applications, and reservation history. Do not implement audit-log UI, admin override UI, notifications, or new backend business logic yet.

## Task 43: Frontend Admin Management Groundwork

### Files Changed

- `frontend/src/components/admin/AdminPageHeader.vue`
- `frontend/src/components/admin/ConfirmAction.vue`
- `frontend/src/components/admin/ConfirmAction.spec.js`
- `frontend/src/components/admin/SelectField.vue`
- `frontend/src/layouts/AppLayout.vue`
- `frontend/src/layouts/AppLayout.spec.js`
- `frontend/src/router/index.js`
- `frontend/src/router/index.spec.js`
- `frontend/src/services/adminParkingApplicationService.js`
- `frontend/src/services/adminParkingSpotService.js`
- `frontend/src/services/adminReservationService.js`
- `frontend/src/services/adminServices.spec.js`
- `frontend/src/services/adminTeamService.js`
- `frontend/src/services/adminUserService.js`
- `frontend/src/services/apiErrors.js`
- `frontend/src/styles/main.css`
- `frontend/src/views/admin/AdminDashboardView.vue`
- `frontend/src/views/admin/AdminParkingApplicationsView.vue`
- `frontend/src/views/admin/AdminParkingSpotsView.vue`
- `frontend/src/views/admin/AdminReservationsView.vue`
- `frontend/src/views/admin/AdminTeamsView.vue`
- `frontend/src/views/admin/AdminTeamsView.spec.js`
- `frontend/src/views/admin/AdminUsersView.vue`
- `resources/docs/implementation_log.md`

### Implemented Admin Frontend Flows

- Added authenticated admin API service modules for:
  - team CRUD,
  - user CRUD,
  - parking spot CRUD,
  - read-only parking application listing,
  - current reservation and reservation-history listing.
- Added admin routes:
  - `/admin`,
  - `/admin/teams`,
  - `/admin/users`,
  - `/admin/parking-spots`,
  - `/admin/parking-applications`,
  - `/admin/reservations`.
- Added admin route metadata and guard behavior:
  - unauthenticated users are redirected to login,
  - authenticated non-admin users are redirected to the dashboard,
  - authenticated admin users with a stored current-user role can access admin routes.
- Added an admin-only navigation section with links to all implemented admin pages.
- Added an admin dashboard with direct links to team, user, parking spot, application, and reservation management.
- Added reusable admin components:
  - `AdminPageHeader`,
  - `SelectField`,
  - `ConfirmAction`.
- Added team management with list, create, edit, delete, loading, empty, success, and error states.
- Added user management with list, create, edit, delete, optional team assignment, role selection, active-state selection, create-only password input, and self-delete error mapping.
- Added parking spot management with list, create, edit, delete, owner assignment/unassignment, active-state selection, and owner/status filters.
- Added read-only parking application listing with availability and status filters.
- Added read-only reservation-history listing with user, parking spot, status, and current/historical filters.
- Extended user-facing API error mapping for known admin team, user, and parking spot errors.
- Extended the existing blue/white UI with responsive admin forms, filters, row actions, confirmation prompts, and active/inactive status styling.

### Review Notes

- All frontend service paths and payload fields were checked against the existing FastAPI admin routers and Pydantic schemas; no backend compatibility changes were required.
- The frontend route guard uses the stored current-user role for navigation and UX. Existing backend `require_admin` dependencies remain the authoritative security boundary, so modifying browser storage cannot grant API authorization.
- Admin navigation is rendered only when the loaded current user has the `admin` role.
- Destructive team, user, and parking spot actions require explicit confirmation before the API request is sent.
- User read data never renders or expects `hashed_password`.
- Password input is shown only while creating users. Password updates were intentionally omitted from the edit form to avoid accidental credential changes.
- Known validation and conflict responses are translated to user-facing messages; raw backend stack traces and unknown internal details are not rendered.
- No tokens, passwords, or sensitive values are logged.
- No audit-log UI, reservation override UI, notification UI, backend logic, migrations, Docker, or Compose changes were introduced.

### Tests Added or Updated

- Updated router tests to verify:
  - admin users can access admin routes,
  - authenticated non-admin users are redirected from admin routes.
- Added layout test verifying admin navigation is visible to admins and hidden from non-admin users.
- Added admin service tests for team, user, and parking spot list/create/update/delete API calls.
- Added `ConfirmAction` test verifying destructive actions require explicit confirmation.
- Added admin teams page smoke test verifying loaded data renders and deletion remains behind confirmation.

### Verification Results

- Frontend tests:
  - Command: `npm.cmd test`
  - Result: passed; `11 test files` and `21 tests` passed.
- Frontend production build:
  - Command: `npm.cmd run build`
  - Result: passed; Vite transformed `118 modules` and generated the production bundle.
- Frontend dependency audit:
  - Command: `npm.cmd audit --omit=optional`
  - Result: passed; found `0 vulnerabilities`.
- Frontend script review:
  - Command: `npm.cmd run`
  - Result: `dev`, `build`, `preview`, and `test` are configured; no lint or type-check scripts are configured.
- Sensitive logging/static review:
  - Command: `rg "console\\.|hashed_password|audit|override|notification" frontend/src -n`
  - Result: no matches.
- Browser visual verification:
  - Attempted the local admin route at `http://127.0.0.1:5173/admin`.
  - Result: blocked because the in-app browser Windows sandbox failed during startup.
- Backend tests, backend compile check, Alembic checks, and Docker/PostgreSQL verification:
  - Result: not run because no backend, schema, migration, Docker, or Compose files were changed.

### Known Limitations

- The frontend admin guard relies on the current user stored after `/auth/me`; backend authorization remains required and authoritative.
- List pages use backend default limits and do not yet expose pagination controls.
- Backend responses expose related entity IDs rather than nested display details, so some admin tables show IDs.
- User password updates are not exposed in the edit form.
- The reservation page uses the history endpoint as the combined current/historical view; a separate current-reservation view is not exposed.
- Browser visual and interactive verification remains blocked by the in-app browser Windows sandbox startup failure.
- Full browser end-to-end coverage, frontend linting, and frontend type checking are not configured.
- Audit-log screens, admin override controls, and notifications remain out of scope.

### Next Suggested Task

Implement frontend admin audit and reservation-override groundwork using the existing backend endpoints: add a read-only assignment audit-log page and explicit, reason-required reservation override/cancellation controls with focused tests. Do not add notifications, change backend ranking/assignment behavior, or add unrelated backend logic.

## Task 44: Frontend Admin Audit-Log and Reservation-Override Groundwork

### Files Changed

- `frontend/src/components/admin/AdminOverrideForm.vue`
- `frontend/src/components/admin/AdminOverrideForm.spec.js`
- `frontend/src/components/admin/JsonDetailsViewer.vue`
- `frontend/src/components/admin/ReservationSummaryCard.vue`
- `frontend/src/layouts/AppLayout.vue`
- `frontend/src/layouts/AppLayout.spec.js`
- `frontend/src/router/index.js`
- `frontend/src/router/index.spec.js`
- `frontend/src/services/adminAssignmentAuditLogService.js`
- `frontend/src/services/adminAuditOverrideServices.spec.js`
- `frontend/src/services/adminReservationOverrideService.js`
- `frontend/src/services/apiErrors.js`
- `frontend/src/styles/main.css`
- `frontend/src/views/admin/AdminAssignmentAuditLogsView.vue`
- `frontend/src/views/admin/AdminAssignmentAuditLogsView.spec.js`
- `frontend/src/views/admin/AdminDashboardView.vue`
- `frontend/src/views/admin/AdminOverridesView.vue`
- `frontend/src/views/admin/AdminOverridesView.spec.js`
- `resources/docs/implementation_log.md`

### Implemented

- Added authenticated admin audit-log service support for:
  - listing assignment audit logs,
  - reading one audit log,
  - reading an audit log by reservation ID.
- Added authenticated admin reservation-override service support for:
  - manual assignment override,
  - replacement assignment override.
- Added guarded admin routes:
  - `/admin/audit-logs`,
  - `/admin/overrides`.
- Added `Audit logs` and `Overrides` to admin-only navigation and the admin dashboard.
- Added a read-only assignment audit-log page with filters for:
  - availability ID,
  - reservation ID,
  - selected user ID,
  - trigger source,
  - ranking policy.
- Added audit-log table output for assignment identifiers, trigger source, ranking policy, creation time, ranking details, and rejected application IDs.
- Added expandable `JsonDetailsViewer` output that formats audit JSON as escaped text instead of rendering it as HTML.
- Added a dedicated reservation-override workspace with:
  - manual assignment form,
  - replacement assignment form,
  - mandatory trimmed reason validation,
  - positive availability/application ID validation,
  - duplicate-submission guards,
  - success and error feedback,
  - returned reservation summaries.
- Extended known user-facing error mappings for override validation, availability/application conflicts, inactive applicants, and reservation conflicts.

### Override UI Placement Decision

- Chose a dedicated `/admin/overrides` page instead of embedding forms in reservation history.
- This keeps high-impact, reason-required actions separate from the read-only history workflow and gives both manual and replacement assignments clear context.
- Form values intentionally remain after a successful override so an administrator can review the submitted identifiers and reason alongside the returned reservation summary.

### Review Notes

- All audit and override service paths and payload fields were checked against the existing FastAPI routers and Pydantic schemas; no backend compatibility changes were required.
- Audit and override routes reuse the existing `requiresAdmin` route metadata. The non-admin route test now targets `/admin/overrides` explicitly.
- Existing backend `require_admin` dependencies remain the authoritative authorization boundary.
- Ranking details and rejected application IDs are rendered through Vue text interpolation and `JSON.stringify`; HTML-like audit values are escaped and never injected as markup.
- Both override forms require a nonblank reason and valid positive integer IDs before emitting a request.
- Override services trim reasons before sending them.
- Rapid duplicate override submissions are ignored while the relevant request is active.
- No passwords, tokens, hashes, or raw backend stack traces are displayed or logged by the new code.
- No notifications, backend logic, ranking policy, migrations, Docker, or Compose changes were introduced.

### Tests Added or Updated

- Added audit/override service tests verifying:
  - audit list/detail/by-reservation request construction,
  - manual override endpoint and payload,
  - replacement override endpoint and payload.
- Added override-form tests verifying:
  - manual override requires a reason,
  - replacement override requires a reason,
  - valid values are normalized and emitted.
- Added audit-log page tests verifying:
  - mocked audit rows render,
  - ranking details render readably,
  - HTML-like ranking details are safely escaped,
  - filters call the service with normalized parameters.
- Added override-page tests verifying:
  - successful manual override shows a reservation summary,
  - successful replacement override shows a reservation summary.
- Updated navigation and route-guard tests to verify:
  - admins see `Audit logs`,
  - non-admin users do not see `Audit logs`,
  - admins can access the audit-log route,
  - non-admin users are redirected from the override route.

### Verification Results

- Frontend tests:
  - Command: `npm.cmd test`
  - Result: passed; `15 test files` and `31 tests` passed.
- Frontend production build:
  - Command: `npm.cmd run build`
  - Result: passed; Vite transformed `125 modules` and generated the production bundle.
- Frontend dependency audit:
  - Command: `npm.cmd audit --omit=optional`
  - Result: passed; found `0 vulnerabilities`.
- Frontend script review:
  - Command: `npm.cmd run`
  - Result: `dev`, `build`, `preview`, and `test` are configured; no lint or type-check scripts are configured.
- Sensitive logging/static review:
  - Command: scoped `rg "console\\.|hashed_password|access_token|password"` across the new audit/override views, components, and services.
  - Result: no matches.
- Static local route delivery:
  - Command: HTTP GET request to `http://127.0.0.1:5173/admin/overrides`.
  - Result: HTTP `200`.
- Browser visual verification:
  - Attempted the local override route with the in-app browser.
  - Result: blocked because the in-app browser Windows sandbox failed during startup.
- Backend tests, backend compile check, Alembic checks, and Docker/PostgreSQL verification:
  - Result: not run because no backend, schema, migration, Docker, or Compose files were changed.

### Known Limitations

- Audit-log listing uses the backend default limit and has no frontend pagination controls.
- Audit filters use exact IDs/source/policy values and do not provide free-text search.
- Audit details are readable formatted JSON but are not transformed into a domain-specific decision explanation.
- Override forms rely on the backend for application/availability compatibility checks and display related records by ID.
- Override actions require a reason but do not include a separate second-step confirmation dialog.
- Form values remain after successful overrides by design and must be manually changed for a new action.
- Browser visual and interactive verification remains blocked by the in-app browser Windows sandbox startup failure.
- Full browser end-to-end coverage, frontend linting, and frontend type checking are not configured.
- Notifications remain outside the planned MVP scope.

### Next Suggested Task

Start Phase 8 reporting groundwork with read-only admin operational summaries and export support: define safe summary/count API contracts, add admin dashboard summary cards, and add CSV export for filtered applications, reservations, and assignment audit logs with focused backend/frontend tests. Do not implement notifications or change ranking/assignment behavior.

## Task 45: Phase 8 Admin Reporting and Export Groundwork

### Files Changed

- `backend/app/main.py`
- `backend/app/routers/admin_reports.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/admin_report.py`
- `backend/app/services/__init__.py`
- `backend/app/services/admin_reports.py`
- `backend/tests/test_admin_reports.py`
- `frontend/src/layouts/AppLayout.vue`
- `frontend/src/layouts/AppLayout.spec.js`
- `frontend/src/router/index.js`
- `frontend/src/router/index.spec.js`
- `frontend/src/services/adminReportService.js`
- `frontend/src/services/adminReportService.spec.js`
- `frontend/src/styles/main.css`
- `frontend/src/views/admin/AdminDashboardView.vue`
- `frontend/src/views/admin/AdminReportsView.vue`
- `frontend/src/views/admin/AdminReportsView.spec.js`
- `resources/docs/implementation_log.md`

### Reports Implemented

- Added a dedicated read-only `AdminReportService` query layer.
- Added typed Pydantic report schemas for:
  - reservation summaries,
  - availability summaries,
  - application summaries,
  - audit-trigger counts,
  - top reserved users,
  - parking spot usage,
  - combined admin summary output.
- Added admin-only endpoints:
  - `GET /admin/reports/summary`,
  - `GET /admin/reports/top-users`,
  - `GET /admin/reports/parking-spot-usage`.
- Combined summary output includes:
  - total, active, cancelled, and completed reservations,
  - total, open, assigned, cancelled, and expired availabilities,
  - open availabilities without any reservation,
  - total, pending, selected, rejected, and cancelled applications,
  - assignment audit counts grouped by trigger source.
- Top reserved-user and parking-spot usage reports count active and completed reservations only. Cancelled reservations remain visible in summary/history reporting but do not count as wins or usage.
- Top-user and parking-spot results are deterministically ordered by reservation count descending and then ID ascending.
- Audit-trigger results are deterministically ordered by count descending and then trigger-source text.

### Date Filter Convention

- All reporting endpoints and CSV exports support optional `date_from` and `date_to` query parameters.
- Filters apply consistently to each record's `created_at` timestamp.
- `date_from` and `date_to` are inclusive UTC calendar dates.
- Reversed date ranges and invalid date values return HTTP `422`.
- The frontend exposes the same created-date filter convention and validates reversed ranges before making requests.

### CSV Export Decision

- Added admin-only CSV endpoints:
  - `GET /admin/reports/reservations.csv`,
  - `GET /admin/reports/availabilities.csv`,
  - `GET /admin/reports/applications.csv`,
  - `GET /admin/reports/audit-logs.csv`.
- CSV output uses Python's standard `csv` module, stable headers, deterministic created-at/ID ordering, `text/csv`, and attachment filenames.
- Audit CSV intentionally excludes raw `ranking_details` and `rejected_application_ids`; it exports only operational assignment metadata.
- CSV exports omit passwords, hashes, tokens, and nested user records.
- String values beginning with spreadsheet formula characters (`=`, `+`, `-`, `@`) are prefixed with an apostrophe to reduce formula-injection risk.
- The frontend downloads CSV through the existing authenticated Axios client, so bearer tokens are not placed in download URLs.

### Frontend Reporting UI

- Added guarded admin route `/admin/reports`.
- Added `Reports` to admin-only navigation and the admin dashboard.
- Added an operational reports page with:
  - inclusive created-date filters,
  - summary cards,
  - reservation, availability, and application lifecycle counts,
  - top reserved-user table,
  - parking spot usage table,
  - audit-trigger summary table,
  - authenticated CSV download buttons.
- Preserved the existing blue/white operational design and responsive table/card behavior.

### Review Notes

- All reporting routes are protected by the existing backend `require_admin` dependency and the frontend `requiresAdmin` route metadata.
- Reporting queries are read-only and do not modify repositories, ranking, assignment, or reservation lifecycle behavior.
- Summary status counts include all records in the selected creation-date range.
- Winner and usage rankings exclude cancelled reservations to avoid counting cancelled/replaced assignments as successful usage.
- `open_without_reservation` counts open availability records with no reservation row.
- Date filtering is consistent across summary, ranking, usage, audit, and CSV queries.
- Audit-trigger tie ordering is explicitly cast to text so SQLite and PostgreSQL use the same deterministic ordering.
- PostgreSQL SQL compilation for the audit-trigger grouped query passed.
- No sensitive fields or raw audit JSON are included in CSV output.
- No new external reporting dependencies, migrations, charts, PDF exports, scheduled reports, email delivery, or external BI integrations were introduced.

### Tests Added or Updated

- Added backend reporting tests for:
  - deterministic summary counts,
  - inclusive created-date filters,
  - top reserved-user ordering,
  - parking spot usage ordering,
  - audit-trigger counts,
  - admin authorization,
  - missing/invalid-token behavior,
  - invalid/reversed date filters,
  - all four CSV content types and stable headers,
  - sensitive-data exclusion,
  - spreadsheet formula neutralization.
- Added frontend reporting-service tests for:
  - summary, top-user, and parking-spot usage request construction,
  - authenticated CSV download behavior.
- Added frontend reports-page tests for:
  - summary and lifecycle rendering,
  - top-user and parking-spot rows,
  - audit-trigger rendering,
  - date-filter propagation,
  - CSV export controls.
- Updated admin navigation and route tests to cover `Reports`.

### Verification Results

- Focused backend reporting tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest tests/test_admin_reports.py`
  - Result: passed; `13 tests` passed with `1` existing Starlette/httpx deprecation warning.
- Full backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest`
  - Result: passed; `538 tests` passed with `1` existing Starlette/httpx deprecation warning.
- Backend compile check:
  - Command: bundled Python `-m compileall app tests`
  - Result: passed.
- Alembic:
  - Commands: bundled Python `-m alembic -c alembic.ini heads` and `history`
  - Result: passed; current head remains `0010`.
- PostgreSQL query compatibility:
  - Command: compiled the deterministic audit-trigger grouped query using SQLAlchemy's PostgreSQL dialect.
  - Result: passed.
- Frontend tests:
  - Command: `npm.cmd test`
  - Result: passed; `17 test files` and `37 tests` passed.
- Frontend production build:
  - Command: `npm.cmd run build`
  - Result: passed; Vite transformed `127 modules` and generated the production bundle.
- Frontend dependency audit:
  - Command: `npm.cmd audit --omit=optional`
  - Result: passed; found `0 vulnerabilities`.
- Sensitive-data static review:
  - Result: no password, hash, access-token, sensitive logging, raw ranking-details, or rejected-application-ID output was found in the new reporting boundary.
- Static local route delivery:
  - Command: HTTP GET request to `http://127.0.0.1:5173/admin/reports`.
  - Result: HTTP `200`.
- Docker Compose:
  - Command: `docker-compose config`
  - Result: passed; Compose configuration rendered successfully.
  - Command: `docker-compose ps`
  - Result: Docker daemon unavailable; PostgreSQL runtime verification could not be performed.
  - The installed `docker` CLI does not support the newer `docker compose` subcommand.
- Browser visual verification:
  - Attempted the local reports route with the in-app browser.
  - Result: blocked because the in-app browser Windows sandbox failed during startup.

### Known Limitations

- Reporting queries and CSV exports load the selected result set into memory and do not yet stream or paginate exports; this is suitable for the current MVP dataset size.
- Reports use UTC `created_at` calendar dates only and do not support administrator-selected time zones or event/start-date reporting.
- Top-user and parking-spot reports display IDs because current backend report contracts do not include nested display names/codes.
- Winner and usage reports count active/completed reservations and do not implement more advanced fairness analytics.
- Summary generation executes multiple simple aggregate queries instead of a materialized reporting model.
- PostgreSQL query compilation passed, but live PostgreSQL reporting execution was not verified because the Docker daemon was unavailable.
- Browser visual and interactive verification remains blocked by the in-app browser Windows sandbox startup failure.
- Charts, scheduled reports, email delivery, PDF export, and external BI integration remain out of scope.

### Next Suggested Task

Start Phase 9 production-readiness groundwork with structured backend request/error logging, safe global error-handling middleware, and focused tests. Document deployment, database backup/restore, and security-review guidance without implementing SSO or changing parking business logic.

## Task 46: Phase 9 Structured Logging, Global Error Handling, and Deployment/Security Documentation

### Files Changed

- `.env.example`
- `backend/.env.example`
- `docker-compose.yml`
- `backend/app/core/config.py`
- `backend/app/core/logging.py`
- `backend/app/main.py`
- `backend/app/middleware/__init__.py`
- `backend/app/middleware/request_context.py`
- `backend/tests/test_infrastructure_files.py`
- `backend/tests/test_production_readiness.py`
- `resources/docs/deployment_security.md`
- `resources/docs/implementation_log.md`

### Logging and Error-Handling Decisions

- Added environment-driven standard Python logging with `LOG_LEVEL=INFO` and `LOG_JSON=true` defaults.
- JSON logs include UTC timestamp, level, logger, event, and available structured HTTP fields.
- Added validated request-ID propagation through `X-Request-ID`, request state, and a context variable.
- Valid safe client request IDs are preserved; missing or unsafe IDs are replaced with generated UUIDs.
- Request logs include method, canonical route template, status code, duration, and request ID.
- Query strings, unmatched raw paths, request bodies, headers, authorization values, passwords, tokens, user data, exception messages, and source-code lines are omitted from emitted HTTP/error logs.
- Unhandled errors are logged once with request ID, exception type, and sanitized stack-frame locations.
- Unhandled API errors return a stable generic `500` response with `detail`, `request_id`, and `error_code`.
- Existing HTTPException and validation error bodies remain unchanged for API-client compatibility; their request ID is available in the response header.
- Added a registered global exception-handler fallback in addition to the outer request-context middleware.

### Security Header Decisions

- Added `X-Content-Type-Options: nosniff`.
- Added `X-Frame-Options: DENY`.
- Added `Referrer-Policy: no-referrer`.
- Exposed `X-Request-ID` through the existing CORS middleware.
- Content Security Policy remains a frontend nginx/ingress concern because the API and frontend are served separately.

### Documentation Added

- Added `resources/docs/deployment_security.md` covering:
  - local Docker Compose startup and migrations,
  - frontend/backend/database endpoints,
  - assignment scheduler command,
  - logging and environment configuration,
  - CORS, JWT, password-hashing, and security-header guidance,
  - PostgreSQL volume, backup, and restore guidance,
  - production deployment checklist,
  - current deployment/security limitations.

### Review Notes

- Logging configuration is idempotent and updates only its marked application handler without clearing pytest or third-party handlers.
- Request ID input is restricted to a short safe-character format before it can enter logs or response headers.
- Canonical route templates are logged instead of dynamic path values; unknown paths use `<unmatched>`.
- Error log formatting intentionally excludes exception messages and source-code text to reduce accidental sensitive-data exposure.
- Normal requests produce one completion log; unhandled failures produce one error log without an additional completion log.
- Middleware ordering keeps request IDs and security headers on CORS and application responses.
- Existing HTTP status codes and response contracts remain unchanged except for generic unhandled `500` responses.
- No business logic, schema, migrations, frontend files, external observability services, or new dependencies were changed.

### Tests Added or Updated

- Added focused tests for:
  - preserved, generated, and unsafe/replaced request IDs,
  - request IDs and security headers on responses,
  - generic unhandled `500` responses without stack-trace leakage,
  - preserved HTTPException and validation response behavior,
  - sensitive header, query, path, and body exclusion from request logs,
  - request ID and error code in failure logs,
  - exception-message omission from JSON logs,
  - JSON/text logging initialization,
  - log-level normalization and validation.
- Updated infrastructure tests for Compose and environment-example logging values.

### Verification Results

- Focused production-readiness and infrastructure tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest tests/test_production_readiness.py tests/test_infrastructure_files.py`
  - Result: passed; `20 tests` passed with `1` existing Starlette/httpx deprecation warning.
- Full backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest`
  - Result: passed; `551 tests` passed with `1` existing Starlette/httpx deprecation warning.
- Backend compile check:
  - Command: bundled Python `-m compileall app tests`
  - Result: passed.
- Alembic:
  - Commands: bundled Python `-m alembic -c alembic.ini heads` and `history`
  - Result: passed; current head remains `0010`.
- Docker Compose static configuration:
  - Command: `docker-compose config`
  - Result: passed; logging environment values rendered successfully. Docker reported an access warning for the user-level Docker config file.
- Docker/PostgreSQL runtime:
  - Command: `docker-compose ps`
  - Result: could not connect because the Docker Desktop daemon is unavailable.
- Frontend verification:
  - Not run because no frontend files were changed.

### Known Limitations

- Docker/PostgreSQL runtime, migrations against live PostgreSQL, and full service startup were not reverified because Docker Desktop is unavailable.
- Structured logs currently write only to process stdout/stderr; external aggregation, metrics, tracing, and alerting remain out of scope.
- Request IDs correlate backend records only and are not distributed tracing identifiers.
- Existing HTTPException and validation bodies do not include request IDs; clients should read `X-Request-ID`.
- Content Security Policy must be configured and verified at the frontend nginx or ingress layer.
- The current local Compose deployment has no TLS, production secret integration, replicas, resource limits, or restart policy.
- SSO/OIDC, refresh-token rotation, token revocation, rate limiting, and CSRF controls remain unimplemented.

### Next Suggested Task

Complete the remaining Phase 9 readiness work with hardened production CORS validation, automated smoke tests for the Dockerized critical path, SSO/OIDC integration notes, and final Docker/PostgreSQL runtime verification when Docker Desktop is available. Do not change parking business logic.

## Task 47: Final Phase 9 CORS Hardening, Smoke Tests, and SSO/OIDC Notes

### Files Changed

- `.env.example`
- `backend/.env.example`
- `frontend/.env.example`
- `docker-compose.yml`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/routers/auth.py`
- `backend/tests/test_auth_api.py`
- `backend/tests/test_infrastructure_files.py`
- `backend/tests/test_production_readiness.py`
- `scripts/smoke_test.ps1`
- `resources/docs/deployment_security.md`
- `resources/docs/implementation_log.md`

### CORS Hardening Decisions

- Added validated, environment-driven `CORS_ALLOWED_ORIGINS` and `CORS_ALLOW_CREDENTIALS` behavior.
- Local defaults remain the exact Vite/nginx origins: `http://localhost:5173` and `http://localhost:8080`.
- Wildcards, empty lists, non-HTTP(S) values, URL paths, query strings, fragments, embedded credentials, whitespace, backslashes, and invalid ports are rejected during settings validation.
- Duplicate origins and a single trailing slash are normalized.
- `ENVIRONMENT=production` or `prod` rejects localhost and loopback origins, forcing an explicit deployment origin.
- `CORS_ALLOW_CREDENTIALS` now defaults to `false`. The frontend uses bearer `Authorization` headers and does not need browser credential mode.
- Credential mode remains configurable for future cookie/client-certificate use and is tested with exact origins.
- Cross-origin methods and non-safelisted headers are explicitly limited instead of using wildcard method/header configuration.
- Request ID and security-header middleware remains outside CORS handling, so preflight and CORS responses retain `X-Request-ID` and hardening headers.

### Smoke Test Approach

- Added `scripts/smoke_test.ps1` for Windows-friendly Dockerized critical-path verification.
- The script checks:
  - backend `/health`,
  - frontend `/`, `/login`, and `/dashboard`,
  - unauthenticated `/auth/me` and `/admin/teams` rejection,
  - allowed-origin CORS preflight,
  - Alembic current/head state,
  - optional login, authenticated `/auth/me`, and admin authorization behavior.
- No seed user was invented. Authenticated checks run only when `SMOKE_LOGIN_IDENTIFIER` and `SMOKE_LOGIN_PASSWORD` are supplied through the current process environment.
- Passwords cannot be supplied as command-line script parameters and are never printed.
- Added PowerShell parser validation and static tests for expected checks and absence of known development secrets.

### SSO/OIDC Documentation Summary

- Extended `resources/docs/deployment_security.md` with a future company OIDC design covering:
  - authorization code flow with PKCE,
  - backend signature/issuer/audience/expiration validation,
  - discovery and JWKS rotation,
  - immutable external identity linking,
  - group/application-role mapping to local roles and teams,
  - staged migration from local passwords,
  - protected break-glass admin fallback,
  - refresh-token storage/rotation,
  - logout and revocation limitations.
- No SSO/OIDC runtime code or external identity-provider dependency was added.

### Review Notes

- Removed an existing `print(credentials)` statement from `/auth/login`; login identifiers and passwords are no longer written to stdout.
- Added regression coverage confirming submitted login passwords are not printed.
- Confirmed the current frontend Axios client uses bearer headers and does not enable browser credential mode.
- Confirmed configured origins receive exact allow-origin behavior; unconfigured origins do not receive `Access-Control-Allow-Origin`.
- Confirmed allowed preflight responses preserve request IDs and security headers.
- Confirmed production settings cannot silently start with local-development CORS origins.
- Confirmed environment examples contain only development placeholders and explicit production-security guidance.
- Confirmed smoke credentials, JWT values, and bearer tokens are not committed in the new script or documentation.
- No parking business logic, database schema, migration, frontend feature, or external integration was changed.

### Tests Added or Updated

- Added focused tests for:
  - configured allowed-origin responses,
  - allowed preflight headers and methods,
  - disallowed simple and preflight requests,
  - configurable credential-header behavior,
  - request ID and security headers on CORS responses,
  - exact-origin normalization,
  - unsafe-origin rejection,
  - production local-origin rejection,
  - Compose/env example CORS configuration,
  - smoke-script critical checks and secret exclusion,
  - login credential stdout exclusion.

### Verification Results

- Focused CORS/hardening/auth tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest tests/test_production_readiness.py tests/test_infrastructure_files.py tests/test_auth_api.py`
  - Result: passed; `41 tests` passed with `1` existing Starlette/httpx deprecation warning.
- Full backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest`
  - Result: passed; `565 tests` passed with `1` existing Starlette/httpx deprecation warning.
- Backend compile check:
  - Command: bundled Python `-m compileall app tests`
  - Result: passed.
- Alembic:
  - Commands: bundled Python `-m alembic -c alembic.ini heads` and `history`
  - Result: passed; current head remains `0010`.
- Frontend tests:
  - Command: `npm.cmd test`
  - Result: passed; `17 test files` and `37 tests` passed.
- Frontend production build:
  - Command: `npm.cmd run build`
  - Result: passed; Vite transformed `127 modules` and generated the production bundle.
- Frontend dependency audit:
  - Command: `npm.cmd audit --omit=optional`
  - Result: passed; found `0 vulnerabilities`.
- Smoke-script syntax:
  - Command: PowerShell AST parser against `scripts/smoke_test.ps1`
  - Result: passed.
- Sensitive-data static review:
  - Result: no credential-print statement, committed smoke credential, known development password, or bearer token was found in the changed security boundary.
- Docker Compose static configuration:
  - Command: `docker-compose config`
  - Result: passed; exact origins and `CORS_ALLOW_CREDENTIALS=false` rendered successfully. Docker reported an access warning for the user-level Docker config file.
- Docker/PostgreSQL runtime:
  - Command: `docker-compose ps`
  - Result: failed because the Docker Desktop daemon is unavailable.
  - Build, startup, live PostgreSQL migration, live health/frontend/CORS checks, smoke-script execution, and shutdown were not attempted after the daemon check failed.
  - The installed `docker` CLI still does not expose the `docker compose` subcommand; the project uses the available `docker-compose` executable.

### Known Limitations

- Live Docker/PostgreSQL and full smoke-script verification remain pending until Docker Desktop is running.
- No prepared disposable user exists by default, so authenticated smoke checks require a manually prepared account.
- Actual SSO/OIDC, identity linking, group mapping, refresh-token rotation, and session revocation remain future work.
- Local JWT/password authentication remains the implemented MVP authentication mechanism.
- CORS production validation blocks loopback origins but cannot determine whether a non-loopback origin is organizationally approved; deployment review must verify the list.
- The existing Starlette/httpx test-client deprecation warning remains.

### Next Suggested Task

Run final MVP acceptance and release-candidate verification when Docker Desktop is available: build all services, apply migrations against PostgreSQL, execute `scripts/smoke_test.ps1` with a prepared admin, verify the documented MVP acceptance criteria end to end, and record release status. Do not add new features unless verification exposes a defect.

## Task 48: Live Docker/PostgreSQL Smoke Verification

### Files Changed

- `resources/docs/implementation_log.md`

### Docker Desktop and Compose Status

- Docker Desktop was available and the Docker Engine reported version `28.5.1`.
- The installed standalone `docker-compose` executable reported Compose version `v2.40.0-desktop.1`.
- The installed `docker` executable still does not expose the `docker compose` subcommand and returns `docker: unknown command: docker compose`.
- Live verification therefore used the functionally equivalent available `docker-compose` executable.

### Docker Build and Startup Results

- Command: `docker-compose config`
  - Result: passed; backend, frontend, PostgreSQL, ports, volume, CORS, and environment configuration rendered successfully.
- Command: `docker-compose build backend frontend`
  - Result: passed; both images built successfully.
  - Backend image: `parkingapp-backend`.
  - Frontend image: `parkingapp-frontend`.
  - Frontend image build ran `npm ci` and the Vite production build; npm reported `0 vulnerabilities`.
- Commands: `docker-compose up -d db backend frontend` and `docker-compose ps`
  - Result: passed.
  - PostgreSQL reported healthy.
  - Backend was available on host port `8000`.
  - Frontend nginx was available on host port `8080`.

### Live PostgreSQL Migration Verification

- Command: `docker-compose exec -T backend alembic -c alembic.ini upgrade head`
  - Result: passed against PostgreSQL.
  - The preserved local database was upgraded from revision `0008` through `0009` to `0010`.
- Commands:
  - `docker-compose exec -T backend alembic -c alembic.ini current`
  - `docker-compose exec -T backend alembic -c alembic.ini heads`
  - Result: both reported `0010 (head)`.
- PostgreSQL startup logs confirmed the existing named-volume database was reused and became ready to accept connections.

### Backend Live Smoke Results

- `GET http://localhost:8000/health`
  - Result: HTTP `200`.
  - Body: `{"status":"ok","service":"Parking Management API","environment":"local"}`.
  - Returned a generated `X-Request-ID`.
  - Returned `X-Content-Type-Options: nosniff`.
  - Returned `X-Frame-Options: DENY`.
  - Returned `Referrer-Policy: no-referrer`.
- Allowed-origin preflight to `OPTIONS http://localhost:8000/auth/me` with origin `http://localhost:8080`
  - Result: HTTP `200`.
  - Returned `Access-Control-Allow-Origin: http://localhost:8080`.
  - Allowed methods: `GET, POST, PUT, PATCH, DELETE, OPTIONS`.
  - Allowed requested headers including `Authorization` and `X-Request-ID`.
  - Did not return `Access-Control-Allow-Credentials`, consistent with the configured default `false`.
  - Returned request ID and security headers.
- Unauthenticated protected checks:
  - `GET /auth/me`: HTTP `401`.
  - `GET /admin/teams`: HTTP `401`.

### Frontend Live Smoke Results

- nginx/Vue Router history fallback returned HTTP `200`, `text/html`, and the Vue app root for:
  - `http://localhost:8080/`
  - `http://localhost:8080/login`
  - `http://localhost:8080/dashboard`
  - `http://localhost:8080/availabilities`
  - `http://localhost:8080/admin`
- Container logs showed normal nginx startup and successful route delivery.
- An unrelated browser request for `/favicon.ico` returned `404`; this does not affect the requested route or application smoke checks.

### Smoke Script Result

- Direct command: `.\scripts\smoke_test.ps1`
  - Result: blocked by the workstation's PowerShell script-execution policy.
- Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1`
  - Result: passed using a process-scoped execution-policy bypass; no system policy was changed.
- Passed checks:
  - backend health,
  - frontend `/`, `/login`, and `/dashboard`,
  - unauthenticated `/auth/me`,
  - unauthenticated admin endpoint,
  - allowed-origin CORS preflight,
  - Alembic current revision at head.
- Authenticated checks were skipped because `SMOKE_LOGIN_IDENTIFIER` and `SMOKE_LOGIN_PASSWORD` were not provided.
- Repository/documentation search found no documented safe seed, bootstrap, or local admin creation command. No user or credential was invented.

### Regression Verification Results

- Full backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest`
  - Result: passed; `565 tests` passed with `1` existing Starlette/httpx deprecation warning.
- Backend compile check:
  - Command: bundled Python `-m compileall app tests`
  - Result: passed.
- Local Alembic metadata:
  - Commands: bundled Python `-m alembic -c alembic.ini heads` and `history`
  - Result: passed; current head remains `0010`.
- Frontend tests:
  - Command: `npm.cmd test`
  - Result: passed; `17 test files` and `37 tests` passed.
- Frontend production build:
  - Command: `npm.cmd run build`
  - Result: passed; Vite transformed `127 modules` and generated the production bundle.
- Frontend dependency audit:
  - Command: `npm.cmd audit --omit=optional`
  - Result: passed; found `0 vulnerabilities`.
- Live container status and logs:
  - Result: PostgreSQL remained healthy; backend/frontend remained running; no application errors were found.

### Cleanup Result

- Command: `docker-compose down`
  - Result: passed; frontend, backend, database containers, and the Compose network were stopped and removed.
- No `-v` option was used.
- Command: `docker volume inspect parkingapp_postgres_data`
  - Result: passed; the `parkingapp_postgres_data` named PostgreSQL volume remains preserved.

### Review Notes

- Live verification exposed no backend, frontend, migration, CORS, security-header, or Compose configuration defect requiring a code fix.
- The preserved PostgreSQL database successfully upgraded to the latest migration head.
- Container logs confirmed structured backend request logging and expected unauthenticated `401` behavior.
- No new features, business logic, models, endpoints, frontend screens, migrations, seed data, or secrets were added.

### Known Limitations

- Authenticated login, `/auth/me`, admin authorization, and full role-based MVP workflows were not verified live because no prepared local user credentials or documented safe seed mechanism exist.
- The workstation requires a process-scoped PowerShell execution-policy bypass to run the checked-in smoke script.
- The installed Docker CLI does not support `docker compose`; verification used the available `docker-compose` v2 executable.
- The existing Starlette/httpx test-client deprecation warning remains.
- The frontend currently has no favicon, so `/favicon.ico` returns `404`.

### Next Suggested Task

Perform authenticated end-to-end MVP acceptance and release-candidate sign-off with an approved manually prepared admin, employee, parking owner, teams, and parking spot dataset. Run the complete create-availability, apply, assign, reserve, cancel/reassign, admin override, audit, and reporting workflows without adding new features unless verification exposes a defect.

## Task 49: Safe Local Admin Seed Command

### Files Changed

- `.env.example`
- `backend/.env.example`
- `docker-compose.yml`
- `backend/app/core/config.py`
- `backend/app/commands/seed_admin.py`
- `backend/tests/test_seed_admin_command.py`
- `backend/tests/test_infrastructure_files.py`
- `scripts/smoke_test.ps1`
- `resources/docs/deployment_security.md`
- `resources/docs/implementation_log.md`

### Seed Safety Decisions

- Added the import-safe command `python -m app.commands.seed_admin`.
- Added optional seed settings using `SEED_ADMIN_*` environment variables.
- `SEED_ADMIN_ENABLED` defaults to `false`; disabled execution exits successfully without opening a database session or changing data.
- Execution is allowed only in `local`, `development`, `dev`, and `test` environments. Production, staging, and every other environment are refused.
- Email, username, password, first name, and last name are required when enabled and validated through the existing `UserCreate` schema.
- The configured password is held as Pydantic `SecretStr`, validated against existing password constraints, hashed with the existing bcrypt helper, and never printed.
- Creation sets the user to active admin.
- Existing matching users are updated to the configured profile, active state, and admin role.
- Existing passwords are preserved unless `SEED_ADMIN_UPDATE_PASSWORD=true`.
- If configured email and username resolve to different users, the command refuses to merge or overwrite either account.
- Database changes commit on success and roll back on failure.
- Command failures print only safe summaries or exception type names, never credential values or hashes.

### Smoke Test Integration

- Updated `scripts/smoke_test.ps1` to select the first complete credential pair from:
  1. `SMOKE_TEST_USERNAME` and `SMOKE_TEST_PASSWORD`,
  2. legacy `SMOKE_LOGIN_IDENTIFIER` and `SMOKE_LOGIN_PASSWORD`,
  3. `SEED_ADMIN_USERNAME` and `SEED_ADMIN_PASSWORD`.
- Username and password values are selected only from the same complete pair; values from different sources cannot be mixed.
- Authenticated smoke checks verify login, `/auth/me`, and an admin endpoint.
- The script continues to skip authenticated checks when no complete credential pair is available.
- No credentials are hardcoded or printed.

### Documentation

- Updated environment examples with disabled-by-default seed settings and local-only warnings.
- Updated Docker Compose backend environment wiring for seed settings.
- Extended `resources/docs/deployment_security.md` with:
  - required local seed variables,
  - Docker seed command,
  - environment allowlist and production refusal,
  - existing-user/password behavior,
  - collision safety,
  - authenticated smoke-test credential priority,
  - production warning and cleanup guidance.

### Tests Added or Updated

- Added focused tests for:
  - import-safe command behavior,
  - disabled no-op behavior,
  - production and non-development environment refusal,
  - clean missing-variable failure,
  - active admin creation,
  - password hashing,
  - default password preservation,
  - explicit password update,
  - idempotent repeated execution,
  - email/username collision refusal,
  - password/hash output exclusion,
  - disabled command clean exit.
- Updated infrastructure tests for Compose/env seed defaults and smoke credential sources.

### Verification Results

- Focused seed/infrastructure tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest tests/test_seed_admin_command.py tests/test_infrastructure_files.py`
  - Result: passed; `30 tests` passed.
- Full backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest`
  - Result: passed; `577 tests` passed with `1` existing Starlette/httpx deprecation warning.
- Backend compile check:
  - Command: bundled Python `-m compileall app tests`
  - Result: passed.
- Alembic:
  - Commands: bundled Python `-m alembic -c alembic.ini heads` and `history`
  - Result: passed; current head remains `0010`.
- Disabled command CLI:
  - Command: bundled Python `-m app.commands.seed_admin`
  - Result: exited successfully with `seed admin disabled; no changes made`.
- Docker Compose:
  - Command: `docker-compose config`
  - Result: passed; seed settings rendered disabled, empty, and password-update disabled by default.
- Smoke-script syntax and committed-secret review:
  - Result: passed; PowerShell syntax is valid and no test credential/hash was committed in the changed runtime boundary.
- Frontend tests/build:
  - Not run because no frontend files were changed.

### Live Docker/PostgreSQL Verification

- Verification used a separate temporary Compose project and PostgreSQL volume so the existing `parkingapp_postgres_data` volume and its users were not modified.
- Backend image build with the new command passed.
- Fresh PostgreSQL migration from base through `0010` passed.
- An initial run with the reserved-domain email `example.invalid` failed closed with only `invalid seed admin fields: EMAIL`; the temporary project and volume were removed.
- A valid isolated run passed:
  - first command run created `smoke_seed_admin`,
  - second command run updated the same user idempotently and reported password preserved,
  - generated password and hash were not printed,
  - authenticated login returned HTTP `200`,
  - authenticated `/auth/me` returned HTTP `200`,
  - authenticated admin endpoint returned HTTP `200`,
  - Alembic current revision was at head.
- A final isolated run supplied an incomplete higher-priority `SMOKE_TEST_*` pair plus a complete `SEED_ADMIN_*` pair:
  - smoke script selected the complete seed pair without mixing sources,
  - all authenticated and unauthenticated checks passed.
- Temporary verification containers, networks, and volumes were removed with `docker-compose down -v`.
- Final cleanup verification:
  - no application or temporary verification containers remain,
  - no `parkingappseedverify` volume remains,
  - existing `parkingapp_postgres_data` remains preserved.

### Review Notes

- Seed command imports do not initialize a database session; session creation is lazy after enablement and environment safety validation.
- Existing schema and repository boundaries are reused; no user-creation endpoint or duplicate persistence logic was introduced.
- Secret values are not included in validation errors, command output, tests, documentation, or committed environment examples.
- Docker Compose makes enabled local seed variables available inside the backend container; these values remain inspectable through local Docker metadata and must never be used for production secrets.
- No business logic, frontend feature, model, migration, public registration, production provisioning, or SSO/OIDC implementation was added.

### Known Limitations

- This command creates or updates one local admin only; it does not provision employees, parking owners, teams, parking spots, or production identities.
- Local Docker environment variables can be inspected by users with Docker access; use generated/disposable local credentials and remove variables after testing.
- The command intentionally cannot run in staging or production.
- No seed-user deletion command is provided. Live verification avoided persistent seed data by using and deleting isolated temporary volumes.
- The existing Starlette/httpx test-client deprecation warning remains.

### Next Suggested Task

Perform authenticated end-to-end MVP acceptance and release-candidate sign-off using the safe local admin seed command plus approved disposable employee and parking-owner test accounts. Verify the complete admin setup, availability, application, assignment, reservation, cancellation/reassignment, override, audit, and reporting workflows without adding new features unless verification exposes a defect.

## Task 50: Final Release Readiness Documentation and Verification

### Files Changed

- `README.md`
- `resources/docs/developer_handoff.md`
- `resources/docs/manual_qa_checklist.md`
- `resources/docs/implementation_log.md`

### Implementation Summary

- Added a root README with project overview, stack, local Docker setup, migration commands, local admin seed usage, smoke testing, backend and frontend developer commands, service URLs, shutdown commands, and known limitations.
- Added `resources/docs/developer_handoff.md` covering backend/frontend architecture, implemented domain workflows, assignment policy, security notes, operational commands, extension points, and known limitations.
- Added `resources/docs/manual_qa_checklist.md` for release-candidate browser QA across authentication, employee workflows, parking owner workflows, admin workflows, frontend routing/layout, API/security behavior, and operational checks.
- No business logic, endpoints, screens, models, migrations, or external integrations were added.

### Code Review Notes

- Documentation uses existing project paths, service names, ports, migration head, command names, and environment variable names.
- Documentation keeps production and local-development concerns separated, especially around local admin seeding and Docker Compose.
- No real secrets or seed passwords were committed.
- The Docker CLI in this environment does not support `docker compose`; the equivalent standalone `docker-compose` command is available and was used for verification.
- A Git status review was not possible because this workspace is not currently inside a Git repository.

### Tests Added or Updated

- No automated tests were added because this task was documentation and release-readiness verification only.

### Verification Results

- Backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest`
  - Result: passed; `577` tests passed with `1` existing Starlette/httpx deprecation warning.
- Backend compile check:
  - Command: bundled Python `-m compileall app tests`
  - Result: passed.
- Alembic metadata checks:
  - Commands: bundled Python with `PYTHONPATH=.test-deps`, `-m alembic -c alembic.ini heads` and `history`
  - Result: passed; head remains `0010`.
- Frontend tests:
  - Command: `npm.cmd test`
  - Result: passed; `17` test files and `37` tests passed.
- Frontend production build:
  - Command: `npm.cmd run build`
  - Result: passed.
- Frontend dependency audit:
  - Command: `npm.cmd audit --omit=optional`
  - Result: passed; `0` vulnerabilities.
- Docker Desktop availability:
  - Initial sandboxed Docker access failed with Docker daemon/config access denied.
  - Elevated Docker access was available.
  - `docker compose version` failed because this Docker CLI does not expose the compose subcommand.
  - `docker-compose version` passed with Docker Compose `v2.40.0-desktop.1`.
- Docker Compose build/start/migration/seed/smoke:
  - Commands run with temporary project `parkingappreleaseverify`: `docker-compose -p parkingappreleaseverify config`, `build backend frontend`, `up -d db backend frontend`, backend Alembic `upgrade head`, Alembic `current`, `python -m app.commands.seed_admin`, and `scripts/smoke_test.ps1`.
  - Result: passed.
  - Migration result: fresh PostgreSQL database upgraded through `0010`; `alembic current` reported `0010 (head)`.
  - Seed result: local-only admin seed created a disposable admin user in the temporary database without printing the password or hash.
  - Smoke script result: backend health, frontend `/`, `/login`, `/dashboard`, unauthenticated auth/admin checks, CORS preflight, authenticated login, authenticated `/auth/me`, authenticated admin endpoint, and Alembic head check all passed.
- Targeted backend smoke checks:
  - Commands run with temporary project `parkingappreleaseverifyheaders`: Compose config/start, Alembic upgrade, PowerShell `Invoke-WebRequest` checks, Alembic current.
  - Result: passed.
  - Backend health returned HTTP `200`.
  - `X-Request-ID` response header round-tripped the supplied request ID.
  - Security headers were present: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`.
  - CORS preflight for `http://localhost:8080` returned HTTP `200` with `Access-Control-Allow-Origin: http://localhost:8080`.
- Frontend HTTP smoke checks:
  - Routes checked: `/`, `/login`, `/dashboard`, `/availabilities`, `/admin`.
  - Result: all returned HTTP `200` through nginx/Vue Router fallback.
- Cleanup:
  - Temporary verification projects were stopped and removed with `docker-compose -p <project> down -v`.
  - Final Docker cleanup check found no temporary `parkingappreleaseverify*` containers or volumes.
  - Existing persistent local volume `parkingapp_postgres_data` remains preserved.

### Known Limitations

- Browser visual QA was not performed in an interactive browser during this task; `resources/docs/manual_qa_checklist.md` now documents the manual release-candidate checks.
- This task did not create employee or parking-owner test accounts for a full manual business workflow pass.
- Production deployment concerns such as TLS, managed secrets, backups, monitoring, and production-like concurrency/load testing remain outside the local Compose verification scope.
- The existing Starlette/httpx test-client deprecation warning remains.

### Next Suggested Task

Perform manual release-candidate QA using `resources/docs/manual_qa_checklist.md` with approved disposable admin, employee, and parking-owner accounts. Treat any failures as defects; do not add new features unless a checklist item exposes a concrete implementation bug.

## Task 51: Swagger OAuth2 Password Form Login Compatibility

### Files Changed

- `backend/app/dependencies/auth.py`
- `backend/app/routers/auth.py`
- `backend/app/commands/seed_admin.py`
- `backend/tests/test_auth_api.py`
- `README.md`
- `resources/docs/implementation_log.md`

### Implementation Summary

- Kept `/auth/login` as the JSON login endpoint for frontend and API clients using `identifier` plus `password`.
- Added `/auth/token` as the OAuth2 password-form token endpoint used by Swagger UI.
- Updated `OAuth2PasswordBearer` to use `tokenUrl="/auth/token"` so the Swagger `Authorize` modal submits form credentials to an endpoint that accepts `username` and `password`.
- Routed both JSON and form login through the same `AuthService` authentication and token creation logic.
- Removed leftover seed-admin debug prints, including a password-leaking print when `SEED_ADMIN_UPDATE_PASSWORD=true`.
- Updated README instructions for Swagger authorization.

### Review Notes

- The frontend contract remains unchanged because `/auth/login` still accepts the existing JSON payload.
- Swagger UI now uses a conventional OAuth2 password flow form endpoint without requiring `client_id` or `client_secret`.
- Authentication failures still return a generic `401` and do not disclose whether the username/email or password was wrong.
- JWT bearer protection semantics remain unchanged; only the token URL advertised in OpenAPI changed.
- The seed-admin cleanup removes sensitive output and does not change seed behavior.

### Tests Added or Updated

- Added tests for `/auth/token` form login with username.
- Added tests for `/auth/token` form login with email.
- Added a `/auth/token` wrong-password `401` test.
- Added an OpenAPI test verifying the OAuth2 password flow uses `/auth/token`.

### Verification Results

- Focused auth and seed tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest tests/test_auth_api.py tests/test_seed_admin_command.py`
  - Result: passed; `23` tests passed with `1` existing Starlette/httpx deprecation warning.
- Backend compile check:
  - Command: bundled Python `-m compileall app tests`
  - Result: passed.
- Full backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest`
  - Result: passed; `581` tests passed with `1` existing Starlette/httpx deprecation warning.
- Alembic:
  - Commands: bundled Python with `PYTHONPATH=.test-deps`, `-m alembic -c alembic.ini heads` and `history`
  - Result: passed; head remains `0010`.

### Known Limitations

- Docker images were not rebuilt for this small backend/OpenAPI fix. Local Docker users must rebuild or recreate the backend container to see the changed Swagger token URL.
- The existing Starlette/httpx test-client deprecation warning remains.

### Next Suggested Task

Rebuild the backend container, open Swagger at `/docs`, use `Authorize` with username/email plus password and empty client fields, then run the manual release-candidate checklist.

## Task 52: Manual Release-Candidate QA Pass

### Files Changed

- `resources/docs/manual_qa_checklist.md`
- `resources/docs/implementation_log.md`

### Scope

- No new functionality was implemented.
- No backend code, frontend code, models, migrations, or Docker files were changed.
- The task focused on live QA guidance, execution, results, and defect recording.

### Environment

- Date: 2026-06-05.
- Environment: local Docker Desktop using standalone `docker-compose`.
- Services: PostgreSQL, backend, frontend.
- Backend URL: `http://localhost:8000`.
- Frontend URL: `http://localhost:8080`.
- Alembic revision: `0010 (head)`.
- Backend runtime override used for this QA run: `SAME_TEAM_PRIORITY_WINDOW_HOURS=0`, so newly created availabilities could be assigned immediately by the scheduled assignment command.

### Docker Commands And Results

- `docker-compose config`
  - Result: passed.
- `docker-compose up -d db backend frontend`
  - Result: services were running.
- `docker-compose exec -T backend alembic -c alembic.ini upgrade head`
  - Result: passed.
- `docker-compose exec -T backend alembic -c alembic.ini current`
  - Result: `0010 (head)`.
- Disposable admin seed command with `SEED_ADMIN_*` environment overrides, including a local disposable `SEED_ADMIN_PASSWORD` value that was not recorded.
  - Result: `qa_admin_manual` created or updated successfully.
- Backend recreated with `SAME_TEAM_PRIORITY_WINDOW_HOURS=0`.
  - Result: backend restarted successfully and Alembic still reported `0010 (head)`.
- `docker-compose exec -T backend python -m app.commands.assign_due_availabilities --limit 100`
  - Result: `processed=1 assigned=1 skipped=0 failed=0`.
- `scripts/smoke_test.ps1`
  - Result: passed with disposable admin credentials.
- Backend restored to normal Compose configuration after QA.
  - Commands: `docker-compose up -d --force-recreate backend`, then `docker-compose exec -T backend alembic -c alembic.ini current`.
  - Result: backend restarted successfully and Alembic reported `0010 (head)`.

### QA Users And Data

- Admin: `qa_admin_manual`.
- Employee: `qa_employee_20260605012932`.
- Second employee: `qa_employee2_20260605012932`.
- Parking owner: `qa_owner_20260605012932`.
- Team ID: `6`.
- Main availability ID: `3`.
- Initial reservation ID: `1`.
- Reassigned reservation ID: `2`.

### Passed QA Checks

- Auth checks passed for username login, email login, Swagger OAuth2 password-form login, wrong-password `401`, unknown-user `401`, inactive-user `401`, missing-token `401`, and `/auth/me` response safety.
- Role checks passed for non-admin `403` on admin routes.
- Frontend nginx fallback returned HTTP `200` for `/`, `/login`, `/dashboard`, `/availabilities`, and `/admin`.
- Backend health, request ID header, security headers, allowed CORS preflight, and disallowed CORS origin behavior passed.
- Admin setup through live API passed for team, users, and parking spots.
- Parking owner availability publishing passed.
- Owner `my availabilities` and employee available-spots visibility passed through the API.
- Employee application creation, duplicate prevention, owner self-application prevention, `my applications`, and pending application cancellation passed.
- Scheduled assignment command passed and created an active reservation.
- Availability, application, reservation, reservation history, assignment audit log, reports, and CSV export checks passed.
- Employee reservation cancellation passed and reopened the availability.
- Reassignment after cancellation passed and created a new active reservation for the second employee.
- Parking owner reservation cancellation passed for an owned availability.
- Admin manual override assignment required a reason and succeeded with a reason.
- Admin reservation cancellation required a reason and succeeded with a reason.
- Backend logs did not contain the disposable QA passwords used in this run.

### Failed QA Checks

- Admin replacement override could not be verified through the public workflow.
  - Expected behavior: an admin can perform a replacement override from an assigned availability by selecting a pending replacement application.
  - Actual behavior: assignment rejects non-selected pending applications, and public application creation rejects assigned availabilities because they are not open. This leaves no public UI/API path to create or retain a pending replacement application for `POST /admin/parking-availabilities/{availability_id}/replace-reservation`.
  - Affected role: admin.
  - Affected endpoint/page: `POST /admin/parking-availabilities/{availability_id}/replace-reservation`, Admin Overrides UI.
  - Suggested fix area: define the intended replacement-candidate workflow. Options include admin-created replacement candidates, retaining non-selected candidates as pending for override workflows, or allowing replacement from a rejected candidate with explicit admin reason.

### Not Fully Verified

- Browser UI click-through, screenshots, visual layout, and responsive behavior were not completed by Codex because the in-app browser runtime failed twice with a local sandbox startup error.
- Admin creation of team, users, and parking spots through UI forms was not completed by Codex. The same setup was verified through live admin API calls.

### Final Release-Candidate Status

Status: not approved for release-candidate sign-off yet.

Reason: the API-backed MVP workflow passed broadly, but replacement override has a public-workflow defect and browser UI/visual QA remains pending.

### Next Suggested Task

Fix the replacement override workflow defect before adding unrelated features. Decide whether replacement candidates should be created by admins, retained as pending after initial assignment, or allowed from rejected applications with explicit override reason; then implement the chosen path and rerun the replacement override QA plus the manual browser checklist.

## Task 53: Replacement Override Workflow Reachability Fix

### Files Changed

- `backend/app/repositories/parking_applications.py`
- `backend/app/routers/admin_reservation_overrides.py`
- `backend/app/schemas/parking_reservation.py`
- `backend/app/services/admin_reservation_override.py`
- `backend/tests/test_admin_reservation_replacements_api.py`
- `backend/tests/test_admin_reservation_replacement_service.py`
- `frontend/src/components/admin/AdminOverrideForm.vue`
- `frontend/src/components/admin/AdminOverrideForm.spec.js`
- `frontend/src/services/adminAuditOverrideServices.spec.js`
- `frontend/src/services/adminReservationOverrideService.js`
- `frontend/src/services/apiErrors.js`
- `frontend/src/styles/main.css`
- `frontend/src/views/admin/AdminOverridesView.vue`
- `frontend/src/views/admin/AdminOverridesView.spec.js`
- `resources/docs/developer_handoff.md`
- `resources/docs/manual_qa_checklist.md`
- `resources/docs/implementation_log.md`

### Implementation Summary

- Selected Option B from the defect analysis.
- `POST /admin/parking-availabilities/{availability_id}/replace-reservation` now accepts exactly one replacement selector:
  - `application_id` for the existing pending-application workflow.
  - `applicant_id` for the newly reachable admin-only workflow.
- Preserved existing `application_id` behavior:
  - selected application must exist,
  - must belong to the availability,
  - must be pending,
  - must not be the currently reserved application,
  - selected applicant must be active.
- Added `applicant_id` replacement behavior:
  - applicant must exist and be active,
  - applicant must not be the current reserved user,
  - existing pending application is reused,
  - existing rejected/cancelled application is reactivated as the admin-only replacement candidate,
  - no existing application creates a pending internal replacement candidate,
  - replacement then updates the active reservation in place.
- Added repository support for locking an application by `(availability_id, applicant_id)`.
- Added request schema validation requiring exactly one of `application_id` or `applicant_id`.
- Added API error mapping for missing applicant and current reserved applicant conflicts.
- Updated the admin replacement UI to allow Application ID or Applicant ID, with helper text explaining applicant ID replacement after assignment.
- Updated frontend API error messages for applicant-not-found and applicant-already-reserved cases.

### Review Notes

- Normal employee application rules remain unchanged; employees still cannot apply to assigned availabilities.
- Route code remains thin and delegates replacement behavior to `AdminReservationOverrideService`.
- The old application-based audit payload remains unchanged except for existing values, preserving current behavior.
- Applicant-based replacements add explicit audit metadata for requested applicant, candidate action, selected application/user, previous application/user, admin actor, reason, and replacement action.
- The replacement is still wrapped in the same service transaction and rolls back on reservation/audit persistence failures.
- No new migrations, models, parking ranking policy, or unrelated workflows were added.
- No secrets were committed or recorded in documentation.

### Tests Added Or Updated

- Backend API tests:
  - replacement by `applicant_id` succeeds with no existing pending application,
  - replacement by `applicant_id` reactivates a rejected application,
  - current reserved user is rejected,
  - missing applicant returns 404,
  - inactive applicant returns 409,
  - both selectors returns 422,
  - neither selector returns 422,
  - non-positive `applicant_id` returns 422,
  - employee application to assigned availability still returns 409.
- Backend service tests:
  - applicant-based replacement creates an internal candidate,
  - applicant-based replacement reactivates a rejected candidate,
  - current, missing, and inactive applicant cases are rejected.
- Frontend tests:
  - replacement form helper text renders,
  - replacement form submits `applicantId`,
  - replacement form enforces exactly one selector,
  - API service sends `applicant_id` payload,
  - admin overrides view submits applicant-based replacement and shows success summary.

### Verification Results

- Focused backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest tests/test_admin_reservation_replacements_api.py tests/test_admin_reservation_replacement_service.py tests/test_parking_applications_api.py`
  - Result: passed; `68` tests passed with `1` existing Starlette/httpx deprecation warning.
- Focused frontend tests:
  - Command: `npm.cmd test -- --run src\components\admin\AdminOverrideForm.spec.js src\services\adminAuditOverrideServices.spec.js src\views\admin\AdminOverridesView.spec.js`
  - Result: passed; `14` tests passed across `3` files.
- Full backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest`
  - Result: passed; `595` tests passed with `1` existing Starlette/httpx deprecation warning.
- Backend compile check:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m compileall app tests`
  - Result: passed.
- Alembic:
  - Commands: bundled Python with `PYTHONPATH=.test-deps`, `-m alembic -c alembic.ini heads` and `history`
  - Result: passed; head remains `0010`.
- Full frontend tests:
  - Command: `npm.cmd test`
  - Result: passed; `43` tests passed across `17` files.
- Frontend production build:
  - Command: `npm.cmd run build`
  - Result: passed.
- Dependency audit:
  - Command: `npm.cmd audit --omit=optional`
  - Result: passed; `0` vulnerabilities.
- Docker Compose config:
  - Command: `docker-compose config`
  - Result: passed. The environment rendered local seed variables from `.env`; secret values were not recorded in this log.
- Docker build:
  - Initial command was blocked by sandbox access to Docker buildx state.
  - Rerun with approval: `docker-compose build backend frontend`
  - Result: passed; backend and frontend images built.
- Docker startup:
  - Command: `docker-compose up -d db backend frontend`
  - Result: db and backend started; frontend failed to bind host port `8080` because the port was already allocated outside the visible Compose project.
- Live PostgreSQL migration:
  - Command: `docker-compose exec -T backend alembic -c alembic.ini upgrade head`
  - Result: passed.
  - Command: `docker-compose exec -T backend alembic -c alembic.ini current`
  - Result: `0010 (head)`.
- Backend smoke checks:
  - `GET http://localhost:8000/health`: HTTP `200`.
  - Request ID header was returned.
  - Security headers were returned: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`.
  - CORS preflight for `http://localhost:8080`: HTTP `200`, `Access-Control-Allow-Origin: http://localhost:8080`.
- Live replacement override smoke:
  - Existing `.env` seeded admin login returned generic `401 Invalid credentials`; no success was assumed.
  - A disposable local admin was created through the safe seed command with environment overrides and without recording the password.
  - Created disposable team, parking owner, current employee, replacement employee, parking spot, availability, application, and initial assignment through the live API.
  - Verified public employee application to the assigned availability still returned `409` with `Parking availability is not open`.
  - Called replacement endpoint with `applicant_id` and reason.
  - Result: replacement updated the same reservation in place, created selected replacement application ID `9`, reserved for replacement user ID `16`, and wrote replacement audit log ID `8` with candidate action `created_application`.
- Frontend HTTP smoke:
  - Because host port `8080` was unavailable, the rebuilt frontend image was run temporarily on `http://localhost:18080`.
  - Checked routes: `/`, `/login`, `/dashboard`, `/availabilities`, `/admin`.
  - Result: all returned HTTP `200` with Vue root content through nginx/Vue Router fallback.
- Cleanup:
  - Temporary frontend smoke container was stopped.
  - Command: `docker-compose down`
  - Result: db, backend, and the stopped frontend Compose container were removed; PostgreSQL volume was preserved.

### Known Limitations

- Host port `8080` was unavailable in this environment, so the frontend Compose service could not be started on the normal local URL during live smoke. The same rebuilt frontend image was verified successfully on temporary port `18080`.
- Existing `.env` seed-admin credentials returned `401` during smoke setup. A disposable admin created by the safe seed command was used instead. The operator should verify local `.env` seed values if relying on that seeded account.
- Browser click-through, screenshots, and responsive visual QA were not performed in this task.
- The existing Starlette/httpx TestClient deprecation warning remains.

### Next Suggested Task

Run the manual release-candidate browser QA checklist again, focusing first on the Admin Overrides UI replacement flow using Applicant ID, then complete the remaining visual/responsive checks. Treat any failed checklist item as the next defect; do not add new features until release-candidate QA passes.

## Task 54: Release-Candidate QA Rerun For Applicant ID Replacement

### Files Changed

- `resources/docs/manual_qa_checklist.md`
- `resources/docs/implementation_log.md`

### Scope

- No backend functionality, frontend functionality, migrations, Docker files, or business logic were changed.
- This task performed release-candidate QA and recorded results only.

### Environment

- Date: 2026-06-19.
- Environment: local Docker Desktop using standalone `docker-compose`.
- Backend URL: `http://localhost:8000`.
- Frontend URL: `http://localhost:8080`.
- Services: PostgreSQL, backend, frontend.
- Migration revision: `0010 (head)`.
- Runtime override: `SAME_TEAM_PRIORITY_WINDOW_HOURS=0` for the QA stack, so the assignment command could process a newly created future availability immediately after application submission.

### Docker Setup And Migration Results

- `docker-compose config --quiet`
  - Result: passed; Docker emitted the local config-file access warning but validation exited successfully.
- `docker-compose build backend frontend`
  - Result: passed.
- `$env:SAME_TEAM_PRIORITY_WINDOW_HOURS="0"; docker-compose up -d db backend frontend`
  - Result: passed; PostgreSQL, backend, and frontend started. Frontend was available on `http://localhost:8080`.
- `docker-compose exec -T backend alembic -c alembic.ini upgrade head`
  - Result: passed.
- `docker-compose exec -T backend alembic -c alembic.ini current`
  - Result: `0010 (head)`.

### Browser QA Result

- The in-app browser runtime failed twice before page interaction with a local sandbox startup error.
- Because the browser could not start, the Admin Overrides UI Applicant ID replacement click-through, screenshots, responsive visual layout, and human browser inspection were not completed by Codex.
- No browser UI pass was claimed.

### Disposable QA Users And Data

- Admin: `rcqa_admin_1780644123674`.
- Parking owner: `rcqa_owner_1780644481335`.
- Employee A: `rcqa_employee_a_1780644481335`.
- Employee B: `rcqa_employee_b_1780644481335`.
- Team ID: `10`.
- Parking spot ID: `10`.
- Replacement availability ID: `16`.
- Replacement reservation ID: `11`.
- Replacement audit log ID: `17`.
- Disposable local passwords were generated during execution and were not recorded. The temporary credential file used by Codex was deleted after QA.

### Applicant ID Replacement QA Result

- Result: passed at API/backend-contract level.
- Assignment command:
  - Command: `docker-compose exec -T backend python -m app.commands.assign_due_availabilities --limit 100`
  - Result: `processed=1 assigned=1 skipped=0 failed=0`.
- Flow verified:
  - admin-created team/users/spot data,
  - owner-published future availability,
  - Employee A application,
  - assignment command created active reservation for Employee A,
  - admin replacement override used Employee B `applicant_id` and mandatory reason,
  - reservation was updated in place and assigned to Employee B,
  - Employee A no longer had the active reservation,
  - Employee B could see the active replacement reservation,
  - normal employee application to assigned availability still returned `409` with `Parking availability is not open`,
  - replacement audit log recorded action, reason, previous user, selected user, requested applicant, and admin override replacement policy.

### Broader Regression QA Result

- Authentication checks passed:
  - username login,
  - email login,
  - wrong-password `401`,
  - unknown-user `401`,
  - inactive-user `401`,
  - invalid-token `/auth/me` `401`,
  - `/auth/me` response did not expose password fields.
- Authorization passed:
  - non-admin admin-route access returned `403`.
- Admin setup passed:
  - team creation,
  - active and inactive user creation,
  - parking spot creation.
- Owner workflows passed:
  - publish availability,
  - list own availabilities,
  - cancel availability,
  - assign availability,
  - cancel owned reservation,
  - reassign after cancellation.
- Employee workflows passed:
  - view available spots,
  - apply,
  - duplicate application blocked,
  - owner self-application blocked,
  - list own applications,
  - cancel own pending application,
  - view own reservation,
  - see replacement reservation as Employee B.
- Admin workflows passed:
  - applications list,
  - reservations list,
  - reservation history,
  - assignment audit logs,
  - summary/top-users/spot-usage reports,
  - CSV exports,
  - manual override assignment with reason,
  - admin cancellation through `/admin/parking-reservations/{reservation_id}/cancel`,
  - replacement override by Applicant ID.
- Frontend route smoke passed:
  - `/`,
  - `/login`,
  - `/dashboard`,
  - `/availabilities`,
  - `/admin`
  all returned HTTP `200` with Vue root content.
- Backend security smoke passed:
  - `GET /health` returned HTTP `200`,
  - request ID header returned,
  - security headers returned,
  - allowed CORS preflight for `http://localhost:8080` returned HTTP `200`,
  - disallowed CORS origin returned HTTP `400`.
- `scripts/smoke_test.ps1`:
  - Initial non-escalated run passed HTTP checks but could not access Docker for Alembic checks.
  - Rerun with Docker access passed fully, including Alembic current/head checks.

### Verification Commands

- Full frontend tests:
  - Command: `npm.cmd test`
  - Result: passed; `43` tests passed across `17` files.
- Full backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps`, `-m pytest`
  - Result: passed; `595` tests passed with `1` existing Starlette/httpx deprecation warning.
- Frontend production build:
  - Command: `npm.cmd run build`
  - Result: passed.
- Alembic local checks:
  - Commands: bundled Python with `PYTHONPATH=.test-deps`, `-m alembic -c alembic.ini heads` and `history`
  - Result: passed; head remains `0010`.
- Cleanup:
  - Command: `docker-compose down`
  - Result: completed; PostgreSQL volume was preserved.

### Failed Verification

- `npm.cmd audit --omit=optional`
  - Result: failed.
  - `form-data` high severity advisory via `axios`; npm reported no fix available.
  - `undici` high severity advisories via `jsdom`/`vitest`; npm reported no fix available.
  - Total reported by npm: `5 high severity vulnerabilities`.

### Known Limitations

- Browser UI click-through and screenshots remain unverified because the in-app browser runtime could not start.
- The Applicant ID replacement workflow is verified through live API/backend contract and frontend route delivery, not through browser form submission.
- `npm audit --omit=optional` is currently failing because of high-severity transitive dependency advisories.
- The existing Starlette/httpx TestClient deprecation warning remains.

### Release-Candidate Status

Status: not approved for full release-candidate sign-off.

Reason: Applicant ID replacement passed API-backed QA, but browser UI/visual QA is still blocked and frontend dependency audit currently fails.

### Next Suggested Task

Resolve the release-candidate blockers before adding features: review and address the frontend dependency audit findings or document an accepted risk/mitigation, then rerun browser-based Admin Overrides UI Applicant ID replacement QA in an environment where the browser runtime can start.

## Task 55: Frontend Dependency Audit Risk Remediation

### Scope

- Investigated and remediated the frontend dependency audit release blocker.
- No business functionality, backend endpoints, frontend screens, database models, or migrations were changed.
- Browser UI QA was not rerun in this task and remains a separate release-candidate blocker.

### Files Changed

- `frontend/package-lock.json`
- `resources/docs/manual_qa_checklist.md`
- `resources/docs/implementation_log.md`

### Initial Audit Result

- Command: `npm.cmd audit --omit=optional`
  - Result before remediation: failed.
  - Reported vulnerable packages:
    - `form-data` `4.0.5`, high severity, `GHSA-hmw2-7cc7-3qxx`.
    - `undici` `7.27.1`, high severity package entry with multiple advisories including `GHSA-vmh5-mc38-953g`, `GHSA-vxpw-j846-p89q`, and `GHSA-hm92-r4w5-c3mj`.
- Command: `npm.cmd audit --json`
  - Result before remediation: failed.
  - Metadata: `2` vulnerable package entries, `0` critical, `2` high, `0` moderate, `0` low.

### Dependency Path And Exposure Analysis

- `form-data`
  - Dependency path: `parking-app-frontend -> axios@1.17.0 -> form-data@4.0.5`.
  - Classification: production dependency in `node_modules`, but not included in the browser-delivered Vite bundle for the deployed nginx static frontend.
  - Exposure: primarily Node.js multipart/form-data handling. The production frontend runs in the browser and uses the built static bundle served by nginx, not Node.js `form-data` multipart processing.
  - Remediation: updated to `form-data@4.0.6` through the existing `axios` range `^4.0.5`.
- `undici`
  - Dependency path: `parking-app-frontend -> jsdom@29.1.1 -> undici@7.27.1`; `jsdom` is a dev dependency and peer-optional test environment for `vitest`.
  - Classification: test-only/development tooling dependency.
  - Exposure: not shipped in the browser-delivered production bundle and not executed by the nginx production container at runtime.
  - Remediation: updated to `undici@7.28.0` through the existing `jsdom` range `^7.25.0`.

### Remediation Applied

- Command: `npm.cmd update form-data undici`
  - Result: passed.
  - Changed `form-data` from `4.0.5` to `4.0.6`.
  - Changed `undici` from `7.27.1` to `7.28.0`.
- Command: `npm.cmd install`
  - Result: passed; lockfile remained valid and npm reported `0` vulnerabilities.
- No `package.json` dependency changes were required.
- No npm `overrides` were added.
- No forced major upgrades were used.
- No advisory suppression or lockfile deletion was used.

### Verification Commands

- `npm.cmd ls`
  - Result: passed.
  - Direct dependency tree remained on the same direct packages:
    - `axios@1.17.0`
    - `jsdom@29.1.1`
    - `vite@6.4.3`
    - `vitest@4.1.8`
    - `vue@3.5.35`
    - `vue-router@4.6.4`
- `npm.cmd test`
  - Result: passed; `43` tests passed across `17` files.
- `npm.cmd run build`
  - Result: passed; production bundle generated successfully.
- `npm.cmd audit`
  - Result: passed; `0` vulnerabilities.
- `npm.cmd audit --omit=dev`
  - Result: passed; `0` vulnerabilities.
- `npm.cmd audit --omit=optional`
  - Result: passed; `0` vulnerabilities.
- `npm.cmd audit --json`
  - Result: passed; empty `vulnerabilities` object and total vulnerability count `0`.
- `docker-compose build frontend`
  - Result: passed; Docker build ran `npm ci`, reported `0` vulnerabilities, and produced the nginx static image.
- `docker-compose up -d frontend`
  - Result: passed; started `db`, `backend`, and `frontend` because of Compose dependencies.
- Frontend route smoke through Docker:
  - `http://localhost:8080/`: HTTP `200`, Vue root present.
  - `http://localhost:8080/login`: HTTP `200`, Vue root present.
  - `http://localhost:8080/dashboard`: HTTP `200`, Vue root present.
  - `http://localhost:8080/admin/overrides`: HTTP `200`, Vue root present.
- `docker-compose down`
  - Result: passed; containers and network removed, PostgreSQL volume preserved.
- `docker-compose ps`
  - Result after cleanup: no running Compose services.

### Code Review Notes

- Reviewed the lockfile changes and confirmed the remediation is limited to patched transitive versions allowed by existing parent dependency ranges.
- `form-data@4.0.6` remains under the existing `axios` semver range; no direct dependency or API compatibility change was introduced.
- `undici@7.28.0` remains under the existing `jsdom` semver range; the affected package is test/development tooling and is not part of the nginx-served production runtime.
- Production exposure was checked by dependency classification and Vite production build behavior. The deployed frontend container serves static assets through nginx and does not execute the local Vite dev server, `jsdom`, `vitest`, or Node.js `form-data` processing at runtime.
- No package overrides, forced upgrades, dependency suppressions, or unrelated upgrades were introduced.
- Documentation was updated to remove the dependency audit blocker from the active RC blocker list while keeping the browser QA blocker separate.

### Known Limitations

- Browser UI click-through QA was intentionally not rerun in this task and remains required before release-candidate sign-off.
- The Git diff command unexpectedly reported that the workspace was not a Git repository despite the workspace containing a `.git` entry, so review was performed through direct lockfile/package inspection and command verification.

### Release-Risk Classification

Status: RESOLVED.

Reason: the required frontend audit commands now report `0` vulnerabilities, no residual frontend dependency risk acceptance document is needed, and the production Docker frontend build and route smoke checks pass.

### Next Suggested Task

Rerun browser-based Admin Overrides UI Applicant ID replacement QA in an environment where browser automation or manual browser testing can start, then update the manual QA checklist and implementation log with screenshots/manual observations and final release-candidate status.

## Task 56: Browser Release-Candidate QA For Admin Overrides Applicant ID Replacement

### Scope

- Performed browser-based release-candidate QA for the Admin Overrides Applicant ID replacement workflow.
- Used the real local frontend at `http://localhost:8080` with PostgreSQL/backend/frontend running through standalone `docker-compose`.
- Did not add new business functionality, endpoints, migrations, or automated E2E framework.
- One scoped UI defect fix was made after browser QA found mobile horizontal overflow in the Admin Overrides workflow.

### Files Changed

- `frontend/src/styles/main.css`
- `resources/docs/manual_qa_checklist.md`
- `resources/docs/implementation_log.md`

### Docker And Migration Setup

- `docker-compose config`
  - Result: passed.
- `$env:SEED_ADMIN_ENABLED="false"; $env:SAME_TEAM_PRIORITY_WINDOW_HOURS="0"; docker-compose up -d db backend frontend`
  - Result: passed; PostgreSQL healthy, backend and frontend running.
  - `SEED_ADMIN_ENABLED=false` was set explicitly so the local `.env` seed settings did not create/update the non-disposable admin on stack startup.
  - `SAME_TEAM_PRIORITY_WINDOW_HOURS=0` was used so a newly published future availability became due for the assignment command immediately after Employee A applied.
- `docker-compose exec -T backend alembic -c alembic.ini upgrade head`
  - Result: passed.
- `docker-compose exec -T backend alembic -c alembic.ini current`
  - Result: `0010 (head)`.

### Disposable QA Data

- Disposable admin: `browserqa_admin_1781956103179`.
- Parking owner: `browserqa_owner_1781956103179`, user ID `56`.
- Employee A: `browserqa_employee_a_1781956103179`, user ID `57`.
- Employee B: `browserqa_employee_b_1781956103179`, user ID `58`.
- Team ID: `42`.
- Parking spot ID: `42`.
- Availability ID: `45`.
- Employee A application ID: `47`.
- Replacement application ID: `48`.
- Reservation ID: `42`.
- Passwords were generated for local disposable QA accounts and were not committed or documented.

### Browser QA Evidence

- Browser: Codex in-app browser runtime against the local production-style frontend container.
- The browser runtime did not expose a user-agent string to page evaluation, so the environment is recorded by runtime name and local URL instead of exact browser version.
- Frontend URL: `http://localhost:8080`.
- Browser page title: `Parking Management`.
- Vue root was present in the browser-rendered app.

### Browser Flow Results

- Admin logged in through the frontend login page.
- Admin created team, parking owner, Employee A, Employee B, and parking spot through the admin UI.
- Admin forms showed success feedback after each create action.
- Parking owner logged in through the UI and published a valid future availability for parking spot `#42`.
- Owner My availabilities showed the published availability.
- Employee A logged in through the UI, opened available spots, applied, and saw application `#47` as `Pending` in My applications.
- Assignment command:
  - Command: `docker-compose exec -T backend python -m app.commands.assign_due_availabilities --limit 100`
  - Result: `processed=1 assigned=1 skipped=0 failed=0`.
- Employee A My reservations showed reservation `#42` as `Active`.
- Employee A My applications showed application `#47` as `Selected`.

### Applicant ID Replacement Result

- Admin opened Admin Overrides in the browser.
- Replacement form accepted availability ID `45` plus Applicant ID `58` without requiring application ID.
- Replacement succeeded through the browser UI.
- Visible reservation summary showed:
  - reservation `#42`,
  - availability `#45`,
  - replacement application `#48`,
  - parking spot `#42`,
  - reserved for user `#58`,
  - status `Active`.
- Success feedback was visible.
- The actual non-blank audit reason recorded for the successful replacement was `Missing selector validation`; this happened during validation sequencing when the Applicant ID field remained populated. The browser result still verifies the intended Applicant ID replacement path with no `application_id`.

### Validation And Error UX

- Blank reason was blocked with client-side validation: `Reason is required.`
- Missing application/applicant selector was blocked with: `Enter either an application ID or an applicant ID.`
- Providing both application ID and applicant ID was blocked with the same selector validation message.
- Invalid applicant ID produced: `The selected applicant could not be found.`
- Repeated same-applicant submission/current reserved user produced: `The selected applicant already has the active reservation.`
- Repeated same-applicant submission did not create a duplicate replacement; reservation `#42` remained assigned to Employee B.

### Post-Replacement Browser Verification

- Employee A no longer showed the active reservation.
- Employee B saw the active replacement reservation.
- Admin reservations/history showed reservation `#42` assigned to user `#58` with `Active` and `Current Active`.
- Admin applications showed replacement application `#48` for applicant `#58` as `Selected`.
- Admin audit logs showed:
  - `action = replacement`,
  - `assignment_method = admin_override`,
  - non-blank override reason,
  - acting admin user ID `55`,
  - previous application `47`,
  - previous user `57`,
  - selected application `48`,
  - selected user `58`,
  - rejected application IDs containing `47`.
- Admin reports remained accessible.

### Browser Regression

- Login/logout passed across admin, employee, and parking-owner roles.
- Role-based navigation passed.
- Employee pages passed:
  - available spots,
  - my applications,
  - my reservations.
- Parking owner page passed:
  - my availabilities.
- Admin pages passed:
  - dashboard,
  - applications,
  - reservations,
  - audit logs,
  - reports,
  - overrides.

### Defect Found And Fixed

- Defect: mobile Admin Overrides layout overflowed horizontally at `390x844`.
- Expected: Admin Overrides fields, buttons, messages, navigation, and summaries remain readable/reachable without document-level horizontal overflow.
- Actual: mobile navigation used five `max-content` columns, expanding the shell to roughly `821px`; visible controls were offscreen.
- Affected area: frontend responsive layout, especially Admin Overrides and admin pages on narrow/mobile-like widths.
- Fix: at `max-width: 640px`, changed `.app-shell__nav` to `repeat(2, minmax(0, 1fr))` and set `overflow-x: visible`.
- Reason this is safe: it only affects the small-screen navigation layout, keeps links visible without requiring horizontal page scroll, and leaves desktop/tablet rules unchanged.

### Visual And Responsive Verification

- Desktop `1280x800` Admin Overrides:
  - no page-level horizontal overflow,
  - no offscreen controls,
  - no unusably small fields.
- Desktop `1280x800` Admin Audit Logs:
  - no page-level horizontal overflow,
  - wide table contained in horizontal table wrapper.
- Mobile `390x844` Admin Overrides after fix:
  - no page-level horizontal overflow,
  - no offscreen controls,
  - no unusably small fields.
- Mobile `390x844` Admin Audit Logs after fix:
  - no page-level horizontal overflow,
  - no offscreen controls,
  - wide table contained in `.data-table-wrap` with usable horizontal scrolling.
- Browser cache note: after rebuilding the frontend image, a cache-busted URL was used to ensure the browser loaded the rebuilt CSS asset.

### Automated Verification

- Backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest`.
  - Result: `595` passed, `1` existing Starlette/httpx deprecation warning.
- Backend compile check:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m compileall app tests`.
  - Result: passed.
- Alembic local heads:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m alembic -c alembic.ini heads`.
  - Result: `0010 (head)`.
- Alembic local history:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m alembic -c alembic.ini history`.
  - Result: migrations `0001` through `0010` listed.
- Alembic Docker current:
  - Command: `docker-compose exec -T backend alembic -c alembic.ini current`.
  - Result: `0010 (head)`.
- Frontend tests:
  - Command: `npm.cmd test`.
  - Result: `43` passed across `17` files.
- Frontend production build:
  - Command: `npm.cmd run build`.
  - Result: passed.
- Frontend Docker build after responsive fix:
  - Command: `docker-compose build frontend`.
  - Result: passed.
- Frontend dependency audit:
  - `npm.cmd audit`: `0` vulnerabilities.
  - `npm.cmd audit --omit=dev`: `0` vulnerabilities.
  - `npm.cmd audit --omit=optional`: `0` vulnerabilities.

### Code Review Notes

- Reviewed the CSS change and confirmed it is scoped to `@media (max-width: 640px)`.
- The fix addresses the specific page-level overflow found by browser QA without changing routing, business logic, API calls, or desktop layout.
- Browser re-verification confirmed the Admin Overrides page and audit table remain usable at desktop and mobile widths.
- The dependency audit blocker remains resolved after the CSS fix.

### Cleanup

- `docker-compose down`
  - Result: passed; containers and network removed, PostgreSQL development volume preserved.
- `docker-compose ps`
  - Result: no running Compose services.
- No disposable credential file was created for this task.

### Release-Candidate Classification

Status: APPROVED.

Reason: Applicant ID replacement passed through the actual browser UI, critical MVP browser regression flows passed, the dependency audit blocker remains resolved, the responsive defect found during QA was fixed and reverified, and no unresolved release blockers remain.

### Next Suggested Task

Move to production-hardening work before real deployment: configure scheduled assignment execution, production secrets/TLS handling, database backup/restore operations, monitoring/observability, frontend E2E coverage, and PostgreSQL concurrency/load validation.

## Task 37: Production-Ready Scheduled Assignment Runner Groundwork

### Task Name

Implement production-ready scheduled assignment runner groundwork.

### Files Changed

- `.env.example`
- `README.md`
- `docker-compose.yml`
- `backend/.env.example`
- `backend/app/core/config.py`
- `backend/app/core/logging.py`
- `backend/app/commands/run_assignment_scheduler.py`
- `backend/app/services/assignment_scheduler_runner.py`
- `backend/tests/test_assignment_scheduler_runner.py`
- `backend/tests/test_infrastructure_files.py`
- `resources/docs/assignment_scheduler.md`
- `resources/docs/deployment_security.md`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added scheduler settings with safe defaults and validation:
  - `ASSIGNMENT_SCHEDULER_ENABLED=false`
  - `ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS=60`
  - `ASSIGNMENT_SCHEDULER_BATCH_LIMIT=100`
  - `ASSIGNMENT_SCHEDULER_LOCK_KEY=740730001`
  - `ASSIGNMENT_SCHEDULER_RUN_IMMEDIATELY=true`
- Added `AssignmentSchedulerRunner` for continuous due-availability assignment execution.
- Added `PostgresAdvisoryLock` using non-blocking `pg_try_advisory_lock` and `pg_advisory_unlock`.
- Added `python -m app.commands.run_assignment_scheduler` with graceful `SIGTERM`/`SIGINT` shutdown and `--once` verification mode.
- Preserved the existing one-shot command: `python -m app.commands.assign_due_availabilities --limit 100`.
- Extended structured logging fields for scheduler run ID, lock status, interval, batch size, duration, counts, and error type.
- Added optional `assignment-scheduler` Docker Compose service behind the `scheduler` profile.
- Kept scheduler execution disabled in the API/backend container. The opt-in scheduler profile service explicitly enables scheduler execution to avoid a disabled-service restart loop.
- Added scheduler operations documentation and updated README/deployment notes.

### Review Notes

- Service boundary review:
  - The runner delegates assignment work to the existing assignment scheduler service through `build_scheduler(db).assign_due_availabilities`.
  - Ranking, fairness, row-locking, assignment, audit, override, and reservation logic were not changed.
- Locking review:
  - Each cycle uses a PostgreSQL session-level advisory lock.
  - Lock acquisition is non-blocking; unavailable lock skips the cycle and leaves the process running.
  - Lock release runs in `finally` after success or failure.
  - Existing row-level assignment locks remain unchanged for individual availability processing.
- Error handling review:
  - Recoverable cycle exceptions are logged and do not stop future cycles.
  - The command returns non-zero only for startup/configuration/fatal command failures.
  - Low-level scheduler code does not raise `HTTPException`.
- Shutdown review:
  - `SIGTERM` and `SIGINT` set a shutdown event.
  - The continuous loop exits after the current cycle or interrupted wait.
- Security/logging review:
  - Scheduler logs contain operational counts and IDs, not passwords, bearer tokens, request bodies, or secret values.
  - Docker config rendering can include local `.env` values; final documented verification used quiet/service-list Compose commands where possible.
- Compose review:
  - `assignment-scheduler` has no exposed ports.
  - It uses the backend image and the same PostgreSQL network/database settings.
  - It depends on the PostgreSQL healthcheck.
  - It is not started by default unless the `scheduler` profile is selected.

### Tests Added Or Updated

- Added `backend/tests/test_assignment_scheduler_runner.py` covering:
  - scheduler config defaults and validation bounds,
  - import-safe scheduler command module,
  - `--once` command wiring,
  - PostgreSQL advisory-lock SQL,
  - successful cycle logging and summary counts,
  - unavailable advisory lock skip behavior,
  - lock release after failure,
  - recoverable exception continuation,
  - immediate and delayed first-cycle behavior,
  - shutdown request behavior,
  - simulated two-instance overlap prevention.
- Updated `backend/tests/test_infrastructure_files.py` for:
  - scheduler Compose service contract,
  - scheduler env example values,
  - scheduler settings defaults and bounds.

### Verification Commands And Results

- Focused scheduler/infrastructure tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest tests\test_assignment_scheduler_runner.py tests\test_infrastructure_files.py`.
  - Result: `31` passed.
- Full backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest`.
  - Result: `608` passed, `1` existing Starlette/httpx deprecation warning.
- Backend compile check:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m compileall app tests`.
  - Result: passed.
- Alembic heads:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m alembic -c alembic.ini heads`.
  - Result: `0010 (head)`.
- Alembic history:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m alembic -c alembic.ini history`.
  - Result: migrations `0001` through `0010` listed.
- Compose syntax:
  - Command: `docker-compose config --quiet`.
  - Result: passed. Docker emitted a non-fatal local config warning: access denied reading the user Docker `config.json`.
- Compose scheduler profile registration:
  - Command: `docker-compose --profile scheduler config --services`.
  - Result: listed `db`, `assignment-scheduler`, `backend`, and `frontend`.
- Backend image build:
  - Command: `docker-compose build backend`.
  - Result: passed.
- Temporary live PostgreSQL stack:
  - Commands:
    - `docker-compose -p parkingappschedverify up -d db backend` with temporary host ports and seed admin disabled.
    - `docker-compose -p parkingappschedverify exec -T backend alembic -c alembic.ini upgrade head`.
    - `docker-compose -p parkingappschedverify exec -T backend alembic -c alembic.ini current`.
  - Result: PostgreSQL healthy, backend running, migrations applied, current revision `0010 (head)`.
- Live scheduler acquired-lock cycle:
  - Command: `docker-compose -p parkingappschedverify exec -T -e ASSIGNMENT_SCHEDULER_ENABLED=true -e ASSIGNMENT_SCHEDULER_LOCK_KEY=987654321 -e ASSIGNMENT_SCHEDULER_BATCH_LIMIT=5 -e ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS=5 backend python -m app.commands.run_assignment_scheduler --once`.
  - Result: exited `0`; structured log showed `assignment_scheduler_cycle_completed`, `lock_acquired=true`, `processed_count=0`, `assigned_count=0`, `skipped_count=0`, `failed_count=0`.
- Live scheduler contention cycle:
  - Command: held `pg_advisory_lock(987654321)` from a separate PostgreSQL session, then ran the scheduler `--once` with the same lock key.
  - Result: exited `0`; structured log showed `assignment_scheduler_cycle_skipped_lock_unavailable` and `lock_acquired=false`.
- Live post-release lock cycle:
  - Command: reran scheduler `--once` after the lock-holder session released the lock.
  - Result: exited `0`; structured log showed `assignment_scheduler_cycle_completed` and `lock_acquired=true`.
- Optional scheduler Compose service:
  - Command: `docker-compose -p parkingappschedverify --profile scheduler up -d assignment-scheduler`, followed by logs and stop.
  - Result: service started, ran an immediate protected cycle, logged `assignment_scheduler_cycle_completed`, and stopped cleanly.
  - Final profile-service rerun after Compose review: `docker-compose -p parkingappschedverify2 --profile scheduler up -d assignment-scheduler` without setting `ASSIGNMENT_SCHEDULER_ENABLED` in the shell.
  - Result: service started with the Compose service-level `ASSIGNMENT_SCHEDULER_ENABLED=true`, ran an immediate protected cycle with `lock_acquired=true`, and the temporary project was removed with `docker-compose -p parkingappschedverify2 down -v`.
- Cleanup:
  - Command: `docker-compose -p parkingappschedverify down -v`.
  - Result: temporary backend, scheduler, PostgreSQL containers, network, and temporary `parkingappschedverify_postgres_data` volume removed.
  - Command: `docker-compose ps`.
  - Result: no normal project services running.

### Known Limitations

- The live scheduler PostgreSQL smoke used an empty migrated database, so it verified runner startup, Alembic compatibility, advisory-lock acquisition, advisory-lock contention skip, release, logging, and Compose service startup, but not a full due-availability assignment with seeded domain records.
- The shell cannot run Docker daemon queries without elevated Docker access in this environment.
- `docker-compose config` can render local `.env` values. Do not paste full rendered config into docs or issue trackers when local secret values are present.
- No new migrations were needed; Alembic remains at `0010 (head)`.

### Release-Hardening Classification

Status: READY.

Reason: the production scheduler runner, lock behavior, Compose service, documentation, focused tests, full backend tests, compile checks, Alembic checks, Docker build, and live PostgreSQL advisory-lock smoke all passed. No unresolved scheduler blocker remains.

### Next Suggested Task

Continue production hardening with deployment secrets and TLS groundwork: document required secret sources, reverse-proxy/TLS expectations, production environment variable handling, and any needed configuration guardrails. Do not change parking business logic.

## Task 38: Production Secrets And TLS Groundwork

### Task Name

Implement production secrets and TLS groundwork.

### Files Changed

- `.dockerignore`
- `.env.example`
- `.gitignore`
- `README.md`
- `backend/.env.example`
- `backend/app/core/config.py`
- `backend/tests/test_infrastructure_files.py`
- `backend/tests/test_production_secrets_config.py`
- `backend/tests/test_seed_admin_command.py`
- `deploy/nginx/Dockerfile`
- `deploy/nginx/tls-proxy.conf`
- `docker-compose.production.yml`
- `frontend/.env.example`
- `resources/docs/deployment_security.md`
- `resources/docs/implementation_log.md`
- `resources/docs/production_secrets_tls.md`
- `scripts/generate_local_tls_certificate.ps1`
- `secrets/.gitkeep`

### Secret-Loading And Precedence Decisions

- Direct environment variables remain supported for local development.
- File-based Docker secret variables were added:
  - `JWT_SECRET_FILE`
  - `DATABASE_PASSWORD_FILE`
  - `POSTGRES_PASSWORD_FILE`
- If no file variable is set, the direct value is used.
- If a file variable is set and the direct value is still a documented default, the file value is used.
- If a file variable is set and a custom direct value is also set, startup fails unless both values match.
- `DATABASE_URL` cannot be combined with a database password file.
- When `DATABASE_URL` is empty, the backend builds the PostgreSQL URL from components and URL-encodes username, password, and database name.
- Secret files trim one trailing newline and reject missing, unreadable, or empty files.
- Validation errors identify the setting but do not print secret contents.

### Production Validation Rules

When `ENVIRONMENT=production` or `ENVIRONMENT=prod`, settings validation rejects:

- default/example JWT secrets,
- JWT secrets shorter than 32 characters,
- empty/example database passwords,
- example database passwords embedded in `DATABASE_URL`,
- `SEED_ADMIN_ENABLED=true`,
- `LOG_LEVEL=DEBUG`,
- localhost/loopback CORS origins,
- non-HTTPS CORS origins,
- wildcard/malformed CORS origins.

Local and test environments continue to support local defaults and existing test fixtures.

### TLS And Reverse-Proxy Architecture

- Added `docker-compose.production.yml` as production-oriented deployment groundwork.
- Added `deploy/nginx/Dockerfile` and `deploy/nginx/tls-proxy.conf`.
- Production stack shape:
  - `db`: PostgreSQL with `POSTGRES_PASSWORD_FILE`, no host-published port.
  - `backend`: FastAPI with file-based JWT/database secrets, internal `expose: 8000`, no host-published port.
  - `proxy`: nginx TLS terminator serving the Vue frontend and proxying `/api/` to FastAPI.
  - `assignment-scheduler`: optional profile service with file-based secrets and no host ports.
- The proxy:
  - redirects HTTP to HTTPS,
  - serves Vue Router fallback,
  - proxies `/api/` to `backend:8000`,
  - forwards `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`, and `X-Request-ID`,
  - uses TLS 1.2 and TLS 1.3,
  - disables nginx server tokens,
  - keeps HSTS commented until the real domain is verified.
- Production Compose uses `PRODUCTION_CORS_ALLOWED_ORIGINS` and `PRODUCTION_VITE_API_BASE_URL` so local `.env` values cannot silently leak into TLS/proxy config.
- Backend production command enables Uvicorn proxy-header handling only in the production Compose shape where backend is not directly published.

### Tests Added Or Updated

- Added `backend/tests/test_production_secrets_config.py` covering:
  - direct secret values,
  - JWT secret file loading,
  - database password file loading,
  - trailing newline trimming,
  - empty/missing secret files,
  - conflicting direct/file secrets without secret leakage,
  - `DATABASE_URL` plus password file rejection,
  - database URL component encoding,
  - production JWT/database/seed-admin/debug/CORS validation,
  - local/test compatibility and scheduler config compatibility.
- Updated `backend/tests/test_infrastructure_files.py` covering:
  - TLS proxy Dockerfile and nginx config,
  - HTTP redirect and HTTPS listener settings,
  - TLS certificate/key mount paths,
  - proxy header forwarding,
  - Vue Router fallback,
  - production Compose internal backend and Docker secrets,
  - secret ignore rules,
  - local TLS certificate script.
- Updated `backend/tests/test_seed_admin_command.py` so production seed-admin rejection is verified at settings validation.

### Verification Commands And Results

- Focused production secret/infrastructure/seed/security tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest tests\test_production_secrets_config.py tests\test_infrastructure_files.py tests\test_seed_admin_command.py tests\test_security.py`.
  - Result: `66` passed.
- Focused production secret/infrastructure tests after Compose variable fix:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest tests\test_production_secrets_config.py tests\test_infrastructure_files.py`.
  - Result: `47` passed.
- Full backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest`.
  - Result: `636` passed, `1` existing Starlette/httpx deprecation warning.
- Backend compile check:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m compileall app tests`.
  - Result: passed.
- Alembic heads:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m alembic -c alembic.ini heads`.
  - Result: `0010 (head)`.
- Alembic history:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m alembic -c alembic.ini history`.
  - Result: migrations `0001` through `0010` listed.
- Frontend tests:
  - Command: `npm.cmd test`.
  - Result: `43` passed across `17` files.
- Frontend production build:
  - Command: `npm.cmd run build`.
  - Result: passed.
- Local Compose config:
  - Command: `docker-compose config --quiet`.
  - Result: passed. Docker emitted the existing non-fatal user config warning: access denied reading the user Docker `config.json`.
- Production/TLS Compose config:
  - Command: `docker-compose -f docker-compose.production.yml config --quiet`.
  - Result: passed with the same non-fatal Docker user config warning.
- Production/TLS Compose services:
  - Command: `docker-compose -f docker-compose.production.yml --profile scheduler config --services`.
  - Result: listed `db`, `backend`, `proxy`, and `assignment-scheduler`.
- Local certificate helper:
  - Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_local_tls_certificate.ps1`.
  - Result: failed safely because OpenSSL is not on PATH; no certificate/key content was printed.
- Disposable local TLS certificate:
  - Command: bundled Python/cryptography generated self-signed localhost SAN cert/key into gitignored `secrets/`.
  - Result: generated temporary `tls_certificate.pem` and `tls_private_key.pem` for verification only.
- Production backend/proxy Docker build:
  - Command: `docker-compose -p parkingapptlsverify -f docker-compose.production.yml build backend proxy`.
  - Result: passed; proxy build ran frontend production build with `VITE_API_BASE_URL=/api`.
- Production TLS stack startup:
  - Command: `docker-compose -p parkingapptlsverify -f docker-compose.production.yml up -d db backend proxy`.
  - Result: PostgreSQL, backend, and proxy started successfully on temporary project/ports.
- Production database migrations:
  - Command: `docker-compose -p parkingapptlsverify -f docker-compose.production.yml exec -T backend alembic -c alembic.ini upgrade head`.
  - Result: applied migrations through `0010`.
  - Command: `docker-compose -p parkingapptlsverify -f docker-compose.production.yml exec -T backend alembic -c alembic.ini current`.
  - Result: `0010 (head)`.
- HTTP redirect smoke:
  - Command: `curl.exe -I http://localhost:18081/login`.
  - Result: `301 Moved Permanently` to HTTPS.
- HTTPS smoke:
  - Windows `curl.exe -k` failed against the self-signed cert with SChannel `SEC_E_NO_CREDENTIALS`.
  - Fallback command: bundled Python `http.client.HTTPSConnection` with verification disabled for local self-signed testing.
  - Results:
    - `HEAD https://localhost:18443/`: `200`, security headers present.
    - `HEAD https://localhost:18443/login`: `200`, Vue Router fallback and security headers present.
    - `HEAD https://localhost:18443/dashboard`: `200`, Vue Router fallback and security headers present.
    - `GET https://localhost:18443/api/health` with `X-Request-ID: tls-smoke-request`: `200`, environment `production`, request ID preserved, backend security headers present.
    - `Strict-Transport-Security` absent as documented for local self-signed verification.
- Nginx syntax:
  - Command: `docker-compose -p parkingapptlsverify -f docker-compose.production.yml exec -T proxy nginx -t`.
  - Result: syntax OK and test successful.
- Backend exposure:
  - Command: `docker-compose -p parkingapptlsverify -f docker-compose.production.yml ps`.
  - Result: only proxy published host ports; backend showed internal `8000/tcp`, db showed internal `5432/tcp`.
- Log secret check:
  - Command: `docker-compose -p parkingapptlsverify -f docker-compose.production.yml logs --tail 80 backend proxy`.
  - Result: logs contained startup, request, and access metadata only; no generated JWT secret, database password, private key, or certificate content was printed.
- Cleanup:
  - Command: `docker-compose -p parkingapptlsverify -f docker-compose.production.yml down -v`.
  - Result: temporary containers, network, and volume removed.
  - Generated local secret/cert files removed from `secrets/`; only `secrets/.gitkeep` remains.
  - Command: `docker-compose ps`.
  - Result: no normal project services running.
  - Secret scan: searched for disposable secret prefixes and PEM private-key/certificate markers.
  - Result: no matches.

### Review Notes

- Production fail-fast behavior is centralized in backend settings and does not affect local/test defaults.
- File-based secret resolution is centralized and never logs secret contents.
- Production Compose references secret files and keeps the backend/database off host ports.
- The TLS proxy forwards the expected headers and uses `/api/` for same-origin frontend-to-backend traffic.
- HSTS is documented but intentionally disabled in the committed config until a real domain is verified.
- Uvicorn forwarded-header trust is only configured in the production Compose topology where the backend is internal-only.
- Frontend bearer-token storage risks and future secure-cookie/CSRF direction are documented without changing authentication design.
- Generated certificate/key and disposable secret files were removed after verification.

### Known Limitations

- The local certificate helper requires OpenSSL on PATH. OpenSSL was not available in this environment, so the helper's failure path was verified and the live TLS smoke used a disposable certificate generated by bundled Python cryptography.
- Windows `curl.exe -k` failed against the self-signed certificate through SChannel; HTTPS smoke was completed with Python's HTTPS client and certificate verification disabled for local-only testing.
- `docker-compose config` still emits a non-fatal local Docker user config warning about `C:\Users\nikola.milosevic\.docker\config.json` access.
- This is deployment groundwork, not a managed production deployment. It does not add cloud secret-manager integration, ACME automation, public DNS, SSO/OIDC, monitoring, or backup automation.
- `git status` could not be used in this workspace because the shell reports `fatal: not a git repository` even though the workspace contains project files.

### Release-Hardening Classification

Status: READY.

Reason: production settings fail closed for insecure secrets/CORS/debug/seed-admin configuration, file-based secret loading is tested, production Compose and TLS proxy configuration render and build, nginx syntax validates, live local HTTPS smoke passes through the proxy, backend/database are internal-only in the production stack, and generated secret material was removed.

### Next Suggested Task

Continue production hardening with database backup and restore operations: add a documented backup/restore runbook, local verification scripts or commands for `pg_dump`/`pg_restore`, restore testing guidance, retention/encryption notes, and focused documentation/config checks. Do not change parking business logic.

## Task 57 - PostgreSQL Backup and Restore Operations Groundwork

Date: 2026-06-20

### Task Name

PostgreSQL backup and restore operations groundwork.

### Files Changed

- `.gitignore`
- `.dockerignore`
- `backups/.gitkeep`
- `scripts/postgres_backup_common.ps1`
- `scripts/backup_postgres.ps1`
- `scripts/verify_postgres_backup.ps1`
- `scripts/restore_postgres.ps1`
- `resources/docs/postgres_backup_restore.md`
- `resources/docs/deployment_security.md`
- `README.md`
- `backend/tests/test_postgres_backup_scripts.py`
- `backend/tests/test_infrastructure_files.py`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added Docker Compose compatible PostgreSQL backup, verification, restore, and shared-helper PowerShell scripts.
- Backup output uses PostgreSQL custom-format `pg_dump -Fc` archives with compression and generated names in `<database>_yyyyMMddTHHmmssZ.pgdump` format.
- Backup metadata sidecars include non-secret operational metadata: backup file name, UTC creation time, database name, PostgreSQL server version, Alembic revision, Compose project details, archive format, compression level, file size, and SHA-256 checksum.
- Verification validates file existence, non-empty archive size, metadata checksum, optional expected checksum, and `pg_restore --list`.
- Restore defaults to a fresh target database and guards destructive existing-database restores behind `-Mode ExistingDatabase -ConfirmDestructive`.
- Production-like restores are guarded behind `-AllowProductionRestore`.
- Retention cleanup supports dry-run and deletes only generated backup file names plus matching metadata sidecars.
- Added a full runbook at `resources/docs/postgres_backup_restore.md` and linked it from README and deployment/security docs.
- Added ignore rules so local backup artifacts under `backups/` are not committed or included in Docker build context.

### Review Notes

- No business logic, API behavior, frontend screens, database models, or Alembic migrations were changed.
- The backup scripts do not print or store database passwords, JWT secrets, seed credentials, private keys, or full database URLs in metadata.
- The restore script validates target database/user identifiers before building SQL for database creation/replacement.
- Live verification found and fixed three PowerShell compatibility bugs:
  - Retention filter incorrectly parsed `-and` as a function parameter.
  - Failure cleanup incorrectly parsed `-and` as a `Test-Path` parameter.
  - `ProcessStartInfo.ArgumentList` was null in Windows PowerShell 5.1, so process helpers now use a quoted `Arguments` string.
- The restore workflow was validated with real PostgreSQL data in a disposable Docker Compose project.

### Tests Added Or Updated

- Added `backend/tests/test_postgres_backup_scripts.py` covering:
  - PowerShell parser checks for all backup/restore scripts,
  - Compose command detection support for `docker-compose` and `docker compose`,
  - generated backup file naming,
  - native process helper compatibility in Windows PowerShell,
  - invalid output directory handling,
  - missing/empty backup rejection,
  - destructive restore confirmation guard,
  - production restore guard,
  - retention dry-run behavior,
  - retention deleting only generated backup names and metadata,
  - metadata excluding secret-like fields,
  - checksum mismatch detection.
- Updated `backend/tests/test_infrastructure_files.py` to verify backup ignore rules, script presence, runbook commands, checksum behavior, and restore guardrail documentation.

### Verification Commands And Results

- Focused backup script tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest tests\test_postgres_backup_scripts.py`.
  - Result: `13` passed.
- Focused infrastructure tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest tests\test_infrastructure_files.py`.
  - Result: `24` passed.
- Full backend tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest`.
  - Result: `650` passed, `1` existing Starlette/httpx deprecation warning.
- Backend compile check:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m compileall app tests`.
  - Result: passed.
- Alembic heads:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m alembic -c alembic.ini heads`.
  - Result: `0010 (head)`.
- Alembic history:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m alembic -c alembic.ini history`.
  - Result: migrations `0001` through `0010` listed.
- Frontend tests:
  - Command: `npm.cmd test`.
  - Result: `43` passed across `17` files.
- Frontend production build:
  - Command: `npm.cmd run build`.
  - Result: passed.
- Local Compose config:
  - Command: `docker-compose config --quiet`.
  - Result: passed.
- Production/TLS Compose config:
  - Command: `docker-compose -f docker-compose.production.yml config --quiet`.
  - Result: passed.
- Docker builds:
  - Command: `docker-compose build backend frontend`.
  - Result: passed; frontend Docker build ran `npm run build` successfully.

### Live Docker/PostgreSQL Drill

Docker Desktop availability: available.

Disposable Compose project: `parkingappbackupverify`.

Commands and results:

- Startup:
  - Command: `docker-compose -p parkingappbackupverify up -d db backend` with temporary host ports and seed admin disabled.
  - Result: PostgreSQL and backend started; PostgreSQL healthcheck passed.
- Migration:
  - Command: `docker-compose -p parkingappbackupverify exec -T backend alembic -c alembic.ini upgrade head`.
  - Result: migrations applied through `0010`.
  - Command: `docker-compose -p parkingappbackupverify exec -T backend alembic -c alembic.ini current`.
  - Result: `0010 (head)`.
- Disposable seed data:
  - Created one team, one employee, one parking owner, one parking spot, one assigned availability, one selected application, and one active reservation.
  - Source row counts:
    - `teams=1`
    - `users=2`
    - `parking_spots=1`
    - `parking_availabilities=1`
    - `parking_applications=1`
    - `parking_reservations=1`
    - `alembic=0010`
- Backup:
  - Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_postgres.ps1 -ComposeFiles docker-compose.yml -ProjectName parkingappbackupverify -OutputDirectory C:\tmp\parkingapp-backup-verify -DatabaseName parking_app -DatabaseUser parking_app`.
  - Result: created `C:\tmp\parkingapp-backup-verify\parking_app_20260620T182046Z.pgdump` and metadata sidecar.
  - Archive size: `40609` bytes.
  - Metadata PostgreSQL version: `16.10`.
  - Metadata Alembic revision: `0010`.
  - Metadata SHA-256: `6ac5981db717eef61a189126f124042cddc6c5caf4e52db49d877674f801f5d9`.
- Backup verification:
  - Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_postgres_backup.ps1 -BackupFile C:\tmp\parkingapp-backup-verify\parking_app_20260620T182046Z.pgdump -ComposeFiles docker-compose.yml -ProjectName parkingappbackupverify`.
  - Result: passed; metadata checksum matched and `pg_restore --list` read the archive.
- Fresh restore:
  - Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\restore_postgres.ps1 -BackupFile C:\tmp\parkingapp-backup-verify\parking_app_20260620T182046Z.pgdump -ComposeFiles docker-compose.yml -ProjectName parkingappbackupverify -TargetDatabase parking_app_restore_verify -DatabaseUser parking_app -SourceDatabaseName parking_app`.
  - Result: restored into `parking_app_restore_verify`; restored Alembic revision `0010`.
- Restored row counts:
  - `teams=1`
  - `users=2`
  - `parking_spots=1`
  - `parking_availabilities=1`
  - `parking_applications=1`
  - `parking_reservations=1`
  - `alembic=0010`
- Retention dry-run:
  - Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_postgres.ps1 -RetentionOnly -RetentionDays 0 -DryRunRetention -OutputDirectory C:\tmp\parkingapp-backup-verify`.
  - Result: reported that the generated backup would be deleted; no file was deleted.
- Cleanup:
  - Command: `docker-compose -p parkingappbackupverify down -v`.
  - Result: disposable containers, network, and `parkingappbackupverify_postgres_data` volume removed.
  - Command: exact-path cleanup of `C:\tmp\parkingapp-backup-verify`.
  - Result: temporary backup directory removed after one sandbox-related access-denied retry with escalation.
  - Command: `docker-compose ps`.
  - Result: no normal project services running.

### Known Limitations

- The scripts provide logical backup/restore operations and a local restore drill. They do not add managed scheduled backups, cloud storage upload, backup encryption, offsite replication, or production monitoring.
- Production backup storage, encryption, retention, alerting, and restore cadence must be implemented in the deployment platform.
- The live restore drill used a disposable local Docker Compose project, not a managed production database.
- Destructive production restore remains an operator-reviewed procedure and intentionally requires explicit flags.
- `npm audit` was not run because this task did not add or change frontend dependencies.

### Release-Hardening Classification

Status: READY.

Reason: backup creation, metadata generation, checksum/archive verification, fresh restore, Alembic revision recovery, representative row-count recovery, retention dry-run, cleanup, docs, and regression tests were all verified successfully. No parking business logic was changed.

### Next Suggested Task

Continue production hardening with monitoring and observability groundwork: define operational health/alerting guidance for the API, assignment scheduler, backup jobs, restore drills, Docker services, and database availability, with focused documentation/config checks only and no parking business logic changes.

## Task 58 - Monitoring, Metrics, Health/Readiness, and Observability Groundwork

Date: 2026-06-21

### Task Name

Monitoring, metrics, health/readiness, and observability groundwork.

### Files Changed

- `backend/requirements.txt`
- `backend/app/core/config.py`
- `backend/app/core/metrics.py`
- `backend/app/main.py`
- `backend/app/middleware/request_context.py`
- `backend/app/routers/auth.py`
- `backend/app/routers/health.py`
- `backend/app/schemas/health.py`
- `backend/app/services/assignment_scheduler_runner.py`
- `backend/app/commands/run_assignment_scheduler.py`
- `backend/tests/test_health.py`
- `backend/tests/test_monitoring_observability.py`
- `backend/tests/test_assignment_scheduler_runner.py`
- `backend/tests/test_infrastructure_files.py`
- `docker-compose.yml`
- `docker-compose.production.yml`
- `deploy/nginx/tls-proxy.conf`
- `deploy/prometheus/prometheus.yml`
- `deploy/prometheus/alert_rules.yml`
- `deploy/grafana/provisioning/datasources/prometheus.yml`
- `deploy/grafana/provisioning/dashboards/dashboards.yml`
- `deploy/grafana/dashboards/parking-app-overview.json`
- `.env.example`
- `backend/.env.example`
- `README.md`
- `resources/docs/deployment_security.md`
- `resources/docs/assignment_scheduler.md`
- `resources/docs/monitoring_observability.md`
- `resources/docs/implementation_log.md`

`git status` could not be used because this workspace reports `fatal: not a git repository`.

### Health Endpoint Design

- Preserved `GET /health` as the existing simple compatibility health response.
- Added `GET /health/live` for process liveness. It does not touch PostgreSQL.
- Added `GET /health/ready` for traffic readiness. It runs a bounded PostgreSQL `SELECT 1` check through existing SQLAlchemy engine infrastructure and returns `503` with generic dependency status when PostgreSQL is unavailable.
- Readiness responses expose only `status`, `service`, `environment`, and generic dependency status. They do not expose credentials, database URLs, exception messages, stack traces, host paths, or secret paths.
- Request ID and security headers remain present on health responses.
- Alembic state remains a deployment/startup verification step; readiness does not run expensive migration history checks.

### Metric Names and Label Policy

Added Prometheus client dependency: `prometheus-client>=0.21,<1.0`.

Metrics:

- `parking_http_requests_total{method,route,status_code,status_class}`
- `parking_http_request_duration_seconds_bucket{method,route,status_code,status_class,le}`
- `parking_http_requests_in_progress{method}`
- `parking_unhandled_exceptions_total{exception_type,route}`
- `parking_auth_failures_total{reason}`
- `parking_readiness_dependency_status{dependency}`
- `parking_assignment_scheduler_cycles_total{result}`
- `parking_assignment_scheduler_assignments_produced_total`
- `parking_assignment_scheduler_cycle_duration_seconds_bucket{result,le}`
- `parking_assignment_scheduler_last_success_timestamp_seconds`
- `parking_assignment_scheduler_running_cycles`
- `parking_assignment_scheduler_lock_skips_total`

Label policy:

- HTTP metrics use route templates such as `/health/ready` or `/admin/users/{user_id}`.
- 404/unmatched requests use `route="<unmatched>"`.
- No usernames, emails, user IDs, request IDs, raw dynamic paths, raw URLs, request bodies, bearer tokens, free-text reasons, database URLs, or secrets are used as labels.
- `/metrics` is excluded from HTTP metric recording to avoid recursive/noisy observations.

### Prometheus/Grafana Architecture

- Backend exposes `/metrics` when `METRICS_ENABLED=true`.
- Scheduler process starts its own internal metrics server on `SCHEDULER_METRICS_PORT`, default `9101`, so the scheduler process can be scraped independently from the API process.
- Local Compose `monitoring` profile adds:
  - Prometheus on `127.0.0.1:${PROMETHEUS_PORT:-9090}:9090`,
  - Grafana on `127.0.0.1:${GRAFANA_PORT:-3000}:3000`,
  - persistent Prometheus and Grafana volumes,
  - Prometheus scrape jobs for `backend:8000/metrics` and `assignment-scheduler:9101/metrics`,
  - Grafana Prometheus datasource provisioning,
  - a minimal Parking App overview dashboard.
- Production TLS proxy explicitly blocks public `/metrics` and `/api/metrics`; backend metrics remain internal-only by default.

### Scheduler Instrumentation

- Successful scheduler cycles increment `parking_assignment_scheduler_cycles_total{result="success"}`.
- Recoverable cycle failures increment `result="error"`.
- Advisory-lock skips increment `result="lock_skipped"` and `parking_assignment_scheduler_lock_skips_total`.
- Cycle duration is observed by result.
- Assignment count increments `parking_assignment_scheduler_assignments_produced_total`.
- Last-success timestamp updates only after successful cycles.
- Running-cycle gauge increments/decrements around every cycle.
- Scheduler metric recording is defensive: if a metric call fails, the scheduler logs a warning and continues.
- Scheduler logs continue to include run ID/request ID, event name, duration, lock status, batch settings, result counts, and error type.

### Alert Examples

Added example Prometheus rules in `deploy/prometheus/alert_rules.yml`:

- `BackendNotReady`
- `HighServerErrorRate`
- `HighRequestLatency`
- `AssignmentSchedulerNoRecentSuccess`
- `AssignmentSchedulerCycleFailures`
- `PostgreSQLReadinessFailure`

Thresholds are documented as examples requiring production tuning. No notification receiver is configured.

### Tests Added or Updated

- Health tests:
  - liveness succeeds without database access,
  - readiness succeeds on successful database ping,
  - readiness returns `503` without sensitive details on dependency failure,
  - request ID and security headers remain present.
- Metrics tests:
  - `/metrics` returns Prometheus text output and expected metric names,
  - normal requests increment request metrics,
  - route templates are used instead of raw paths,
  - 404 paths do not create raw-path labels,
  - request duration metrics are recorded,
  - in-progress gauge returns to zero,
  - metrics can be disabled,
  - unhandled exception metrics avoid sensitive labels/text.
- Scheduler tests:
  - success metrics increment,
  - error metrics increment,
  - lock-skip metrics increment,
  - last-success timestamp updates,
  - metrics failure does not break scheduler execution.
- Configuration/infrastructure tests:
  - metrics settings defaults and validation,
  - readiness timeout validation,
  - monitoring Compose profile structure,
  - production proxy metrics blocking config,
  - Prometheus scrape config and alert rule structure,
  - Grafana datasource/dashboard provisioning.

### Verification Commands and Results

- Focused health/metrics/scheduler/infrastructure tests:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest tests\test_health.py tests\test_monitoring_observability.py tests\test_assignment_scheduler_runner.py tests\test_infrastructure_files.py`.
  - Result: `49` passed, `1` existing Starlette/httpx deprecation warning.
- Focused scheduler/metrics tests after final metric-server logging fix:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest tests\test_monitoring_observability.py tests\test_assignment_scheduler_runner.py`.
  - Result: `20` passed, `1` existing Starlette/httpx deprecation warning.
- Full backend tests after final code review change:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest`.
  - Result: `662` passed, `1` existing Starlette/httpx deprecation warning.
- Backend compile check:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m compileall app tests`.
  - Result: passed.
- Alembic heads:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m alembic -c alembic.ini heads`.
  - Result: `0010 (head)`.
- Alembic history:
  - Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m alembic -c alembic.ini history`.
  - Result: migrations `0001` through `0010` listed.
- Local Compose config:
  - Command: `docker-compose config --quiet`.
  - Result: passed.
- Monitoring profile Compose config:
  - Command: `docker-compose --profile monitoring config --quiet`.
  - Result: passed.
- Production/TLS Compose config:
  - Command: `docker-compose -f docker-compose.production.yml config --quiet`.
  - Result: passed.
- Frontend tests:
  - Command: `npm.cmd test`.
  - Result: `43` passed across `17` files.
- Frontend production build:
  - Command: `npm.cmd run build`.
  - Result: passed.
- Frontend dependency audit:
  - Command: `npm.cmd audit --omit=optional`.
  - Result: `0` vulnerabilities.
- Python dependency audit:
  - Installed `pip-audit` into ignored `.test-deps` because it was not already available.
  - First command failed because default cache path was outside writable workspace.
  - Rerun command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pip_audit -r requirements.txt --cache-dir C:\tmp\pip-audit-cache`.
  - Result: `No known vulnerabilities found`.
  - Temporary audit cache was removed.
- Docker builds:
  - Command: `docker-compose -p parkingappmonitorverify build backend frontend`.
  - Result: passed; backend image installed `prometheus-client`.
  - Command: `docker-compose -p parkingappmonitorproxyverify -f docker-compose.production.yml build backend proxy`.
  - Result: passed; proxy build included updated nginx metrics-blocking config.

### Live Docker Monitoring Verification

Docker Desktop availability: available.

Disposable monitoring project: `parkingappmonitorverify`.

- Startup:
  - Command: `docker-compose -p parkingappmonitorverify up -d db backend` with temporary ports.
  - Result: PostgreSQL and backend started; database healthcheck passed.
- Migration:
  - Command: `docker-compose -p parkingappmonitorverify exec -T backend alembic -c alembic.ini upgrade head`.
  - Result: migrations applied through `0010`.
- Monitoring profile:
  - Command: `docker-compose -p parkingappmonitorverify --profile monitoring up -d assignment-scheduler prometheus grafana`.
  - Result: scheduler, Prometheus, and Grafana started.
- Health checks:
  - `GET http://localhost:18003/health/live`: `200`, liveness body returned, request ID/security headers present.
  - `GET http://localhost:18003/health/ready`: `200`, readiness body returned with database `ok`, request ID/security headers present.
- Backend metrics:
  - `GET http://localhost:18003/metrics`: returned Prometheus output including `parking_http_requests_total` and `parking_readiness_dependency_status`.
- Prometheus targets:
  - `GET http://127.0.0.1:19090/api/v1/targets`: both `parking-backend` and `parking-assignment-scheduler` targets were `up`.
- Scheduler metrics:
  - Prometheus query `parking_assignment_scheduler_cycles_total`: returned scheduler `success` cycles.
  - Advisory lock simulation:
    - Command: `docker-compose -p parkingappmonitorverify exec -T db psql -U parking_app -d parking_app -c "SELECT pg_advisory_lock(740730001); SELECT pg_sleep(12); SELECT pg_advisory_unlock(740730001);"`
    - Result: lock held and released successfully.
    - Prometheus query `parking_assignment_scheduler_cycles_total{result="lock_skipped"}` returned value `2`.
- Readiness failure/recovery:
  - Command: `docker-compose -p parkingappmonitorverify stop db`.
  - `GET /health/live`: `200`.
  - `GET /health/ready`: `503`, generic database error status only.
  - Command: `docker-compose -p parkingappmonitorverify start db`.
  - `GET /health/ready`: recovered to `200`.
- HTTP metrics in Prometheus:
  - Query `sum by (route,status_class) (parking_http_requests_total)` showed `/health/live`, `/health/ready` `2xx`, and `/health/ready` `5xx`.
- Grafana:
  - `HEAD http://127.0.0.1:13000/login`: `200`.
- Port exposure:
  - `docker-compose -p parkingappmonitorverify ps` showed Prometheus bound to `127.0.0.1:19090` and Grafana bound to `127.0.0.1:13000`; scheduler metrics port was internal-only.

Disposable production proxy project: `parkingappmonitorproxyverify`.

- Generated local-only gitignored secrets and self-signed TLS files for verification.
- Startup:
  - Command: `docker-compose -p parkingappmonitorproxyverify -f docker-compose.production.yml up -d db backend proxy`.
  - Result: production-shaped db, backend, and TLS proxy started on temporary ports.
- Migration:
  - Command: `docker-compose -p parkingappmonitorproxyverify -f docker-compose.production.yml exec -T backend alembic -c alembic.ini upgrade head`.
  - Result: migrations applied through `0010`.
- Nginx syntax:
  - Command: `docker-compose -p parkingappmonitorproxyverify -f docker-compose.production.yml exec -T proxy nginx -t`.
  - Result: syntax OK.
- Proxy metrics exposure:
  - `GET https://localhost:18444/metrics`: `404`.
  - `GET https://localhost:18444/api/metrics`: `404`.
  - `GET https://localhost:18444/api/health/live`: `200`.
- Production service exposure:
  - `docker-compose -p parkingappmonitorproxyverify -f docker-compose.production.yml ps` showed backend and db internal-only; only proxy exposed temporary host ports.

Cleanup:

- Command: `docker-compose -p parkingappmonitorverify down -v`.
  - Result: disposable monitoring containers, network, and volumes removed.
- Command: `docker-compose -p parkingappmonitorproxyverify -f docker-compose.production.yml down -v`.
  - Result: disposable production proxy containers, network, and volume removed.
- Generated verification secrets removed from `secrets/`; only `secrets/.gitkeep` remains.
- Command: `docker-compose ps`.
  - Result: no normal project services running.

### Code Review Notes

- Middleware records metrics after route resolution so route labels use normalized route templates.
- `/metrics` is skipped for HTTP metric recording but remains logged through existing request logging.
- In-progress request gauge uses only method label to avoid route-resolution timing and dynamic path cardinality.
- Readiness dependency failure logs only safe internal fields: dependency, duration, and exception type.
- The settings object passed to `create_app` is now also used for FastAPI dependencies via dependency override, fixing a pre-existing inconsistency where health dependencies could fall back to the cached global settings.
- Scheduler metric calls are wrapped so metric failures cannot break assignment execution.
- Production proxy denies metrics paths before the `/api/` proxy rule.
- Prometheus and Grafana local host ports are loopback-bound in local Compose.
- The current metrics setup is single-process. Multiprocess Uvicorn/Gunicorn would require explicit Prometheus multiprocess configuration before scaling workers.

### Known Limitations

- Prometheus/Grafana are local/Compose groundwork, not a managed production monitoring deployment.
- No Alertmanager receiver or commercial/cloud monitoring integration is configured.
- No distributed tracing backend is added.
- Readiness gauge reflects the most recent `/health/ready` probe; production should have a platform readiness probe or synthetic check hitting that endpoint.
- Prometheus Python multiprocess mode is not implemented. The backend currently runs one Uvicorn worker.
- Backup observability remains guidance only; backup scheduling and metrics publication belong to the future external backup job/platform integration.

### Release-Hardening Classification

Status: READY.

Reason: liveness/readiness endpoints are implemented and tested, Prometheus metrics are exported with safe low-cardinality labels, scheduler metrics are exported from the scheduler process, Prometheus successfully scraped backend and scheduler targets, readiness failure/recovery was verified live, production proxy metrics exposure was blocked live, docs are updated, and regression checks passed.

### Next Suggested Task

Continue production hardening with PostgreSQL concurrency and load validation for assignment, cancellation, reassignment, and admin override flows against a disposable PostgreSQL environment. Focus on race-condition/load tests, transaction behavior, and operational limits; do not add new product features.

## Task 59 - PostgreSQL Concurrency Validation Phase 1

### Task Name

Deterministic PostgreSQL concurrency tests for assignment and application creation.

### Files Changed

- `backend/app/services/parking_applications.py`
- `backend/pyproject.toml`
- `backend/tests/postgres_concurrency/test_assignment_application_concurrency.py`
- `resources/docs/postgres_concurrency_load_validation.md`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added a dedicated `postgres_concurrency` pytest marker.
- Added a PostgreSQL-only integration test suite under `backend/tests/postgres_concurrency/`.
- Added safety checks so the concurrency suite:
  - requires `POSTGRES_CONCURRENCY_DATABASE_URL`,
  - requires a PostgreSQL URL,
  - requires a disposable/test-oriented database name,
  - truncates model tables before and after each test,
  - uses separate sessions/connections for concurrent actors,
  - coordinates workers with barriers/events and bounded timeouts,
  - collects worker exceptions in the parent test thread.
- Covered Phase 1 scenarios:
  - two concurrent scheduler assignment attempts for the same due availability,
  - scheduler advisory-lock-protected cycle overlapping direct assignment,
  - two direct assignment calls for the same availability,
  - two direct assignment calls for different availabilities,
  - duplicate same-employee application creation,
  - different-employee concurrent applications,
  - application submission overlapping assignment start.
- Added `resources/docs/postgres_concurrency_load_validation.md`.

### Defects Found and Fixes

- Review found an application creation versus assignment race: application creation read the availability without taking the same row lock that assignment takes.
- Minimal fix:
  - `ParkingApplicationService.apply_for_availability` now calls `get_by_id_for_update`.
  - duplicate insert races are mapped to the existing `ParkingApplicationDuplicateError`.
- No Alembic migration was required because existing constraints remain valid:
  - unique application per availability/applicant,
  - unique reservation per application,
  - partial unique active reservation per availability.

### Review Notes

- Assignment lock order remains availability row, pending application rows, reservation insert, application status updates, availability status update, audit insert, caller commit.
- Scheduler advisory locking remains scoped to overlapping scheduler cycles only; direct assignment still relies on row-level availability locking.
- Application creation now uses the same availability row-lock boundary as assignment, preventing pending orphan applications after assignment.
- The service-level duplicate handling preserves existing API behavior because the router already maps `ParkingApplicationDuplicateError` to HTTP `409`.
- Test settings explicitly disable dotenv loading where ranking/scheduler settings are needed, avoiding accidental reads from local Compose `.env` values.
- Secrets were not added or committed.

### Tests Added or Updated

- Added `backend/tests/postgres_concurrency/test_assignment_application_concurrency.py`.
- Updated `backend/pyproject.toml` with the `postgres_concurrency` marker.

### Exact Verification Commands and Results

- Command: `docker-compose config`.
  - Result: passed. Docker emitted a local client-config access warning, but Compose rendered valid configuration. Expanded output was not copied because it can contain local `.env` values.
- Command: `docker-compose -p parkingappconcurrencyphase1 up -d db` with disposable values `POSTGRES_DB=parking_app_concurrency`, `POSTGRES_PORT=55432`.
  - Result: disposable PostgreSQL container started and reached healthy state.
- Command: backend Alembic `upgrade head` with `DATABASE_URL=postgresql+psycopg://parking_app:parking_app@localhost:55432/parking_app_concurrency`.
  - Result: migrations applied through `0010`.
- Command: `pytest -c backend/pyproject.toml -m postgres_concurrency backend/tests/postgres_concurrency -q`.
  - First result: failed because test helper settings read root `.env` Compose-only keys. Fixed by injecting test settings with dotenv loading disabled.
  - Final result: `7 passed`.
- Command: from `backend`, `pytest tests/test_parking_application_service.py tests/test_parking_applications_api.py tests/test_parking_reservation_assignment_service.py tests/test_parking_assignment_scheduler.py -q`.
  - Result: passed with one existing Starlette deprecation warning.
- Command: from `backend`, `pytest -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` unset.
  - Result: passed; PostgreSQL concurrency tests skipped as intended; one existing Starlette deprecation warning.
- Command: from `backend`, `python -m compileall app tests\postgres_concurrency`.
  - Result: passed.
- Command: `alembic -c alembic.ini heads`.
  - Result: `0010 (head)`.
- Command: `alembic -c alembic.ini history`.
  - Result: linear history from `0001` through `0010`.
- Command: `alembic -c alembic.ini current` against disposable PostgreSQL.
  - Result: `0010 (head)`.
- Command: `python -m pip_audit --cache-dir C:\tmp\pip-audit-cache -r requirements.txt -r requirements-dev.txt`.
  - Result: `No known vulnerabilities found`.
- Command: disposable PostgreSQL `psql` invariant query.
  - Result: `active_reservations=0`, `pending_applications=0`, `alembic_version=0010`.
- Command: `docker-compose -p parkingappconcurrencyphase1 down -v`.
  - Result: disposable container, network, and `parkingappconcurrencyphase1_postgres_data` volume removed.
- Command: `docker-compose -p parkingappconcurrencyphase1 ps`.
  - Result: no remaining disposable services.

### Known Limitations

- Phase 1 does not cover cancellation, reassignment, admin manual override, or replacement override concurrency.
- Phase 1 does not include a general load-test harness, moderate load profile, stress profile, or connection-pool tuning.
- The normal backend test suite intentionally skips PostgreSQL concurrency tests unless `POSTGRES_CONCURRENCY_DATABASE_URL` is provided.

### Completion Classification

Status: READY.

Reason: deterministic PostgreSQL assignment/application concurrency tests pass against a disposable PostgreSQL database, critical invariants hold, the application/assignment race was fixed with the smallest row-locking change, regression checks passed, Alembic remains at `0010`, dependency audit passed, and the disposable database/volume were removed after verification.

### Next Suggested Task

Phase 2 PostgreSQL concurrency validation for cancellation, reassignment, admin manual override, and replacement override flows against a disposable PostgreSQL environment. Keep the scope to deterministic race-condition tests and minimal fixes; do not add a general load harness yet.

## Task 60 - PostgreSQL Concurrency Validation Phase 2

### Task Name

Deterministic PostgreSQL concurrency tests for cancellation, reassignment, admin manual override, and replacement override flows.

### Files Changed

- `backend/app/services/parking_reservation_cancellation.py`
- `backend/app/services/admin_reservation_override.py`
- `backend/tests/postgres_concurrency/test_cancellation_reassignment_override_concurrency.py`
- `resources/docs/postgres_concurrency_load_validation.md`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added Phase 2 PostgreSQL-only concurrency tests for cancellation, reassignment, manual override, and replacement override races.
- Reused the Phase 1 disposable PostgreSQL guardrails:
  - `POSTGRES_CONCURRENCY_DATABASE_URL` is required,
  - the URL must point to PostgreSQL,
  - the database name must be disposable/test-oriented,
  - model tables are truncated before and after tests,
  - each concurrent actor uses a separate SQLAlchemy session,
  - coordination uses barriers/events and bounded worker timeouts.
- Covered these Phase 2 race scenarios:
  - two admin cancellations for the same reservation,
  - employee cancellation racing admin cancellation,
  - cancellation started before replacement override,
  - cancellation followed by reassignment,
  - two reassignments for the same cancelled availability,
  - reassignment racing direct assignment,
  - reassignment racing manual override,
  - two manual overrides for the same availability,
  - manual override racing direct assignment,
  - two application-id replacements for the same original reservation,
  - two applicant-id replacements for the same original reservation,
  - repeated identical applicant-id replacement,
  - application-id and applicant-id replacement for the same original reservation,
  - replacement override racing cancellation.
- Updated the PostgreSQL concurrency validation documentation with Phase 2 results and next-phase guidance.

### Defects Found and Fixes

- Cancellation versus replacement race:
  - Expected behavior: a cancellation that started before a replacement must not cancel the replacement winner after waiting for the availability row lock.
  - Actual behavior found by the new deterministic test: the cancellation could read the original reservation, wait, then operate on the replacement winner after the replacement committed.
  - Fix: `ParkingReservationCancellationService` now records a scalar reservation identity snapshot before lock contention and raises controlled `ParkingReservationCancellationIntegrityError` when the active reservation identity changes before cancellation proceeds.
- Concurrent replacement override race:
  - Expected behavior: concurrent replacements targeting the same original reservation should not silently use last-write-wins behavior.
  - Actual behavior found by the new deterministic tests: replacement workers could both snapshot the same original reservation before lock contention, then the second worker could replace the first worker's result.
  - Fix: `AdminReservationOverrideService.replace_existing_reservation` now records the original active reservation identity before lock contention and raises controlled `AdminReservationOverrideIntegrityError` when the active reservation changed before replacement proceeds.
- No Alembic migration was required because these are service-layer transaction and stale-state guards.

### Review Notes

- The new guards use scalar snapshots instead of ORM object references because SQLAlchemy can refresh the same ORM instance during row-lock queries.
- The cancellation guard is intentionally scoped to active-reservation identity changes while cancellation is waiting on locks; normal already-cancelled and missing-reservation paths keep their existing controlled errors.
- The replacement guard checks reservation id, application id, reserved user id, and status before proceeding.
- Row-lock ordering stays consistent with the existing service design: availability row first, then reservation/application state changes.
- Repository behavior and schema constraints were not broadened.
- No secrets were added. Expanded `docker-compose config` output was not copied into documentation because it can include local `.env` values.

### Tests Added or Updated

- Added `backend/tests/postgres_concurrency/test_cancellation_reassignment_override_concurrency.py`.
- Added 14 Phase 2 PostgreSQL concurrency tests.
- Updated `resources/docs/postgres_concurrency_load_validation.md` with Phase 2 verification details.

### Exact Verification Commands and Results

- Command: `docker-compose config`.
  - Result: passed. Docker emitted a local client-config access warning, but Compose rendered valid configuration. Expanded output was not copied because it can contain local `.env` values.
- Command: `docker-compose -p parkingappconcurrencyphase2 up -d db` with disposable values `POSTGRES_DB=parking_app_concurrency`, `POSTGRES_PORT=55432`.
  - Result: disposable PostgreSQL container started and reached healthy state.
- Command: backend Alembic `upgrade head` with `DATABASE_URL=postgresql+psycopg://parking_app:parking_app@localhost:55432/parking_app_concurrency`.
  - Result: migrations applied through `0010`.
- Command: from `backend`, `pytest tests/postgres_concurrency/test_cancellation_reassignment_override_concurrency.py -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` pointing at the disposable PostgreSQL database.
  - First result: failed on stale cancellation/replacement and concurrent replacement races. Fixed with scalar stale-state guards.
  - Final result: `14 passed`.
- Command: from `backend`, `pytest tests/postgres_concurrency -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` pointing at the disposable PostgreSQL database.
  - Result: `21 passed`.
- Command: from `backend`, `pytest tests/test_parking_reservation_cancellation_service.py tests/test_parking_reservation_cancellations_api.py tests/test_parking_reassignment_service.py tests/test_parking_reassignment_api.py tests/test_admin_reservation_override_service.py tests/test_admin_reservation_overrides_api.py tests/test_admin_reservation_replacement_service.py tests/test_admin_reservation_replacements_api.py tests/test_parking_application_service.py tests/test_parking_applications_api.py tests/test_parking_reservation_assignment_service.py tests/test_parking_assignment_scheduler.py -q`.
  - Result: passed with one existing Starlette deprecation warning.
- Command: from `backend`, `pytest -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` unset.
  - Result: passed; PostgreSQL concurrency tests skipped as intended; one existing Starlette deprecation warning.
- Command: from `backend`, `python -m compileall app tests\postgres_concurrency`.
  - Result: passed.
- Command: `alembic -c alembic.ini heads`.
  - Result: `0010 (head)`.
- Command: `alembic -c alembic.ini history`.
  - Result: linear history from `0001` through `0010`.
- Command: `alembic -c alembic.ini current` against disposable PostgreSQL.
  - Result: `0010 (head)`.
- Command: `python -m pip_audit --cache-dir C:\tmp\pip-audit-cache -r requirements.txt -r requirements-dev.txt`.
  - Result: `No known vulnerabilities found`.
- Command: disposable PostgreSQL invariant query for active reservations, pending applications, and Alembic version.
  - Result: `active_reservations=0`, `pending_applications=0`, `alembic_version=0010`.
- Command: inspected disposable PostgreSQL logs for deadlocks, serialization failures, lock timeouts, uncontrolled integrity errors, and secret leakage.
  - Result: no matching error conditions found.
- Command: `docker-compose -p parkingappconcurrencyphase2 down -v`.
  - Result: disposable container, network, and `parkingappconcurrencyphase2_postgres_data` volume removed.
- Command: `docker-compose -p parkingappconcurrencyphase2 ps`.
  - Result: no remaining disposable services.
- Command: from `backend`, `pytest tests/postgres_concurrency -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` unset.
  - Result: `21 skipped`.

### Known Limitations

- Phase 2 validates correctness under deterministic races, not throughput capacity.
- It does not include a general API load harness, moderate load profile, stress profile, or connection-pool tuning.
- It does not include frontend browser QA.
- The normal backend suite intentionally skips PostgreSQL concurrency tests unless `POSTGRES_CONCURRENCY_DATABASE_URL` is provided.

### Completion Classification

Status: READY.

Reason: Phase 2 deterministic PostgreSQL concurrency tests pass against a disposable PostgreSQL database, the two discovered stale-state races were fixed with scoped service-layer guards, existing focused regression tests and the full backend suite pass, Alembic remains at `0010`, dependency audit passed, disposable PostgreSQL logs did not show lock/deadlock failures, and the disposable database/volume were removed after verification.

### Next Suggested Task

Phase 3 production hardening: add bounded API-level load and smoke validation for the completed MVP flows. Focus on authenticated admin/parking-owner/employee API paths, moderate request profiles, connection-pool and timeout behavior, Prometheus latency/error reporting, and a final release-hardening report. Do not add new product features.

## Task 61 - PostgreSQL Concurrency and Load Validation Phase 3A

### Task Name

Bounded API smoke load-validation harness, connection-pool configuration, sanitized reporting, and disposable Docker validation.

### Files Changed

- `backend/app/core/config.py`
- `backend/app/db/session.py`
- `backend/app/load_validation/__init__.py`
- `backend/app/load_validation/smoke.py`
- `backend/app/commands/run_load_validation.py`
- `backend/tests/test_database_pool_config.py`
- `backend/tests/test_load_validation_harness.py`
- `backend/tests/test_infrastructure_files.py`
- `.env.example`
- `backend/.env.example`
- `docker-compose.yml`
- `docker-compose.production.yml`
- `README.md`
- `resources/docs/postgres_concurrency_load_validation.md`
- `resources/docs/monitoring_observability.md`
- `resources/docs/load_validation_phase3a_smoke_report.json`
- `resources/docs/load_validation_phase3a_smoke_report.md`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added bounded SQLAlchemy pool settings:
  - `DB_POOL_SIZE`, default `5`.
  - `DB_MAX_OVERFLOW`, default `5`.
  - `DB_POOL_TIMEOUT_SECONDS`, default `30`.
  - `DB_POOL_RECYCLE_SECONDS`, default `1800`.
  - `DB_POOL_PRE_PING`, default `true`.
- Wired pool settings into backend and scheduler services in local and production Compose files.
- Added `engine_kwargs_from_settings` so PostgreSQL engines receive queue pool settings while SQLite-compatible test URLs skip queue-pool-only arguments.
- Added `python -m app.commands.run_load_validation --profile smoke`.
- Added the Phase 3A smoke profile only. The moderate profile was intentionally not implemented.
- Added safe CLI/configuration behavior:
  - local targets allowed by default,
  - non-local targets refused unless explicitly overridden,
  - credential-bearing target URLs rejected,
  - concurrency bounded to `5-10`,
  - iterations bounded to `1-3`,
  - request timeout bounded to `0.1-30` seconds,
  - admin credentials read from environment variable names and not printed or reported.
- Added disposable API data setup and direct tracked-ID cleanup.
- Added sanitized JSON and Markdown report generation.
- Added final invariant checks for:
  - active reservation uniqueness,
  - selected application uniqueness,
  - duplicate application absence,
  - availability/reservation state agreement,
  - cancellation/replacement history coherence,
  - expected success audit records,
  - orphan reference absence.
- Saved sanitized Phase 3A smoke reports:
  - `resources/docs/load_validation_phase3a_smoke_report.json`,
  - `resources/docs/load_validation_phase3a_smoke_report.md`.

### Review Notes

- The harness uses the standard library HTTP client so it runs in the existing backend Docker image without adding runtime dependencies.
- The command is import-safe and keeps secret values out of CLI flags by default.
- Reports use operation names and aggregate counts rather than raw request bodies, bearer tokens, emails, or credential-bearing URLs.
- Expected duplicate-application `409` responses are classified as `expected_domain_conflict`, not invariant failures.
- Cleanup deletes only IDs tracked by the run and is enabled by default.
- The disposable smoke report was scanned for the disposable admin password, username, email, bearer tokens, access tokens, full database URLs, and credential strings; no matches were found.
- The moderate profile, Prometheus metric deltas, pool saturation validation, and capacity claims remain out of scope for Phase 3A.

### Defects Found and Fixes

- Disposable seed email using a `.invalid` domain was rejected by `EmailStr` validation.
- The harness initially used the same `.invalid` disposable domain for generated users.
- Fix: generated disposable smoke users now use unique `example.com` addresses. Report sanitization still excludes emails from generated reports.

### Tests Added or Updated

- Added `backend/tests/test_database_pool_config.py`.
- Added `backend/tests/test_load_validation_harness.py`.
- Updated `backend/tests/test_infrastructure_files.py`.

New/updated tests cover:

- valid pool values,
- zero/negative invalid pool values,
- excessive timeout/recycle/pool bounds,
- boolean parsing,
- engine kwargs receiving configured PostgreSQL pool values,
- SQLite-compatible local/test engine kwargs,
- CLI credential environment variable wiring,
- production/non-local target refusal,
- explicit non-local override,
- safe maximums,
- deterministic run slug generation,
- percentile calculations,
- result classification,
- report sanitization,
- cleanup behavior,
- partial report on controlled failure,
- interruption reporting.

### Exact Verification Commands and Results

- Command: from `backend`, `pytest tests/test_database_pool_config.py tests/test_infrastructure_files.py tests/test_load_validation_harness.py -q`.
  - Result: `64 passed`.
- Command: from `backend`, `python -m compileall app tests\test_database_pool_config.py tests\test_load_validation_harness.py`.
  - Result: passed.
- Command: from `backend`, `python -m app.commands.run_load_validation --help`.
  - Result: passed and displayed smoke-only CLI options.
- Command: `docker-compose -p parkingapploadphase3a config --quiet` with disposable environment variables.
  - Result: passed with no expanded config output copied.
- Command: `docker-compose -p parkingapploadphase3a build backend`.
  - Result: passed.
- Command: `docker-compose -p parkingapploadphase3a up -d db backend` with `POSTGRES_DB=parking_app_load_validation`, `POSTGRES_PORT=55433`, and `BACKEND_PORT=18000`.
  - Result: disposable PostgreSQL reached healthy state and backend started.
- Command: `docker-compose -p parkingapploadphase3a exec -T backend alembic -c alembic.ini upgrade head`.
  - Result: migrations applied through `0010`.
- Command: `docker-compose -p parkingapploadphase3a exec -T backend alembic -c alembic.ini current`.
  - Result: `0010 (head)`.
- Command: disposable local admin seed using `SEED_ADMIN_*` environment variables.
  - First result: failed because the `.invalid` email domain was rejected.
  - Final result: passed with an `example.com` disposable email. Disposable password value was not recorded.
- Command: `docker-compose -p parkingapploadphase3a exec -T backend python -m app.commands.run_load_validation --profile smoke --target-base-url http://localhost:8000 --seed 20260622 --concurrency 5 --iterations 1 --request-timeout 10 --report-path /tmp/phase3a-smoke.json --markdown-report-path /tmp/phase3a-smoke.md`.
  - Result: `load validation READY`.
  - Requests: `54` total, `53` success, `1` expected domain conflict.
  - Latency: p50 `47.023 ms`, p95 `254.122 ms`, p99 `333.824 ms`.
  - Invariants: all passed.
  - Cleanup: succeeded.
- Command: copied sanitized reports from the disposable backend container to `resources/docs/load_validation_phase3a_smoke_report.json` and `resources/docs/load_validation_phase3a_smoke_report.md`.
  - Result: passed.
- Command: scanned saved reports for disposable credentials, emails, bearer tokens, access tokens, password/secret strings, and full PostgreSQL URLs.
  - Result: no matches.
- Command: disposable PostgreSQL post-cleanup query.
  - Result: `disposable_users=0`, `disposable_availabilities=0`, `active_reservations=0`, `alembic_version=0010`.
- Command: scanned disposable backend/database logs for deadlocks, serialization failures, lock timeouts, tracebacks, internal server errors, bearer tokens, access tokens, credential URLs, and the disposable admin password.
  - Result: no matches.
- Command: created disposable database `parking_app_concurrency` in the temporary PostgreSQL container and ran Alembic `upgrade head`.
  - Result: migrations applied through `0010`.
- Command: from `backend`, `pytest tests/postgres_concurrency -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` pointing at the disposable concurrency database.
  - Result: `21 passed`.
- Command: from `backend`, `pytest -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` unset.
  - Result: passed; PostgreSQL concurrency tests skipped as intended; one existing Starlette deprecation warning.
- Command: from `backend`, `python -m compileall app tests`.
  - Result: passed.
- Command: `alembic -c alembic.ini heads`.
  - Result: `0010 (head)`.
- Command: `alembic -c alembic.ini history`.
  - Result: linear history from `0001` through `0010`.
- Command: `alembic -c alembic.ini current` against disposable PostgreSQL.
  - Result: `0010 (head)`.
- Command: `python -m pip_audit --cache-dir C:\tmp\pip-audit-cache -r requirements.txt -r requirements-dev.txt`.
  - Result: `No known vulnerabilities found`.
- Command: `docker-compose -p parkingapploadphase3a down -v`.
  - Result: disposable containers, network, and `parkingapploadphase3a_postgres_data` volume removed.
- Command: `docker-compose -p parkingapploadphase3a ps`.
  - Result: no remaining disposable services.

### Known Limitations

- Phase 3A is a bounded smoke load validation, not a throughput benchmark.
- The moderate profile was not implemented.
- Stress testing, distributed load testing, and production SLA/SLO claims remain out of scope.
- Prometheus before/after metric deltas were not collected in Phase 3A.
- Frontend behavior was not changed or revalidated in this task.

### Completion Classification

Status: READY.

Reason: the smoke harness works against a disposable Docker/PostgreSQL backend, report generation is sanitized, cleanup succeeded, invariants held, connection-pool configuration is bounded and tested, Phase 1/2 PostgreSQL concurrency tests still pass, full backend tests pass, Alembic remains at `0010`, dependency audit passed, logs/reports did not show secret leakage or uncontrolled errors, and the disposable project/volume were removed.

### Next Suggested Task

Phase 3B production hardening: implement the moderate API profile, Prometheus metric deltas, connection-pool saturation/recovery validation, and final local load report. Do not implement stress testing or make production capacity claims.

## Task 62 - PostgreSQL Concurrency and Load Validation Phase 3B

### Task Name

Moderate API load-validation profile, Prometheus metric deltas, PostgreSQL diagnostics, bounded pool saturation/recovery diagnostic, and final local Phase 3B reports.

### Files Changed

- `backend/app/load_validation/smoke.py`
- `backend/app/commands/run_load_validation.py`
- `backend/tests/test_load_validation_harness.py`
- `README.md`
- `resources/docs/postgres_concurrency_load_validation.md`
- `resources/docs/monitoring_observability.md`
- `resources/docs/load_validation_phase3b_smoke_baseline_report.json`
- `resources/docs/load_validation_phase3b_smoke_baseline_report.md`
- `resources/docs/load_validation_phase3b_moderate_report.json`
- `resources/docs/load_validation_phase3b_moderate_report.md`
- `resources/docs/load_validation_phase3b_pool_report.json`
- `resources/docs/load_validation_phase3b_pool_report.md`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added `python -m app.commands.run_load_validation --profile moderate`.
- Added explicit `--confirm-moderate` gating for the moderate profile.
- Added moderate safety bounds:
  - concurrency between `25` and `50`,
  - iterations between `1` and `2`,
  - global timeout between `30` and `600` seconds.
- Added CLI options for:
  - `--global-timeout`,
  - `--scheduler-metrics-url`,
  - `--skip-metrics`,
  - `--skip-pool-diagnostic`.
- Added Prometheus text parsing and metric snapshot/delta collection for backend and scheduler metrics.
- Added PostgreSQL aggregate diagnostic sampling during the moderate run.
- Added a deliberate bounded connection-pool saturation/recovery diagnostic using a separate one-connection SQLAlchemy engine.
- Extended report schema with:
  - `report_schema_version`,
  - latency min, max, average, p50, p95, p99,
  - Prometheus baseline/final/delta sections,
  - PostgreSQL diagnostic samples and summary,
  - pool diagnostic result,
  - global timeout.
- Saved final sanitized Phase 3B smoke, moderate, and pool diagnostic reports.

### Review Notes

- The moderate profile keeps the same security boundaries as Phase 3A: local targets only by default, no credential-bearing target URLs, admin credentials read from environment variables, and no request bodies, bearer tokens, emails, or secrets in reports.
- The report contains metric names, labels, and numeric values from Prometheus text output; labels are expected to be route templates/status classes/results, not PII.
- The pool diagnostic intentionally expects one bounded timeout and then verifies recovery by checking that the diagnostic pool has no checked-out connections after recovery.
- `401` and `403` classifications are split into authentication and authorization failures for clearer diagnostics.
- The moderate profile is local validation only. It is not a stress test and does not make production capacity, SLA, or SLO claims.
- Final review found one CLI naming inconsistency: shared `--concurrency` and `--iterations` help text still referred only to smoke. The wording now says the bounds are profile-specific.
- Frontend code was not changed in this task.

### Defects Found and Fixes

- A first moderate dry run exposed a harness setup defect: the workload attempted to create a replacement candidate application through the public application endpoint after the availability was already assigned.
- The product behavior was correct: the public endpoint rejected the application because the availability was no longer open.
- Fix: the harness now creates that one disposable pending replacement candidate application directly as setup data, then exercises the real admin replacement endpoint.
- After this fix, the clean final smoke and moderate runs completed with `READY`.

### Tests Added or Updated

- Updated `backend/tests/test_load_validation_harness.py`.

New/updated tests cover:

- moderate profile confirmation requirement,
- moderate concurrency/iteration safety bounds,
- CLI mapping for the confirmed moderate profile,
- Prometheus text parsing and delta calculation,
- missing metric handling,
- latency min/max/average reporting,
- pool diagnostic behavior for non-PostgreSQL URLs,
- sanitized PostgreSQL diagnostic failure handling,
- separate authentication and authorization failure classifications.

### Exact Verification Commands and Results

- Command: from `backend`, bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest tests\test_load_validation_harness.py tests\test_database_pool_config.py tests\test_infrastructure_files.py -q`.
  - Result: passed.
- Command: from `backend`, bundled Python `-m compileall app tests\test_load_validation_harness.py`.
  - Result: passed.
- Command: from `backend`, bundled Python with `PYTHONPATH=.test-deps;.`, `-m app.commands.run_load_validation --help`.
  - Result: passed and displayed `smoke,moderate`, `--confirm-moderate`, `--global-timeout`, `--scheduler-metrics-url`, `--skip-metrics`, and `--skip-pool-diagnostic`.
- Command: disposable project `parkingapploadphase3b`, `docker-compose -p parkingapploadphase3b build backend`.
  - Result: passed.
- Command: disposable project `parkingapploadphase3b`, `docker-compose -p parkingapploadphase3b down -v`.
  - Result: removed the previous disposable containers and volumes to remove stale log artifacts from an earlier out-of-order scheduler startup and two corrected manual SQL probes.
- Command: `docker-compose -p parkingapploadphase3b config --quiet`.
  - Result: passed.
- Command: `docker-compose -p parkingapploadphase3b up -d db backend`.
  - Result: disposable PostgreSQL and backend started.
- Command: `docker-compose -p parkingapploadphase3b exec -T backend alembic -c alembic.ini upgrade head`.
  - Result: migrations applied through `0010`.
- Command: `docker-compose -p parkingapploadphase3b exec -T backend alembic -c alembic.ini current`.
  - Result: `0010 (head)`.
- Command: disposable local admin seed using `SEED_ADMIN_*` environment variables.
  - Result: admin created; disposable password value was not recorded.
- Command: `docker-compose -p parkingapploadphase3b --profile monitoring up -d assignment-scheduler prometheus`.
  - Result: scheduler and Prometheus started after migrations.
- Command: `docker-compose -p parkingapploadphase3b exec -T backend python -m app.commands.run_load_validation --profile smoke --target-base-url http://localhost:8000 --seed 2026062205 --concurrency 5 --iterations 1 --request-timeout 10 --report-path /tmp/phase3b-smoke-baseline-final.json --markdown-report-path /tmp/phase3b-smoke-baseline-final.md`.
  - Result: `load validation READY`.
- Command: `docker-compose -p parkingapploadphase3b exec -T backend python -m app.commands.run_load_validation --profile moderate --confirm-moderate --target-base-url http://localhost:8000 --scheduler-metrics-url http://assignment-scheduler:19101/metrics --seed 2026062206 --concurrency 25 --iterations 1 --request-timeout 15 --global-timeout 240 --report-path /tmp/phase3b-moderate-final.json --markdown-report-path /tmp/phase3b-moderate-final.md`.
  - Result: `load validation READY`.
  - Requests: `284` total, `283` success, `1` expected domain conflict.
  - Duration: `22.236` seconds.
  - Throughput: `12.772` requests/second.
  - Latency: p95 `358.833 ms`, p99 `470.241 ms`.
  - Invariants: all passed.
  - Cleanup: succeeded.
  - PostgreSQL samples: `46`.
  - PostgreSQL deadlock delta: `0`.
  - Pool diagnostic: expected timeout observed, recovery succeeded, checked-out connections after recovery `0`.
- Command: copied clean-run reports from the backend container to `resources/docs/load_validation_phase3b_*`.
  - Result: passed.
- Command: scanned saved Phase 3B reports for disposable credential strings, emails, bearer tokens, access tokens, password/secret strings, and full PostgreSQL URLs.
  - Result: no matches.
- Command: disposable PostgreSQL post-cleanup query.
  - Result: `disposable_users=0`, `disposable_teams=0`, `disposable_spots=0`, `disposable_availabilities=0`, `disposable_applications=0`, `active_reservations=0`, `alembic_version=0010`.
- Command: scanned clean-run backend, database, scheduler, and Prometheus logs for tracebacks, errors, deadlocks, serialization failures, lock timeouts, internal server errors, bearer tokens, access tokens, credential URLs, and the disposable admin password.
  - Result: no matches.
- Command: created disposable database `parking_app_concurrency_phase3b` and ran Alembic `upgrade head`.
  - Result: migrations applied through `0010`.
- Command: from `backend`, bundled Python with `PYTHONPATH=.test-deps;.` and `POSTGRES_CONCURRENCY_DATABASE_URL` pointing at the disposable PostgreSQL database, `-m pytest tests\postgres_concurrency -q`.
  - Result: `21 passed`.
- Command: from `backend`, bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest -q` with `POSTGRES_CONCURRENCY_DATABASE_URL` unset.
  - Result: passed; PostgreSQL concurrency tests skipped as intended; one existing Starlette deprecation warning.
- Command: from `backend`, bundled Python `-m compileall app tests`.
  - Result: passed.
- Command: `docker-compose -p parkingapploadphase3b exec -T backend alembic -c alembic.ini heads`.
  - Result: `0010 (head)`.
- Command: `docker-compose -p parkingapploadphase3b exec -T backend alembic -c alembic.ini history`.
  - Result: linear history from `0001` through `0010`.
- Command: `docker-compose -p parkingapploadphase3b exec -T backend alembic -c alembic.ini current`.
  - Result: `0010 (head)`.
- Command: from `backend`, bundled Python `-m pip_audit --cache-dir C:\tmp\pip-audit-cache -r requirements.txt -r requirements-dev.txt`.
  - Result: `No known vulnerabilities found`.

### Known Limitations

- Phase 3B is a bounded local moderate validation profile, not a stress test.
- It does not perform distributed load testing.
- It does not establish production PostgreSQL capacity, SLA, or SLO values.
- It does not tune pool sizes based on production traffic.
- Frontend browser behavior was not revalidated because no frontend code changed.

### Cleanup

- Command: `docker-compose -p parkingapploadphase3b down -v`.
  - Result: disposable backend, database, scheduler, Prometheus containers, network, PostgreSQL volume, and Prometheus volume removed.
- Command: `docker-compose -p parkingapploadphase3b ps`.
  - Result: no remaining disposable services.

### Completion Classification

Status: READY.

Reason: the moderate profile completed against disposable Docker/PostgreSQL with metrics and diagnostics enabled, invariant checks passed, cleanup succeeded, reports were sanitized, logs did not show uncontrolled errors or secret leakage, PostgreSQL concurrency tests passed, full backend tests passed, Alembic remains at `0010`, and dependency audit found no known vulnerabilities.

### Next Suggested Task

Production hardening follow-up: add frontend end-to-end smoke coverage for the completed MVP flows, using the existing Dockerized stack and disposable local users. Do not add new product features while doing this.

## Task 63 - Frontend End-To-End MVP Smoke Coverage

### Task Name

Playwright browser smoke setup for completed admin, owner, employee, assignment, replacement, authorization, and responsive MVP flows.

### Files Changed

- `.gitignore`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/vite.config.js`
- `frontend/playwright.config.js`
- `frontend/e2e/helpers/auth.js`
- `frontend/e2e/helpers/assignment.js`
- `frontend/e2e/mvp-smoke.spec.js`
- `scripts/run_e2e_smoke.ps1`
- `README.md`
- `resources/docs/manual_qa_checklist.md`
- `resources/docs/developer_handoff.md`
- `resources/docs/implementation_log.md`

### E2E Framework And Architecture

- Added `@playwright/test` `1.55.1`; no previous E2E framework existed.
- Pinned Chromium runtime installed by Playwright: Chromium `140.0.7339.186`, Playwright build `1193`.
- Added one serial Chromium desktop suite with six logical tests and deterministic 60-second test, 30-second navigation, and 10-second action/expect timeouts.
- Added screenshots only on failure, traces and video retained on failure, and gitignored artifact directories.
- Added reusable login, logout, auth-clearing, and Docker assignment-command helpers.
- Selectors use accessible labels, roles, headings, named regions, and run-specific record text. No production `data-testid` attributes were needed.
- Vitest now excludes `e2e/**`, preventing browser specs from being collected as unit tests.

### Covered Flows

- Admin login and UI creation of a disposable team, parking owner, employee A, employee B, and owner-assigned parking spot.
- Owner login, future availability publication, and own availability verification.
- Employee A and B login and application submission; employee A application-history verification.
- Real `docker-compose exec -T backend python -m app.commands.assign_due_availabilities --limit 100` execution and employee A reservation verification.
- Admin replacement page checks for blank reason, unknown applicant, and current reserved user.
- Successful Applicant ID replacement to employee B with success feedback and reservation summary assertions.
- Employee A no longer seeing the active reservation, employee B seeing it, and admin reservation history, assignment audit log, and reports verification.
- Unauthenticated protected-route redirect, employee admin-route blocking, role-specific navigation, desktop execution, and mobile `390x844` overflow/form/error visibility.

### Test-Data Strategy

- `scripts/run_e2e_smoke.ps1` creates a dedicated `parkingappe2e` Compose project by default.
- The runner uses isolated ports `55435`, `18003`, and `18083`, database `parking_app_e2e`, generated in-memory database/JWT/user credentials, and run-specific `E2E` record names.
- It builds the backend/frontend, starts PostgreSQL/backend/frontend, applies migrations, verifies current revision, seeds a disposable admin, waits for HTTP readiness, and runs Playwright.
- `SAME_TEAM_PRIORITY_WINDOW_HOURS=0` makes the test availability immediately eligible for the explicit one-shot assignment command.
- The runner removes containers and the dedicated PostgreSQL volume in `finally`; `-KeepStack` is available only for local diagnosis.
- No credentials, tokens, browser artifacts, or screenshots were committed.

### Review Notes

- No backend endpoint, model, migration, business rule, or frontend screen was added.
- The suite uses the existing admin UI for primary setup and the actual role-specific UI for all critical flows.
- Assignment command failures are bounded to 60 seconds, sanitized to the final 1,500 output characters, and fail the test unless exactly one assignment succeeds with zero failures.
- Native Docker, migration, seed, and build command exit codes are checked explicitly by the lifecycle runner.
- Serial execution is intentional; retries are disabled because replaying a stateful create test against the same database would make results nondeterministic.
- Failure traces can contain generated disposable credentials, so artifact directories are ignored and documentation warns against committing them.

### Defects Found And Fixes

- Initial frontend regression run found that Vitest discovered `frontend/e2e/mvp-smoke.spec.js` and failed on missing E2E environment variables.
- Fixed by adding `e2e/**` to the Vitest exclude list; the full unit suite then passed.
- Review found that the first lifecycle runner version relied on later HTTP failures when a native Docker command returned non-zero.
- Fixed by adding explicit native-command exit-code checks for Compose config/build/up, Alembic upgrade/current, and admin seed.
- Review also removed CI retries from the serial stateful suite and made the protected-route assertion independent of URL slash-encoding style.

### Exact Verification Commands And Results

- Command: from `frontend`, `npm.cmd install --save-dev @playwright/test@1.55.1`.
  - Result: package and lockfile updated; audit reported `0` vulnerabilities.
- Command: from `frontend`, `npx.cmd playwright install chromium`.
  - Result: Chromium `140.0.7339.186` build `1193`, headless shell, FFmpeg, and Winldd installed successfully.
- Command: from `frontend`, Playwright Chromium launch against a local `data:` page.
  - Result: passed with title `runtime-ok`; the previous Windows browser sandbox startup issue did not recur.
- Command: from `frontend`, `npx.cmd playwright test e2e/mvp-smoke.spec.js --list` with placeholder discovery-only environment values.
  - Result: six Chromium desktop tests discovered.
- Command: from `frontend`, `npm.cmd test`.
  - Initial result: failed because Vitest collected the E2E spec.
  - Final result after the exclude fix: `17` files and `43` tests passed.
- Command: from `frontend`, `npm.cmd run build`.
  - Result: passed; `127` modules transformed.
- Command: from `frontend`, `npm.cmd audit`.
  - Result: `0` vulnerabilities.
- Backend regression suite was not rerun because no backend source, dependency, schema, migration, or infrastructure behavior was changed.
- Command: Node syntax checks for Playwright config, smoke spec, and helpers.
  - Result: passed.
- Command: PowerShell parser check for `scripts/run_e2e_smoke.ps1`.
  - Result: passed.
- Command: `docker-compose config --quiet`.
  - Result: configuration valid; Docker CLI emitted a sandbox-only warning that its user-level config file was inaccessible.
- Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m alembic -c alembic.ini heads`.
  - Result: `0010 (head)`.
- Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m alembic -c alembic.ini history`.
  - Result: linear history from `0001` through `0010`.
- Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_e2e_smoke.ps1`.
  - Initial sandbox result: blocked before stack startup because the execution account `codexsandboxoffline` received `Access is denied` opening Docker Desktop named pipe `//./pipe/docker_engine`.
  - Final interactive Windows result: passed from an account with Docker Desktop access.
  - Disposable Compose project: `parkingappe2e`.
  - Docker result: backend and frontend images built; the disposable network and PostgreSQL volume were created; PostgreSQL became healthy; backend and frontend started.
  - Alembic result: migrations applied from the initial revision through `0010 (head)`.
  - Playwright result: `6 passed` using Chromium, one worker, in `13.2 seconds`.
  - Cleanup result: frontend, backend, and PostgreSQL containers, the disposable network, and the disposable PostgreSQL volume were removed.
  - The normal development volume `parkingapp_postgres_data` remained present and was not used or removed.
- Command: HTTP probes for existing `http://localhost:8000/health` and `http://localhost:8080/`.
  - Historical sandbox result: no pre-existing stack was listening; the later interactive run used the isolated disposable stack as designed.

### Final Browser Flow Results

The real Chromium browser passed all six serial MVP tests:

1. Admin created the disposable team, users, and owned parking spot through the UI.
2. The parking owner published future availability and verified it in My availabilities.
3. Employees applied and Employee A received the scheduled assignment.
4. Admin validation cases passed and Applicant ID replacement succeeded.
5. The replacement was reflected for both employees and on admin operational pages.
6. Protected routes, role navigation, and the `390x844` mobile Admin Overrides layout remained usable.

No application-code or test-code changes were required after the successful run.

### Final Security And Cleanup Review

- Disposable database, JWT, admin, and user credentials were generated in process memory and restored/cleared by the lifecycle script; no credential file was generated.
- No disposable password, JWT, bearer token, or access-token value was copied into this log or other documentation.
- A focused scan found no generated password pattern or JWT in the successful-run artifacts.
- Successful execution produced no screenshots, traces, or videos because those are configured only for failures.
- The remaining successful-run artifacts are the expected HTML report (`frontend/playwright-report/index.html`, `478212` bytes) and last-run marker (`frontend/test-results/.last-run.json`, `45` bytes). These are small runtime artifacts, not source files.
- `frontend/playwright-report/`, `frontend/test-results/`, and `frontend/blob-report/` are covered by `.gitignore` and must not be committed.
- The HTML report is generated with `open: "never"`; README documents its location, trace inspection, and removal after diagnosis.
- `docker-compose -p parkingappe2e ps -a`, filtered container, network, and volume checks returned no disposable resources.
- The normal development PostgreSQL volume `parkingapp_postgres_data` remained present and untouched.

### Browser And Runtime Status

- Playwright package installation, browser installation, Chromium launch, JavaScript discovery, and artifact configuration are verified.
- Full browser interaction is verified against the disposable Docker/PostgreSQL stack from an interactive Windows account with Docker Desktop access.
- All six tests passed through the real UI; HTTP route checks were not used as a substitute for browser execution.
- The previous Docker named-pipe limitation applied only to the Codex sandbox account and is no longer a Task 63 blocker.

### Known Limitations

- The suite intentionally certifies only Chromium for the critical smoke flow; broad cross-browser certification and visual regression remain out of scope.
- Playwright HTML reports are generated for successful runs but remain local and gitignored.

### Completion Classification

Status: READY.

Reason: Chromium executed all six critical MVP browser flows against the disposable Docker/PostgreSQL stack; Alembic reached `0010 (head)`; admin, owner, employee, assignment, Applicant ID replacement, authorization, and mobile responsive checks passed; generated credentials were not persisted or documented; and all disposable containers, network, and PostgreSQL storage were removed without touching the normal development volume. No unresolved E2E blockers remain.

### Final Documentation Verification

- `git diff` could not run because the workspace `.git` directory contains no repository metadata; Git reports that the workspace is not a repository.
- The complete Task 63 section was reviewed directly after editing.
- A strict documentation scan found no generated disposable password, JWT, bearer-token value, or access-token value.
- The Task 63 section contains one final classification, `Status: READY`; the prior provisional status no longer remains in the classification field.
- The documented lifecycle command and referenced script, Playwright configuration, smoke spec, HTML report, and last-run marker paths were verified.
- README, the manual QA checklist, and the developer handoff already contained accurate E2E execution and artifact guidance, so they required no final edits.

### Next Suggested Task

Production-hardening follow-up: add a bounded CI pipeline for backend tests, frontend unit/build/audit checks, Alembic validation, and the Playwright smoke suite against disposable services. Keep credentials in CI secret storage, preserve failure artifacts with controlled retention, and do not add product features as part of the pipeline task.

## Task 64 - Bounded GitHub Actions CI Pipeline

### Task Name

Repository-ready CI for backend quality, PostgreSQL concurrency, frontend quality, Compose/image validation, and Playwright Chromium smoke verification.

### Files Changed

- `.github/workflows/ci.yml`
- `.github/workflows/e2e.yml`
- `backend/requirements-dev.txt`
- `backend/tests/test_ci_configuration.py`
- `frontend/playwright.config.js`
- `frontend/e2e/helpers/assignment.js`
- `scripts/run_e2e_smoke.sh`
- `README.md`
- `resources/docs/ci_pipeline.md`
- `resources/docs/developer_handoff.md`
- `resources/docs/implementation_log.md`

### Workflow Architecture

- Added GitHub Actions because no existing repository CI platform was present.
- `.github/workflows/ci.yml` contains four independent jobs:
  - `backend-quality`, timeout 15 minutes;
  - `postgres-concurrency`, timeout 20 minutes;
  - `frontend-quality`, timeout 15 minutes;
  - `compose-validation`, timeout 25 minutes.
- `.github/workflows/e2e.yml` contains `e2e-smoke` with a 30-minute timeout.
- Both workflows trigger for pull requests, pushes to `main`, and manual dispatch.
- Both use read-only `contents` permission and workflow/branch/PR concurrency groups.
- Superseded branch and pull-request runs are cancelled; manually dispatched investigations are not cancelled automatically.
- No deployment, publishing, scheduled E2E execution, cloud infrastructure, or product behavior was added.

### Job Responsibilities

- Backend quality uses Python 3.12 with pip caching, installs `requirements-dev.txt`, runs the full normal backend suite, compiles application/tests, checks for exactly one Alembic head, prints history, and runs `pip-audit`.
- PostgreSQL concurrency uses a PostgreSQL 16 Alpine service, migrates an isolated concurrency database, compares dynamic current/head revisions, runs every `postgres_concurrency` test, and parses JUnit XML to require tests greater than zero and skips equal to zero.
- Frontend quality uses Node 22 with npm caching and runs `npm ci`, tests, production build, and all three required npm audit forms.
- Compose validation checks local, scheduler, monitoring, production, and production scheduler configurations, then builds backend/frontend and the distinct production TLS proxy image.
- E2E installs only Chromium, runs the six existing serial MVP browser tests through a disposable Linux Docker lifecycle, verifies cleanup, and uploads bounded failure artifacts.

### Dependency And Test Groundwork

- Added `pip-audit` to the authoritative backend development requirements.
- Added explicit `PyYAML` because infrastructure tests import it and a clean CI environment must not rely on an undeclared transitive/local package.
- Added CI structure tests for triggers, permissions, timeouts, required commands, action references, synthetic credential policy, Linux lifecycle behavior, and artifact ignores.
- Updated the assignment helper to support both standalone `docker-compose` and Docker Compose plugin invocation without shell parsing.
- Local Windows E2E behavior remains unchanged.

### Secret And Artifact Strategy

- No production secret, secret file, or GitHub repository secret is required.
- The PostgreSQL service uses clearly synthetic CI-only values.
- The Linux E2E runner generates database, JWT, admin, and user credentials in process memory using OpenSSL and never enables shell tracing.
- Failure service logs are bounded and redact every generated credential before console output or artifact storage.
- CI disables Playwright traces and videos because they can capture passwords, request headers, or tokens.
- Failure uploads are limited to JUnit XML, screenshots, HTML report, last-run metadata, Docker status, and redacted service logs.
- Artifact retention is five days, uploads run only after failure, and upload errors cannot hide the originating failure.
- Database dumps, environment files, and production secret files are never uploaded.

### E2E Lifecycle

- Added `scripts/run_e2e_smoke.sh` for Ubuntu/GitHub runners while retaining the verified PowerShell runner.
- The Linux lifecycle validates its Compose project name, generates disposable values, builds backend/frontend, starts PostgreSQL/backend/frontend, applies Alembic head, seeds the disposable admin, waits for HTTP readiness, and runs `npm run e2e:smoke`.
- A trap captures sanitized diagnostics only after failure and always executes `docker compose down -v --remove-orphans`.
- The workflow separately checks for remaining containers, volumes, and networks.
- The Node assignment helper uses `docker compose exec` on Linux and `docker-compose.exe` on Windows.

### Review Notes

- Official actions are limited to `actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`, and `actions/upload-artifact@v4`.
- No obscure action is used for application execution or secret handling.
- Dependency audits fail normally; no finding is suppressed and no force-fix command exists.
- PostgreSQL test execution is not validated through a hardcoded test count. JUnit assertions require a positive count and zero skips.
- Alembic comparison derives the current head dynamically instead of duplicating `0010` as workflow logic.
- Image validation avoids rebuilding the backend for the production Compose file because it uses the same Dockerfile; the distinct TLS proxy is built separately.
- The existing Starlette/httpx deprecation warning remains visible and does not suppress failures.
- The deprecated `glob` package warning appeared during the proxy image `npm ci`, but all npm audit forms reported zero vulnerabilities.

### Tests Added

- Added `backend/tests/test_ci_configuration.py`.
- Focused tests cover YAML structure, bounded triggers, job timeouts, permissions, job names, command coverage, official action references, synthetic-only values, Linux cleanup/redaction behavior, and CI-safe Playwright artifact configuration.

### Exact Local Verification Results

- Command: bundled Python with `PYTHONPATH=.test-deps;.`, `-m pytest tests\test_ci_configuration.py tests\test_infrastructure_files.py -q`.
  - Result: `31 passed`.
- Command: bundled Python with PostgreSQL concurrency URL unset, `-m pytest`.
  - Result: `722 passed`, `21 skipped` as intended, and one visible existing Starlette/httpx deprecation warning.
- Command: bundled Python, `-m compileall -q app tests`.
  - Result: passed.
- Command: Alembic `heads` and `history`.
  - Result: one head, `0010 (head)`, with linear history from `0001` through `0010`.
- Command: bundled Python, `-m pip_audit --cache-dir C:\tmp\pip-audit-ci-cache -r requirements-dev.txt`.
  - Result: `No known vulnerabilities found`.
- Command: `npm.cmd test`.
  - Result: `43 passed` across `17` files.
- Command: `npm.cmd run build`.
  - Result: passed; `127` modules transformed.
- Commands: `npm.cmd audit`, `npm.cmd audit --omit=dev`, and `npm.cmd audit --omit=optional`.
  - Result: all three reported `0 vulnerabilities`.
- Command: disposable PostgreSQL project `parkingappcivalidation`, Alembic `upgrade head` and `current`.
  - Result: fresh PostgreSQL 16 database migrated through `0010 (head)`.
- Command: bundled Python, `-m pytest -m postgres_concurrency tests\postgres_concurrency --junitxml=postgres-concurrency-local.xml`.
  - Result: `21 passed`; parsed JUnit values were `tests=21`, `skipped=0`, `failures=0`, `errors=0`.
- Cleanup command: `docker-compose -p parkingappcivalidation down -v --remove-orphans`.
  - Result: disposable container, network, and volume removed; the local JUnit verification artifact was also removed.
- Commands: standalone `docker-compose` configuration checks for local, scheduler, monitoring, and production files.
  - Result: passed.
- Commands: Docker Compose plugin configuration checks for local, scheduler, monitoring, production, and production scheduler forms.
  - Result: passed with Docker Compose `v2.40.2-desktop.1` using the interactive Docker context.
- Command: `docker run --rm ... rhysd/actionlint:1.7.7` against both workflows.
  - Result: passed; image digest was `sha256:887a259a5a534f3c4f36cb02dca341673c6089431057242cdc931e9f133147e9`.
- Command: `docker run --rm ... bash:5.2 bash -n /repo/scripts/run_e2e_smoke.sh`.
  - Result: Bash syntax passed.
- Command: `docker-compose -f docker-compose.production.yml build proxy`.
  - Result: production TLS proxy image built successfully; frontend `npm ci` and production build passed in the image.
- Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_e2e_smoke.ps1`.
  - Result: backend/frontend images built, PostgreSQL became healthy, Alembic reached `0010 (head)`, and all six Chromium tests passed with one worker in `14.4 seconds`.
  - Covered admin setup, owner availability, employee applications/assignment, Applicant ID replacement, cross-role post-replacement checks, protected routes, navigation, and mobile layout.
  - Cleanup removed all `parkingappe2e` containers, network, and PostgreSQL volume.
- Final filtered Docker checks for `parkingappe2e` and `parkingappcivalidation`.
  - Result: no remaining containers, networks, or volumes.
- Strict scans of workflows, Linux runner, documentation, and successful Playwright artifacts for private keys, GitHub tokens, JWTs, bearer tokens, and generated password patterns.
  - Result: no matches.

### Verification Issues Resolved

- The first elevated all-in-one PostgreSQL validation could not load the workspace Alembic module entry point. Docker control and host Python execution were separated; the normal workspace Python then migrated PostgreSQL correctly.
- The first local JUnit output path under `C:\tmp` was owned by a different execution context. The rerun used the same workspace-relative output location as CI and all 21 tests passed.
- A local assertion command had PowerShell quoting issues after the tests had already passed. The generated JUnit XML was parsed directly and confirmed zero skips/failures/errors.
- Sandboxed `docker compose` could not load the user-scoped plugin. Exact plugin commands were rerun successfully through the interactive Docker context.
- These were local execution-context issues; no workflow or application defect remained.

### Hosted CI Verification Status

- GitHub Actions was not executed because this workspace has no Git repository metadata or configured remote.
- The workflows were not committed, pushed, or published.
- YAML was parsed by project tests and both workflows passed `actionlint`.
- Individual job commands and the Windows E2E parity lifecycle are locally verified.

### Completion Classification

Status: PARTIALLY_VERIFIED.

Reason: workflow configuration, command coverage, timeouts, permissions, synthetic credential handling, failure artifacts, YAML/action semantics, local quality gates, PostgreSQL concurrency, Docker images, Compose profiles, and all six browser flows are verified. A definitive `READY` classification requires the workflows to be committed to the real GitHub repository and complete at least one hosted Actions run; this metadata-free workspace cannot perform that step.

### Known Limitations

- The Linux lifecycle has passed Bash syntax and shares the verified Docker/browser contract, but has not run on a GitHub-hosted Ubuntu runner yet.
- CI currently targets Chromium only; broad cross-browser certification remains out of scope.
- GitHub-hosted timing and cache behavior are not known until the first real run.

### Next Suggested Task

Commit the CI files into the actual GitHub repository and run both workflows through `workflow_dispatch` or a pull request. Fix only hosted-run environment defects, record job runtimes and artifact behavior, and promote Task 64 to `READY` after a clean hosted run. Do not add deployment or release publishing in that verification task.

## Task 65 - End-User Guide Groundwork And Screenshot Workflow

### Task Name

Dedicated ParkingApp end-user guide for employees, parking owners, and administrators, plus an opt-in disposable screenshot generation workflow.

### Files Changed

- `resources/docs/user_guide.md`
- `resources/docs/images/user_guide/.gitkeep`
- `frontend/e2e/user-guide-screenshots.spec.js`
- `scripts/generate_user_guide_screenshots.ps1`
- `frontend/package.json`
- `README.md`
- `resources/docs/developer_handoff.md`
- `resources/docs/implementation_log.md`

### What Was Implemented

- Added a role-based user guide covering:
  - application purpose and access,
  - general navigation,
  - employee workflows,
  - parking owner workflows,
  - administrator workflows,
  - status reference,
  - common messages,
  - troubleshooting,
  - quick-reference workflows.
- Added `resources/docs/images/user_guide/` for guide screenshots.
- Added an opt-in Playwright screenshot spec that captures the real browser UI with disposable local data.
- Added `scripts/generate_user_guide_screenshots.ps1` to create an isolated Docker Compose project, migrate PostgreSQL, seed a QA admin, run the screenshot spec, replace only `resources/docs/images/user_guide/*.png` after success, and clean up the disposable stack by default.
- Added `npm run e2e:user-guide` for the screenshot spec.
- Linked the user guide and screenshot generator from README and the developer handoff.

### Review Notes

- No product feature, backend endpoint, database model, migration, or business rule was changed.
- Guide wording is user-facing and avoids API, database, Docker, Alembic, and JWT details except for the local screenshot generation command in developer-facing README/handoff content.
- Navigation labels, statuses, and common messages were cross-checked against the Vue source and shared API error handling.
- The guide does not claim unsupported browser behavior: admin reservation cancellation is not described as a browser action; owner availability review is described as availability-focused rather than reservation-detail-focused.
- The screenshot workflow uses `example.com` disposable QA users and generated passwords/JWT/database values kept in process environment only.
- The screenshot script requires `-ConfirmOverwrite` before replacing existing PNGs.
- The script removes the disposable Compose project and temporary screenshot directory in `finally` unless `-KeepStack` is explicitly used.

### Tests Or Checks Added

- Added `frontend/e2e/user-guide-screenshots.spec.js` with four serial Playwright tests:
  - login and admin setup screenshots,
  - owner availability screenshots,
  - employee application/reservation screenshots,
  - admin operational and mobile override screenshots.
- Added the npm script `e2e:user-guide`.

### Exact Verification Commands And Results

- Command: `node -e "JSON.parse(require('fs').readFileSync('frontend/package.json','utf8')); console.log('package ok')"; node --check frontend/e2e/user-guide-screenshots.spec.js`
  - Result: package JSON parsed successfully; screenshot spec JavaScript syntax passed.
- Command: `powershell.exe -NoProfile -Command '$null = [scriptblock]::Create((Get-Content -Raw ''scripts/generate_user_guide_screenshots.ps1'')); ''script parses'''`
  - Result: `script parses`.
- Command: Markdown image link check against `resources/docs/user_guide.md`.
  - Result: 16 image links found; all 16 PNG files are still missing because live screenshot generation was blocked before the Playwright run could create them.
- Command: focused secret-pattern scan of the user guide, screenshot script, screenshot spec, README, and developer handoff.
  - Result: no persisted generated secret values were found. Expected script variable names and generated-password templates appeared only inside the local generator source.
- Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_user_guide_screenshots.ps1 -ConfirmOverwrite`
  - Result: blocked by the Codex Windows execution context before Compose could start. Docker returned `open //./pipe/dockerDesktopLinuxEngine: Access is denied` and `open C:\Users\nikola.milosevic\.docker\buildx\.lock: Access is denied`.
  - Cleanup path still executed and attempted `docker-compose -p parkingappuserguide down -v --remove-orphans`, but Docker pipe access was also denied for cleanup. Since Compose startup did not proceed, no disposable containers or volumes were created by this run from this context.
- Command: `npm.cmd test` from `frontend`.
  - Result: blocked by sandboxed Windows process restrictions while Vite loaded config: `Error: spawn EPERM`.
- Command: `npm.cmd run build` from `frontend`.
  - Result: blocked by the same Vite `spawn EPERM` issue.
- Command: `npm.cmd audit --omit=optional` from `frontend`.
  - Result: `found 0 vulnerabilities`.
- Command: bundled Python `-m compileall -q backend/app backend/tests`.
  - Result: passed.
- Command: `USER_GUIDE_SCREENSHOTS=true` plus dummy required E2E credentials, then `npm.cmd run e2e:user-guide -- --list`.
  - Result: Playwright listed 4 tests in `frontend/e2e/user-guide-screenshots.spec.js` successfully without launching the browser flow.

### Known Limitations

- Status: PARTIALLY_VERIFIED.
- Real screenshots were not generated in this Codex execution context because Docker Desktop pipe access is denied to the sandboxed process.
- The guide currently references the expected screenshot file names, but the PNG files must still be generated from a normal PowerShell session with Docker Desktop access.
- Frontend unit tests and production build were attempted but blocked by local sandbox `spawn EPERM`; previous frontend checks remain documented in earlier tasks, and this task did not change application runtime code.
- Browser visual/privacy review of the guide screenshots remains pending until the PNGs are generated.

### Next Suggested Task

Run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_user_guide_screenshots.ps1 -ConfirmOverwrite` from a normal user PowerShell session with Docker Desktop access, visually review every PNG in `resources/docs/images/user_guide/`, rerun the Markdown image link check and frontend `npm.cmd test` / `npm.cmd run build` outside the restricted Codex sandbox if needed, then update Task 65 to `READY` if the screenshots are correct and contain only disposable QA data.

### Task 65 Docker Retry Note

- Retry command after Docker Desktop was reported running: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_user_guide_screenshots.ps1 -ConfirmOverwrite`.
- Result: still blocked from this Codex execution context before Compose startup. Docker returned `open //./pipe/dockerDesktopLinuxEngine: Access is denied` and `open C:\Users\nikola.milosevic\.docker\buildx\.lock: Access is denied`.
- Conclusion: Docker Desktop availability is no longer the blocker; the remaining blocker is this sandboxed Codex process lacking permission to access the Docker Desktop named pipe and user Docker buildx lock. No screenshot PNGs were generated, and no disposable Compose resources were started.

### Task 65 Final Docker Screenshot Verification

- Selector fix applied after the first live run: the Admin Applications screenshot assertion now anchors to the leading application ID in the row instead of matching any `#1` value in the row. This avoids confusing application ID with availability ID or user ID.
- Rerun command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_user_guide_screenshots.ps1 -ConfirmOverwrite`.
- Result: succeeded.
  - Backend and frontend images built for disposable Compose project `parkingappuserguide`.
  - Fresh PostgreSQL volume was created and migrated through `0010 (head)`.
  - Local QA admin was seeded with disposable `qa_admin` / `qa.admin@example.com` data.
  - Playwright user-guide screenshot run passed: `4 passed` in Chromium.
  - Generated 16 PNG files in `resources/docs/images/user_guide/`.
  - Compose cleanup removed the disposable frontend, backend, and PostgreSQL containers, the disposable network, and the disposable PostgreSQL volume.
- Screenshot file verification:
  - `admin-applications.png`
  - `admin-audit-logs.png`
  - `admin-overrides.png`
  - `admin-parking-spots.png`
  - `admin-reports.png`
  - `admin-reservations.png`
  - `admin-teams.png`
  - `admin-users.png`
  - `employee-applications.png`
  - `employee-dashboard.png`
  - `employee-open-availabilities.png`
  - `employee-reservations.png`
  - `login-page.png`
  - `mobile-admin-overrides.png`
  - `owner-availability-list.png`
  - `owner-publish-availability.png`
- Markdown image-link verification: 16 links checked, all target PNG files exist.
- Docker cleanup verification commands: `docker-compose -p parkingappuserguide ps -a`, `docker volume ls --filter name=parkingappuserguide`, and `docker network ls --filter name=parkingappuserguide`.
  - Result: no remaining containers, volumes, or networks for the disposable project.
- Screenshot metadata/nonblank verification: all 16 PNGs are nonblank; desktop screenshots are `1280px` wide, mobile override screenshot is `390px` wide, and file sizes are nonzero.
- Privacy review:
  - Screenshot data is generated from disposable QA usernames and `example.com` emails.
  - The guide and generated screenshot source were scanned for bearer tokens, JWT-like values, personal company email domains, and generated password values.
  - Result: no persisted generated secrets or real personal/company email values were found. Expected password/JWT variable names and templates appear only in the local generator script source.
- Artifact cleanup:
  - Removed `frontend/test-results` and `frontend/playwright-report` after the failed and successful screenshot runs to avoid retaining traces/videos/reports that may contain generated credentials.
  - Removed temporary contact-sheet review files.

### Task 65 Final Regression Results

- Command: `npm.cmd test` from `frontend` outside the restricted sandbox.
  - Result: `17 passed` test files, `43 passed` tests.
- Command: `npm.cmd run build` from `frontend` outside the restricted sandbox.
  - Result: Vite production build passed; `127` modules transformed.
- Command: `npm.cmd audit --omit=optional`.
  - Result: `found 0 vulnerabilities`.
- Command: bundled Python `-m compileall -q backend/app backend/tests`.
  - Result: passed.

### Task 65 Final Completion Classification

Status: READY.

Reason: the end-user guide exists, all required guide sections are present, real screenshots were generated through the disposable Docker/PostgreSQL/Playwright browser flow, Markdown image links resolve, Docker cleanup was verified, frontend tests/build/audit passed, backend compile passed, generated artifacts with possible credentials were removed, and screenshots use disposable QA data only. The Codex image viewer could not display local PNG files due a Windows sandbox wrapper limitation, so visual review relied on Playwright page assertions, controlled screenshot generation, nonblank image metadata, and source-data privacy checks rather than direct in-agent image display.

### Task 65 Next Suggested Task

Perform a quick human visual pass over `resources/docs/user_guide.md` and the 16 screenshots in `resources/docs/images/user_guide/` from the normal desktop file viewer, then commit the user-guide documentation and screenshot workflow. After that, continue with hosted CI verification from Task 64 if the project has been connected to the real GitHub repository.

## Task 66 - Frontend UI/UX Improvement Pass

### Task Name

Focused frontend-only UI/UX polish for navigation, help, page guidance, empty states, tables, admin workflows, and responsive layout.

### Files Changed

- `frontend/src/layouts/AppLayout.vue`
- `frontend/src/layouts/AppLayout.spec.js`
- `frontend/src/router/index.js`
- `frontend/src/router/index.spec.js`
- `frontend/src/views/HelpView.vue`
- `frontend/src/views/HelpView.spec.js`
- `frontend/src/views/DashboardView.vue`
- `frontend/src/views/admin/AdminDashboardView.vue`
- `frontend/src/views/AvailableSpotsView.vue`
- `frontend/src/views/AvailableSpotsView.spec.js`
- `frontend/src/views/MyApplicationsView.vue`
- `frontend/src/views/MyReservationsView.vue`
- `frontend/src/views/MyAvailabilitiesView.vue`
- `frontend/src/views/admin/AdminOverridesView.vue`
- `frontend/src/views/admin/AdminOverridesView.spec.js`
- `frontend/src/components/admin/AdminOverrideForm.vue`
- `frontend/src/components/admin/AdminOverrideForm.spec.js`
- `frontend/src/components/admin/AdminPageHeader.vue`
- `frontend/src/components/common/EmptyState.vue`
- `frontend/src/views/admin/AdminAssignmentAuditLogsView.vue`
- `frontend/src/views/admin/AdminParkingApplicationsView.vue`
- `frontend/src/views/admin/AdminParkingSpotsView.vue`
- `frontend/src/views/admin/AdminReportsView.vue`
- `frontend/src/views/admin/AdminReservationsView.vue`
- `frontend/src/views/admin/AdminTeamsView.vue`
- `frontend/src/views/admin/AdminUsersView.vue`
- `frontend/src/styles/main.css`
- `resources/docs/images/user_guide/*.png`
- `resources/docs/user_guide.md`
- `resources/docs/manual_qa_checklist.md`
- `resources/docs/developer_handoff.md`
- `resources/docs/implementation_log.md`

### UX Improvements Implemented

- Added desktop sidebar collapse/expand in `AppLayout`.
  - The toggle is a keyboard-focusable button with accessible labels.
  - Collapsed state is stored in `localStorage` key `parking-app-sidebar-collapsed`.
  - Mobile layout ignores the collapsed desktop state and keeps full navigation labels visible.
- Added an authenticated `/help` page with non-technical quick-start guidance for:
  - Employee,
  - Parking owner,
  - Administrator.
- Added Help entry points in the sidebar and top bar.
- Improved dashboard guidance:
  - employee/owner dashboard cards now describe the next action more clearly;
  - admin dashboard cards are grouped by People and teams, Parking spots, Operations, and Reports and audit.
- Added short contextual page descriptions and help blocks for:
  - Available spots,
  - My availabilities,
  - Admin Overrides,
  - Admin Audit Logs,
  - Admin Reports,
  - Admin application/reservation/spot/team/user screens.
- Improved empty states with clearer messages and suggested next actions.
- Improved table readability by renaming ID-heavy headings and adding mobile `data-label` attributes on key employee/owner workflow tables.
- Added responsive table-card behavior for small screens and preserved the existing desktop table layout.
- Polished spacing, card borders, focus states, help panels, empty states, and admin override field guidance.

### Navigation Behavior

- Expanded sidebar remains the default.
- Desktop users can collapse the sidebar to compact letter marks and expand it again.
- The active route remains visible in both expanded and collapsed modes.
- `Sign out`, current user display, and Help remain accessible.
- On tablet/mobile widths, the sidebar behaves as a top navigation area with full labels to avoid hidden controls and horizontal overflow.

### Help/User-Guide Additions

- Added `frontend/src/views/HelpView.vue` and `/help` route.
- Help content is static, role-specific, and avoids API/Docker/Alembic/internal file-path terminology.
- Updated `resources/docs/user_guide.md` to mention Help and the collapsible desktop sidebar.
- Regenerated the user-guide screenshots after the UI changes.

### Tests Added Or Updated

- Updated `AppLayout.spec.js` for:
  - admin-only navigation,
  - authenticated Help entry visibility,
  - sidebar collapse behavior,
  - sidebar collapsed-state persistence.
- Added `HelpView.spec.js` for role-specific Help content.
- Updated router tests for authenticated `/help` access.
- Updated `AvailableSpotsView.spec.js` for the improved empty state.
- Updated `AdminOverrideForm.spec.js` for clearer override ID and audit-reason guidance.
- Existing admin, employee, owner, services, and E2E selectors remain stable.

### Exact Verification Commands And Results

- Command: JavaScript syntax checks with `node --check` for changed test/router files.
  - Result: passed.
- Command: `npm.cmd test -- src/views/AvailableSpotsView.spec.js` after fixing the actual empty-state template.
  - Result: `1 passed` test file, `2 passed` tests.
- Command: `npm.cmd test` from `frontend`.
  - Result: `18 passed` test files, `50 passed` tests.
- Command: `npm.cmd run build` from `frontend`.
  - Result: Vite production build passed; `128` modules transformed.
- Command: `npm.cmd audit --omit=optional` from `frontend`.
  - Result: `found 0 vulnerabilities`.
- Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_e2e_smoke.ps1`.
  - Result: disposable Docker/PostgreSQL/Chromium MVP smoke passed; `6 passed` tests.
  - Covered admin setup, owner availability publishing, employee application/assignment, Applicant ID replacement, post-replacement checks, protected routes, role navigation, and the `390x844` mobile Admin Overrides layout.
  - Alembic reached `0010 (head)` in the disposable PostgreSQL database.
  - Cleanup removed the disposable `parkingappe2e` containers, network, and PostgreSQL volume.
- Command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_user_guide_screenshots.ps1 -ConfirmOverwrite`.
  - Result: screenshot generation passed; Playwright user-guide run reported `4 passed` and generated 16 PNG screenshots.
  - Alembic reached `0010 (head)` in the disposable screenshot PostgreSQL database.
  - Cleanup removed the disposable `parkingappuserguide` containers, network, and PostgreSQL volume.
- Commands: Docker cleanup checks for `parkingappe2e` and `parkingappuserguide` containers, volumes, and networks.
  - Result: no remaining disposable resources.
- Command: Markdown image-link check for `resources/docs/user_guide.md`.
  - Result: 16 image links checked and all target PNG files exist.
- Command: PNG metadata/nonblank check for `resources/docs/images/user_guide/*.png`.
  - Result: all 16 screenshots are nonblank with nonzero file sizes.
- Command: focused secret-pattern scan across user guide docs, generated screenshot directory, frontend source, manual QA checklist, and developer handoff.
  - Result: no bearer tokens, JWT-like values, real personal/company email domains, or generated password values were found.
- Cleanup: removed `frontend/test-results` and `frontend/playwright-report` after successful browser runs to avoid retaining traces/reports that may contain generated credentials.

### Responsive And Accessibility Review

- Responsive behavior was verified through the existing Chromium E2E mobile Admin Overrides check at `390x844`.
- User-guide screenshot regeneration exercised desktop pages and the mobile Admin Overrides screenshot.
- Sidebar toggle has accessible labels and visible focus styles.
- Help route and Help links are keyboard-reachable via normal links/buttons.
- Status text remains visible; status badges are not color-only.
- Mobile table cards use `data-label` attributes on key workflow tables so IDs and statuses remain understandable.

### Code Review Notes

- No backend files, database migrations, SQLAlchemy models, API services, assignment logic, authorization rules, or business behavior were changed.
- No new dependency or UI framework was introduced.
- The sidebar state stores only a boolean UI preference in localStorage; no credentials or tokens were added beyond existing auth storage behavior.
- E2E selectors based on accessible labels, routes, headings, and regions remained compatible; the full six-test smoke passed without spec changes.
- Admin Overrides replacement-by-Applicant-ID behavior remains intact.
- The generated screenshots use disposable QA data only.
- The workspace has no Git metadata, so `git status --short` could not provide a changed-file list.

### Completion Classification

Status: READY.

Reason: frontend-only UI/UX improvements were implemented, focused tests were added, full frontend tests/build/audit passed, Docker-backed Playwright MVP smoke passed, user-guide screenshots were regenerated and verified, disposable Docker cleanup passed, no backend behavior changed, and no critical UX/accessibility regression remains from this pass.

### Next Suggested Task

Perform a short human visual review of the updated app and regenerated user-guide screenshots from the normal desktop browser/file viewer. If accepted, commit the frontend UX pass. After that, continue with hosted CI verification from Task 64 if the project has been connected to the real GitHub repository.

## Task 66 Follow-up - Sidebar and Navigation Visual Regression Fix

### Task Name

Targeted frontend-only repair for the Task 66 sidebar/navigation and responsive table visual regressions.

### Root Cause

The original sidebar CSS used the broad selector '.app-shell__nav span' to add padding, pale text, and 'opacity: 0.72'. Task 66 introduced structured badge and label spans inside every navigation link, so the legacy selector also styled those new elements. Its higher selector specificity overrode parts of the new component styles, producing faded labels, washed-out active items, padded placeholder-like badges, and poor compact alignment.

### Files Changed

- 'frontend/src/layouts/AppLayout.vue'
- 'frontend/src/layouts/AppLayout.spec.js'
- 'frontend/src/styles/main.css'
- 'frontend/src/views/AvailableSpotsView.vue'
- 'frontend/src/views/admin/AdminAssignmentAuditLogsView.vue'
- 'frontend/src/views/admin/AdminParkingApplicationsView.vue'
- 'frontend/src/views/admin/AdminParkingSpotsView.vue'
- 'frontend/src/views/admin/AdminReservationsView.vue'
- 'frontend/src/views/admin/AdminTeamsView.vue'
- 'frontend/src/views/admin/AdminUsersView.vue'
- 'frontend/e2e/mvp-smoke.spec.js'
- 'resources/docs/images/user_guide/*.png'
- 'resources/docs/implementation_log.md'

### Visual Fixes Made

- Replaced the accidental broad-span interaction with explicit badge/label overrides at sufficient specificity.
- Set normal navigation links to near-white text on the blue sidebar and active links to white with dark-blue text.
- Added restrained hover, border, shadow, and focus states without changing the blue/white identity.
- Normalized link height, spacing, label wrapping, and badge dimensions.
- Rebalanced the compact sidebar brand/toggle stack and centered every 44px navigation target and 30px badge.
- Preserved complete labels on tablet/mobile and kept Help and Sign out reachable.
- Added compact-mode accessible names while preserving native Vue Router 'aria-current' active-state semantics.
- Added bordered horizontal-scroll table containers on desktop, a useful minimum width for audit decisions, and mobile labels for the requested employee/admin tables.
- Prevented empty pseudo-label columns for table cells that do not declare 'data-label'.
- Regenerated all 16 user-guide screenshots with disposable QA data.

### Tests Added Or Updated

- Expanded 'AppLayout.spec.js' to verify role-based navigation, Help reachability, collapsed state and localStorage persistence, compact accessible names/tooltips, and active route class/'aria-current' in expanded and collapsed states.
- Strengthened the sixth Playwright MVP smoke test to verify expanded normal/active colors, Help visibility, active-route semantics, collapsed state and persistence, compact badge centering within one pixel, and the existing mobile Admin Overrides behavior without page overflow.

### Exact Verification Commands And Results

- 'npm.cmd test -- src/layouts/AppLayout.spec.js src/views/AvailableSpotsView.spec.js'
  - Result: 2 passed files, 7 passed tests.
- 'npm.cmd test'
  - Result: 18 passed files, 51 passed tests.
- 'npm.cmd run build'
  - Result: passed; Vite transformed 128 modules.
- 'npm.cmd audit --omit=optional'
  - Result: found 0 vulnerabilities.
- 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_e2e_smoke.ps1'
  - Result: 6 passed; strengthened desktop expanded/collapsed and 390x844 mobile assertions passed.
  - Disposable PostgreSQL migrated to 0010 (head).
  - Disposable parkingappe2e containers, network, and volume were removed.
- 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_user_guide_screenshots.ps1 -ConfirmOverwrite'
  - Result: 4 passed; regenerated 16 PNG screenshots.
  - Disposable PostgreSQL migrated to 0010 (head).
  - Disposable parkingappuserguide containers, network, and volume were removed.

### Browser And Screenshot Verification

- Desktop expanded sidebar was verified in Chromium through computed foreground/background color checks, active-route semantics, Help visibility, and the normal MVP page flow.
- Desktop collapsed sidebar was verified in Chromium through collapsed-class, persistence, accessible-name, active-state, and badge-centering geometry checks.
- Mobile Admin Overrides was verified at 390x844 with no document-level horizontal overflow and usable validation controls.
- The generated desktop and mobile screenshots completed successfully and are nonzero PNG files.
- The Codex local image viewer remained unavailable because the Windows restricted-token sandbox could not prepare its wrapper. Direct in-agent visual viewing was therefore not claimed; automated Chromium assertions, screenshot generation, and artifact checks were used.

### Code Review Notes

- No backend, database, migration, authorization, or business behavior changed.
- No dependency or UI framework was added.
- Role-based navigation and the Help page remain intact.
- Vue Router continues to expose active links with 'aria-current="page"'.
- Desktop tables intentionally use a contained horizontal scrollbar where all columns cannot fit; mobile tables use labeled cards.
- The first focused test run exposed only an ambiguous test selector between the brand and Dashboard links; the selector was narrowed and all reruns passed.

### Completion Classification

Status: READY.

Reason: sidebar contrast and alignment are repaired, the compact state is intentional and accessible, Help and role navigation remain correct, table containment/mobile labels are improved, all frontend tests/build/audit pass, strengthened Docker-backed browser verification passes, and screenshots were regenerated successfully.

### Next Suggested Task

Perform a short human visual acceptance pass over the regenerated screenshots and the expanded/collapsed sidebar in the normal desktop browser. If accepted, commit the Task 66 UX work and this regression repair. Then continue with hosted CI verification from Task 64 when the project is connected to the real GitHub repository.
## Task 66 Follow-up 2 - Remaining Sidebar Row Alignment Defect

### Task Name

Narrow frontend CSS repair for expanded sidebar badge/label vertical alignment.

### Root Cause

The legacy '.app-shell__nav span' rule still set 'display: block' with greater selector specificity than the newer '.app-shell__nav-icon' rule. Although the previous regression fix corrected color, opacity, and padding, the badge therefore did not retain 'inline-flex'. Its fixed box was aligned by the parent row, but the letter inside used normal block-line baseline rendering and appeared detached from the label.

### Files Changed

- 'frontend/src/styles/main.css'
- 'frontend/e2e/mvp-smoke.spec.js'
- 'resources/docs/images/user_guide/*.png'
- 'resources/docs/implementation_log.md'

### Exact CSS And Layout Fix

- At the scoped '.app-shell__nav .app-shell__nav-icon' specificity:
  - restored 'display: inline-flex';
  - explicitly retained two-axis centering;
  - set 'line-height: 1'.
- Reset badge and label margins to zero.
- Set labels to 'align-self: center' and a controlled 'line-height: 1.25'.
- Kept the existing row flex layout, 44px minimum row height, fixed badge size, expanded padding, active state, collapsed centering, and mobile behavior unchanged.
- No negative margins, transforms, or absolute positioning were introduced for normal row alignment.

### Alignment Verification

The Playwright MVP smoke test now measures Dashboard, Available spots, My availabilities, Admin dashboard, Applications, and Overrides in expanded desktop mode. For every link it verifies:

- badge center Y is within one pixel of nav-row center Y;
- label center Y is within one pixel of nav-row center Y;
- badge and label bounds remain inside the nav-row bounds;
- the nav row has no horizontal or vertical overflow.

The existing compact assertion also verifies badge center X within one pixel of the collapsed link center. The existing 390x844 Admin Overrides check verifies no document-level horizontal overflow and usable controls.

### Exact Verification Commands And Results

- 'npm.cmd test -- src/layouts/AppLayout.spec.js'
  - Result: 1 passed file, 5 passed tests.
- 'npm.cmd test'
  - Result: 18 passed files, 51 passed tests.
- 'npm.cmd run build'
  - Result: passed; Vite transformed 128 modules.
- 'npm.cmd audit --omit=optional'
  - Result: found 0 vulnerabilities.
- 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_e2e_smoke.ps1'
  - Result: 6 passed, including the new expanded row center/bounds/overflow assertions, collapsed centering, and mobile Admin Overrides.
  - Disposable PostgreSQL reached 0010 (head).
  - Disposable parkingappe2e containers, network, and volume were removed.
- 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_user_guide_screenshots.ps1 -ConfirmOverwrite'
  - Result: 4 passed; all 16 user-guide screenshots were regenerated.
  - Disposable PostgreSQL reached 0010 (head).
  - Disposable parkingappuserguide containers, network, and volume were removed.

### Browser And Screenshot Status

- Expanded employee/admin sidebar alignment was directly asserted in Chromium using center-point and containment geometry.
- Active Admin Overrides alignment was included in the same assertions.
- Collapsed admin link X-centering remained within one pixel.
- Mobile Admin Overrides remained usable at 390x844 without page overflow.
- Screenshot generation covered the employee dashboard, Admin Applications, Admin Overrides, other documented desktop workflows, and mobile Admin Overrides.
- The Codex local image viewer remains unavailable because of the Windows restricted-token sandbox wrapper; no claim of direct in-agent image viewing is made. The browser geometry checks specifically address the visual defect that prior color/class assertions missed.

### Code Review Notes

- Scope remained CSS, Playwright layout verification, regenerated screenshots, and this log entry.
- No component markup, routes, Help behavior, role navigation, backend, database, authorization, or business logic changed.
- The higher-specificity reset is localized to structured sidebar badges and labels and does not affect unrelated spans.
- Expanded, active, hover, focus, collapsed, and mobile states share the same flex alignment model.

### Completion Classification

Status: READY.

Reason: expanded badge and label center alignment is now proven within one pixel across representative primary/admin links, active content stays within its pill, collapsed centering and mobile behavior pass, all frontend tests/build/audit pass, Docker-backed Chromium verification passes, and screenshots were regenerated successfully.

### Next Suggested Task

Perform a short human visual acceptance pass in the normal desktop browser. If accepted, commit the Task 66 UX changes and both targeted regression repairs.
## Owner Availability Publishing UX And Safety Improvement

### Task Name

Replace manual parking spot ID entry with owner-scoped active parking spot discovery and selection.

### Files Changed

- backend/app/main.py
- backend/app/routers/parking_spots.py
- backend/tests/test_parking_availabilities_api.py
- frontend/src/components/admin/SelectField.vue
- frontend/src/services/parkingSpotService.js
- frontend/src/services/parkingServices.spec.js
- frontend/src/views/MyAvailabilitiesView.vue
- frontend/src/views/MyAvailabilitiesView.spec.js
- frontend/src/styles/main.css
- frontend/e2e/mvp-smoke.spec.js
- frontend/e2e/user-guide-screenshots.spec.js
- resources/docs/user_guide.md
- resources/docs/manual_qa_checklist.md
- resources/docs/developer_handoff.md
- resources/docs/images/user_guide/*.png
- resources/docs/implementation_log.md

### Selected Endpoint And Design

Added authenticated GET /parking-spots/mine.

- It uses the existing ParkingSpotRepository owner and active filters.
- It returns only active parking spots whose owner_id equals the authenticated user ID.
- Parking owners see their own active spots only.
- Employees and administrators without personally owned active spots receive an empty list.
- The existing ParkingSpotRead schema supplies id, code, location, description, owner_id, active status, and timestamps.
- No schema or migration change was needed.

### Authorization Behavior

The new endpoint derives owner_id exclusively from get_current_user; it does not accept an owner ID from the client. Another user's spots cannot be requested through query parameters.

ParkingAvailabilityService remains the authoritative publish boundary and already enforces:

- parking spot existence;
- active parking spot status;
- parking_spot.owner_id equal to current_user.id;
- valid future time range;
- no blocking overlap.

Focused regression coverage confirms own-active publishing succeeds, publishing another owner's spot returns 403, and publishing an inactive owned spot returns 409. Existing admin parking spot APIs and operational ID visibility are unchanged.

### Frontend UX Behavior

- Zero active owned spots:
  - no raw ID input;
  - contact-admin guidance is shown;
  - the publishing fieldset and submit button are disabled.
- One active owned spot:
  - a read-only code/location summary is shown;
  - the spot ID is selected internally and submitted automatically.
- Multiple active owned spots:
  - an owner-scoped dropdown shows code/location labels;
  - only IDs returned by GET /parking-spots/mine can be selected.
- Owned-spot loading failure:
  - a helpful retry/contact-admin error is shown;
  - publishing is disabled.
- Start, End, Note, date semantics, overlap errors, cancellation behavior, and list updates remain unchanged.
- Successful messages identify the user-facing spot code/location rather than requiring an internal ID.

### Tests Added Or Updated

Backend API coverage includes:

- owner receives only their own active spot;
- another owner's spot is excluded;
- inactive owned spot is excluded;
- employee receives an empty list;
- unauthenticated request returns 401;
- existing own/other/inactive publish authorization tests remain passing;
- existing admin parking spot API tests remain passing in the full suite.

Frontend coverage includes:

- owned spots load on mount;
- one-spot read-only summary and no raw ID control;
- multiple-spot dropdown;
- zero-spot disabled state and guidance;
- API-failure disabled state and guidance;
- start/end validation without raw-ID messaging;
- auto-selected and explicitly selected internal IDs in publish payloads;
- successful publish updates the visible list;
- service endpoint request contract.

### Exact Verification Commands And Results

- Focused backend:
  - bundled Python with temporary declared dependency environment, pytest tests/test_parking_availabilities_api.py -q
  - Result: 32 passed; one Starlette/httpx deprecation warning.
- Full backend:
  - bundled Python with temporary declared dependency environment, pytest --basetemp C:\tmp\parkingapp-pytest-run-availability -q
  - Result: 725 passed, 21 PostgreSQL-concurrency tests skipped by marker; no failures.
  - Collection check: 746 tests collected.
- Backend compile:
  - bundled Python -m compileall -q app tests
  - Result: passed.
- Alembic heads/history:
  - Result: passed; 0010 remains head.
- Focused frontend:
  - npm.cmd test -- src/views/MyAvailabilitiesView.spec.js src/services/parkingServices.spec.js
  - Result: 2 files passed, 12 tests passed.
- Full frontend:
  - npm.cmd test
  - Result: 18 files passed, 58 tests passed.
- Frontend build:
  - npm.cmd run build
  - Result: passed; 129 modules transformed.
- Frontend audit:
  - npm.cmd audit --omit=optional
  - Result: found 0 vulnerabilities.
- Docker/Playwright MVP:
  - powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_e2e_smoke.ps1
  - Final result: 6 passed.
  - Owner test verifies assigned code/location is visible, Parking spot ID input count is zero, and publishing succeeds.
  - Disposable PostgreSQL reached 0010 (head).
  - Disposable parkingappe2e containers, network, and volume were removed.
- User-guide screenshots:
  - powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_user_guide_screenshots.ps1 -ConfirmOverwrite
  - Result: 4 passed; 16 screenshots regenerated.
  - Disposable PostgreSQL reached 0010 (head).
  - Disposable parkingappuserguide containers, network, and volume were removed.

### Environment And Review Notes

- The workspace OneDrive .test-deps cache contained empty pytest and FastAPI package directories. Pip could not replace those folders because OneDrive denied deletion, so the declared requirements-dev.txt environment was installed under C:\tmp for verification. No dependency manifest changed.
- The first full backend attempt had 44 setup errors because pytest's default user temp directory was inaccessible; rerunning with --basetemp under C:\tmp passed.
- An overly broad PowerShell E2E text replacement matched the earlier admin assertion and removed one test block. A subsequent failed recovery command emptied the spec because PowerShell continued after a regex exception. The exact pre-failure source was recovered from the local Playwright trace, the six-test structure was restored, node syntax validation passed, and the complete Docker-backed suite then passed 6/6.
- No credentials from the failed trace were copied into source or documentation. Transient Playwright artifacts are removed during final cleanup.
- No database model, migration, assignment/fairness behavior, admin API behavior, route authorization policy, or unrelated UI was changed.

### Documentation And Screenshots

- Updated the user guide to explain automatic one-spot selection, multiple-spot selection, and contact-admin guidance.
- Updated the owner manual-QA checklist for zero/one/multiple spots and direct API authorization checks.
- Updated developer handoff documentation with GET /parking-spots/mine and the server-side authorization boundary.
- Regenerated owner publishing/list screenshots and all other workflow screenshots using disposable QA data.

### Completion Classification

Status: READY.

Reason: owners no longer type raw parking spot IDs, zero/one/multiple active-spot states are handled, the backend returns only current-user active spots and still rejects other-owner/inactive publishing, focused and full backend/frontend checks pass, Docker/PostgreSQL/Chromium verification passes, and user documentation/screenshots are updated.

### Next Suggested Task

Perform a short human visual acceptance pass of the owner My availabilities page for zero, one, and multiple assigned active spots. If accepted, commit this owner publishing UX and safety improvement.
## Task 64 Follow-up - CI Pipeline Revalidation After Owner Publishing UX

### Task Name

Revalidate and tighten the existing bounded GitHub Actions pipeline after the owner-scoped parking spot publishing change.

### Existing Workflow Assessment

The requested CI architecture was already implemented by Task 64:

- .github/workflows/ci.yml contains backend-quality, postgres-concurrency, frontend-quality, and compose-validation.
- .github/workflows/e2e.yml contains the Ubuntu Chromium e2e-smoke job.
- Pull requests, pushes to main, and manual dispatch are bounded by explicit timeouts and concurrency cancellation.
- Read-only repository permissions, synthetic CI credentials, failure-only artifacts, five-day retention, redacted logs, dependency audits, Compose/profile validation, image builds, and unconditional E2E cleanup were already present.
- scripts/run_e2e_smoke.sh already provides the Linux disposable lifecycle while the PowerShell runner preserves Windows parity.

No competing workflow or duplicate local CI script was added.

### Files Changed

- frontend/e2e/mvp-smoke.spec.js
- backend/tests/test_ci_configuration.py
- resources/docs/ci_pipeline.md
- resources/docs/developer_handoff.md
- resources/docs/implementation_log.md

README.md was reviewed and remains accurate; no command or workflow filename changed, so it did not require an edit. The workflow YAML files were also reviewed and required no configuration change.

### CI Contract Improvements

- The sixth Playwright flow now clicks the authenticated Help link, verifies the /help route, and confirms the How to use ParkingApp heading before returning to Admin Overrides.
- Static CI configuration coverage now requires:
  - exactly six serial MVP browser flows;
  - the owner availability flow;
  - absence of a manual Parking spot ID control;
  - display of the assigned parking spot code/location;
  - Help link navigation and /help URL verification.
- CI documentation now enumerates the six browser flows and explains that these owner-scoped and Help assertions are guarded against silent regression.

### Workflow Architecture And Triggers

- backend-quality: Python 3.12, 15-minute timeout.
- postgres-concurrency: PostgreSQL 16 Alpine, Python 3.12, 20-minute timeout.
- frontend-quality: Node 22, 15-minute timeout.
- compose-validation: local/production profiles and bounded images, 25-minute timeout.
- e2e-smoke: Ubuntu, Chromium only, disposable Compose services, 30-minute timeout.
- Triggers: pull_request, push to main, workflow_dispatch.
- Manual dispatch runs are not auto-cancelled; superseded branch/PR runs are cancelled.
- No scheduled heavy run, deployment, publishing, or cloud-specific infrastructure was added.

### Secret And Artifact Strategy

- Workflows require no production secrets or secret files.
- PostgreSQL concurrency uses clearly synthetic CI-only values.
- Linux E2E generates database, JWT, admin, and user credentials in memory with shell tracing disabled.
- Failure diagnostics redact generated values and limit service log volume.
- CI traces and videos remain disabled because they can contain credentials or tokens.
- Failure screenshots, HTML reports, sanitized status/logs, and JUnit output use five-day retention.
- Artifact upload remains failure-only and continue-on-error so upload issues cannot hide the original failure.

### E2E Lifecycle

The Linux and Windows lifecycle contract builds backend/frontend images, starts disposable PostgreSQL/backend/frontend services, migrates to dynamic Alembic head, seeds a disposable admin, waits for HTTP readiness, executes all six serial browser flows, captures sanitized diagnostics only on failure, and removes containers, networks, and volumes.

The owner flow now verifies the assigned spot is shown and no raw Parking spot ID input exists. The final flow verifies protected routes, role navigation, actual Help navigation, sidebar layout states, and mobile Admin Overrides usability.

### Exact Local Verification Results

- Focused CI/infrastructure tests:
  - Result: 32 passed.
- E2E JavaScript syntax:
  - bundled Node --check frontend/e2e/mvp-smoke.spec.js.
  - Result: passed.
- Workflow YAML/action semantics:
  - pinned rhysd/actionlint:1.7.7 container.
  - Result: both workflows passed.
- Linux lifecycle syntax:
  - pinned bash:5.2 bash -n scripts/run_e2e_smoke.sh.
  - Result: passed.
- Compose configuration:
  - local default, scheduler, monitoring, production default, and production scheduler forms.
  - Result: all passed.
- Full normal backend suite:
  - 747 tests collected.
  - Result: 726 passed, 21 PostgreSQL-marked tests skipped as intended, no failures.
  - One existing Starlette/httpx deprecation warning remained visible.
- Backend compile:
  - Result: passed.
- Alembic heads/history:
  - Result: one head, 0010 (head), linear history.
- Python dependency audit:
  - Result: No known vulnerabilities found.
- PostgreSQL concurrency parity:
  - Fresh disposable PostgreSQL 16 database migrated to 0010 (head).
  - Result: JUnit tests=21, skipped=0, failures=0, errors=0.
  - Disposable parkingappcirevalidation container, network, and volume were removed.
- Frontend unit/component suite:
  - Result: 18 files passed, 58 tests passed.
- Frontend production build:
  - Result: passed; 129 modules transformed.
- npm audit, npm audit --omit=dev, and npm audit --omit=optional:
  - Result: all three reported 0 vulnerabilities.
- Backend/frontend image validation:
  - The E2E lifecycle built both images successfully.
- Production TLS proxy image:
  - Result: built successfully; npm install/build completed with 0 vulnerabilities.
  - The existing deprecated glob warning remained visible.
- Docker/Playwright MVP:
  - Result: 6 passed in Chromium.
  - Included actual Help navigation and owner-scoped no-ID publishing.
  - Fresh PostgreSQL reached 0010 (head).
  - Disposable parkingappe2e containers, network, and volume were removed.

### Hosted CI Status

GitHub Actions was not executed. This workspace still has no .git metadata or configured remote, and git status/remote commands report that it is not a Git repository. No repository was initialized, no workflow was committed, and nothing was pushed or published.

### Completion Classification

Status: PARTIALLY_VERIFIED.

Reason: workflow configuration is complete, actionlint/YAML semantics pass, every represented local quality gate passes, PostgreSQL concurrency executes without skips, Docker images build, and all six browser flows pass. A definitive READY classification requires committing the workflows to the real repository and completing both hosted GitHub Actions workflows.

### Known Limitations

- GitHub-hosted Ubuntu timing, cache behavior, service startup, and artifact upload are not proven until the first hosted run.
- CI intentionally covers Chromium only.
- The local OneDrive backend .test-deps cache remains incomplete, so this revalidation used the authoritative requirements-dev.txt installed under C:\tmp. No dependency manifest was changed.

### Next Suggested Task

Commit the existing CI files and this contract update into the real GitHub repository, then run both workflows through workflow_dispatch or a pull request. Record hosted job runtimes, cache behavior, cleanup, and failure-artifact behavior; fix only hosted-run environment defects and promote Task 64 to READY after a clean hosted run.

## Task 64 Hosted CI Follow-up - Backend Quality and PostgreSQL Concurrency

### Task Name

Fix hosted GitHub Actions failures for backend quality and PostgreSQL concurrency.

### Hosted Failures

- CI run `29171807508` at commit `bd5839784f32a5976d208f3db79aabb36912d6a4` failed.
- Backend quality job `86594111448` failed during `Run backend tests`: 11 backup-script tests attempted to launch Windows-only `powershell.exe` on Ubuntu. The remaining result was 715 passed, 21 skipped, two warnings.
- PostgreSQL concurrency job `86594111430` migrated to `0010` and all 21 concurrency tests passed, but its post-test parser read counters from the `<testsuites>` root instead of the nested `<testsuite>`, producing `(0, 0)`.
- The first local dependency audit after fixing those failures found patched `pytest` advisory `PYSEC-2026-1845` and unpatched transitive `ecdsa` advisory `PYSEC-2026-1325`. Suppression was not added.

### Files Changed

- `.github/workflows/ci.yml`
- `backend/app/core/security.py`
- `backend/requirements.txt`
- `backend/requirements-dev.txt`
- `backend/tests/test_auth_api.py`
- `backend/tests/test_auth_service.py`
- `backend/tests/test_ci_configuration.py`
- `backend/tests/test_postgres_backup_scripts.py`
- `backend/tests/test_security.py`
- `resources/docs/ci_pipeline.md`
- `resources/docs/developer_handoff.md`
- `resources/docs/implementation_log.md`

### Exact Fix

- PowerShell tests resolve `powershell.exe` on Windows or `pwsh` on Linux and reuse that path in native-process helper coverage.
- The concurrency JUnit assertion aggregates `tests`, `skipped`, `failures`, and `errors` across nested suites; it requires at least one test and zero non-passing counters.
- `pytest` now requires a fixed 9.x release.
- `python-jose` was replaced with PyJWT because its mandatory `ecdsa` dependency had no patched version. Token claims, configured algorithm/secret use, invalid-token behavior, and public schemas remain unchanged.
- Synthetic test HMAC keys were lengthened to meet the 32-byte HS256 recommendation.

### Review Notes

- No endpoint, model, migration, frontend, Docker, Compose, or business-rule behavior changed.
- Authentication failure remains reusable and HTTP-independent: invalid or expired tokens return `None`.
- No vulnerability was ignored and no quality gate was weakened.
- Hosted credentials remain synthetic; no secrets were added.

### Tests And Local Verification

- Focused PowerShell/CI tests: 22 passed.
- Focused auth/security/PowerShell/CI tests after PyJWT: 49 passed.
- Full backend suite: passed with 21 PostgreSQL-marked tests skipped as intended and one existing Starlette/httpx deprecation warning.
- Backend compile: passed.
- Alembic heads/history: passed; one head at `0010`.
- `pip-audit -r requirements-dev.txt`: no known vulnerabilities found.
- Pinned actionlint 1.7.7: passed.
- `docker compose config --quiet`: passed.
- Original hosted PostgreSQL execution: 21 passed before the old report parser failed.

### Hosted Rerun

- Pull request: `#1` (`fix/hosted-backend-ci` -> `main`).
- Fix commit: `fa8a2466f17b03cfad3dbd004a809e949172ddca`.
- CI run `29187865561`: success.
- Backend quality job `86637131256`: success.
- PostgreSQL concurrency job `86637131274`: success.
- Frontend quality job `86637131251`: success.
- Compose and image validation job `86637131241`: success.
- E2E Smoke run `29187865548`: success.

### Completion Classification

Status: READY.

### Known Limitations

No unresolved CI limitation remains. Broader production deployment limitations are unchanged and outside this CI-fix scope.

### Next Suggested Task

Review and merge pull request `#1`. No additional CI fix is required.

## MVP Release Finalization - v1.0.0-mvp

### Task Name

Prepare the ParkingApp MVP release finalization.

### Release Version

- Version: 1.0.0-mvp
- Intended annotated tag: v1.0.0-mvp
- Release title: ParkingApp v1.0.0 MVP
- Baseline before release documentation: cf041bea977020c9eef1de22be6485d1ac7c27ef, the merge of PR #1 into main.

### Files Changed

- CHANGELOG.md
- README.md
- frontend/package.json
- frontend/package-lock.json
- resources/docs/release_notes_v1.0.0-mvp.md
- resources/docs/developer_handoff.md
- resources/docs/implementation_log.md

### Release Content

- Added the first MVP changelog entry with Added, Changed, Security, Verification, and Known Limitations sections.
- Added copy-ready release notes and GitHub Release draft text.
- Updated the existing frontend package version reference to 1.0.0-mvp.
- Added concise README and developer-handoff release status.
- Documented local runtime, deployment prerequisites, Alembic head 0010, and post-MVP recommendations.

### CI And GitHub Actions Status

- PR #1 is merged into main.
- Hosted backend quality, PostgreSQL concurrency, frontend quality, Compose/image validation, and Chromium E2E were passing before release finalization.
- CI run 29187865561 and E2E run 29187865548 passed on the functional fix.
- Final documentation follow-up CI run 29188011034 and E2E run 29188011039 also passed.
- Release PR #2 CI run 29188575812 and E2E Smoke run 29188575807 passed for release commit 9d0dcff9f4f4b3014dc497cb0369aa1b56d28538.
- Release finalization changes contain documentation and package-version metadata only; no product behavior, schema, migration, CI, Docker, or deployment behavior changed.

### Tag Preparation Status

- Local and remote v1.0.0-mvp did not exist when checked.
- The tag was not created or pushed because explicit tag-creation permission was not provided.
- After this release commit is merged to a clean, current main, run:
  - git tag -a v1.0.0-mvp -m "ParkingApp v1.0.0 MVP"
  - git push origin v1.0.0-mvp
- Never move or recreate the published tag.

### Verification

- main matched origin/main at cf041bea977020c9eef1de22be6485d1ac7c27ef before editing.
- Working tree was clean before release preparation.
- CI workflow files were present.
- Markdown structure, intended-file staging, secret patterns, generated artifacts, frontend tests, and frontend production build are verified below before commit.

### Known Limitations

- No production deployment or Docker image publication is part of this release.
- Deployment operators must provide real secrets, TLS certificates, scheduler orchestration, backup operations, monitoring/alerting, and environment-specific validation.
- SSO/OIDC, notifications, scheduled reports, and external observability integrations remain post-MVP work.

### Next Suggested Task

Review and merge the release/v1.0.0-mvp branch. From the resulting clean and current main, create and push the annotated v1.0.0-mvp tag, then publish the prepared GitHub Release text without deploying or publishing images.

## Production Deployment Plan And Operational Runbook

### Task Name

Prepare a practical production deployment plan for ParkingApp v1.0.0-mvp.

### Files Changed

- resources/docs/production_deployment_plan.md
- README.md
- resources/docs/developer_handoff.md
- resources/docs/implementation_log.md

### Existing Asset Review

Reviewed production/local Compose, all environment examples, nginx TLS proxy, Prometheus rules/configuration, Grafana provisioning, backup/restore/verification scripts, local TLS helper, release notes, CI documentation, secrets/TLS runbook, observability runbook, developer handoff, implementation log, and README.

### Deployment Decisions And Boundaries

- Target is a maintained Linux VM or on-premises server with Docker Engine and Compose v2.
- Current production Compose directly supports its bundled PostgreSQL db service and persistent postgres_data volume.
- External PostgreSQL requires a reviewed override because production Compose fixes DATABASE_HOST=db and depends on db.
- The nginx proxy is the current HTTPS/SPA/API production entry point.
- Prometheus/Grafana assets are groundwork; those services are not declared in docker-compose.production.yml and require a production override or external platform.
- PowerShell 7 is required on Linux for the supplied database operational scripts.
- GitHub Actions validates releases but does not deploy or publish images.
- No application, schema, auth, business logic, CI, Compose, or deployment configuration was changed.

### Plan Coverage

The plan documents architecture, prerequisites, ports/firewall/DNS, environment and secret files, TLS, containerized and external database strategies, Alembic 0010 migration, build/start/stop/log commands, scheduler operation, backup/restore, monitoring, logging, health, CI/CD, rollback, security controls, incident runbook, post-deployment checks, and future automation.

### Validation

- Referenced paths and production Compose service/profile names checked against repository assets.
- Production Compose default and scheduler profile validation performed after documentation creation.
- Markdown structure, command/service references, generated-artifact status, and secret patterns checked.
- No backend/frontend/E2E suite rerun required because only documentation changed.
- docker compose -f docker-compose.production.yml config --quiet: passed.
- docker compose -f docker-compose.production.yml --profile scheduler config --quiet: passed.
- Resolved default services: db, backend, proxy.
- Resolved scheduler-profile services: db, assignment-scheduler, backend, proxy.
- Referenced-path, Markdown structure, service/profile, artifact, and secret scans: passed.

### Config Findings

No existing configuration was changed. Two operational limitations are documented explicitly:

1. External PostgreSQL is not selectable through environment values alone in the current production Compose file.
2. Production Compose does not currently declare Prometheus/Grafana services.

### Completion Classification

Status: READY.

### Known Limitations

This task does not deploy, publish images, create infrastructure, provide secrets, or prove behavior on the final target host.

### Next Suggested Task

Review the plan with the target infrastructure owner, choose containerized versus managed PostgreSQL and built-in versus external TLS/monitoring, then create environment-specific deployment overrides and an approved staging rehearsal without adding production secrets to Git.

## Staging Deployment Rehearsal Checklist And Operator Runbook

### Task Name

Prepare a staging deployment rehearsal checklist for ParkingApp v1.0.0-mvp.

### Files Changed

- resources/docs/staging_deployment_rehearsal.md
- README.md
- resources/docs/developer_handoff.md
- resources/docs/implementation_log.md

### Scope And Decisions

- Documentation only; no deployment, image publication, product behavior, schema, auth, business logic, or Compose configuration change.
- Uses docker-compose.production.yml with containerized PostgreSQL for the baseline rehearsal.
- No example environment or Compose override was added because the existing production path is sufficient.
- All users, data, database credentials, JWT secrets, certificates, and backup targets are synthetic/staging-only.
- External PostgreSQL and production Prometheus/Grafana remain separate reviewed-override decisions.
- Admin bootstrap preserves the seed guard: a one-off seed container uses ENVIRONMENT=test with synthetic values from a protected operator file; long-running services remain production mode.

### Checklist Coverage

The runbook includes preconditions, required inputs, roles/evidence, clean host baseline, release checkout, environment and secret preparation, TLS, Compose validation/build, PostgreSQL startup, Alembic 0010, backend/proxy health, safe admin bootstrap, manual admin/owner/employee smoke, scheduler operation, logs/request IDs, internal metrics, backup/verification, disposable restore, rollback simulation, clean stop, acceptance criteria, failure log, and sign-off.

### Validation

- Markdown structure and referenced paths checked.
- Production default and scheduler Compose configurations checked.
- Service/profile names and command references checked against repository files.
- Secret-pattern and generated-artifact scans checked.
- No full backend/frontend/E2E rerun required because this task changes documentation only.
- docker compose -f docker-compose.production.yml config --quiet: passed.
- docker compose -f docker-compose.production.yml --profile scheduler config --quiet: passed.
- Default services resolved as db, backend, proxy.
- Scheduler profile resolved as db, backend, proxy, assignment-scheduler.
- Markdown/path, command/service, secret-pattern, and generated-artifact checks: passed.

### Completion Classification

Status: READY.

### Known Limitations

- This checklist is not evidence that a rehearsal has run.
- Staging hostname, TLS material, infrastructure, synthetic credentials, monitoring option, and operator approvals must be provided out-of-band.
- The unrelated staged .idea/vcs.xml change was present before this task and was not modified or included in task scope.

### Next Suggested Task

Obtain staging approval and operator inputs, execute the checklist on a clean staging server, record failures and evidence, and treat any failed acceptance item as the next deployment defect before considering production.

## Human-Readable Frontend Operations And UX Clarity

### Task Name

Improve frontend naming, status clarity, operational context, and role-specific navigation without changing domain behavior.

### Files Changed

- Backend display schemas, application relationship loading, and focused API/schema tests under `backend/app` and `backend/tests`.
- Frontend display utilities, shared status badge, role navigation, dashboards, employee/owner/admin operational views, styles, and unit tests under `frontend/src`.
- Playwright MVP smoke and user-guide screenshot specifications under `frontend/e2e`.
- `frontend/package-lock.json` through the existing dependency ranges.
- `scripts/run_e2e_smoke.ps1` and `scripts/generate_user_guide_screenshots.ps1`.
- `resources/docs/user_guide.md`, `resources/docs/manual_qa_checklist.md`, `resources/docs/developer_handoff.md`, this log, and refreshed user-guide screenshots.

### Naming And Display Decisions

- Employee-facing `applications` are presented as `requests`; owner-facing `availabilities` are presented as `parking offers`.
- Routes, API payload fields, database columns, enum values, CSV identifiers, and authorization rules are unchanged.
- A shared frontend mapping translates raw statuses into readable labels such as `Waiting for assignment`, `Open for requests`, and `Not selected`.
- Additive nested read-schema summaries provide parking spot and user context without exposing password hashes or changing persistence.
- Technical IDs remain available as secondary references. Admin override ID inputs remain advanced controls; searchable selectors are documented as follow-up work.

### Review Notes

- Repository eager loading covers the nested availability/spot context required by async response serialization.
- Existing service/repository boundaries and ownership checks remain intact.
- Nested display schemas expose only operational identity fields; recursive API assertions verify that password fields are absent.
- Desktop table widths and header wrapping were adjusted after screenshot review so action controls remain visible. Mobile overflow behavior remained intact.
- Windows E2E database host ports moved from reserved ports `55435`/`55438` to `15435`/`15438`; this changes only disposable test infrastructure.
- `npm audit fix` updated the lockfile within existing manifest ranges and removed the reported frontend vulnerabilities; no unrelated dependency was added.

### Tests And Verification

- Frontend unit tests: `20` files, `64` tests passed.
- Frontend production build: passed (`131` modules transformed).
- Frontend dependency audit: `npm audit --omit=optional` passed with `0` vulnerabilities.
- Focused backend schema tests in the backend image: `45` passed.
- Full backend tests in the managed host environment: `727` passed, `21` skipped, `1` warning, and `1` environment-only failure in the existing PowerShell backup checksum test because the managed Windows shell lacked `Get-FileHash`.
- Full containerized backend suite excluding that PowerShell-only backup module: passed.
- Backend compile check: passed.
- Alembic heads/history: passed; latest revision remains `0010 (head)` and no migration was added.
- `docker-compose build backend frontend`: passed.
- Disposable Chromium MVP smoke: `6` passed in `15.6s`; migrations reached `0010` and cleanup succeeded.
- Disposable user-guide screenshot workflow: `4` passed in `13.3s`; `16` screenshots were generated and cleanup succeeded.
- Visual review passed for representative employee, parking-owner, admin, and mobile screens after the final responsive adjustments.

### Known Limitations

- The managed host cannot fully execute the existing PowerShell backup checksum test; this is unrelated to the changed frontend/display code and the remaining backend verification passed.
- Admin override selectors still require known request or employee references. Human-readable discovery is available on Requests and Reservations, while searchable override selectors remain future work.
- The unrelated untracked `.idea/vcs.xml` file was present before this task and was not modified or included in scope.

### Completion Classification

Status: READY.

The frontend tests, production build, dependency audit, six-flow browser smoke, screenshot generation, and focused backend display-contract tests all pass. The reviewed screens use role-appropriate workflow names, readable statuses, and human context while preserving backend contracts.

### Next Suggested Task

Run the approved staging deployment rehearsal. Treat any failed acceptance item as the next deployment defect; do not add unrelated product functionality before staging evidence is recorded.

## Capability-Based Navigation, Person Cells, And Audit Detail Polish

### Task Name

Improve frontend capability navigation, person identity presentation, and assignment audit-log details without changing backend behavior.

### Root UX Problems

- The frontend treated administrators as an admin-only audience even though existing authenticated self-service endpoints allow them to request parking, hold reservations, and publish offers for spots they own.
- Several tables used fragile single-line identity formatting or exposed long names and emails without a reusable layout boundary.
- Assignment decision details were raw-JSON-first and difficult to scan during normal operational review.

### Capability And Navigation Decision

- Kept the existing single `UserRole` model and all backend authorization unchanged.
- All authenticated roles now receive **Available spots**, **My requests**, and **My reservations**.
- Administrator privileges remain additive and the full Admin section remains present.
- **Offer my spot** is visible to parking-owner accounts and to any other authenticated account whose owner-scoped active-spot lookup returns a record.
- Added `useOwnedSpotCapability` to query `GET /parking-spots/mine` with a one-record limit. A failed capability lookup safely hides only the conditional owner link; backend ownership and active-status validation remain authoritative.

### Person And Audit UI Changes

- Added reusable `PersonCell` rendering full name, email, optional username, and optional user reference as separate stacked lines with deterministic fallbacks.
- Applied it to available spots, admin users, parking spots, requests, reservations, report user previews, override reservation context, and audit decisions.
- Replaced the audit-log wide raw-detail table with decision cards and added `AuditDecisionDetails` for ranking, not-selected requests, override/replacement context, reasons, actors, user context, and secondary IDs.
- Retained the complete recorded payload under a collapsed **Technical details** JSON view, including irregular-payload fallback behavior.
- Visual review found overly broad audit label styling and cramped three-column reservation summaries. The label selector was scoped, controlled identity wrapping was added, and reservation details were changed to two stable columns.

### Files Changed

- Frontend capability/navigation, dashboard, Help, display components, affected operational views, shared styles, and unit tests under `frontend/src`.
- `frontend/e2e/mvp-smoke.spec.js` and `frontend/e2e/user-guide-screenshots.spec.js`.
- All `16` screenshots under `resources/docs/images/user_guide`.
- `resources/docs/user_guide.md`, `resources/docs/manual_qa_checklist.md`, `resources/docs/developer_handoff.md`, and this log.

No backend, API schema, database model, migration, Compose, deployment, assignment, fairness, reservation, or override business behavior changed.

### Review Notes

- Confirmed normal parking routers depend on `get_current_user`; self-service queries and mutations remain scoped to the authenticated user.
- Confirmed publishing validates current-user ownership and active spot state, and requesting still rejects an owner's own offer.
- Confirmed `PersonCell` never exposes `hashed_password` and raw audit JSON continues to render through escaped Vue interpolation.
- Corrected the email-only identity fallback so the address appears once instead of being duplicated as both primary and secondary text.
- Confirmed unknown identity and irregular audit payload fallbacks remain readable and preserve technical evidence.
- Fixed the one Playwright ambiguity caused by both **My requests** and **Requests** being present for admins by using the exact accessible link name.

### Tests And Verification

- Frontend unit tests: `22` files, `73` tests passed.
- Frontend production build: passed; Vite transformed `134` modules.
- Frontend dependency audit: `npm audit --omit=optional` passed with `0` vulnerabilities.
- Disposable Chromium MVP smoke: `6` passed in `26.3s`; migrations reached `0010`, all role flows completed, structured audit details opened, and cleanup succeeded.
- Disposable user-guide screenshot workflow: `4` passed in `23.7s`; migrations reached `0010 (head)`, `16` screenshots were regenerated, and cleanup succeeded.
- Visual review passed for admin requests, reservations, audit logs, overrides, users, parking spots, employee available spots, and the `390x844` mobile override screen after the final wrapping fix.
- Backend tests and standalone Alembic commands were not rerun because no backend or migration file changed. Both disposable browser workflows applied the complete migration chain through `0010 (head)` against PostgreSQL.

### Known Limitations

- The account schema still stores one role; the frontend derives only the active-owned-spot capability dynamically rather than introducing a multi-role permission model.
- The conditional owner link is shown after its small owner-scoped API request resolves. A lookup failure does not grant access and leaves backend authorization unchanged.
- Very long synthetic test identities wrap inside narrow table/card columns; normal-length addresses remain intact where width permits.
- The unrelated untracked `.idea/vcs.xml` file was present before this task and was not modified or included in scope.

### Completion Classification

Status: READY.

Admin self-service capabilities are exposed without weakening authorization, person identities are consistently readable, audit decisions are structured rather than JSON-first, technical details remain available, and all required frontend, browser, screenshot, and visual checks pass.

### Next Suggested Task

Run the approved staging deployment rehearsal and record environment-specific evidence. Treat any failed rehearsal acceptance item as the next defect before adding unrelated product functionality.

## GPT-6 Frontend Review And Targeted Improvements - 2026-09-08

### Scope And Review

Reviewed AppLayout, shared CSS, all self-service and admin views, common/dashboard/admin components, router guards, frontend tests, the six-flow Playwright smoke suite, screenshot workflow, user guide and existing images, manual QA checklist, developer handoff, and prior implementation entries. The implementation plan was shared before editing. This pass preserves the blue/white identity and all assignment, reservation, ownership, authorization, API, database, deployment, and CI behavior.

### UX Issues Found And Safe Fixes

- Expanded mobile admin navigation occupied most of the initial screen. A persisted desktop collapse also retained 44px links on smaller screens. Added an independent Menu disclosure with explicit expanded state, close-on-selection, Escape focus restoration, and responsive width resets; retained desktop icon alignment and persistence.
- Keyboard focus on light backgrounds was faint and there was no shortcut past navigation. Added contrasting focus outlines, a skip link, semantic dashboard group headings, and reduced-motion support.
- The main dashboard mixed personal tasks, owner tasks, and administrative duties in one grid, while employee copy described admin access unnecessarily. Split capability-aware task groups, let cards use the available width, and separate Audit and Reporting in the admin dashboard.
- Mobile table cells placed each child into a two-column grid, separating references and date ranges incorrectly and squeezing statuses/actions. Stack each label above its complete cell content, retain visually hidden native headers, add missing action labels, wrap statuses and row actions, and reduce the visual emphasis of technical ID columns without removing any IDs.
- Offer form fixed minimum widths crowded intermediate screen sizes. Group the assigned spot, paired start/end controls, optional note, and actions with a local-time explanation.
- Override API feedback appeared above both forms, far from mobile submission, and old success context could remain after a failed retry. Scope feedback to each submitting form, clear its previous result on a new submission, retain entered values, describe Offer # mapping and audit reasons, and link to reference lists in separate tabs. Existing reference inputs, reason validation, payloads, and business rules are unchanged.
- Empty personal request/reservation lists lacked a direct next step. Add links to Available spots and My requests respectively.
- The new tablet check exposed overflow in expanded audit details, including long ranking policy identifiers and fixed ranking columns. Allow wrapping and flexible ranking columns while keeping structured decisions and collapsed raw JSON intact. Visual inspection also corrected offscreen skip-link capture artifacts and prevented long employee names from squeezing mobile audit status badges.

### Files Changed

- Shell/styles: `frontend/src/layouts/AppLayout.vue`, its existing test, and `frontend/src/styles/main.css`.
- Dashboard: `frontend/src/views/DashboardView.vue`, its existing test, `frontend/src/views/admin/AdminDashboardView.vue`, and `frontend/src/components/dashboard/DashboardCard.vue`.
- Forms/feedback: `frontend/src/components/common/BaseInput.vue`, `BaseTextarea.vue`, `frontend/src/components/admin/AdminOverrideForm.vue`, its existing test, `ReservationSummaryCard.vue`, `frontend/src/views/admin/AdminOverridesView.vue`, and its existing test.
- Self-service: `frontend/src/views/AvailableSpotsView.vue`, `MyAvailabilitiesView.vue`, `MyApplicationsView.vue`, `MyReservationsView.vue`, and the existing request/reservation tests.
- Browser verification: `frontend/e2e/mvp-smoke.spec.js` and `frontend/e2e/user-guide-screenshots.spec.js`.
- Documentation: this log, `resources/docs/user_guide.md`, `resources/docs/manual_qa_checklist.md`, `resources/docs/developer_handoff.md`, and the 16 existing user-guide PNGs. Corrected two stale backend directory references in the handoff during path review.

### Verification And Screenshot Status

- Frontend tests: 22 files, 79 tests passed. Added regression coverage for menu state, responsibility grouping, linked field guidance, local override feedback/stale results, and empty-state navigation. Existing capability navigation, owner publishing, person cells, friendly statuses, Help, and structured/raw audit tests remain passing.
- Production build: passed locally and in the disposable frontend image (134 modules).
- Full `npm audit`: passed, zero vulnerabilities; no dependency updates were needed.
- Disposable Chromium MVP smoke: all 6 flows passed, including normal admin parking access, owner publication without raw spot ID, employee requests/assignment, replacement validation and submission, audit details, collapsed sidebar alignment, and mobile Menu/Escape/navigation/override validation.
- The initial screenshot check correctly failed on tablet audit overflow; guide image replacement did not occur on failure. Final screenshot workflow: 4 tests passed (22.4s), 16 guide images regenerated, and 24 responsive review captures generated. All eight required pages passed page-overflow checks at 390x844, 768x844, and 1280x844, including expanded audit decisions with collapsed raw JSON. Visual review confirmed readable mobile cards, form controls, role tasks, and audit details.
- Documentation checks passed: 18 local Markdown links (including all 16 guide images), balanced code fences, and git diff --check. Intended frontend/tests/docs changes are staged; no build output, browser traces, credentials, unrelated files, or untracked source files are included.
- No backend file changed, so backend tests and standalone Alembic checks were not required. Disposable browser workflows applied the existing migration chain through `0010 (head)` and clean up their own containers and volumes.
- Host Vite child-process execution and Docker engine access required approved execution outside the sandbox; these environment restrictions did not require repository configuration changes.

### Follow-Up Work And Known Limitations

- Searchable override selectors and a live preview of current/requested assignment context remain follow-up work. The current API workflows still use technical references, with Requests and Reservations providing human-readable discovery and post-submit reservation context.
- Live dashboard counts, table sorting/pagination, and broader form standardization were deliberately deferred to keep this pass bounded.
- Browser verification uses Chromium. A dedicated screen-reader and Safari/Firefox pass remains useful; semantic markup and keyboard checks are not a substitute for assistive-technology testing.
- Wide tables continue to scroll within their container at tablet widths; mobile widths use stacked cards. Review captures are temporary artifacts under ignored `frontend/test-results/`; only guide images are intended documentation assets.
- The unrelated untracked `.idea/vcs.xml` existed before this task and is excluded from staging.

### Completion Classification

Status: READY. Bounded improvements are implemented and verified. Frontend tests, production build, full dependency audit, six-flow browser smoke, responsive screenshot workflow, documentation checks, and staging review pass. Intended changes are staged; the pre-existing unrelated .idea/vcs.xml remains untracked.

### Next Recommended Task

Run the existing staging deployment rehearsal as a separate task and record environment-specific acceptance evidence. Keep searchable override discovery as a bounded frontend follow-up if operator feedback prioritizes it. No deployment or image publication was performed in this review.

## Sidebar Navigation Icon Polish - 2026-09-08

### Scope And Design Issue

The desktop sidebar still used single-letter badges for every route. Those marks were difficult to interpret when labels were visually hidden, while the framed badge treatment made the expanded navigation feel heavier than the rest of the application. This change is limited to the frontend navigation shell, its focused tests, guide screenshots, and this log. Routes, capability checks, persistence, mobile disclosure behavior, authorization, business logic, and backend code are unchanged.

### Icon And Visual Strategy

- Added `NavigationIcon.vue`, a dependency-free inline-SVG component with consistent 20px, `currentColor` stroke icons for every primary and admin destination.
- Kept icons decorative with `aria-hidden`; expanded links retain visible labels, and collapsed links retain accessible names and titles.
- Replaced the text collapse chevron with a local SVG and removed framed navigation badges while preserving the Parking brand mark.
- Refined the blue sidebar gradient, row density, hover state, compact active pill and indicator, Admin separator, and collapsed centering. Existing high-contrast `focus-visible` behavior remains in force.
- Preserved the responsive reset that shows complete labels in the mobile Menu regardless of the persisted desktop collapsed preference.

### Files Changed

- `frontend/src/components/common/NavigationIcon.vue`
- `frontend/src/layouts/AppLayout.vue`
- `frontend/src/layouts/AppLayout.spec.js`
- `frontend/src/styles/main.css`
- `frontend/e2e/mvp-smoke.spec.js`
- The 16 existing PNGs under `resources/docs/images/user_guide`
- `resources/docs/implementation_log.md`

The user guide wording already describes label-based navigation and does not mention letter badges, so no prose change was required. The manual QA checklist and developer handoff remain accurate.

### Verification

- Frontend unit tests: 22 files, 80 tests passed. New coverage verifies that every navigation entry renders a named decorative SVG while labels/accessibility and role/capability navigation remain intact.
- Frontend production build: passed; Vite transformed 135 modules.
- Full `npm audit`: passed with 0 vulnerabilities; no package was added.
- Disposable Chromium MVP smoke: 6 passed. It verifies one SVG per dynamically rendered link, meaningful Overrides icon output, expanded alignment, active styling and semantics, centered collapsed icons, persisted collapse state, Help navigation, focus behavior, and 390x844 mobile navigation without overflow.
- User-guide screenshot workflow: 4 passed; all 16 guide screenshots were regenerated. Visual review covered the expanded employee dashboard, expanded admin Overrides page, active route treatment, full admin hierarchy, and 390x844 mobile shell.
- Backend tests were not run because no backend file changed.

### Completion Classification

Status: READY.

Meaningful local icons replace all navigation letter placeholders, expanded and collapsed states are clear and aligned, mobile/accessibility behavior is preserved, targeted unit/build/audit/browser/screenshot checks pass, and the unrelated pre-existing `.idea/vcs.xml` remains untouched.

## Sidebar Brand Header Polish - 2026-09-09

### Scope And Visual Change

Polished only the sidebar brand/header and collapse control. Replaced the remaining plain `P` badge with a local parking-sign SVG inside a distinctive softly shaded brand tile, refined the Parking wordmark spacing and typography, and changed the collapse control into a smaller circular utility button. In collapsed desktop mode the logo and expand control are independently centered with deliberate spacing and a subtle visual connector, so they read as a brand plus secondary control rather than two matching square badges.

The dashboard link remains accessible as **Parking dashboard** when collapsed. The collapse/expand labels, `aria-pressed` state, localStorage persistence, keyboard focus, routes, navigation icons and labels, role/capability filtering, mobile Menu behavior, and all page/backend behavior are unchanged.

### Files Changed

- `frontend/src/layouts/AppLayout.vue`
- `frontend/src/layouts/AppLayout.spec.js`
- `frontend/src/styles/main.css`
- `frontend/e2e/mvp-smoke.spec.js`
- The existing user-guide PNGs under `resources/docs/images/user_guide`
- `resources/docs/implementation_log.md`

The user guide, manual QA checklist, and developer handoff do not describe the old badge appearance and remain accurate, so no prose edits were required.

### Verification

- Frontend unit tests: 22 files, 81 tests passed. Focused coverage now checks the decorative brand SVG, visible app name, collapsed accessible brand link, collapse toggle, persistence, and the unchanged navigation matrix.
- Frontend production build: passed; Vite transformed 135 modules.
- Full `npm audit`: passed with 0 vulnerabilities.
- Disposable Chromium MVP smoke: 6 passed. Added geometry checks for expanded logo/control vertical alignment and collapsed logo/control horizontal centering; existing navigation, focus, persistence, active state, Help, and 390x844 mobile checks remain passing.
- User-guide screenshot workflow: 4 passed; 16 screenshots regenerated. Visual review covered expanded employee/admin headers and the 390x844 mobile header.
- Backend tests were not run because no backend file changed.

### Completion Classification

Status: READY.

The brand header now reads as a coherent product identity in expanded and collapsed states, the lighter chevron remains discoverable and accessible, behavior is unchanged, and all targeted verification passes. The unrelated pre-existing `.idea/vcs.xml` remains untouched.

### Brand Mark Contrast Follow-Up - 2026-09-09

Corrected the legacy structured-span reset so it no longer overrides the brand mark's intended `#1d4ed8` color with inherited white. The light badge, SVG geometry, header layout, hover/focus behavior, accessibility, and navigation behavior remain unchanged. Chromium now asserts the dark-blue computed color in both expanded and collapsed states. Frontend tests (81), production build, `npm audit` (0 vulnerabilities), MVP smoke (6), and screenshot workflow (4; 16 images regenerated) all passed; visual review confirms the `P` is clearly legible on desktop and mobile.

## Reports Summary Layout Polish - 2026-09-09

### Scope And Layout Decision

Replaced only the three small table presentations on the Reports page—**Top reserved users**, **Parking spot usage**, and **Assignment audit triggers**—with compact semantic lists. The new layouts remove table wrappers and their unnecessary horizontal scrollbars, reduce empty card space, keep counts aligned, and wrap long identity text naturally. Existing filters, report requests/calculations, lifecycle summaries, CSV exports, navigation, and backend behavior are unchanged.

- Top users reuse the existing stacked `PersonCell` name/email presentation. The technical user ID appears only as a fallback when the identity lookup is unavailable.
- Parking usage resolves each report ID through the existing admin parking-spot lookup, showing the spot code first and location or description as supporting context. `Spot #ID` remains the fallback when no display data is available.
- Audit sources render as readable status badges with compact numeric event counts.
- Each card has a compact column header, while repeated row-level unit and helper labels have been removed. Focused empty-state wording remains present for each list.

The report API remains unchanged and continues to return `parking_spot_id` and `reservation_count`. The page performs a read-only display lookup through the existing `/admin/parking-spots` endpoint, so no backend or report-contract change was required.

### Files Changed And Verification

- Changed `frontend/src/views/admin/AdminReportsView.vue`, its focused test, Reports-only styles in `frontend/src/styles/main.css`, and responsive assertions in `frontend/e2e/user-guide-screenshots.spec.js`.
- Frontend unit tests: 22 files, 83 tests passed, including compact headers, human-readable user/spot display, spot-ID fallback, and empty-state coverage. Existing filter and CSV-download tests remain passing.
- Frontend production build: passed; Vite transformed 135 modules. Full `npm audit`: 0 vulnerabilities.
- Disposable Chromium MVP smoke: 6 passed, including the existing Reports route check.
- Screenshot workflow: 4 passed and 16 guide images regenerated. Reports now asserts human-readable identity/spot output, absence of repeated helper text, compact-list/no-table rendering, and grid/document overflow behavior at 390, 768, and 1280px.
- The first responsive run exposed the generic mobile workspace section's 20px negative full-bleed margin on the new cards. A Reports-scoped mobile override corrected it; the final run passed at all widths.
- Visual review confirmed compact desktop/tablet/mobile cards, readable wrapped email text, unclipped badges, usable filters/exports, and no summary-card scrollbars.
- No backend file changed, so backend tests were not run.

### Completion Classification

Status: READY.

All three report breakdowns use compact headers and human-readable values without unnecessary horizontal scrolling. User and spot IDs remain safe fallbacks, filters and exports are unchanged, targeted automated and visual verification passes, and no backend or unrelated product code was changed.
