"""What the packaged program relies on, tested in the development environment: the crash
log and the self-test. The executable itself is built and checked by tools/build_exe.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from brunelleschi.gui import crash

REPO = Path(__file__).parent.parent


def test_crash_log_is_written(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    try:
        raise ValueError("something unexpected")
    except ValueError as exc:
        log = crash.write_crash_log(type(exc), exc, exc.__traceback__)
    assert log is not None
    assert log.parent == tmp_path / "BrunelleschiBIM" / "logs"
    text = log.read_text(encoding="utf-8")
    assert text.startswith("BrunelleschiBIM ")
    assert "ValueError: something unexpected" in text
    assert "test_crash_log_is_written" in text  # the traceback is there
    message = crash.message(ValueError("x"), log)
    assert str(log) in message


def test_hook_logs_without_showing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    shown: list[str] = []
    monkeypatch.setattr(crash, "show_message", shown.append)
    old = sys.excepthook
    try:
        crash.install(show=False)
        sys.excepthook(RuntimeError, RuntimeError("in a slot"), None)
        crash.install(show=True)
        sys.excepthook(RuntimeError, RuntimeError("again"), None)
    finally:
        sys.excepthook = old
    assert len(list((tmp_path / "BrunelleschiBIM" / "logs").glob("crash-*.log"))) >= 1
    assert len(shown) == 1 and "again" in shown[0]


def test_selftest_passes_in_development(tmp_path: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
    result = subprocess.run(
        [sys.executable, "-m", "brunelleschi.gui.selftest", "--selftest", str(tmp_path)],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert result.returncode == 0, json.dumps(report, indent=2)
    assert report["passed"] is True
    assert set(report["checks"]) == {"save", "ifc", "reference", "svg", "dxf", "window"}
    assert (tmp_path / "window.png").is_file()


def test_entry_refuses_unknown_arguments() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO / "packaging" / "entry.py"), "bootstrap.py"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert result.returncode == 2
    assert "unexpected arguments" in result.stderr
