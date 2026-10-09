"""Tests for CLI arguments, subcommands, output files, and execution paths."""

from __future__ import annotations

from pathlib import Path

from cli.commands import main


def test_cli_demo_1_creates_file(tmp_path: Path) -> None:
    out_file = tmp_path / "test_out_1.txt"
    code = main(["--demo", "1", "--output", str(out_file)])
    assert code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "STATUS (11-SEP-2026)" in content
    assert "HR-Tool" in content
    assert "Backend PR:" in content
    assert "Frontend PR:" in content


def test_cli_demo_2_creates_file(tmp_path: Path) -> None:
    out_file = tmp_path / "test_out_2.txt"
    code = main(["--demo", "2", "--output", str(out_file)])
    assert code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "STATUS (16-SEP-2026)" in content
    assert "Reviewed PRs:" in content
    assert "MB-228: Payroll run" in content


def test_cli_demo_3_creates_file(tmp_path: Path) -> None:
    out_file = tmp_path / "test_out_3.txt"
    code = main(["--demo", "3", "--output", str(out_file)])
    assert code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "STATUS (22-SEP-2026)" in content
    assert "HMT-291 | Backend issues" in content


def test_cli_invalid_date() -> None:
    code = main(["--date", "not-a-valid-date"])
    assert code == 1


def test_cli_projects_subcommands(tmp_path: Path) -> None:
    config_file = tmp_path / "test_projects.json"
    # 1. Add
    code_add = main(
        [
            "projects",
            "add",
            "--name",
            "SeedFunds",
            "--owner",
            "seedfunds",
            "--repo",
            "backend",
            "--category",
            "Backend",
            "--config",
            str(config_file),
        ]
    )
    assert code_add == 0

    # 2. List
    code_list = main(["projects", "list", "--config", str(config_file)])
    assert code_list == 0

    # 3. Remove
    code_rem = main(
        [
            "projects",
            "remove",
            "--owner",
            "seedfunds",
            "--repo",
            "backend",
            "--config",
            str(config_file),
        ]
    )
    assert code_rem == 0


def test_cli_clean_reports_default_keeps_latest(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    f1 = reports_dir / "status_report_11_SEP_2026.txt"
    f2 = reports_dir / "status_report_24_SEP_2026.txt"
    f3 = reports_dir / "status_report_23_SEP_20268.txt"
    f1.write_text("old 1", encoding="utf-8")
    f3.write_text("old 2", encoding="utf-8")
    f2.write_text("active report", encoding="utf-8")

    code = main(["clean-reports", "--reports-dir", str(reports_dir)])
    assert code == 0
    assert not f1.exists()
    assert not f3.exists()
    assert f2.exists()


def test_cli_clean_reports_keep_specific_date(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    f1 = reports_dir / "status_report_11_SEP_2026.txt"
    f2 = reports_dir / "status_report_24_SEP_2026.txt"
    f1.write_text("demo 1", encoding="utf-8")
    f2.write_text("active", encoding="utf-8")

    code = main(["clean-reports", "--keep", "11-SEP-2026", "--reports-dir", str(reports_dir)])
    assert code == 0
    assert f1.exists()
    assert not f2.exists()


def test_cli_clean_reports_all(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    f1 = reports_dir / "status_report_11_SEP_2026.txt"
    f2 = reports_dir / "status_report_24_SEP_2026.txt"
    gitkeep = reports_dir / ".gitkeep"
    f1.write_text("demo 1", encoding="utf-8")
    f2.write_text("active", encoding="utf-8")
    gitkeep.write_text("", encoding="utf-8")

    code = main(["clean-reports", "--all", "--reports-dir", str(reports_dir)])
    assert code == 0
    assert not f1.exists()
    assert not f2.exists()
    assert gitkeep.exists()


def test_cli_clean_reports_dry_run(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    f1 = reports_dir / "status_report_11_SEP_2026.txt"
    f2 = reports_dir / "status_report_24_SEP_2026.txt"
    f1.write_text("demo 1", encoding="utf-8")
    f2.write_text("active", encoding="utf-8")

    code = main(["clean-reports", "--dry-run", "--reports-dir", str(reports_dir)])
    assert code == 0
    assert f1.exists()
    assert f2.exists()


def test_cli_validation_flag(tmp_path: Path) -> None:
    """CLI runs validation pipeline with --validate and can disable with --no-validate."""
    out_file = tmp_path / "val_out.txt"
    code = main(["--demo", "1", "--output", str(out_file), "--validate", "--sleep", "0.0"])
    assert code == 0
    assert out_file.exists()

    code_no_val = main(["--demo", "1", "--output", str(out_file), "--no-validate"])
    assert code_no_val == 0
