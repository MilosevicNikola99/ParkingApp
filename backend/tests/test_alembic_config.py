from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


BACKEND_DIR = Path(__file__).resolve().parents[1]


def make_alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


def test_alembic_config_points_to_backend_migration_directory() -> None:
    config = make_alembic_config()
    script = ScriptDirectory.from_config(config)

    assert Path(script.dir).resolve() == BACKEND_DIR / "alembic"


def test_alembic_current_head_preserves_cancelled_reservation_history() -> None:
    script = ScriptDirectory.from_config(make_alembic_config())
    revision = script.get_revision("0010")

    assert script.get_current_head() == "0010"
    assert revision is not None
    assert revision.down_revision == "0009"
    assert callable(revision.module.upgrade)
    assert callable(revision.module.downgrade)


def test_alembic_offline_upgrade_loads_environment_without_database(capsys) -> None:
    command.upgrade(make_alembic_config(), "head", sql=True)

    output = capsys.readouterr().out

    assert "CREATE TABLE alembic_version" in output
    assert output.count("CREATE TYPE user_role AS ENUM") == 1
    assert "CREATE TABLE teams" in output
    assert "CREATE TABLE users" in output
    assert "CREATE TABLE parking_spots" in output
    assert "CREATE TYPE parking_availability_status AS ENUM" in output
    assert "CREATE TABLE parking_availabilities" in output
    assert "CREATE TYPE parking_application_status AS ENUM" in output
    assert "CREATE TABLE parking_applications" in output
    assert "uq_parking_applications_availability_id_applicant_id" in output
    assert "ix_parking_applications_availability_status" in output
    assert "CREATE TYPE parking_reservation_status AS ENUM" in output
    assert "CREATE TABLE parking_reservations" in output
    assert "uq_parking_reservations_availability_id" in output
    assert "uq_parking_reservations_application_id" in output
    assert "ix_parking_reservations_spot_start_end" in output
    assert "ix_parking_reservations_user_status" in output
    assert "CREATE TYPE parking_assignment_trigger_source AS ENUM" in output
    assert "CREATE TABLE parking_assignment_audit_logs" in output
    assert "uq_parking_assignment_audit_logs_reservation_id" in output
    assert "ix_parking_assignment_audit_logs_availability_id" in output
    assert "ix_parking_assignment_audit_logs_reservation_id" in output
    assert "ix_parking_assignment_audit_logs_selected_user_id" in output
    assert "ix_parking_assignment_audit_logs_created_at" in output
    assert "ALTER TYPE parking_assignment_trigger_source ADD VALUE IF NOT EXISTS 'admin_override'" in output
    assert (
        "ALTER TABLE parking_assignment_audit_logs DROP CONSTRAINT "
        "uq_parking_assignment_audit_logs_reservation_id"
    ) in output
    assert (
        "ALTER TABLE parking_reservations DROP CONSTRAINT "
        "uq_parking_reservations_availability_id"
    ) in output
    assert (
        "CREATE UNIQUE INDEX uq_parking_reservations_active_availability_id "
        "ON parking_reservations (availability_id) WHERE status = 'active'"
    ) in output
    assert "ix_parking_availabilities_status_start_at" in output
    assert "ix_parking_availabilities_spot_start_end" in output
    assert "ix_parking_spots_code" in output
    assert "ix_parking_spots_owner_id" in output
    assert "0010" in output
