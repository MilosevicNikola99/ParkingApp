from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from collections.abc import Sequence

from app.load_validation.smoke import (
    CompletionClassification,
    LoadValidationConfig,
    LoadValidationConfigurationError,
    run_load_validation,
)


DEFAULT_ADMIN_IDENTIFIER_ENV = "LOAD_VALIDATION_ADMIN_IDENTIFIER"
DEFAULT_ADMIN_PASSWORD_ENV = "LOAD_VALIDATION_ADMIN_PASSWORD"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run bounded local API load validation against the Parking app.",
    )
    parser.add_argument(
        "--profile",
        default="smoke",
        choices=["smoke", "moderate"],
        help="Validation profile to run.",
    )
    parser.add_argument(
        "--target-base-url",
        default=os.getenv("LOAD_VALIDATION_TARGET_BASE_URL", "http://localhost:8000"),
        help="API origin root. Local targets are allowed by default.",
    )
    parser.add_argument("--seed", type=int, default=730_001, help="Deterministic random seed.")
    parser.add_argument("--concurrency", type=int, default=6, help="Worker concurrency, bounded by profile.")
    parser.add_argument("--iterations", type=int, default=1, help="Profile iterations, bounded by profile.")
    parser.add_argument(
        "--confirm-moderate",
        action="store_true",
        help="Required confirmation for the bounded moderate profile.",
    )
    parser.add_argument(
        "--global-timeout",
        type=float,
        default=120.0,
        help="Overall profile timeout in seconds.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=10.0,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("load_validation_reports") / "smoke-report.json",
        help="Sanitized JSON report path.",
    )
    parser.add_argument(
        "--markdown-report-path",
        type=Path,
        default=None,
        help="Optional sanitized Markdown report path.",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Leave disposable smoke data in the database for debugging.",
    )
    parser.add_argument(
        "--allow-non-local-target",
        action="store_true",
        help="Required for non-local API targets. Do not use against production data.",
    )
    parser.add_argument(
        "--scheduler-metrics-url",
        default=os.getenv("LOAD_VALIDATION_SCHEDULER_METRICS_URL"),
        help="Optional scheduler metrics URL, for example http://assignment-scheduler:9101/metrics.",
    )
    parser.add_argument(
        "--skip-metrics",
        action="store_true",
        help="Skip Prometheus metric snapshots.",
    )
    parser.add_argument(
        "--skip-pool-diagnostic",
        action="store_true",
        help="Skip the internal PostgreSQL pool saturation diagnostic.",
    )
    parser.add_argument(
        "--admin-identifier-env",
        default=DEFAULT_ADMIN_IDENTIFIER_ENV,
        help="Environment variable name containing the admin username or email.",
    )
    parser.add_argument(
        "--admin-password-env",
        default=DEFAULT_ADMIN_PASSWORD_ENV,
        help="Environment variable name containing the admin password.",
    )
    return parser


def config_from_args(args: argparse.Namespace) -> LoadValidationConfig:
    admin_identifier = os.getenv(args.admin_identifier_env, os.getenv("SEED_ADMIN_USERNAME", ""))
    admin_password = os.getenv(args.admin_password_env, os.getenv("SEED_ADMIN_PASSWORD", ""))
    return LoadValidationConfig(
        profile=args.profile,
        target_base_url=args.target_base_url,
        seed=args.seed,
        concurrency=args.concurrency,
        iterations=args.iterations,
        request_timeout_seconds=args.request_timeout,
        report_path=args.report_path,
        markdown_report_path=args.markdown_report_path,
        cleanup=not args.no_cleanup,
        allow_non_local_target=args.allow_non_local_target,
        admin_identifier=admin_identifier,
        admin_password=admin_password,
        confirm_moderate=args.confirm_moderate,
        global_timeout_seconds=args.global_timeout,
        scheduler_metrics_url=args.scheduler_metrics_url,
        collect_metrics=not args.skip_metrics,
        run_pool_diagnostic=not args.skip_pool_diagnostic,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = config_from_args(args)

    try:
        report = run_load_validation(config)
    except LoadValidationConfigurationError as exc:
        print(f"load validation configuration failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"load validation command failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    completion = report.get("completion_classification")
    print(f"load validation {completion}: report={config.report_path}")
    return 0 if completion == CompletionClassification.READY.value else 1


if __name__ == "__main__":
    raise SystemExit(main())
