# Journal

One entry per working session: what was decided, what was verified, what is open. Newest
first.

## 2026-11-16: M5 IFC4 export

**Decided**

- IfcOpenShell pinned to `==0.9.0.post1`. All calls to it are in `brunelleschi.ifc`
  (and the IFC tests); mypy's untyped-call check is relaxed for exactly those modules,
  because the library is only partly typed.
- Export is a pure function `Project -> ifcopenshell.file`, built entity by entity
  (geometry by hand, `ifcopenshell.api` for units, contexts and relationships).
- Mapping: storeys at level elevations; `IfcWall` (SOLIDWALL) in its base level's storey,
  placed at its start along its direction, with an `Axis` polyline and a `Body` extruded
  from the joined footprint (mitres and tees are in the IFC); per door/window an
  `IfcOpeningElement` voiding the wall and an `IfcDoor`/`IfcWindow` filling it, in the
  wall's storey, with a simple box body (no frame/leaf detail yet). Units: metre.
- Door operation: the door's local y axis points to the swing side, and `OperationType`
  is SINGLE_SWING_LEFT/RIGHT by the hinge side seen along that axis, per the IFC4
  definition. Worth a look in a viewer that draws door swings.
- GlobalIds: model elements use their UUID; derived entities use `uuid5(owner, role)`
  (opening of a door, site and building of the project); relationships use their
  subject (aggregates: the whole; containment: the storey; voids: the opening; fills:
  the filling). An unknown relationship type makes export fail, so no random id can
  slip in. Adding an element leaves every other id unchanged (tested).
- The project needed its own stable id: file format version 4 adds `id`. Migration 3 -> 4
  derives it from the file content (uuid5), so the same unsaved old file always exports
  with the same identifiers.
- `bbim ifc export FILE OUT [--validate]` and `bbim ifc validate FILE`. Without pytest
  installed, validation runs the schema checks only and says so.

**Verified**

- 268 tests pass on Python 3.13 and 3.11; ruff and mypy strict clean.
- Validation with schema and EXPRESS rules: zero issues on the test house, an empty
  project and a minimal one; a deliberately broken door is reported, so the zero means
  something.
- Geometry checked through IfcOpenShell's own evaluation (`ifcopenshell.geom`): every
  wall's volume equals its joined footprint area x height minus its openings; elevations
  and the door's position match the model; moving a level changes storey elevation and
  wall height in the export.
- Real CLI session: the M4 house file (version 3, upgraded on load) exported as valid
  IFC4 with schema and rules in under 2 s; two exports have identical GlobalIds (31).
- Found by tests: my first "invalid file" example (a wall with only a GlobalId) is valid
  IFC4, since every other IfcWall attribute is optional; the test now omits the GlobalId.

**Open**

- **Manual checks of ADR 0007 not done**: the buildingSMART validation service needs an
  upload under the owner's account, and opening a viewer would mean driving the owner's
  screen. The exported test house is ready for the owner to check.
- The STEP header says `ViewDefinition [CoordinationView]` (IfcOpenShell's default,
  an IFC2x3 view). Check what the buildingSMART service expects before changing it.
- Header timestamp makes the file bytes differ between exports (ids do not).
- No property sets, materials or wall types yet; windows have no inside/outside.

## 2026-11-16: M4 hosted door and window

**Decided**

- `Door` and `Window` share a base: host wall, `position` (distance from the wall's
  start to the element's *centre*, so resizing keeps it centred), `width`, `height`,
  `sill_height` above the wall's base. Doors also have `swing_side` (left/right, seen
  from the wall's start) and `hinge` (the jamb nearer the wall's start or end): explicit
  names instead of Revit's two "flip" toggles. Windows have no inside/outside yet; it
  will be added with a migration when IFC export or plans need it.
- Position is relative to the wall's start. Moving the start therefore moves the
  elements with it (Revit keeps them fixed in space instead); stated, tested.
- Hard errors (the change is refused, naming the element): an element not fitting the
  wall along or in height, overlapping elements in one wall, invalid sizes. This applies
  to indirect changes too: shortening a wall, lowering a level, so nothing is ever
  dropped silently.
- Warnings (`bbim check`): an opening reaching into the corner join at a wall end, or a
  wall meeting the host in a T inside the opening (at heights the opening spans).
- Openings are derived: a plan rectangle across the full wall thickness plus absolute
  bottom and top. `WallGeometry.plan_cut(z)` gives wall outlines cut at an elevation with
  the openings that plane crosses removed; M6 builds on it.
- File format version 3 adds `doors` and `windows` arrays; migration 2 -> 3 with a real
  version 2 sample; schemas 1 and 2 stay frozen.

**Verified**

- 241 tests pass on Python 3.13 and 3.11; ruff and mypy strict clean.
- Real CLI session on the house file (a real version 2 file, upgraded on load): two
  doors and three windows placed (one refused: it reached past the wall start);
  `bbim check` found the window that the partition meets; lowering the first floor to
  2.20 m was refused naming the door and window that would not fit; shortening the wall
  was refused naming the window; an overlapping door was refused; raising the level
  moved six walls; deleting the partition deleted its door. The file validates against
  `schemas/bbim-3.schema.json`.
- Found by tests: the first "blocked opening" check intersected the opening with other
  walls' footprints, which reported corner walls twice and never caught tees (a tee
  stops at the face, so it only touches the opening). Replaced by a check on tee joins.

**Open**

- Error messages about an element that failed to be created still mention an id the
  user never saw (also for walls, see M2).
- Elements on walls with a vertical extent that changes along the wall (none yet) and
  elements spanning joins are not handled beyond the warning.

## 2026-11-16: M3 wall joins

**Decided**

- Joins are derived, never stored. Wall ends meet when their coordinates are equal on a
  micrometre grid; a T needs the end exactly on the other wall's centre line. Walls whose
  vertical extents do not overlap never join (storeys join separately at a shared
  corner).
- Supported: L corners by mitre (any thickness pair), straight continuations, T butts,
  and a wall ending where a wall is split in two equal-thickness straight pieces (found
  by a scale test: without it every split wall with a partition was unsupported).
- Unsupported cases leave square ends and produce a `JoinIssue`, never a silent result:
  more than two walls at a point otherwise, X crossings, walls lying on each other,
  corners beyond a mitre limit of 10 half-thicknesses (sharper than about 11.5 degrees,
  or nearly straight walls of different thickness), cuts that pass the far end of a
  short wall.
- `regen/` exists now: a per-project cache with diff-based invalidation (see
  ARCHITECTURE). Shapely 2.2 is a runtime dependency (already chosen in ADR 0002), used
  for polygons and validity; the join maths is plain 2D vector code.
- New command `bbim wall joins`; `wall list --json` includes each wall's cut footprint.

**Verified**

- 191 tests pass on Python 3.13 and 3.11; ruff and mypy strict clean. Area tests: an L
  has exactly thickness x centre-line length, footprints never overlap, the corner
  square is covered (no gap), a closed room is a ring with one hole, two rooms sharing
  a split wall give two holes.
- The incremental test moves one room corner and checks that exactly four join points
  are recomputed and that another room's footprints are reused objects.
- Found by tests: the cache forgot a freshly solved corner when the old corner was
  processed after the new one. Fixed by clearing all affected ends before solving.
- Real CLI session on the M2 file: closing the ground floor room and adding a 12 cm
  partition gave four mitres and two tees; the first-floor wall above a ground-floor
  wall did not join it; a free wall crossing the partition was reported.

**Open**

- Four-way crossings and other multi-wall points (Revit handles them; we report them).
- O(n²) rebuild; add a spatial index when models grow.
- No visual check yet: the plan in SVG (M6) will be the first one.

## 2026-11-16: M2 walls bound to levels

**Decided**

- A wall stores its centre line (`start`, `end`), `thickness`, base level + offset, and
  a top that is either a level + offset or an unconnected height. The two kinds of top
  are separate types, so a wall cannot have both. The location line is fixed to the
  centre line for now; other location lines would be a later, migrated addition.
- Absolute elevations are derived on demand, not cached (see ARCHITECTURE, "Change
  propagation"). The `regen/` module waits until joins need it.
- Moving a level so that a wall's top would be at or below its base fails the whole
  move, listing the walls. It is not a silent warning.
- Walls have no name; users refer to them by a unique id prefix of at least four
  characters (`bbim` shows eight), like short git hashes.
- File format version 2 adds `walls`. Points are `[x, y]` arrays; the top is
  `{"kind": "level", ...}` or `{"kind": "height", ...}`. Version 1's schema stays
  published and frozen; a test checks both. The migration refuses a version 1 file that
  already has a `walls` key rather than dropping it.

**Verified**

- 150 tests pass on Python 3.13 and 3.11; ruff and mypy strict clean.
- Real CLI session on the file saved during M1 (a real version 1 file): it opened and
  was upgraded; four walls added (to a top level with negative offset, between upper
  levels, unconnected); moving "Primo piano" from 3.20 to 3.50 moved exactly the three
  bound walls; moving it to 0 was refused naming both walls that would invert; deleting
  it was refused naming its three walls; the saved file validates against
  `schemas/bbim-2.schema.json`.
- Found by that session: argparse took `-0,20` (negative, decimal comma) for an option.
  `bbim` now rewrites such arguments to `-0.20` before parsing; tested.

**Open**

- An error about a wall that failed to be created mentions its id, which the user never
  saw. Harmless, slightly confusing; revisit when error messages get a pass.

## 2026-11-16: M0 scaffolding and M1 project and levels

**Decided**

- The owner approved Phase 0. Forking Bonsai was discussed and rejected: Bonsai is a
  Blender add-on where IFC is the native model, the opposite of ADR 0001, and it would
  tie the program to Blender's GPL interface.
- pydantic v2 adopted for the file format only (amendment to ADR 0003).
- Levels are identified by UUID; names are unique ignoring case and surrounding spaces,
  and the CLI refers to levels by name.
- Transactions roll back to a snapshot that keeps object identity, so references held by
  scripts stay valid after a failure. Undo/redo will replace snapshots with recorded
  inverse operations later, without changing the API.
- The `.bbim` writer normalises `-0.0` to `0.0` and refuses NaN/infinity.
- The CLI accepts a decimal comma (`3,15`) and forces UTF-8 output, because a redirected
  stream on Windows otherwise uses the legacy code page.

**Verified**

- 82 tests pass on Python 3.13 and 3.11; ruff and mypy strict are clean.
- Real CLI session in a scratch folder: new, add (including a negative elevation and a
  non-Latin name), duplicate refused with exit code 1, move, rename, list, `--json`
  redirected to a file, info, `new` refusing to overwrite. The saved file validates
  against `schemas/bbim-1.schema.json`.

**Open**

- CI result not visible from here (private repository, no `gh` login): the owner checks
  the Actions tab.
- `_dependents` in `commands/levels.py` is the hook that M2 fills in, so deleting a level
  used by walls is refused.

## 2026-11-16: Phase 0, design

**Decided with the owner**

- Target user: small Italian practices, residential and small commercial buildings,
  metric units.
- Data model: left to the architect's recommendation. Chosen: internal parametric model,
  IFC derived (ADR 0001).
- Project file: a format that lets programs talk to each other. Chosen: documented JSON
  with a published schema, plus IFC, DXF and SVG for exchange (ADR 0006).
- Tooling: Python 3.13 and uv installed on the owner's machine; minimum Python 3.11.
- Interface: standalone executable that integrates with CartesioCAD (ADR 0005).
- Stack and licence: Python + IfcOpenShell, LGPL-3.0, as in the owner's brief. An earlier
  answer in the same session (C++/Qt, GPL-3.0) was superseded by the brief.

**Verified**

- PyPI: `ifcopenshell` latest is `0.9.0.post1`, Python `>=3.10,<3.16`,
  LGPL-3.0-or-later. The Windows wheel list was not read verbatim, but the install below
  confirms a Windows x64 wheel for Python 3.13.
- Local probe on Windows, Python 3.13.18, in a scratch folder outside the repository:
  wall + opening + door filling created through `ifcopenshell.api`; validation works and
  flags a missing placement; the wall mesh is cut by the opening; Shapely 2.2.0 and ezdxf
  1.4.5 import.
- In IfcOpenShell 0.9 the opening functions are `feature.add_feature` and
  `feature.add_filling` (formerly `void.*`).
- `ifcopenshell.validate` with EXPRESS rules needs `pytest` at runtime.

**Open**

- Owner approval of Phase 0.
- pydantic v2 for model definitions and JSON Schema: confirm and pin in M0.
- Licence review for a bundled executable (ADR 0004).
- Whether most authoring tools still export IFC4 rather than IFC4.3 (single secondary
  source).
- 3D viewport technology for the interface (deferred, ADR 0005).
