"""DXF writer for drawings: an editable drawing for CartesioCAD and other CAD programs.

- Real size in millimetres (``$INSUNITS`` 4), like CartesioCAD's own files; DXF R2000.
- One layer per drawing layer, with colour, line weight and line type, so the drawing can
  be finished in a CAD program (hide, lock, restyle by layer).
- Cut walls: a solid HATCH (the poché) plus closed polylines for the outline.
- Doors and windows: blocks (``DOOR_900``, ``WINDOW_1200x300``) inserted with a rotation,
  so all doors of a size are one definition, editable at once. A mirrored door uses a
  mirrored definition (``DOOR_900_M``) rather than a negative scale: some DXF readers
  mishandle arcs in negatively scaled blocks.
"""

from __future__ import annotations

import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ezdxf import const, units
from ezdxf.document import Drawing as DxfDocument
from ezdxf.filemanagement import new as new_dxf
from ezdxf.layouts.base import BaseLayout

from brunelleschi.drawings.primitives import Arc, Area, Block, Drawing, Insert, Line, Shape, Vec

MM = 1000.0  # model metres to drawing millimetres


@dataclass(frozen=True, slots=True)
class DxfLayer:
    name: str
    colour: int  # AutoCAD colour index
    lineweight: int  # hundredths of a millimetre
    linetype: str = "Continuous"


# Drawing layer -> DXF layer.
LAYERS: dict[str, DxfLayer] = {
    "wall-cut": DxfLayer("WALL-CUT-HATCH", 8, 0),
    "wall-cut-outline": DxfLayer("WALL-CUT", 7, 50),
    "wall-projection": DxfLayer("WALL-BELOW", 8, 18),
    "opening-above": DxfLayer("OPENING-ABOVE", 8, 18, "DASHED"),
    "door": DxfLayer("DOOR", 7, 35),
    "door-swing": DxfLayer("DOOR-SWING", 7, 18),
    "window": DxfLayer("WINDOW", 4, 25),
}


def _mm(p: Vec) -> tuple[float, float]:
    return (round(p[0] * MM, 6), round(p[1] * MM, 6))


def _layer(name: str) -> str:
    return LAYERS[name].name if name in LAYERS else name.upper()


def _add_shape(layout: BaseLayout, shape: Shape) -> None:
    layer = _layer(shape.layer)
    if isinstance(shape, Area):
        hatch = layout.add_hatch(color=LAYERS.get(shape.layer, LAYERS["wall-cut"]).colour)
        hatch.dxf.layer = layer
        hatch.set_solid_fill(color=LAYERS.get(shape.layer, LAYERS["wall-cut"]).colour)
        for i, ring in enumerate(shape.rings):
            flags = const.BOUNDARY_PATH_EXTERNAL if i == 0 else const.BOUNDARY_PATH_DEFAULT
            hatch.paths.add_polyline_path([_mm(p) for p in ring], is_closed=True, flags=flags)
    elif isinstance(shape, Line):
        points = [_mm(p) for p in shape.points]
        if len(points) == 2 and not shape.closed:
            layout.add_line(points[0], points[1], dxfattribs={"layer": layer})
        else:
            layout.add_lwpolyline(points, close=shape.closed, dxfattribs={"layer": layer})
    else:
        _add_arc(layout, shape, layer)


def _add_arc(layout: BaseLayout, arc: Arc, layer: str) -> None:
    cx, cy = arc.centre
    a0 = math.atan2(arc.start[1] - cy, arc.start[0] - cx)
    a1 = math.atan2(arc.end[1] - cy, arc.end[0] - cx)
    sweep = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi  # the minor arc, signed
    start, end = (a0, a1) if sweep >= 0 else (a1, a0)  # DXF arcs run counter-clockwise
    radius = math.hypot(arc.start[0] - cx, arc.start[1] - cy) * MM
    layout.add_arc(
        _mm(arc.centre),
        round(radius, 6),
        round(math.degrees(start) % 360, 9),
        round(math.degrees(end) % 360, 9),
        dxfattribs={"layer": layer},
    )


def _define(doc: DxfDocument, block: Block) -> None:
    if block.name in doc.blocks:
        return
    definition = doc.blocks.new(name=block.name)
    for shape in block.shapes:
        _add_shape(definition, shape)


def _mirrored(block: Block) -> Block:
    """The block reflected in its x axis, as its own definition."""

    def flip(p: Vec) -> Vec:
        return (p[0], -p[1])

    shapes: list[Shape] = []
    for shape in block.shapes:
        if isinstance(shape, Line):
            shapes.append(Line(shape.layer, tuple(flip(p) for p in shape.points), shape.closed))
        elif isinstance(shape, Arc):
            shapes.append(Arc(shape.layer, flip(shape.centre), flip(shape.start), flip(shape.end)))
        else:
            shapes.append(Area(shape.layer, tuple(tuple(flip(p) for p in r) for r in shape.rings)))
    return Block(f"{block.name}_M", tuple(shapes))


def to_dxf(drawing: Drawing) -> DxfDocument:
    """The drawing as a DXF document (model space, millimetres)."""
    doc = new_dxf("R2000", setup=["linetypes"])
    doc.units = units.MM
    doc.header["$INSUNITS"] = 4
    doc.header["$MEASUREMENT"] = 1
    doc.header["$LUNITS"] = 2  # decimal
    for spec in LAYERS.values():
        doc.layers.add(
            spec.name, color=spec.colour, lineweight=spec.lineweight, linetype=spec.linetype
        )
    msp = doc.modelspace()
    for primitive in drawing.primitives:
        if isinstance(primitive, Insert):
            block = _mirrored(primitive.block) if primitive.mirror else primitive.block
            _define(doc, block)
            msp.add_blockref(
                block.name,
                _mm(primitive.position),
                dxfattribs={
                    "layer": _layer(primitive.layer),
                    "rotation": round(math.degrees(primitive.rotation) % 360, 9),
                },
            )
        else:
            _add_shape(msp, primitive)
    return doc


def write_dxf(drawing: Drawing, path: str | os.PathLike[str]) -> None:
    """Write a DXF file; like project files, the old file is replaced only once the new
    one is complete, and the folder must exist."""
    target = Path(path)
    doc = to_dxf(drawing)
    fd, tmp = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    os.close(fd)
    try:
        doc.saveas(tmp)
        Path(tmp).replace(target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
