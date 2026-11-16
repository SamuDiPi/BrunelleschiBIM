"""Drawings derived from the model: views produce neutral 2D primitives, writers turn
them into files (SVG now, DXF for CartesioCAD later)."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from brunelleschi.drawings.plan import DEFAULT_CUT_HEIGHT, plan_view
from brunelleschi.drawings.primitives import Drawing
from brunelleschi.drawings.svg import PAPER_SIZES, Sheet, to_svg
from brunelleschi.model import Project


def plan_svg(
    project: Project,
    level: UUID | str,
    sheet: Sheet | None = None,
    cut_height: float = DEFAULT_CUT_HEIGHT,
) -> str:
    """The plan of a level as an SVG document, with a one-line title."""
    sheet = sheet or Sheet()
    lv = project.level(level)
    title = f"{project.name} - {lv.name} - 1:{sheet.scale:g}"
    return to_svg(plan_view(project, lv.id, cut_height), sheet, title)


def write_plan_dxf(
    project: Project,
    level: UUID | str,
    path: str | os.PathLike[str],
    cut_height: float = DEFAULT_CUT_HEIGHT,
) -> None:
    """The plan of a level as an editable DXF at real size, in millimetres."""
    from brunelleschi.drawings.dxf import write_dxf  # ezdxf loads only when needed

    write_dxf(plan_view(project, project.level(level).id, cut_height), path)


def write_plan_svg(
    project: Project,
    level: UUID | str,
    path: str | os.PathLike[str],
    sheet: Sheet | None = None,
    cut_height: float = DEFAULT_CUT_HEIGHT,
) -> None:
    text = plan_svg(project, level, sheet, cut_height)
    Path(path).write_text(text, encoding="utf-8", newline="\n")


__all__ = [
    "DEFAULT_CUT_HEIGHT",
    "PAPER_SIZES",
    "Drawing",
    "Sheet",
    "plan_svg",
    "plan_view",
    "to_svg",
    "write_plan_dxf",
    "write_plan_svg",
]
