import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT_DIR / "scripts"
POWERSHELL_EXECUTABLE = shutil.which("powershell.exe") or shutil.which("pwsh")


def run_powershell(*args: str) -> subprocess.CompletedProcess[str]:
    if POWERSHELL_EXECUTABLE is None:
        raise RuntimeError("PowerShell executable not found")

    return subprocess.run(
        [POWERSHELL_EXECUTABLE, "-NoProfile", "-ExecutionPolicy", "Bypass", *args],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def test_postgres_backup_scripts_parse_successfully() -> None:
    script_paths = [
        SCRIPTS_DIR / "postgres_backup_common.ps1",
        SCRIPTS_DIR / "backup_postgres.ps1",
        SCRIPTS_DIR / "verify_postgres_backup.ps1",
        SCRIPTS_DIR / "restore_postgres.ps1",
    ]
    command = (
        "$ErrorActionPreference = 'Stop'; "
        "$files = @("
        + ",".join(f"'{path}'" for path in script_paths)
        + "); "
        "foreach ($file in $files) { "
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile($file, [ref]$tokens, [ref]$errors) | Out-Null; "
        "if ($errors.Count -gt 0) { throw ($errors | Out-String) } "
        "}"
    )

    result = run_powershell("-Command", command)

    assert result.returncode == 0, result.stderr


def test_compose_command_detection_supports_standalone_and_plugin() -> None:
    common_script = (SCRIPTS_DIR / "postgres_backup_common.ps1").read_text(encoding="utf-8")

    assert "function Resolve-ComposeCommand" in common_script
    assert "docker-compose" in common_script
    assert "docker compose" in common_script
    assert "Neither docker-compose nor docker compose is available." in common_script


def test_backup_filename_generation_is_timestamped_and_includes_database_name() -> None:
    common_script = SCRIPTS_DIR / "postgres_backup_common.ps1"
    command = (
        f". '{common_script}'; "
        "$timestamp = [datetime]::Parse('2026-06-20T12:34:56Z').ToUniversalTime(); "
        "New-PostgresBackupFileName -DatabaseName 'parking-app' -TimestampUtc $timestamp"
    )

    result = run_powershell("-Command", command)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "parking-app_20260620T123456Z.pgdump"


def test_native_process_helpers_work_with_available_powershell(tmp_path: Path) -> None:
    assert POWERSHELL_EXECUTABLE is not None

    common_script = SCRIPTS_DIR / "postgres_backup_common.ps1"
    output_file = tmp_path / "native-output.txt"
    input_file = tmp_path / "native-input.txt"
    input_file.write_text("input text", encoding="utf-8")
    powershell_path = POWERSHELL_EXECUTABLE.replace("'", "''")
    powershell_name = Path(POWERSHELL_EXECUTABLE).name.replace("'", "''")
    command = (
        f". '{common_script}'; "
        f"$ps = '{powershell_path}'; "
        "$cmd = [pscustomobject]@{ "
        "Executable = $ps; "
        "Prefix = @('-NoProfile', '-Command'); "
        f"DisplayName = '{powershell_name}' "
        "}; "
        f"Invoke-NativeToFile -ComposeCommand $cmd -CommandArguments @('[Console]::Out.Write(\"ok\")') -OutputFile '{output_file}'; "
        f"$inputResult = Invoke-NativeWithInputFileText -ComposeCommand $cmd -CommandArguments @('[Console]::Out.Write([Console]::In.ReadToEnd())') -InputFile '{input_file}'; "
        f"if ((Get-Content -LiteralPath '{output_file}' -Raw) -ne 'ok') {{ throw 'output helper failed' }}; "
        "if ($inputResult -ne 'input text') { throw 'input helper failed' }; "
        "Write-Host 'helpers ok'"
    )

    result = run_powershell("-Command", command)

    assert result.returncode == 0, result.stderr
    assert "helpers ok" in result.stdout


def test_backup_script_rejects_output_directory_that_is_file(tmp_path: Path) -> None:
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("content", encoding="utf-8")

    result = run_powershell(
        "-File",
        str(SCRIPTS_DIR / "backup_postgres.ps1"),
        "-PlanOnly",
        "-OutputDirectory",
        str(output_file),
    )

    assert result.returncode != 0
    assert "Output directory path points to a file" in (result.stderr + result.stdout)


def test_verify_script_rejects_missing_backup_file(tmp_path: Path) -> None:
    result = run_powershell(
        "-File",
        str(SCRIPTS_DIR / "verify_postgres_backup.ps1"),
        "-BackupFile",
        str(tmp_path / "missing.pgdump"),
        "-SkipArchiveValidation",
    )

    assert result.returncode != 0
    assert "Backup file does not exist" in (result.stderr + result.stdout)


def test_verify_script_rejects_empty_backup_file(tmp_path: Path) -> None:
    backup_file = tmp_path / "empty.pgdump"
    backup_file.write_bytes(b"")

    result = run_powershell(
        "-File",
        str(SCRIPTS_DIR / "verify_postgres_backup.ps1"),
        "-BackupFile",
        str(backup_file),
        "-SkipArchiveValidation",
    )

    assert result.returncode != 0
    assert "Backup file is empty" in (result.stderr + result.stdout)


def test_destructive_restore_requires_confirmation(tmp_path: Path) -> None:
    result = run_powershell(
        "-File",
        str(SCRIPTS_DIR / "restore_postgres.ps1"),
        "-BackupFile",
        str(tmp_path / "missing.pgdump"),
        "-Mode",
        "ExistingDatabase",
        "-TargetDatabase",
        "parking_restore",
    )

    assert result.returncode != 0
    assert "requires -ConfirmDestructive" in (result.stderr + result.stdout)


def test_production_restore_requires_explicit_flag(tmp_path: Path) -> None:
    result = run_powershell(
        "-File",
        str(SCRIPTS_DIR / "restore_postgres.ps1"),
        "-BackupFile",
        str(tmp_path / "missing.pgdump"),
        "-Environment",
        "production",
        "-TargetDatabase",
        "parking_restore",
    )

    assert result.returncode != 0
    assert "Production restore requires -AllowProductionRestore" in (result.stderr + result.stdout)


def test_retention_dry_run_does_not_delete_matching_backups(tmp_path: Path) -> None:
    backup_file = tmp_path / "parking_app_20200101T000000Z.pgdump"
    backup_file.write_text("backup", encoding="utf-8")
    old_time = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
    backup_file.touch()
    import os

    os.utime(backup_file, (old_time, old_time))

    result = run_powershell(
        "-File",
        str(SCRIPTS_DIR / "backup_postgres.ps1"),
        "-RetentionOnly",
        "-RetentionDays",
        "0",
        "-DryRunRetention",
        "-OutputDirectory",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    assert backup_file.exists()
    assert "retention dry-run would delete" in result.stdout


def test_retention_deletes_only_generated_backup_name_pattern(tmp_path: Path) -> None:
    generated_backup = tmp_path / "parking_app_20200101T000000Z.pgdump"
    generated_metadata = tmp_path / "parking_app_20200101T000000Z.pgdump.metadata.json"
    nonmatching_file = tmp_path / "manual-important.dump"
    generated_backup.write_text("backup", encoding="utf-8")
    generated_metadata.write_text("{}", encoding="utf-8")
    nonmatching_file.write_text("keep", encoding="utf-8")
    old_time = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
    import os

    for path in (generated_backup, generated_metadata, nonmatching_file):
        os.utime(path, (old_time, old_time))

    result = run_powershell(
        "-File",
        str(SCRIPTS_DIR / "backup_postgres.ps1"),
        "-RetentionOnly",
        "-RetentionDays",
        "0",
        "-OutputDirectory",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    assert not generated_backup.exists()
    assert not generated_metadata.exists()
    assert nonmatching_file.exists()


def test_backup_metadata_fields_exclude_secret_names() -> None:
    backup_script = (SCRIPTS_DIR / "backup_postgres.ps1").read_text(encoding="utf-8")
    metadata_block = backup_script.split("$metadata = [ordered]@{", 1)[1].split("}", 1)[0]

    assert "Test-Path -LiteralPath $backupPath -and" not in backup_script
    assert "password" not in metadata_block.lower()
    assert "secret" not in metadata_block.lower()
    assert "database_url" not in metadata_block.lower()
    assert "sha256" in metadata_block
    assert "alembicCurrentRevision" in metadata_block


def test_checksum_verification_detects_modified_backup(tmp_path: Path) -> None:
    backup_file = tmp_path / "parking_app_20260620T123456Z.pgdump"
    original_content = b"original backup content"
    backup_file.write_bytes(original_content)
    metadata = {
        "backupFilename": backup_file.name,
        "sha256": hashlib.sha256(original_content).hexdigest(),
    }
    (tmp_path / f"{backup_file.name}.metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )
    backup_file.write_bytes(b"modified backup content")

    result = run_powershell(
        "-File",
        str(SCRIPTS_DIR / "verify_postgres_backup.ps1"),
        "-BackupFile",
        str(backup_file),
        "-SkipArchiveValidation",
    )

    assert result.returncode != 0
    assert "checksum does not match metadata" in (result.stderr + result.stdout)
