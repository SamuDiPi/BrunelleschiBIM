"""IFC4 export: a pure function of the project.

Mapping:

- project, site and building: ``IfcProject``, ``IfcSite``, ``IfcBuilding``;
- level: ``IfcBuildingStorey`` at its elevation;
- wall: ``IfcWall`` contained in its base level's storey, with an ``Axis`` curve and a
  ``Body`` extruded from its joined footprint (mitres and tees included);
- door or window: an ``IfcOpeningElement`` voiding the wall (``IfcRelVoidsElement``),
  filled by an ``IfcDoor`` or ``IfcWindow`` (``IfcRelFillsElement``) contained in the same
  storey as the wall, with a simple box as its body.

Every ``GlobalId`` is derived from the ids in the model, so exporting the same project
twice gives the same identifiers, and changing one element does not renumber others.
"""

from __future__ import annotations

import math
import os
import uuid
from collections.abc import Sequence
from typing import Any, Final
from uuid import UUID

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.feature
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import ifcopenshell.guid

from brunelleschi import __version__
from brunelleschi.geometry.joins import Vec, WallLine
from brunelleschi.model import Door, HostedElement, Jamb, Project, Side, Wall, short_id
from brunelleschi.regen import wall_geometry
from brunelleschi.regen.openings import CUT_MARGIN

Entity = Any  # ifcopenshell.entity_instance; the library is not typed

SCHEMA: Final = "IFC4"

# Thickness of the simple boxes that stand for a door leaf and a window frame.
DOOR_LEAF_THICKNESS = 0.05
WINDOW_FRAME_THICKNESS = 0.10


def global_id(element_id: UUID) -> str:
    """The IFC GlobalId of a model element: its UUID in IFC's 22-character encoding."""
    return str(ifcopenshell.guid.compress(element_id.hex))


def derived_id(owner: UUID, role: str) -> str:
    """A GlobalId for something that exists because of ``owner`` (its opening, a
    relationship it is the subject of), stable as long as the owner exists."""
    return global_id(uuid.uuid5(owner, role))


class _Writer:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.f = ifcopenshell.file(schema=SCHEMA)
        self.origin = self.point3((0.0, 0.0, 0.0))
        self.z_axis = self.f.createIfcDirection((0.0, 0.0, 1.0))
        self.x_axis = self.f.createIfcDirection((1.0, 0.0, 0.0))

    # ------------------------------------------------------------ primitives

    def point2(self, p: Vec) -> Entity:
        return self.f.createIfcCartesianPoint((float(p[0]), float(p[1])))

    def point3(self, p: tuple[float, float, float]) -> Entity:
        return self.f.createIfcCartesianPoint(tuple(float(v) for v in p))

    def placement(
        self,
        relative_to: Entity | None,
        location: tuple[float, float, float] = (0.0, 0.0, 0.0),
        x_dir: tuple[float, float] | None = None,
    ) -> Entity:
        axis = self.f.createIfcAxis2Placement3D(
            self.point3(location),
            self.z_axis if x_dir else None,
            self.f.createIfcDirection((x_dir[0], x_dir[1], 0.0)) if x_dir else None,
        )
        return self.f.createIfcLocalPlacement(relative_to, axis)

    def polyline(self, points: Sequence[Vec], closed: bool) -> Entity:
        entities = [self.point2(p) for p in points]
        if closed:
            entities.append(entities[0])
        return self.f.createIfcPolyline(entities)

    def extrusion(self, profile: Entity, z: float, depth: float) -> Entity:
        position = self.f.createIfcAxis2Placement3D(self.point3((0.0, 0.0, z)), None, None)
        return self.f.createIfcExtrudedAreaSolid(profile, position, self.z_axis, float(depth))

    def rectangle(self, centre: Vec, x_dim: float, y_dim: float) -> Entity:
        position = self.f.createIfcAxis2Placement2D(self.point2(centre), None)
        return self.f.createIfcRectangleProfileDef("AREA", None, position, x_dim, y_dim)

    def body(self, solid: Entity) -> Entity:
        return self.f.createIfcShapeRepresentation(self.body_ctx, "Body", "SweptSolid", [solid])

    def product(self, ifc_class: str, gid: str, name: str, predefined: str | None) -> Entity:
        entity = ifcopenshell.api.root.create_entity(
            self.f, ifc_class=ifc_class, predefined_type=predefined, name=name
        )
        entity.GlobalId = gid
        return entity

    # ----------------------------------------------------------------- build

    def build(self) -> ifcopenshell.file:
        p = self.project
        ifc_project = self.product("IfcProject", global_id(p.id), p.name, None)
        units = [
            ifcopenshell.api.unit.add_si_unit(self.f, unit_type="LENGTHUNIT"),
            ifcopenshell.api.unit.add_si_unit(self.f, unit_type="AREAUNIT"),
            ifcopenshell.api.unit.add_si_unit(self.f, unit_type="VOLUMEUNIT"),
            ifcopenshell.api.unit.add_si_unit(self.f, unit_type="PLANEANGLEUNIT"),
        ]
        ifcopenshell.api.unit.assign_unit(self.f, units=units)
        model = ifcopenshell.api.context.add_context(self.f, context_type="Model")
        self.body_ctx = ifcopenshell.api.context.add_context(
            self.f, "Model", "Body", "MODEL_VIEW", parent=model
        )
        self.axis_ctx = ifcopenshell.api.context.add_context(
            self.f, "Model", "Axis", "GRAPH_VIEW", parent=model
        )

        site = self.product("IfcSite", derived_id(p.id, "site"), "Site", None)
        building = self.product("IfcBuilding", derived_id(p.id, "building"), p.name, None)
        site.ObjectPlacement = self.placement(None)
        building.ObjectPlacement = self.placement(site.ObjectPlacement)
        ifcopenshell.api.aggregate.assign_object(self.f, [site], ifc_project)
        ifcopenshell.api.aggregate.assign_object(self.f, [building], site)

        storeys: dict[UUID, Entity] = {}
        for level in p.levels_by_elevation():
            storey = self.product("IfcBuildingStorey", global_id(level.id), level.name, None)
            storey.Elevation = level.elevation
            storey.ObjectPlacement = self.placement(
                building.ObjectPlacement, (0.0, 0.0, level.elevation)
            )
            storeys[level.id] = storey
        if storeys:
            ifcopenshell.api.aggregate.assign_object(self.f, list(storeys.values()), building)

        geometry = wall_geometry(p)
        contents: dict[UUID, list[Entity]] = {}
        for wall in p.walls:
            line = geometry.lines[wall.id]
            ifc_wall = self.wall(wall, line, geometry.footprints[wall.id].corners, storeys)
            contents.setdefault(wall.base_level_id, []).append(ifc_wall)
            for element in p.hosted_in(wall.id):
                filling = self.hosted(element, line, ifc_wall)
                contents[wall.base_level_id].append(filling)
        for level_id, products in contents.items():
            ifcopenshell.api.spatial.assign_container(self.f, products, storeys[level_id])

        self.stabilise_relationship_ids()
        self.f.header.file_name.originating_system = f"BrunelleschiBIM {__version__}"
        return self.f

    def wall(
        self, wall: Wall, line: WallLine, corners: Sequence[Vec], storeys: dict[UUID, Entity]
    ) -> Entity:
        ifc_wall = self.product(
            "IfcWall", global_id(wall.id), f"Wall {short_id(wall.id)}", "SOLIDWALL"
        )
        ifc_wall.ObjectPlacement = self.placement(
            storeys[wall.base_level_id].ObjectPlacement,
            (line.start[0], line.start[1], wall.base_offset),
            line.direction,
        )
        local = [_to_local(line, c) for c in corners]
        profile = self.f.createIfcArbitraryClosedProfileDef(
            "AREA", None, self.polyline(local, closed=True)
        )
        axis = self.f.createIfcShapeRepresentation(
            self.axis_ctx,
            "Axis",
            "Curve2D",
            [self.polyline([(0.0, 0.0), (line.length, 0.0)], False)],
        )
        body = self.body(self.extrusion(profile, 0.0, line.top_z - line.base_z))
        ifc_wall.Representation = self.f.createIfcProductDefinitionShape(None, None, [axis, body])
        return ifc_wall

    def hosted(self, element: HostedElement, line: WallLine, ifc_wall: Entity) -> Entity:
        a, b = element.along()
        bottom, _ = element.vertical()
        opening = self.product(
            "IfcOpeningElement",
            derived_id(element.id, "opening"),
            f"Opening {short_id(element.id)}",
            "OPENING",
        )
        opening.ObjectPlacement = self.placement(ifc_wall.ObjectPlacement)
        cutter = self.rectangle(((a + b) / 2, 0.0), element.width, line.thickness + 2 * CUT_MARGIN)
        opening.Representation = self.f.createIfcProductDefinitionShape(
            None, None, [self.body(self.extrusion(cutter, bottom, element.height))]
        )
        ifcopenshell.api.feature.add_feature(self.f, feature=opening, element=ifc_wall)

        if isinstance(element, Door):
            # The door's local y axis points where the leaf swings; IFC names the
            # operation by the side of the hinges seen along that axis.
            towards_left = element.swing_side == Side.LEFT
            origin_x, x_dir = (a, (1.0, 0.0)) if towards_left else (b, (-1.0, 0.0))
            hinge_at_origin = (element.hinge == Jamb.START) == towards_left
            filling = self.product(
                "IfcDoor", global_id(element.id), f"Door {short_id(element.id)}", "DOOR"
            )
            filling.OperationType = "SINGLE_SWING_LEFT" if hinge_at_origin else "SINGLE_SWING_RIGHT"
            depth = DOOR_LEAF_THICKNESS
        else:
            origin_x, x_dir = a, (1.0, 0.0)
            filling = self.product(
                "IfcWindow", global_id(element.id), f"Window {short_id(element.id)}", "WINDOW"
            )
            filling.PartitioningType = "SINGLE_PANEL"
            depth = WINDOW_FRAME_THICKNESS
        filling.OverallWidth = element.width
        filling.OverallHeight = element.height
        filling.ObjectPlacement = self.placement(
            opening.ObjectPlacement, (origin_x, 0.0, bottom), x_dir
        )
        box = self.rectangle((element.width / 2, 0.0), element.width, depth)
        filling.Representation = self.f.createIfcProductDefinitionShape(
            None, None, [self.body(self.extrusion(box, 0.0, element.height))]
        )
        ifcopenshell.api.feature.add_filling(self.f, opening=opening, element=filling)
        return filling

    def stabilise_relationship_ids(self) -> None:
        """Give relationships GlobalIds derived from what they relate."""
        keys = {
            "IfcRelAggregates": lambda r: ("aggregates", r.RelatingObject),
            "IfcRelContainedInSpatialStructure": lambda r: ("contains", r.RelatingStructure),
            "IfcRelVoidsElement": lambda r: ("voids", r.RelatedOpeningElement),
            "IfcRelFillsElement": lambda r: ("fills", r.RelatedBuildingElement),
        }
        for rel in self.f.by_type("IfcRelationship"):
            key = keys.get(rel.is_a())
            if key is None:  # a new kind of relationship needs a stable id rule here
                raise NotImplementedError(f"no stable GlobalId rule for {rel.is_a()}")
            role, subject = key(rel)
            owner = UUID(hex=ifcopenshell.guid.expand(subject.GlobalId))
            rel.GlobalId = derived_id(owner, role)


def _to_local(line: WallLine, p: Vec) -> Vec:
    """A plan point in the wall's coordinates: x along the wall from its start, y to its
    left."""
    (sx, sy), (dx, dy) = line.start, line.direction
    rx, ry = p[0] - sx, p[1] - sy
    x, y = rx * dx + ry * dy, dx * ry - dy * rx
    return (0.0 if math.isclose(x, 0, abs_tol=1e-12) else x, 0.0 if y == 0 else y)


def export_ifc(project: Project) -> ifcopenshell.file:
    """The project as an in-memory IFC4 model."""
    project.check()
    return _Writer(project).build()


def write_ifc(project: Project, path: str | os.PathLike[str]) -> None:
    """Write the project to an IFC4 (STEP) file."""
    export_ifc(project).write(str(path))
