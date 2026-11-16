"""Reading IFC files of others as read-only references.

Everything with a body is triangulated by IfcOpenShell, in world coordinates and in
metres whatever the file's units (IfcOpenShell's default, ``convert-back-units`` off).
Storey elevations are attributes in the file's units and are scaled here. Elements that
have no body, or whose geometry IfcOpenShell cannot build, are counted and reported, not
dropped silently.
"""

from __future__ import annotations

import multiprocessing
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.unit
import numpy as np
from numpy.typing import NDArray

from brunelleschi.errors import BrunelleschiError

# Elements that are not physical: never drawn.
SKIPPED_CLASSES = ("IfcOpeningElement", "IfcSpace", "IfcVirtualElement", "IfcAnnotation")


class ReferenceError(BrunelleschiError):
    """An IFC file cannot be read as a reference."""


@dataclass(frozen=True, slots=True)
class ReferenceStorey:
    global_id: str
    name: str
    elevation: float  # metres


@dataclass(frozen=True, slots=True)
class ReferenceElement:
    global_id: str
    ifc_class: str
    name: str
    storey: str | None  # GlobalId of its storey, if it is contained in one
    vertices: NDArray[np.float64]  # (n, 3), metres, world coordinates
    triangles: NDArray[np.int32]  # (m, 3)


@dataclass
class ReferenceModel:
    path: Path
    schema: str
    storeys: list[ReferenceStorey] = field(default_factory=list)
    elements: list[ReferenceElement] = field(default_factory=list)
    without_geometry: Counter[str] = field(default_factory=Counter)  # class -> count
    failed: Counter[str] = field(default_factory=Counter)  # class -> count

    def summary(self) -> str:
        parts = [f"{len(self.elements)} elements"]
        if self.without_geometry:
            parts.append(f"{sum(self.without_geometry.values())} without geometry")
        if self.failed:
            classes = ", ".join(f"{n} {c}" for c, n in self.failed.most_common(3))
            parts.append(f"{sum(self.failed.values())} could not be shown ({classes})")
        return ", ".join(parts)


def _storey_of(element: Any) -> str | None:
    container: Any = ifcopenshell.util.element.get_container(element)
    while container is not None and not container.is_a("IfcBuildingStorey"):
        container = ifcopenshell.util.element.get_aggregate(container)
    return str(container.GlobalId) if container is not None else None


def load_reference(path: str | os.PathLike[str], threads: int | None = None) -> ReferenceModel:
    """Read and triangulate an IFC file. Raises ``ReferenceError`` if it cannot be opened."""
    source = Path(path)
    if not source.is_file():
        raise ReferenceError(f"file not found: {source}")
    try:
        f: Any = ifcopenshell.open(str(source))
    except Exception as exc:  # IfcOpenShell raises several kinds of errors
        raise ReferenceError(f"not a readable IFC file: {source.name} ({exc})") from None
    model = ReferenceModel(path=source, schema=str(f.schema))
    scale = float(ifcopenshell.util.unit.calculate_unit_scale(f))
    for storey in f.by_type("IfcBuildingStorey"):
        model.storeys.append(
            ReferenceStorey(
                global_id=str(storey.GlobalId),
                name=str(storey.Name or ""),
                elevation=float(storey.Elevation or 0.0) * scale,
            )
        )

    candidates = [e for e in f.by_type("IfcElement") if not any(e.is_a(c) for c in SKIPPED_CLASSES)]
    with_body = []
    for element in candidates:
        if element.Representation is None:
            model.without_geometry[element.is_a()] += 1
        else:
            with_body.append(element)
    if not with_body:
        return model

    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    built: set[int] = set()
    iterator = ifcopenshell.geom.iterator(
        settings, f, threads or multiprocessing.cpu_count(), include=with_body
    )
    if iterator.initialize():
        while True:
            shape: Any = iterator.get()
            element = f.by_id(shape.id)
            vertices = np.array(shape.geometry.verts, dtype=np.float64).reshape(-1, 3)
            triangles = np.array(shape.geometry.faces, dtype=np.int32).reshape(-1, 3)
            built.add(int(shape.id))
            if len(triangles):
                model.elements.append(
                    ReferenceElement(
                        global_id=str(element.GlobalId),
                        ifc_class=str(element.is_a()),
                        name=str(element.Name or ""),
                        storey=_storey_of(element),
                        vertices=vertices,
                        triangles=triangles,
                    )
                )
            else:
                model.failed[element.is_a()] += 1
            if not iterator.next():
                break
    for element in with_body:
        if element.id() not in built:
            model.failed[element.is_a()] += 1
    model.elements.sort(key=lambda e: e.global_id)  # independent of thread timing
    return model


# ------------------------------------------------------------ storeys/levels


def match_storeys(
    storeys: list[ReferenceStorey], levels: list[tuple[Any, str, float]], tolerance: float = 0.05
) -> dict[str, Any]:
    """Storey GlobalId -> level id: by elevation within ``tolerance`` metres, else by name
    (ignoring case and spaces). ``levels`` are (id, name, elevation). Storeys matching
    nothing are left out."""
    result: dict[str, Any] = {}
    for storey in storeys:
        close = [lv for lv in levels if abs(lv[2] - storey.elevation) <= tolerance]
        if close:
            result[storey.global_id] = min(close, key=lambda lv: abs(lv[2] - storey.elevation))[0]
            continue
        named = [lv for lv in levels if lv[1].strip().casefold() == storey.name.strip().casefold()]
        if named:
            result[storey.global_id] = named[0][0]
    return result


def section(
    vertices: NDArray[np.float64], triangles: NDArray[np.int32], z: float
) -> NDArray[np.float64]:
    """Line segments where a horizontal plane at ``z`` cuts a triangle mesh: (k, 2, 2)."""
    if len(triangles) == 0:
        return np.zeros((0, 2, 2))
    tri = vertices[triangles]  # (m, 3, 3)
    d = tri[:, :, 2] - z
    # Nudge vertices lying on the plane, so each crossing triangle gives exactly two points.
    d = np.where(np.abs(d) < 1e-9, 1e-9, d)
    crosses = (d.min(axis=1) < 0) & (d.max(axis=1) > 0)
    tri, d = tri[crosses], d[crosses]
    segments = []
    for k in range(len(tri)):
        points = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if (d[k, i] < 0) != (d[k, j] < 0):
                t = d[k, i] / (d[k, i] - d[k, j])
                p = tri[k, i] + t * (tri[k, j] - tri[k, i])
                points.append(p[:2])
        if len(points) == 2:
            segments.append(points)
    return np.array(segments, dtype=np.float64).reshape(-1, 2, 2)
