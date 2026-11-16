"""Build IFC files as another authoring tool might: millimetres, IfcOpenShell's own API,
storeys, walls, a slab, a column, an element without geometry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit


def _product(f: Any, ifc_class: str, name: str) -> Any:
    return ifcopenshell.api.root.create_entity(f, ifc_class=ifc_class, name=name)


def build_foreign_ifc(path: Path) -> Path:
    """Two storeys at 0 and 3000 mm named "PT" and "P1"; on PT a 5 m wall along x, a 4 m
    wall along y (from x = 5 m), a 6 x 5 m slab 0.2 m thick, a 0.3 m column; a piece of
    furniture with no body. Lengths given to IfcOpenShell's API are in metres; it writes
    them in the file's millimetres."""
    f: Any = ifcopenshell.file(schema="IFC4")
    project = _product(f, "IfcProject", "Strutture")
    ifcopenshell.api.unit.assign_unit(f)  # millimetres
    model = ifcopenshell.api.context.add_context(f, context_type="Model")
    body = ifcopenshell.api.context.add_context(f, "Model", "Body", "MODEL_VIEW", parent=model)
    site = _product(f, "IfcSite", "Site")
    building = _product(f, "IfcBuilding", "Building")
    ifcopenshell.api.aggregate.assign_object(f, [site], project)
    ifcopenshell.api.aggregate.assign_object(f, [building], site)
    ground = _product(f, "IfcBuildingStorey", "PT")
    ground.Elevation = 0.0
    first = _product(f, "IfcBuildingStorey", "P1")
    first.Elevation = 3000.0
    ifcopenshell.api.aggregate.assign_object(f, [ground, first], building)

    geometry = ifcopenshell.api.geometry
    contained = []

    def place(product: Any, x: float = 0.0, y: float = 0.0, rotate: bool = False) -> None:
        import numpy as np

        matrix = np.identity(4)
        if rotate:  # 90 degrees about z
            matrix[:2, :2] = [[0, -1], [1, 0]]
        matrix[0, 3], matrix[1, 3] = x, y  # metres: the API converts
        geometry.edit_object_placement(f, product=product, matrix=matrix, is_si=True)

    wall_x = _product(f, "IfcWall", "Muro A")
    geometry.assign_representation(
        f,
        product=wall_x,
        representation=geometry.add_wall_representation(
            f, context=body, length=5.0, height=3.0, thickness=0.2
        ),
    )
    place(wall_x)
    wall_y = _product(f, "IfcWall", "Muro B")
    geometry.assign_representation(
        f,
        product=wall_y,
        representation=geometry.add_wall_representation(
            f, context=body, length=4.0, height=3.0, thickness=0.2
        ),
    )
    place(wall_y, x=5.0, rotate=True)
    slab = _product(f, "IfcSlab", "Solaio")
    geometry.assign_representation(
        f,
        product=slab,
        representation=geometry.add_slab_representation(
            f, context=body, depth=0.2, polyline=[(0.0, 0.0), (6.0, 0.0), (6.0, 5.0), (0.0, 5.0)]
        ),
    )
    place(slab)
    column = _product(f, "IfcColumn", "Pilastro")
    geometry.assign_representation(
        f,
        product=column,
        representation=geometry.add_profile_representation(
            f,
            context=body,
            profile=f.createIfcRectangleProfileDef("AREA", None, None, 300.0, 300.0),
            depth=3.0,
        ),
    )
    place(column, x=2.0, y=2.0)
    contained += [wall_x, wall_y, slab, column]
    chair = _product(f, "IfcFurniture", "Sedia")  # no body at all
    contained.append(chair)
    ifcopenshell.api.spatial.assign_container(f, contained, ground)
    f.write(str(path))
    return path
