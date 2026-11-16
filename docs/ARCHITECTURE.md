# Architecture

Status: proposed in Phase 0, not yet implemented. Decisions and their alternatives are in
`docs/adr/`.

## Principles

- **Headless first.** The core is a Python library with an API and a CLI. It is fully
  testable without a graphical interface.
- **One way to change the model.** Every mutation goes through a command. The CLI, the
  scripting API and the future interface all call the same commands.
- **Store intent, derive the rest.** The project stores parameters and constraints.
  Geometry, absolute elevations, joins, IFC and drawings are derived and can always be
  regenerated.
- **No home-made kernel or IFC parser.** We build on IfcOpenShell (IFC, 3D evaluation) and
  Shapely (2D).

## Modules

```
brunelleschi/
  model/      Elements, parameters, references between elements, the Project container
  regen/      Dependency graph and regeneration of derived state
  geometry/   2D footprints, wall joins, opening cuts (Shapely)
  commands/   Transactions; the only code allowed to mutate the model
  storage/    Project file (.bbim JSON), schema version, migrations
  ifc/        IFC4 export, validation; later IFC import
  drawings/   Views (plan first) -> 2D primitives -> SVG and DXF writers
  api/        Stable scripting facade over commands and queries
  cli/        `bbim` command-line tool, a thin client of api
  gui/        `bbim-gui` desktop interface (PySide6, optional extra), a client of api only
```

Dependency rule: arrows point downwards only.

```
cli -> api -> commands -> model
                 |          ^
                 v          |
               regen -> geometry
ifc, drawings, storage -> model (+ derived state from regen); never the reverse
```

`model` imports nothing from the other modules. `ifc`, `drawings` and `storage` are
leaves: nothing in the core depends on them, so an exporter can be rewritten without
touching the model.

## Data model

- A `Project` owns elements. Every element has a stable UUID.
- Elements hold **parameters** (numbers, enums, text) and **references** to other
  elements by id.
- Phase 1 elements:

| Element | Parameters | References |
|---|---|---|
| `Level` | name, elevation | none |
| `Wall` | start point, end point, thickness, base offset, top offset or unconnected height | base level, optional top level |
| `Door`, `Window` | width, height, sill height, distance of the centre along the host; doors: swing side and hinge jamb | host wall |

- Lengths are stored in metres as floats. Comparisons use a documented tolerance.
- Derived state is never written to the project file: wall footprint polygons, join
  geometry, absolute Z values, opening placements.

## Change propagation

**State at M3.** Cheap derived values (a wall's base and top elevation) are computed on
demand by pure queries such as `Project.wall_z_range`. Wall joins and footprints are
cached per project in `regen/` and brought up to date at each query: the cache compares
what each wall's geometry depends on (centre line, thickness, vertical extent) with what
it saw last time, and recomputes only the join points at the old and new ends of changed
walls and along their centre lines. Commands do not notify the cache, so no change can
be missed, and a rolled-back transaction needs no special handling. The explicit
dependency graph below is the target once derived state gets expensive beyond walls.
Door and window openings (M4) are cheap and recomputed at each query from the cached
wall lines.

Cost: a full rebuild is O(n²) in the number of walls (about 0.45 s for 480 walls on
the owner's machine; 0.1 s to update after one change). A spatial index (Shapely
`STRtree`) is the planned fix when real models need it.

1. A command runs inside a **transaction**. It edits parameters or references.
2. Each edited element is marked dirty. The **dependency graph** gives everything that
   depends on it:
   - `Level` -> walls that use it as base or top;
   - `Wall` -> the joins at its two ends, and its hosted doors and windows;
   - a join -> the footprints of the walls that meet there;
   - hosted element -> the opening cut in its host wall.
3. Regeneration recomputes derived state for the dirty set in dependency order.
   Wall-to-wall dependence is not direct: walls depend on **join nodes**, and joins depend
   only on wall centre lines and thicknesses. This keeps the graph acyclic.
4. Constraints are checked at commit. A violated constraint (a door wider than its wall,
   a top level below the base level) fails the transaction or is recorded as an explicit
   model warning. It is never ignored silently.
5. On commit the transaction becomes one undo step: the difference between the snapshot
   taken at its start and the new state (elements added, removed or changed, and the
   element order when membership changed). Undo and redo apply it backwards or forwards
   on the same element objects. The history lives in memory, per project, and is not saved.

Example, "raise Level 1 by 0.30 m": the level is dirty, so the walls with base or top on
Level 1 regenerate their Z extent, their hosted doors and windows keep their sill height
relative to the wall base, and the openings follow. IFC and plan output are regenerated
on demand from the new state.

## IFC

- Export is a pure function of the model: `Project -> IFC4 file`.
- Each element's IFC `GlobalId` is derived deterministically from its UUID, so repeated
  exports of the same project are stable and diffable.
- Mapping in Phase 1: project/site/building/storeys, `IfcWall` with extruded body,
  `IfcOpeningElement` + `IfcRelVoidsElement`, `IfcDoor`/`IfcWindow` + `IfcRelFillsElement`.
- Every export in the test suite is validated with `ifcopenshell.validate` (schema and
  EXPRESS rules). Milestones are also checked by hand in an external viewer and the
  buildingSMART validation service.
- IFC import comes later and produces non-parametric elements at first.

## Drawings

A view (plan at a cut height above a level) queries derived geometry and produces neutral
2D primitives (lines, polygons, arcs, text) with layers and line weights. Writers turn
those into SVG first, DXF later. DXF is the bridge to CartesioCAD.

## Interface (later)

A standalone desktop application (PySide6), packaged as an executable, using only the
`api` module. See ADR 0005.

## Testing

- Unit tests per module; property-style tests for joins and propagation.
- Golden files for SVG and for a normalized IFC summary.
- End-to-end test that runs the Phase 1 scenario through the CLI.
