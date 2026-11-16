"""The command-line tool starts and reports its version."""

from __future__ import annotations

import re
import subprocess
import sys

import pytest

import brunelleschi
from brunelleschi.cli import main


def test_package_has_a_real_version() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+.*", brunelleschi.__version__)
    assert "unknown" not in brunelleschi.__version__


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"bbim {brunelleschi.__version__}"


def test_no_arguments_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: bbim" in capsys.readouterr().out


def test_unknown_option_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--no-such-option"])
    assert exit_info.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_module_runs_as_a_program() -> None:
    """The installed package works as a real process, not only when imported."""
    result = subprocess.run(
        [sys.executable, "-m", "brunelleschi.cli", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == f"bbim {brunelleschi.__version__}"
