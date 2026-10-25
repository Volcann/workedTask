import ast
import json
from pathlib import Path

import pytest
from cli.commands import main
from ghtoolkit import write_snapshot


def configure(tmp_path, activity, schedule):
    snapshot = tmp_path / "snapshot.json"
    write_snapshot(snapshot, "alice", schedule.window, (activity,))
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "repositories": ["acme/widget"],
                "author": "alice",
                "timezone": "Asia/Karachi",
                "shift_start": "09:00",
                "shift_end": "18:00",
                "day_start": "06:00",
                "snapshot": str(snapshot),
            }
        )
    )
    return config


def test_cli_writes_report_and_per_pr_jsonl_without_network(tmp_path, activity, schedule):
    config = configure(tmp_path, activity, schedule)
    output = tmp_path / "report.txt"
    chunks = tmp_path / "chunks.jsonl"
    status = main(
        [
            "2026-10-24",
            "--config",
            str(config),
            "--output",
            str(output),
            "--format",
            "office",
            "--chunks-output",
            str(chunks),
        ]
    )
    assert status == 0
    assert "STATUS (24-OCT-2026)" in output.read_text()
    assert len(chunks.read_text().splitlines()) == 4


def test_cli_output_to_stdout(tmp_path, activity, schedule, capsys):
    config = configure(tmp_path, activity, schedule)
    assert main(["2026-10-24", "--config", str(config)]) == 0
    out = capsys.readouterr()
    assert "STATUS (24-OCT-2026)" in out.out
    assert "HR-Tool" in out.out
    assert "(The task is done in extra time)" in out.out
    assert out.err == ""


def test_cli_office_format_output(tmp_path, activity, schedule, capsys):
    config = configure(tmp_path, activity, schedule)
    assert main(["2026-10-24", "--config", str(config), "--format", "office"]) == 0
    out = capsys.readouterr()
    assert "STATUS (24-OCT-2026)" in out.out
    assert "HR-Tool" in out.out
    assert out.err == ""


def test_cli_rejects_unsupported_formats(tmp_path, activity, schedule, capsys):
    config = configure(tmp_path, activity, schedule)
    for bad_format in ("markdown", "json", "html"):
        with pytest.raises(SystemExit) as exc_info:
            main(["2026-10-24", "--config", str(config), "--format", bad_format])
        assert exc_info.value.code == 2
        err = capsys.readouterr().err
        assert "invalid choice" in err


def test_failed_cli_preserves_existing_report(tmp_path, activity, schedule, capsys):
    config = configure(tmp_path, activity, schedule)
    output = tmp_path / "report.md"
    output.write_text("Keep existing report")
    assert main(["2026-10-25", "--config", str(config), "--output", str(output)]) == 1
    assert output.read_text() == "Keep existing report"
    assert "does not match" in capsys.readouterr().err


def test_cli_requires_actual_shift_hours(tmp_path, capsys):
    assert main(["2026-10-24", "--repo", "acme/widget", "--author", "alice"]) == 1
    assert "cannot be inferred" in capsys.readouterr().err


def test_cli_invalid_date_does_not_create_output(tmp_path, activity, schedule):
    config = configure(tmp_path, activity, schedule)
    output = tmp_path / "report.md"
    assert main(["not-a-date", "--config", str(config), "--output", str(output)]) == 1
    assert not output.exists()


def test_cli_rejects_timezone_free_manual_tasks(tmp_path, activity, schedule, capsys):
    config = configure(tmp_path, activity, schedule)
    manual = tmp_path / "manual.json"
    manual.write_text(json.dumps([{"id": "x", "title": "Task", "completed_at": "2026-10-24T12:00:00"}]))
    assert main(["2026-10-24", "--config", str(config), "--manual-tasks", str(manual)]) == 1
    assert "timezone offset" in capsys.readouterr().err


def test_no_github_sdk_http_or_shell_implementation_in_worked_task():
    roots = [
        Path(__file__).parents[1] / "src" / "cli",
        Path(__file__).parents[1] / "src" / "report",
        Path(__file__).parents[1] / "src" / "ai",
        Path(__file__).parents[1] / "config",
    ]
    prohibited = {"githubkit", "requests", "httpx", "urllib", "subprocess", "github"}
    failures = []
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text()
            tree = ast.parse(text)
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [(node.module or "").split(".")[0]]
                if prohibited.intersection(names):
                    failures.append(str(path))
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and ("api.github.com" in node.value or "gh api" in node.value or "/repos/{" in node.value)
                ):
                    failures.append(str(path))
    assert failures == []


def test_no_gh_cli_fallback_in_new_toolkit():
    root = Path(__file__).parents[2] / "ghToolkit" / "src" / "ghtoolkit"
    assert root.is_dir()
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name != "subprocess" for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module != "subprocess"
