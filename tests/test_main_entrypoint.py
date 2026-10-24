from __future__ import annotations

import runpy
from pathlib import Path
from unittest.mock import patch

import pytest


def test_main_entrypoint_invokes_main_and_exits_cleanly():
    main_path = str(Path(__file__).parents[1] / "src" / "__main__.py")
    with patch("cli.commands.main", return_value=0) as mock_main:
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_path(main_path, run_name="__main__")
        assert exc_info.value.code == 0
        mock_main.assert_called_once_with()


def test_main_entrypoint_propagates_nonzero_exit_code():
    main_path = str(Path(__file__).parents[1] / "src" / "__main__.py")
    with patch("cli.commands.main", return_value=42) as mock_main:
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_path(main_path, run_name="__main__")
        assert exc_info.value.code == 42
        mock_main.assert_called_once_with()


def test_main_entrypoint_does_not_execute_when_imported_as_library():
    main_path = str(Path(__file__).parents[1] / "src" / "__main__.py")
    with patch("cli.commands.main") as mock_main:
        runpy.run_path(main_path, run_name="src.__main__")
        mock_main.assert_not_called()
