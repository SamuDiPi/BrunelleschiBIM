"""Phase 1 demonstration, as a script.

Builds a small house through the public API, exports IFC4 and a plan in SVG, raises the
first floor by 20 cm and exports again. Every wall bound to the first floor follows.

    uv run python examples/phase1_demo.py OUTPUT_DIR

Writes casa.bbim, casa-before.ifc, casa-before.svg, casa-after.ifc and casa-after.svg.
The same scenario as a command-line session: phase1_demo.ps1 and phase1_demo.sh.
"""

from __future__ import annotations

import sys
from pathlib import Path

from brunelleschi import api
from brunelleschi.ifc import validate_ifc, write_ifc


def build() -> api.Project:
    project = api.new_project("Casa")
    ground = api.add_level(project, "Piano terra", 0.00)
    first = api.add_level(project, "Primo piano", 3.00)

    # A 6 x 4 m room: four 30 cm walls from the ground floor up to the first floor.
    # Consecutive walls share their end points, so the corners are mitred.
    corners = [(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0)]
    walls = [
        api.add_wall(project, start, corners[(i + 1) % 4], 0.30, ground.id, top_level=first.id)
        for i, start in enumerate(corners)
    ]
    south, _, north, _ = walls

    # A 90 x 210 cm door opening inwards, and a 120 x 140 cm window with a 90 cm sill.
    api.add_door(project, south.id, 1.50, 0.90, 2.10, swing_side="left", hinge="start")
    api.add_window(project, north.id, 3.00, 1.20, 1.40, 0.90)
    return project


def report(project: api.Project, label: str) -> None:
    first = project.level("Primo piano")
    tops = sorted({round(project.wall_z_range(w)[1], 3) for w in project.walls})
    print(f"{label}: 'Primo piano' at {first.elevation:+.2f} m, wall tops at {tops} m")


def export(project: api.Project, folder: Path, stem: str) -> None:
    write_ifc(project, folder / f"{stem}.ifc")
    issues = validate_ifc(folder / f"{stem}.ifc").issues
    sheet = api.Sheet("A4", scale=50)
    api.write_plan_svg(project, "Piano terra", folder / f"{stem}.svg", sheet)
    print(f"  wrote {stem}.ifc ({len(issues)} validation issues) and {stem}.svg")


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    project = build()
    joins = api.wall_geometry(project).joins
    print(f"built {len(project.walls)} walls with {len(joins)} corner joins, 1 door, 1 window")

    report(project, "before")
    export(project, folder, "casa-before")

    api.set_level_elevation(project, "Primo piano", 3.20)
    report(project, "after ")
    export(project, folder, "casa-after")

    api.save(project, folder / "casa.bbim")
    print("  saved casa.bbim")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
