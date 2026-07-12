from pathlib import Path

import yaml


ROOT_DIR = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT_DIR / ".github" / "workflows"
CI_WORKFLOW = WORKFLOW_DIR / "ci.yml"
E2E_WORKFLOW = WORKFLOW_DIR / "e2e.yml"
LINUX_E2E_RUNNER = ROOT_DIR / "scripts" / "run_e2e_smoke.sh"
E2E_SMOKE_SPEC = ROOT_DIR / "frontend" / "e2e" / "mvp-smoke.spec.js"


def load_workflow(path: Path) -> dict[str, object]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict)
    return workflow


def test_ci_workflows_have_bounded_triggers_permissions_and_jobs() -> None:
    ci = load_workflow(CI_WORKFLOW)
    e2e = load_workflow(E2E_WORKFLOW)

    assert set(ci["on"]) == {"pull_request", "push", "workflow_dispatch"}
    assert set(e2e["on"]) == {"pull_request", "push", "workflow_dispatch"}
    assert ci["permissions"] == {"contents": "read"}
    assert e2e["permissions"] == {"contents": "read"}
    assert set(ci["jobs"]) == {
        "backend-quality",
        "postgres-concurrency",
        "frontend-quality",
        "compose-validation",
    }
    assert set(e2e["jobs"]) == {"e2e-smoke"}
    assert all(job.get("timeout-minutes") for job in ci["jobs"].values())
    assert all(job.get("timeout-minutes") for job in e2e["jobs"].values())
    assert ci["concurrency"]["cancel-in-progress"]
    assert e2e["concurrency"]["cancel-in-progress"]


def test_ci_workflows_cover_required_quality_and_e2e_commands() -> None:
    ci_text = CI_WORKFLOW.read_text(encoding="utf-8")
    e2e_text = E2E_WORKFLOW.read_text(encoding="utf-8")

    for command in (
        "python -m pytest",
        "python -m compileall",
        "alembic -c alembic.ini heads",
        "alembic -c alembic.ini history",
        "python -m pip_audit",
        "postgres_concurrency",
        "npm test",
        "npm run build",
        "npm audit",
        "docker compose config --quiet",
        "docker compose -f docker-compose.production.yml config --quiet",
        "docker compose build backend frontend",
        "docker compose -f docker-compose.production.yml build proxy",
    ):
        assert command in ci_text

    assert "npx playwright install --with-deps chromium" in e2e_text
    assert "bash scripts/run_e2e_smoke.sh" in e2e_text
    assert "if: failure()" in e2e_text
    assert "retention-days: 5" in e2e_text
    assert "frontend/playwright-report/" in e2e_text
    assert "frontend/test-results/" in e2e_text


def test_postgres_concurrency_junit_check_aggregates_nested_suites() -> None:
    ci_text = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "root.findall('testsuite')" in ci_text
    assert "('tests', 'skipped', 'failures', 'errors')" in ci_text
    assert "counts['tests'] > 0" in ci_text
    assert "counts['skipped'] == counts['failures'] == counts['errors'] == 0" in ci_text


def test_backup_script_tests_select_cross_platform_powershell() -> None:
    test_module = (ROOT_DIR / "backend" / "tests" / "test_postgres_backup_scripts.py").read_text(
        encoding="utf-8",
    )

    assert 'shutil.which("powershell.exe") or shutil.which("pwsh")' in test_module


def test_ci_uses_only_official_pinned_major_actions() -> None:
    workflow_text = CI_WORKFLOW.read_text(encoding="utf-8") + E2E_WORKFLOW.read_text(encoding="utf-8")
    action_references = [
        line.strip().removeprefix("- uses: ")
        for line in workflow_text.splitlines()
        if line.strip().startswith("- uses: ")
    ]

    assert action_references
    assert set(action_references).issubset(
        {
            "actions/checkout@v4",
            "actions/setup-python@v5",
            "actions/setup-node@v4",
            "actions/upload-artifact@v4",
        },
    )


def test_ci_uses_disposable_values_without_production_secret_sources() -> None:
    workflow_text = CI_WORKFLOW.read_text(encoding="utf-8") + E2E_WORKFLOW.read_text(encoding="utf-8")

    assert "ci-only-postgres-password" in workflow_text
    assert "ci-only-jwt-secret" in workflow_text
    assert "${{ secrets." not in workflow_text
    assert "/run/secrets" not in workflow_text
    assert ".env" not in workflow_text


def test_linux_e2e_runner_generates_and_redacts_disposable_credentials() -> None:
    script = LINUX_E2E_RUNNER.read_text(encoding="utf-8")

    assert "openssl rand" in script
    assert "E2E_COMPOSE_PROJECT" in script
    assert "docker compose" in script
    assert "alembic -c alembic.ini upgrade head" in script
    assert "npm run e2e:smoke" in script
    assert "[REDACTED]" in script
    assert "compose down -v --remove-orphans" in script
    assert "set -x" not in script


def test_ci_disables_sensitive_playwright_traces_and_ignores_artifacts() -> None:
    playwright_config = (ROOT_DIR / "frontend" / "playwright.config.js").read_text(encoding="utf-8")
    gitignore = (ROOT_DIR / ".gitignore").read_text(encoding="utf-8")

    assert 'trace: isCi ? "off" : "retain-on-failure"' in playwright_config
    assert 'video: isCi ? "off" : "retain-on-failure"' in playwright_config
    assert "frontend/playwright-report/" in gitignore
    assert "frontend/test-results/" in gitignore
    assert "frontend/blob-report/" in gitignore

def test_ci_e2e_contract_keeps_six_flows_owner_scoping_and_help_navigation() -> None:
    spec = E2E_SMOKE_SPEC.read_text(encoding="utf-8")

    assert spec.count('  test("') == 6
    assert 'test.describe.serial("MVP browser smoke"' in spec
    assert "owner publishes future availability and sees it in own list" in spec
    assert 'getByLabel("Parking spot ID")).toHaveCount(0)' in spec
    assert 'getByText(state.spot.code + " - " + state.spot.location)' in spec
    assert 'getByRole("link", { name: "Help" })' in spec
    assert "toHaveURL(/\\/help$/)" in spec
