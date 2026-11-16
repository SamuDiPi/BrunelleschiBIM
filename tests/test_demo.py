"""The Phase 1 demonstration, end to end (milestone M7).

Runs ``examples/phase1_demo.py`` and the command-line session for this platform
(``phase1_demo.ps1`` on Windows, ``phase1_demo.sh`` elsewhere) as real processes, then
checks what they wrote: the model, the IFC files before and after raising the first
floor, and the plans.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape
import pytest

from brunelleschi import api
from brunelleschi.ifc import validate_ifc

EXAMPLES = Path(__file__).parent.parent / "examples"


def run(args: list[str]) -> str:
    # The scripts call `bbim`; put this environment's executables first on the PATH.
    env = dict(os.environ)
    scripts = Path(sys.executable).parent
    env["PATH"] = f"{scripts}{os.pathsep}{env.get('PATH', '')}"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", env=env, check=False
    )
    assert result.returncode == 0, f"{args[0]} failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout


def wall_tops(path: Path) -> list[float]:
    f: Any = ifcopenshell.open(str(path))
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    tops = []
    for wall in f.by_type("IfcWall"):
        shape: Any = ifcopenshell.geom.create_shape(settings, wall)
        vertices = ifcopenshell.util.shape.get_vertices(shape.geometry)
        tops.append(round(float(ifcopenshell.util.shape.get_bbox(vertices)[1][2]), 6))
    return tops


def storey_elevations(path: Path) -> dict[str, float]:
    f: Any = ifcopenshell.open(str(path))
    return {s.Name: s.Elevation for s in f.by_type("IfcBuildingStorey")}


def check_outputs(folder: Path) -> None:
    """What every form of the demonstration must produce."""
    project = api.load(folder / "casa.bbim")
    assert [lv.name for lv in project.levels] == ["Piano terra", "Primo piano"]
    assert len(project.walls) == 4
    assert (len(project.doors), len(project.windows)) == (1, 1)
    geometry = api.wall_geometry(project)
    assert [str(j.kind) for j in geometry.joins] == ["mitre"] * 4
    assert geometry.issues == ()
    # After: the first floor is at 3.20 and every wall bound to it follows.
    assert project.level("Primo piano").elevation == 3.2
    assert {round(project.wall_z_range(w)[1], 9) for w in project.walls} == {3.2}

    before, after = folder / "casa-before.ifc", folder / "casa-after.ifc"
    assert storey_elevations(before) == {"Piano terra": 0.0, "Primo piano": 3.0}
    assert storey_elevations(after) == {"Piano terra": 0.0, "Primo piano": 3.2}
    assert wall_tops(before) == [3.0] * 4
    assert wall_tops(after) == [3.2] * 4
    for path in (before, after):
        assert validate_ifc(path).issues == ()
    ids_before = {e.GlobalId for e in ifcopenshell.open(str(before)).by_type("IfcRoot")}
    ids_after = {e.GlobalId for e in ifcopenshell.open(str(after)).by_type("IfcRoot")}
    assert ids_before == ids_after  # the same building, changed: same identities

    # The ground floor plan is cut at 1.20 m: raising the floor above does not change it.
    plan_before = (folder / "casa-before.svg").read_text(encoding="utf-8")
    assert plan_before == (folder / "casa-after.svg").read_text(encoding="utf-8")
    assert 'width="297mm" height="210mm"' in plan_before
    for layer in ("door", "door-swing", "window"):
        assert f'<g id="{layer}"' in plan_before


def test_script(tmp_path: Path) -> None:
    out = run([sys.executable, str(EXAMPLES / "phase1_demo.py"), str(tmp_path)])
    assert "before: 'Primo piano' at +3.00 m, wall tops at [3.0] m" in out
    assert "after : 'Primo piano' at +3.20 m, wall tops at [3.2] m" in out
    assert out.count("(0 validation issues)") == 2
    check_outputs(tmp_path)


def _cli_session() -> list[str] | None:
    if os.name == "nt":
        shell = shutil.which("powershell") or shutil.which("pwsh")
        script = EXAMPLES / "phase1_demo.ps1"
        return (
            [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
            if shell
            else None
        )
    shell = shutil.which("sh")
    return [shell, str(EXAMPLES / "phase1_demo.sh")] if shell else None


def test_cli_session(tmp_path: Path) -> None:
    command = _cli_session()
    if command is None:
        pytest.skip("no shell to run the command-line session")
    out = run([*command, str(tmp_path)])
    assert "moved level 'Primo piano' from +3.000 m to +3.200 m" in out
    assert "4 wall(s) follow" in out
    assert out.count("valid IFC4 (schema and rules)") == 2
    check_outputs(tmp_path)
