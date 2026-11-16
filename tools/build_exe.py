"""Build BrunelleschiBIM.exe with PyInstaller (ADR 0009), and check it.

    uv run --group build python tools/build_exe.py           build dist/BrunelleschiBIM/
    uv run --group build python tools/build_exe.py --check   build, then run its self-tests

The check runs the packaged program the way a user's machine would: no Python on the PATH,
no console window, a hard timeout, output only into files. It never shows a window.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "BrunelleschiBIM"
DIST = ROOT / "dist"
WORK = ROOT / "build" / "pyinstaller"


def _express_dir() -> Path:
    spec = importlib.util.find_spec("ifcopenshell")
    assert spec is not None and spec.origin is not None, "ifcopenshell is not installed"
    return Path(spec.origin).parent / "express"


def build() -> Path:
    express = _express_dir()
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", NAME,
        "--distpath", str(DIST), "--workpath", str(WORK), "--specpath", str(WORK),
        # IfcOpenShell: data files, schema rule modules, and the parser module its express
        # package would otherwise generate by relaunching sys.executable (ADR 0009).
        "--collect-all", "ifcopenshell",
        "--paths", str(express),
        "--hidden-import", "codegen",
        "--hidden-import", "express_parser",
        "--add-data", f"{express / 'express_parser.py'}{os.pathsep}ifcopenshell/express",
        "--collect-data", "ezdxf",
        str(ROOT / "packaging" / "entry.py"),
    ]  # fmt: skip
    start = time.perf_counter()
    subprocess.run(args, check=True, cwd=ROOT)
    exe = DIST / NAME / f"{NAME}.exe"
    size = sum(f.stat().st_size for f in (DIST / NAME).rglob("*") if f.is_file()) / 2**20
    print(f"built {exe} in {time.perf_counter() - start:.0f} s, folder {size:.0f} MB")
    return exe


def _run_isolated(exe: Path, args: list[str], timeout: float = 120) -> tuple[int | None, float]:
    """Run without Python on the PATH and without a console; kill the tree on timeout."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() not in ("PATH", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "QT_PLUGIN_PATH")
    }
    env["PATH"] = os.pathsep.join(
        str(Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / p) for p in ("System32", "")
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    start = time.perf_counter()
    with tempfile.TemporaryFile() as out:
        process = subprocess.Popen(
            [str(exe), *args], env=env, stdout=out, stderr=out, creationflags=flags
        )
        while process.poll() is None and time.perf_counter() - start < timeout:
            time.sleep(0.05)
        if process.poll() is None:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False
            )
            return None, time.perf_counter() - start
    return process.returncode, time.perf_counter() - start


def check(exe: Path) -> bool:
    ok = True
    folder = Path(tempfile.mkdtemp(prefix="bbim-selftest-"))
    for mode in ("--selftest", "--selftest-gl"):
        out = folder / mode.strip("-")
        code, seconds = _run_isolated(exe, [mode, str(out)])
        report_file = out / "report.json"
        if code is None:
            print(f"{mode}: TIMEOUT after {seconds:.0f} s (process tree killed)")
            ok = False
            continue
        if not report_file.is_file():
            print(f"{mode}: exit {code} in {seconds:.1f} s, no report (see the crash log)")
            ok = False
            continue
        report = json.loads(report_file.read_text(encoding="utf-8"))
        print(f"{mode}: exit {code} in {seconds:.1f} s, frozen={report['frozen']}")
        for name, result in report["checks"].items():
            mark = "ok  " if result["passed"] else "FAIL"
            print(f"  {mark} {name:<10} {result['result']}  ({result['seconds']} s)")
        for name, trace in report.get("tracebacks", {}).items():
            print(f"--- {name}\n{trace}")
        ok = ok and code == 0
    # Unknown arguments must be refused without a window, quickly.
    code, seconds = _run_isolated(exe, ["bootstrap.py"], timeout=30)
    print(f"unknown argument: exit {code} in {seconds:.1f} s (expected 2)")
    ok = ok and code == 2
    print(f"outputs in {folder}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BrunelleschiBIM.exe.")
    parser.add_argument("--check", action="store_true", help="run the self-tests afterwards")
    parser.add_argument("--no-build", action="store_true", help="only check an existing build")
    args = parser.parse_args()
    if shutil.which("pyinstaller") is None and importlib.util.find_spec("PyInstaller") is None:
        print("PyInstaller is missing: run with `uv run --group build`", file=sys.stderr)
        return 2
    exe = DIST / NAME / f"{NAME}.exe" if args.no_build else build()
    if args.check or args.no_build:
        return 0 if check(exe) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
