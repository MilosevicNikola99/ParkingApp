from pathlib import Path

from pydantic import ValidationError
import pytest
import yaml

from app.core.config import Settings


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
DEPLOY_DIR = ROOT_DIR / "deploy"
SMOKE_SCRIPT = ROOT_DIR / "scripts" / "smoke_test.ps1"
BACKUP_DOC = ROOT_DIR / "resources" / "docs" / "postgres_backup_restore.md"
PROMETHEUS_CONFIG = DEPLOY_DIR / "prometheus" / "prometheus.yml"
PROMETHEUS_ALERTS = DEPLOY_DIR / "prometheus" / "alert_rules.yml"
GRAFANA_DATASOURCE = DEPLOY_DIR / "grafana" / "provisioning" / "datasources" / "prometheus.yml"
GRAFANA_DASHBOARD = DEPLOY_DIR / "grafana" / "dashboards" / "parking-app-overview.json"


def test_backend_dockerfile_uses_expected_runtime_and_entrypoint() -> None:
    dockerfile = (BACKEND_DIR / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim" in dockerfile
    assert "COPY requirements.txt ." in dockerfile
    assert "pip install --no-cache-dir -r requirements.txt" in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert 'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]' in dockerfile


def test_frontend_dockerfile_builds_and_serves_static_assets() -> None:
    dockerfile = (FRONTEND_DIR / "Dockerfile").read_text(encoding="utf-8")
    nginx_config = (FRONTEND_DIR / "nginx.conf").read_text(encoding="utf-8")
    dockerignore = (FRONTEND_DIR / ".dockerignore").read_text(encoding="utf-8")

    assert "FROM node:22-alpine AS build" in dockerfile
    assert "COPY package.json package-lock.json ./" in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "RUN npm run build" in dockerfile
    assert "FROM nginx:1.27-alpine" in dockerfile
    assert "EXPOSE 80" in dockerfile
    assert 'CMD ["nginx", "-g", "daemon off;"]' in dockerfile
    assert "try_files $uri $uri/ /index.html;" in nginx_config
    assert "node_modules/" in dockerignore
    assert "dist/" in dockerignore


def test_tls_proxy_dockerfile_builds_frontend_and_nginx_proxy() -> None:
    dockerfile = (DEPLOY_DIR / "nginx" / "Dockerfile").read_text(encoding="utf-8")
    nginx_config = (DEPLOY_DIR / "nginx" / "tls-proxy.conf").read_text(encoding="utf-8")

    assert "FROM node:22-alpine AS frontend-build" in dockerfile
    assert "ARG VITE_API_BASE_URL=/api" in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "RUN npm run build" in dockerfile
    assert "FROM nginx:1.27-alpine" in dockerfile
    assert "COPY deploy/nginx/tls-proxy.conf /etc/nginx/conf.d/default.conf" in dockerfile
    assert "EXPOSE 80 443" in dockerfile
    assert "listen 80;" in nginx_config
    assert "return 301 https://$host$request_uri;" in nginx_config
    assert "listen 443 ssl;" in nginx_config
    assert "http2 on;" in nginx_config
    assert "ssl_certificate /run/secrets/tls_certificate;" in nginx_config
    assert "ssl_certificate_key /run/secrets/tls_private_key;" in nginx_config
    assert "ssl_protocols TLSv1.2 TLSv1.3;" in nginx_config
    assert "SSLv3" not in nginx_config
    assert "TLSv1 " not in nginx_config
    assert "TLSv1.1" not in nginx_config
    assert "proxy_pass http://backend:8000/;" in nginx_config
    assert "location = /metrics" in nginx_config
    assert "location = /api/metrics" in nginx_config
    assert "proxy_set_header Host $host;" in nginx_config
    assert "proxy_set_header X-Real-IP $remote_addr;" in nginx_config
    assert "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;" in nginx_config
    assert "proxy_set_header X-Forwarded-Proto $scheme;" in nginx_config
    assert "proxy_set_header X-Request-ID $proxy_request_id;" in nginx_config
    assert "try_files $uri $uri/ /index.html;" in nginx_config
    assert "Enable HSTS here only after HTTPS is verified" in nginx_config


def test_docker_compose_defines_backend_database_and_frontend_services() -> None:
    compose = yaml.safe_load((ROOT_DIR / "docker-compose.yml").read_text(encoding="utf-8"))

    services = compose["services"]
    db_service = services["db"]
    backend_service = services["backend"]
    scheduler_service = services["assignment-scheduler"]
    frontend_service = services["frontend"]
    prometheus_service = services["prometheus"]
    grafana_service = services["grafana"]

    assert db_service["image"] == "postgres:16-alpine"
    assert "postgres_data:/var/lib/postgresql/data" in db_service["volumes"]
    assert db_service["healthcheck"]["test"][0] == "CMD-SHELL"
    assert backend_service["build"]["context"] == "./backend"
    assert backend_service["depends_on"]["db"]["condition"] == "service_healthy"
    assert backend_service["ports"] == ["${BACKEND_PORT:-8000}:8000"]
    assert backend_service["environment"]["DATABASE_HOST"] == "db"
    assert "@db:5432/" in backend_service["environment"]["DATABASE_URL"]
    assert backend_service["environment"]["DB_POOL_SIZE"] == "${DB_POOL_SIZE:-5}"
    assert backend_service["environment"]["DB_MAX_OVERFLOW"] == "${DB_MAX_OVERFLOW:-5}"
    assert backend_service["environment"]["DB_POOL_TIMEOUT_SECONDS"] == "${DB_POOL_TIMEOUT_SECONDS:-30}"
    assert backend_service["environment"]["DB_POOL_RECYCLE_SECONDS"] == "${DB_POOL_RECYCLE_SECONDS:-1800}"
    assert backend_service["environment"]["DB_POOL_PRE_PING"] == "${DB_POOL_PRE_PING:-true}"
    assert backend_service["environment"]["SAME_TEAM_PRIORITY_WINDOW_HOURS"] == (
        "${SAME_TEAM_PRIORITY_WINDOW_HOURS:-2}"
    )
    assert backend_service["environment"]["RECENT_WIN_FAIRNESS_WINDOW_DAYS"] == (
        "${RECENT_WIN_FAIRNESS_WINDOW_DAYS:-30}"
    )
    assert backend_service["environment"]["RECENT_WIN_SOFT_LIMIT"] == "${RECENT_WIN_SOFT_LIMIT:-2}"
    assert backend_service["environment"]["ASSIGNMENT_SCHEDULER_ENABLED"] == (
        "${ASSIGNMENT_SCHEDULER_ENABLED:-false}"
    )
    assert backend_service["environment"]["ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS"] == (
        "${ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS:-60}"
    )
    assert backend_service["environment"]["ASSIGNMENT_SCHEDULER_BATCH_LIMIT"] == (
        "${ASSIGNMENT_SCHEDULER_BATCH_LIMIT:-100}"
    )
    assert backend_service["environment"]["ASSIGNMENT_SCHEDULER_LOCK_KEY"] == (
        "${ASSIGNMENT_SCHEDULER_LOCK_KEY:-740730001}"
    )
    assert backend_service["environment"]["ASSIGNMENT_SCHEDULER_RUN_IMMEDIATELY"] == (
        "${ASSIGNMENT_SCHEDULER_RUN_IMMEDIATELY:-true}"
    )
    assert backend_service["environment"]["METRICS_ENABLED"] == "${METRICS_ENABLED:-true}"
    assert backend_service["environment"]["METRICS_PATH"] == "${METRICS_PATH:-/metrics}"
    assert backend_service["environment"]["SCHEDULER_METRICS_PORT"] == "${SCHEDULER_METRICS_PORT:-9101}"
    assert backend_service["environment"]["READINESS_DATABASE_TIMEOUT_SECONDS"] == (
        "${READINESS_DATABASE_TIMEOUT_SECONDS:-2}"
    )
    assert backend_service["environment"]["LOG_LEVEL"] == "${LOG_LEVEL:-INFO}"
    assert backend_service["environment"]["LOG_JSON"] == "${LOG_JSON:-true}"
    assert backend_service["environment"]["CORS_ALLOWED_ORIGINS"] == (
        '${CORS_ALLOWED_ORIGINS:-["http://localhost:5173","http://localhost:8080"]}'
    )
    assert backend_service["environment"]["CORS_ALLOW_CREDENTIALS"] == (
        "${CORS_ALLOW_CREDENTIALS:-false}"
    )
    assert backend_service["environment"]["SEED_ADMIN_ENABLED"] == "${SEED_ADMIN_ENABLED:-false}"
    assert backend_service["environment"]["SEED_ADMIN_UPDATE_PASSWORD"] == (
        "${SEED_ADMIN_UPDATE_PASSWORD:-false}"
    )
    assert scheduler_service["profiles"] == ["scheduler", "monitoring"]
    assert scheduler_service["build"]["context"] == "./backend"
    assert scheduler_service["command"] == ["python", "-m", "app.commands.run_assignment_scheduler"]
    assert "ports" not in scheduler_service
    assert scheduler_service["depends_on"]["db"]["condition"] == "service_healthy"
    assert scheduler_service["environment"]["DATABASE_HOST"] == "db"
    assert scheduler_service["environment"]["DB_POOL_SIZE"] == "${DB_POOL_SIZE:-5}"
    assert scheduler_service["environment"]["DB_MAX_OVERFLOW"] == "${DB_MAX_OVERFLOW:-5}"
    assert scheduler_service["environment"]["DB_POOL_TIMEOUT_SECONDS"] == "${DB_POOL_TIMEOUT_SECONDS:-30}"
    assert scheduler_service["environment"]["DB_POOL_RECYCLE_SECONDS"] == "${DB_POOL_RECYCLE_SECONDS:-1800}"
    assert scheduler_service["environment"]["DB_POOL_PRE_PING"] == "${DB_POOL_PRE_PING:-true}"
    assert scheduler_service["environment"]["ASSIGNMENT_SCHEDULER_ENABLED"] == "true"
    assert scheduler_service["environment"]["ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS"] == (
        "${ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS:-60}"
    )
    assert scheduler_service["environment"]["ASSIGNMENT_SCHEDULER_BATCH_LIMIT"] == (
        "${ASSIGNMENT_SCHEDULER_BATCH_LIMIT:-100}"
    )
    assert scheduler_service["environment"]["ASSIGNMENT_SCHEDULER_LOCK_KEY"] == (
        "${ASSIGNMENT_SCHEDULER_LOCK_KEY:-740730001}"
    )
    assert scheduler_service["environment"]["ASSIGNMENT_SCHEDULER_RUN_IMMEDIATELY"] == (
        "${ASSIGNMENT_SCHEDULER_RUN_IMMEDIATELY:-true}"
    )
    assert scheduler_service["environment"]["METRICS_ENABLED"] == "${METRICS_ENABLED:-true}"
    assert scheduler_service["environment"]["METRICS_PATH"] == "${METRICS_PATH:-/metrics}"
    assert scheduler_service["environment"]["SCHEDULER_METRICS_PORT"] == "${SCHEDULER_METRICS_PORT:-9101}"
    assert scheduler_service["environment"]["SEED_ADMIN_ENABLED"] == "false"
    assert scheduler_service["expose"] == ["${SCHEDULER_METRICS_PORT:-9101}"]
    assert frontend_service["build"]["context"] == "./frontend"
    assert frontend_service["build"]["dockerfile"] == "Dockerfile"
    assert frontend_service["build"]["args"]["VITE_API_BASE_URL"] == (
        "${VITE_API_BASE_URL:-http://localhost:8000}"
    )
    assert frontend_service["ports"] == ["${FRONTEND_PORT:-8080}:80"]
    assert frontend_service["depends_on"]["backend"]["condition"] == "service_started"
    assert prometheus_service["profiles"] == ["monitoring"]
    assert prometheus_service["image"] == "prom/prometheus:v2.55.1"
    assert prometheus_service["ports"] == ["127.0.0.1:${PROMETHEUS_PORT:-9090}:9090"]
    assert "./deploy/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro" in prometheus_service["volumes"]
    assert prometheus_service["depends_on"]["backend"]["condition"] == "service_started"
    assert prometheus_service["depends_on"]["assignment-scheduler"]["condition"] == "service_started"
    assert grafana_service["profiles"] == ["monitoring"]
    assert grafana_service["image"] == "grafana/grafana-oss:11.4.0"
    assert grafana_service["ports"] == ["127.0.0.1:${GRAFANA_PORT:-3000}:3000"]
    assert grafana_service["environment"]["GF_SECURITY_ADMIN_PASSWORD"] == (
        "${GRAFANA_ADMIN_PASSWORD:-local-grafana-admin}"
    )


def test_production_compose_defines_internal_backend_tls_proxy_and_secrets() -> None:
    compose = yaml.safe_load((ROOT_DIR / "docker-compose.production.yml").read_text(encoding="utf-8"))

    services = compose["services"]
    db_service = services["db"]
    backend_service = services["backend"]
    scheduler_service = services["assignment-scheduler"]
    proxy_service = services["proxy"]
    secrets = compose["secrets"]

    assert "ports" not in db_service
    assert db_service["environment"]["POSTGRES_PASSWORD_FILE"] == "/run/secrets/postgres_password"
    assert db_service["secrets"] == ["postgres_password"]
    assert "ports" not in backend_service
    assert backend_service["expose"] == ["8000"]
    assert "--proxy-headers" in backend_service["command"]
    assert "--forwarded-allow-ips=*" in backend_service["command"]
    assert backend_service["environment"]["ENVIRONMENT"] == "production"
    assert backend_service["environment"]["DATABASE_PASSWORD_FILE"] == "/run/secrets/postgres_password"
    assert backend_service["environment"]["DATABASE_URL"] == ""
    assert backend_service["environment"]["DB_POOL_SIZE"] == "${DB_POOL_SIZE:-5}"
    assert backend_service["environment"]["DB_MAX_OVERFLOW"] == "${DB_MAX_OVERFLOW:-5}"
    assert backend_service["environment"]["DB_POOL_TIMEOUT_SECONDS"] == "${DB_POOL_TIMEOUT_SECONDS:-30}"
    assert backend_service["environment"]["DB_POOL_RECYCLE_SECONDS"] == "${DB_POOL_RECYCLE_SECONDS:-1800}"
    assert backend_service["environment"]["DB_POOL_PRE_PING"] == "${DB_POOL_PRE_PING:-true}"
    assert backend_service["environment"]["JWT_SECRET_FILE"] == "/run/secrets/jwt_secret"
    assert backend_service["environment"]["CORS_ALLOWED_ORIGINS"] == (
        '${PRODUCTION_CORS_ALLOWED_ORIGINS:-["https://parking.example.com"]}'
    )
    assert backend_service["environment"]["METRICS_ENABLED"] == "${METRICS_ENABLED:-true}"
    assert backend_service["environment"]["METRICS_PATH"] == "${METRICS_PATH:-/metrics}"
    assert backend_service["environment"]["READINESS_DATABASE_TIMEOUT_SECONDS"] == (
        "${READINESS_DATABASE_TIMEOUT_SECONDS:-2}"
    )
    assert backend_service["environment"]["SEED_ADMIN_ENABLED"] == "false"
    assert backend_service["secrets"] == ["jwt_secret", "postgres_password"]
    assert scheduler_service["profiles"] == ["scheduler"]
    assert scheduler_service["environment"]["ASSIGNMENT_SCHEDULER_ENABLED"] == "true"
    assert scheduler_service["environment"]["DB_POOL_SIZE"] == "${DB_POOL_SIZE:-5}"
    assert scheduler_service["environment"]["DB_MAX_OVERFLOW"] == "${DB_MAX_OVERFLOW:-5}"
    assert scheduler_service["environment"]["DB_POOL_TIMEOUT_SECONDS"] == "${DB_POOL_TIMEOUT_SECONDS:-30}"
    assert scheduler_service["environment"]["DB_POOL_RECYCLE_SECONDS"] == "${DB_POOL_RECYCLE_SECONDS:-1800}"
    assert scheduler_service["environment"]["DB_POOL_PRE_PING"] == "${DB_POOL_PRE_PING:-true}"
    assert scheduler_service["environment"]["METRICS_ENABLED"] == "${METRICS_ENABLED:-true}"
    assert scheduler_service["environment"]["SCHEDULER_METRICS_PORT"] == "${SCHEDULER_METRICS_PORT:-9101}"
    assert scheduler_service["expose"] == ["${SCHEDULER_METRICS_PORT:-9101}"]
    assert "ports" not in scheduler_service
    assert proxy_service["build"]["dockerfile"] == "deploy/nginx/Dockerfile"
    assert proxy_service["build"]["args"]["VITE_API_BASE_URL"] == "${PRODUCTION_VITE_API_BASE_URL:-/api}"
    assert proxy_service["ports"] == ["${HTTP_PORT:-8081}:80", "${HTTPS_PORT:-8443}:443"]
    assert proxy_service["secrets"] == ["tls_certificate", "tls_private_key"]
    assert secrets["jwt_secret"]["file"] == "./secrets/jwt_secret.txt"
    assert secrets["postgres_password"]["file"] == "./secrets/postgres_password.txt"
    assert secrets["tls_certificate"]["file"] == "./secrets/tls_certificate.pem"
    assert secrets["tls_private_key"]["file"] == "./secrets/tls_private_key.pem"


def test_settings_accept_database_component_environment_values() -> None:
    settings = Settings(
        database_host="db",
        database_port=5432,
        database_name="parking_app",
        database_user="parking_app",
        database_password="parking_app",
        database_url="postgresql+psycopg://parking_app:parking_app@db:5432/parking_app",
    )

    assert settings.database_host == "db"
    assert settings.database_port == 5432
    assert settings.database_url == "postgresql+psycopg://parking_app:parking_app@db:5432/parking_app"
    assert settings.db_pool_size == 5
    assert settings.db_max_overflow == 5
    assert settings.db_pool_timeout_seconds == 30
    assert settings.db_pool_recycle_seconds == 1800
    assert settings.db_pool_pre_ping is True
    assert settings.same_team_priority_window_hours == 2
    assert settings.recent_win_fairness_window_days == 30
    assert settings.recent_win_soft_limit == 2
    assert settings.assignment_scheduler_enabled is False
    assert settings.assignment_scheduler_interval_seconds == 60
    assert settings.assignment_scheduler_batch_limit == 100
    assert settings.assignment_scheduler_lock_key == 740730001
    assert settings.assignment_scheduler_run_immediately is True
    assert settings.metrics_enabled is True
    assert settings.metrics_path == "/metrics"
    assert settings.scheduler_metrics_port == 9101
    assert settings.readiness_database_timeout_seconds == 2
    assert settings.log_level == "INFO"
    assert settings.log_json is True


def test_settings_default_cors_origins_include_local_frontends() -> None:
    settings = Settings()

    assert settings.cors_allowed_origins == [
        "http://localhost:5173",
        "http://localhost:8080",
    ]
    assert settings.cors_allow_credentials is False


def test_settings_normalize_exact_cors_origins() -> None:
    settings = Settings(
        cors_allowed_origins=[
            " https://parking.example.com/ ",
            "https://parking.example.com",
        ],
    )

    assert settings.cors_allowed_origins == ["https://parking.example.com"]


@pytest.mark.parametrize(
    "origins",
    [
        ["*"],
        [],
        ["parking.example.com"],
        ["https://parking.example.com/path"],
        ["https://user:password@parking.example.com"],
        ["https://parking example.com"],
        ["https://parking.example.com\\unexpected"],
    ],
)
def test_settings_reject_unsafe_cors_origins(origins: list[str]) -> None:
    with pytest.raises(ValidationError):
        Settings(cors_allowed_origins=origins)


def test_settings_require_non_local_cors_origins_in_production() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production")

    settings = Settings(
        environment="production",
        jwt_secret_key="production-jwt-secret-with-at-least-32-characters",
        database_url="",
        database_password="production-database-password",
        cors_allowed_origins=["https://parking.example.com"],
    )

    assert settings.cors_allowed_origins == ["https://parking.example.com"]


def test_settings_accept_custom_recent_win_soft_limit() -> None:
    settings = Settings(recent_win_soft_limit=5)

    assert settings.recent_win_soft_limit == 5


def test_settings_validate_assignment_scheduler_bounds() -> None:
    settings = Settings(
        assignment_scheduler_enabled=True,
        assignment_scheduler_interval_seconds=5,
        assignment_scheduler_batch_limit=1,
        assignment_scheduler_lock_key=1,
    )

    assert settings.assignment_scheduler_enabled is True
    assert settings.assignment_scheduler_interval_seconds == 5
    assert settings.assignment_scheduler_batch_limit == 1
    assert settings.assignment_scheduler_lock_key == 1

    with pytest.raises(ValidationError):
        Settings(assignment_scheduler_interval_seconds=4)
    with pytest.raises(ValidationError):
        Settings(assignment_scheduler_batch_limit=0)
    with pytest.raises(ValidationError):
        Settings(assignment_scheduler_batch_limit=1001)
    with pytest.raises(ValidationError):
        Settings(assignment_scheduler_lock_key=0)
    with pytest.raises(ValidationError):
        Settings(metrics_path="metrics")
    with pytest.raises(ValidationError):
        Settings(metrics_path="/metrics/{tenant}")
    with pytest.raises(ValidationError):
        Settings(scheduler_metrics_port=0)
    with pytest.raises(ValidationError):
        Settings(readiness_database_timeout_seconds=0)


def test_settings_normalize_and_validate_log_level() -> None:
    assert Settings(log_level="debug").log_level == "DEBUG"

    with pytest.raises(ValidationError):
        Settings(log_level="verbose")


def test_environment_examples_include_frontend_docker_values() -> None:
    root_env_example = (ROOT_DIR / ".env.example").read_text(encoding="utf-8")
    backend_env_example = (BACKEND_DIR / ".env.example").read_text(encoding="utf-8")
    frontend_env_example = (FRONTEND_DIR / ".env.example").read_text(encoding="utf-8")

    assert "FRONTEND_PORT=8080" in root_env_example
    assert "HTTP_PORT=8081" in root_env_example
    assert "HTTPS_PORT=8443" in root_env_example
    assert "VITE_API_BASE_URL=http://localhost:8000" in root_env_example
    assert "PRODUCTION_VITE_API_BASE_URL=/api" in root_env_example
    assert 'PRODUCTION_CORS_ALLOWED_ORIGINS=["https://parking.example.com"]' in root_env_example
    assert "POSTGRES_PASSWORD_FILE=" in root_env_example
    assert "DATABASE_PASSWORD_FILE=" in root_env_example
    assert "JWT_SECRET_FILE=" in root_env_example
    assert "DB_POOL_SIZE=5" in root_env_example
    assert "DB_MAX_OVERFLOW=5" in root_env_example
    assert "DB_POOL_TIMEOUT_SECONDS=30" in root_env_example
    assert "DB_POOL_RECYCLE_SECONDS=1800" in root_env_example
    assert "DB_POOL_PRE_PING=true" in root_env_example
    assert "SAME_TEAM_PRIORITY_WINDOW_HOURS=2" in root_env_example
    assert "RECENT_WIN_FAIRNESS_WINDOW_DAYS=30" in root_env_example
    assert "RECENT_WIN_SOFT_LIMIT=2" in root_env_example
    assert "ASSIGNMENT_SCHEDULER_ENABLED=false" in root_env_example
    assert "ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS=60" in root_env_example
    assert "ASSIGNMENT_SCHEDULER_BATCH_LIMIT=100" in root_env_example
    assert "ASSIGNMENT_SCHEDULER_LOCK_KEY=740730001" in root_env_example
    assert "ASSIGNMENT_SCHEDULER_RUN_IMMEDIATELY=true" in root_env_example
    assert "METRICS_ENABLED=true" in root_env_example
    assert "METRICS_PATH=/metrics" in root_env_example
    assert "SCHEDULER_METRICS_PORT=9101" in root_env_example
    assert "READINESS_DATABASE_TIMEOUT_SECONDS=2" in root_env_example
    assert "PROMETHEUS_PORT=9090" in root_env_example
    assert "GRAFANA_PORT=3000" in root_env_example
    assert "LOG_LEVEL=INFO" in root_env_example
    assert "LOG_JSON=true" in root_env_example
    assert 'CORS_ALLOWED_ORIGINS=["http://localhost:5173","http://localhost:8080"]' in root_env_example
    assert "CORS_ALLOW_CREDENTIALS=false" in root_env_example
    assert "Production: load a high-entropy JWT secret from a secret manager." in root_env_example
    assert "SEED_ADMIN_ENABLED=false" in root_env_example
    assert "SEED_ADMIN_PASSWORD=" in root_env_example
    assert "SEED_ADMIN_UPDATE_PASSWORD=false" in root_env_example
    assert "SAME_TEAM_PRIORITY_WINDOW_HOURS=2" in backend_env_example
    assert "DATABASE_PASSWORD_FILE=" in backend_env_example
    assert "POSTGRES_PASSWORD_FILE=" in backend_env_example
    assert "JWT_SECRET_FILE=" in backend_env_example
    assert "DB_POOL_SIZE=5" in backend_env_example
    assert "DB_MAX_OVERFLOW=5" in backend_env_example
    assert "DB_POOL_TIMEOUT_SECONDS=30" in backend_env_example
    assert "DB_POOL_RECYCLE_SECONDS=1800" in backend_env_example
    assert "DB_POOL_PRE_PING=true" in backend_env_example
    assert "RECENT_WIN_FAIRNESS_WINDOW_DAYS=30" in backend_env_example
    assert "RECENT_WIN_SOFT_LIMIT=2" in backend_env_example
    assert "ASSIGNMENT_SCHEDULER_ENABLED=false" in backend_env_example
    assert "ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS=60" in backend_env_example
    assert "ASSIGNMENT_SCHEDULER_BATCH_LIMIT=100" in backend_env_example
    assert "ASSIGNMENT_SCHEDULER_LOCK_KEY=740730001" in backend_env_example
    assert "ASSIGNMENT_SCHEDULER_RUN_IMMEDIATELY=true" in backend_env_example
    assert "METRICS_ENABLED=true" in backend_env_example
    assert "METRICS_PATH=/metrics" in backend_env_example
    assert "SCHEDULER_METRICS_PORT=9101" in backend_env_example
    assert "READINESS_DATABASE_TIMEOUT_SECONDS=2" in backend_env_example
    assert "LOG_LEVEL=INFO" in backend_env_example
    assert "LOG_JSON=true" in backend_env_example
    assert 'PRODUCTION_CORS_ALLOWED_ORIGINS=["https://parking.example.com"]' in backend_env_example
    assert 'CORS_ALLOWED_ORIGINS=["http://localhost:5173","http://localhost:8080"]' in backend_env_example
    assert "CORS_ALLOW_CREDENTIALS=false" in backend_env_example
    assert "Production: load a high-entropy JWT secret from a secret manager." in backend_env_example
    assert "SEED_ADMIN_ENABLED=false" in backend_env_example
    assert "SEED_ADMIN_PASSWORD=" in backend_env_example
    assert "SEED_ADMIN_UPDATE_PASSWORD=false" in backend_env_example
    assert "VITE_API_BASE_URL=http://localhost:8000" in frontend_env_example
    assert "public HTTPS backend URL" in frontend_env_example
    assert "Production TLS proxy builds can use /api" in frontend_env_example


def test_gitignore_and_root_dockerignore_exclude_secret_and_backup_files() -> None:
    gitignore = (ROOT_DIR / ".gitignore").read_text(encoding="utf-8")
    dockerignore = (ROOT_DIR / ".dockerignore").read_text(encoding="utf-8")

    assert "secrets/*" in gitignore
    assert "!secrets/.gitkeep" in gitignore
    assert "backups/*" in gitignore
    assert "!backups/.gitkeep" in gitignore
    assert "secrets/*" in dockerignore
    assert "!secrets/.gitkeep" in dockerignore
    assert "backups/*" in dockerignore
    assert "!backups/.gitkeep" in dockerignore
    assert (ROOT_DIR / "secrets" / ".gitkeep").exists()
    assert (ROOT_DIR / "backups" / ".gitkeep").exists()


def test_postgres_backup_restore_scripts_and_runbook_exist() -> None:
    backup_script = (ROOT_DIR / "scripts" / "backup_postgres.ps1").read_text(encoding="utf-8")
    verify_script = (ROOT_DIR / "scripts" / "verify_postgres_backup.ps1").read_text(encoding="utf-8")
    restore_script = (ROOT_DIR / "scripts" / "restore_postgres.ps1").read_text(encoding="utf-8")
    runbook = BACKUP_DOC.read_text(encoding="utf-8")

    assert "pg_dump" in backup_script
    assert '"-Fc"' in backup_script
    assert "sha256" in backup_script
    assert "alembicCurrentRevision" in backup_script
    assert "Invoke-PostgresBackupRetention" in backup_script
    assert "pg_restore" in verify_script
    assert "--list" in verify_script
    assert "ExpectedSha256" in verify_script
    assert "ConfirmDestructive" in restore_script
    assert "AllowProductionRestore" in restore_script
    assert "FreshDatabase" in restore_script
    assert "ExistingDatabase" in restore_script
    assert "powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\backup_postgres.ps1" in runbook
    assert "verify_postgres_backup.ps1" in runbook
    assert "restore_postgres.ps1" in runbook
    assert "Volume persistence is not a backup" in runbook
    assert "Production restore requires -AllowProductionRestore" in runbook


def test_prometheus_and_grafana_monitoring_files_are_structured() -> None:
    prometheus_config = yaml.safe_load(PROMETHEUS_CONFIG.read_text(encoding="utf-8"))
    alert_config = yaml.safe_load(PROMETHEUS_ALERTS.read_text(encoding="utf-8"))
    grafana_datasource = yaml.safe_load(GRAFANA_DATASOURCE.read_text(encoding="utf-8"))
    dashboard_text = GRAFANA_DASHBOARD.read_text(encoding="utf-8")
    dashboard = yaml.safe_load(dashboard_text)

    scrape_jobs = {scrape["job_name"]: scrape for scrape in prometheus_config["scrape_configs"]}
    assert scrape_jobs["parking-backend"]["metrics_path"] == "/metrics"
    assert scrape_jobs["parking-backend"]["static_configs"][0]["targets"] == ["backend:8000"]
    assert scrape_jobs["parking-assignment-scheduler"]["metrics_path"] == "/metrics"
    assert scrape_jobs["parking-assignment-scheduler"]["static_configs"][0]["targets"] == [
        "assignment-scheduler:9101",
    ]
    assert "/etc/prometheus/rules/*.yml" in prometheus_config["rule_files"]

    alert_names = {
        rule["alert"]
        for group in alert_config["groups"]
        for rule in group["rules"]
    }
    assert {
        "BackendNotReady",
        "HighServerErrorRate",
        "HighRequestLatency",
        "AssignmentSchedulerNoRecentSuccess",
        "AssignmentSchedulerCycleFailures",
        "PostgreSQLReadinessFailure",
    }.issubset(alert_names)
    assert grafana_datasource["datasources"][0]["url"] == "http://prometheus:9090"
    assert dashboard["title"] == "Parking App Overview"
    assert "parking_http_requests_total" in dashboard_text


def test_local_tls_certificate_script_outputs_only_gitignored_paths() -> None:
    script = (ROOT_DIR / "scripts" / "generate_local_tls_certificate.ps1").read_text(encoding="utf-8")

    assert "tls_certificate.pem" in script
    assert "tls_private_key.pem" in script
    assert "subjectAltName=DNS:localhost,IP:127.0.0.1" in script
    assert "ignored by Git" in script


def test_smoke_script_contains_safe_critical_path_checks() -> None:
    smoke_script = SMOKE_SCRIPT.read_text(encoding="utf-8")

    assert "/health" in smoke_script
    assert "/auth/login" in smoke_script
    assert "/auth/me" in smoke_script
    assert "/admin/teams" in smoke_script
    assert '"/login"' in smoke_script
    assert '"/dashboard"' in smoke_script
    assert "alembic -c alembic.ini current" in smoke_script
    assert "alembic -c alembic.ini heads" in smoke_script
    assert "Access-Control-Request-Method" in smoke_script
    assert "SMOKE_LOGIN_IDENTIFIER" in smoke_script
    assert "SMOKE_LOGIN_PASSWORD" in smoke_script
    assert "SMOKE_TEST_USERNAME" in smoke_script
    assert "SMOKE_TEST_PASSWORD" in smoke_script
    assert "SEED_ADMIN_USERNAME" in smoke_script
    assert "SEED_ADMIN_PASSWORD" in smoke_script
    assert "valid-password" not in smoke_script
    assert "change-this-in-real-environments" not in smoke_script
