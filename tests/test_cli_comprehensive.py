from __future__ import annotations

import runpy
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cli.commands import main, parser, write_atomic
from ghtoolkit import GitHubError
from report.data_classes import DailyReport


def test_write_atomic_writes_content_correctly(tmp_path: Path):
    target = tmp_path / "sub" / "dir" / "file.txt"
    write_atomic(target, "Hello atomic world!")
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == "Hello atomic world!"


def test_write_atomic_cleans_up_temp_file_on_write_failure(tmp_path: Path):
    target = tmp_path / "target.txt"

    class FailingFile:
        def __init__(self, *args, **kwargs):
            self.name = str(tmp_path / "failing_temp_file.tmp")
            Path(self.name).write_text("temporary content", encoding="utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def write(self, content):
            raise IOError("Disk full simulation")

    with patch("tempfile.NamedTemporaryFile", side_effect=FailingFile):
        with pytest.raises(IOError, match="Disk full"):
            write_atomic(target, "some content")

    assert not target.exists()
    assert not (tmp_path / "failing_temp_file.tmp").exists()


def test_write_atomic_cleans_up_temp_file_on_replace_failure(tmp_path: Path):
    target = tmp_path / "target.txt"

    with patch("os.replace", side_effect=OSError("Replace failed simulation")):
        with pytest.raises(OSError, match="Replace failed"):
            write_atomic(target, "some content")

    assert not target.exists()


def test_parser_parses_all_arguments_and_flags():
    p = parser()
    args = p.parse_args(
        [
            "2026-10-24",
            "--config",
            "cfg.json",
            "--repo",
            "org/repo1",
            "--repo",
            "org/repo2",
            "--author",
            "john",
            "--alias",
            "alias1",
            "--alias",
            "alias2",
            "--timezone",
            "Asia/Karachi",
            "--shift-start",
            "09:00",
            "--shift-end",
            "18:00",
            "--day-start",
            "06:00",
            "--workers",
            "4",
            "--manual-tasks",
            "tasks.json",
            "--snapshot",
            "snap.json",
            "--ai",
            "--model",
            "gemini-2.5-flash",
            "--ai-failure",
            "keep-raw",
            "--format",
            "office",
            "--output",
            "out.txt",
            "--chunks-output",
            "chunks.jsonl",
        ]
    )

    assert args.date == "2026-10-24"
    assert args.config == Path("cfg.json")
    assert args.repositories == ["org/repo1", "org/repo2"]
    assert args.author == "john"
    assert args.author_aliases == ["alias1", "alias2"]
    assert args.timezone == "Asia/Karachi"
    assert args.shift_start == "09:00"
    assert args.shift_end == "18:00"
    assert args.day_start == "06:00"
    assert args.workers == 4
    assert args.manual_tasks == "tasks.json"
    assert args.snapshot == "snap.json"
    assert args.ai is True
    assert args.model == "gemini-2.5-flash"
    assert args.ai_failure == "keep-raw"
    assert args.format == "office"
    assert args.output == Path("out.txt")
    assert args.chunks_output == Path("chunks.jsonl")


def test_main_with_output_and_chunks_output_files(tmp_path: Path):
    output_file = tmp_path / "report.txt"
    chunks_file = tmp_path / "chunks.jsonl"

    fake_report = MagicMock(spec=DailyReport)
    fake_report.chunks = ()

    with (
        patch("cli.commands.generate_report", return_value=fake_report) as mock_gen,
        patch("cli.commands.format_office_status", return_value="STATUS (24-OCT-2026)\n"),
        patch("cli.commands.render_pr_chunks", return_value='{"kind": "pr"}\n'),
    ):
        code = main(
            [
                "2026-10-24",
                "--repo",
                "org/repo",
                "--author",
                "alice",
                "--shift-start",
                "09:00",
                "--shift-end",
                "18:00",
                "--output",
                str(output_file),
                "--chunks-output",
                str(chunks_file),
            ]
        )

    assert code == 0
    mock_gen.assert_called_once()
    assert output_file.read_text() == "STATUS (24-OCT-2026)\n"
    assert chunks_file.read_text() == '{"kind": "pr"}\n'


@pytest.mark.parametrize(
    "exc_type, exc_msg",
    [
        (GitHubError, "GitHub API unavailable"),
        (ValueError, "Invalid argument value"),
        (TypeError, "Unexpected argument type"),
        (KeyError, "Missing required key"),
        (OSError, "File not found on filesystem"),
        (RuntimeError, "AI summarization runtime error"),
    ],
)
def test_main_catches_all_documented_exceptions(exc_type, exc_msg, capsys):
    with patch("cli.commands.generate_report", side_effect=exc_type(exc_msg)):
        code = main(
            [
                "2026-10-24",
                "--repo",
                "org/repo",
                "--author",
                "alice",
                "--shift-start",
                "09:00",
                "--shift-end",
                "18:00",
            ]
        )

    assert code == 1
    err = capsys.readouterr().err
    assert "Report failed:" in err
    assert exc_msg in err


def test_cli_commands_main_block_invocation():
    commands_path = str(Path(__file__).parents[1] / "src" / "cli" / "commands.py")
    with patch("cli.commands.main", return_value=0) as mock_main:
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_path(commands_path, run_name="__main__")
        assert exc_info.value.code == 0
        mock_main.assert_called_once()
