# Journal

One entry per working session: what was decided, what was verified, what is open. Newest
first.

## 2026-11-16: M7 Phase 1 demonstration, and where Phase 1 stands

**Done**

- `examples/phase1_demo.py` (API), `phase1_demo.ps1` and `phase1_demo.sh` (CLI) build a
  6 x 4 m room on two levels with four mitred corners, a door and a window; export IFC4
  and a plan; raise the first floor from 3.00 to 3.20 m; export again.
- `tests/test_demo.py` runs the script and this platform's CLI session as real
  processes and checks: the model after the change; storey elevations and wall tops
  before and after, measured on the IFC geometry evaluated by IfcOpenShell; both IFC
  files valid with schema and rules and with identical GlobalIds; the ground floor plan
  unchanged (its cut at 1.20 m is below the change).
- `--quiet` on `wall/door/window add` prints only the new id, so a shell session can
  pass a wall to a door without copying ids by hand.
- README shows the scenario in Python and PowerShell; both snippets were run as written.
- mypy now also checks `examples/`.

**Found while doing it**

- A PowerShell helper named `Bbim` called itself (function names are case-insensitive)
  and overflowed the call stack. Renamed `Invoke-Bbim`, with a comment.
- Unquoted `3,00` is an array in PowerShell, not a decimal comma. Quoted everywhere in
  the PowerShell examples, with a comment; the README says so too.
- The extra test that ran the POSIX script on Windows was dropped: `sh` is not on the
  PATH of the test environment; on Linux CI the POSIX session is the one that runs.

**Phase 1, overall**

- Met, by automated tests and real runs: levels; walls bound to levels with corner and
  T joins; a door and a window hosted in a wall with automatic openings; level changes
  propagate; IFC4 output valid by IfcOpenShell's validator (schema and EXPRESS rules);
  plan in SVG at scale. 295 tests on Python 3.13 and 3.11.
- **Not yet met:** ADR 0007's manual checks (buildingSMART validation service and an
  external viewer) need the owner; CI results have never been seen from here (private
  repository, no `gh` login). Phase 1 is complete only when both are recorded here.

## 2026-11-16: M6 plan in SVG

**Decided**

- Pipeline as in ARCHITECTURE: `drawings/plan.py` turns the model into neutral 2D
  primitives (areas, lines, arcs, texts) on named layers; `drawings/svg.py` plots them on
  an ISO A sheet at a scale. The DXF writer for CartesioCAD will reuse the primitives.
- Plan content at a cut height (default 1.20 m): cut walls as one filled mass with one
  outline (their union); door leaf open at 90 degrees on the swing side from the hinge
  jamb, with its arc; window as the two wall faces and a glass line; openings entirely
  above the cut, dashed; walls of the level lower than the cut, thin outline. Openings
  entirely below the cut (none in practice yet) are not drawn.
- Paper: `width`/`height` in mm and a mm `viewBox`, so the file prints at scale; the
  drawing is centred; if it does not fit inside 10 mm margins, a clear error with the
  sizes. Pens: 0.50 cut outline, 0.35 door, 0.25 window and dashed openings, 0.18 swing
  and projections; poché light grey (#a6a6a6) so dashed lines over it stay visible.
- Output is deterministic (fixed number format, layer order, model order, no
  timestamps). Golden files in `tests/golden/`, rewritten with `pytest --update-golden`
  and accepted only after looking at them as images.
- `tools/render_svg.py` renders SVG to PNG with QtSvg in a throwaway environment (PySide6
  is not a project dependency); it opens no window.

**Verified**

- 293 tests pass on Python 3.13 and 3.11; ruff and mypy strict clean.
- Looked at the plans as images (first visual check of the geometry in the project).
  The first renders showed two defects no test caught: join lines between walls (each
  wall outlined separately; also seams where fills meet), and the dashed high window
  invisible under the dark poché. Fixed by filling and outlining the union, drawing
  dashed openings above the poché and lightening it. Mitres, split-wall tees, a slanted
  tee, both door swings and the windows were then checked by eye.
- Text was missing in the first renders: Qt's offscreen platform on Windows has no fonts.
  Not an SVG problem; the render tool uses the normal platform.
- Real CLI session: plans of the house file at 1:50 on A3 and 1:100 on A4 portrait;
  1:20 on A4 refused with the drawing and sheet sizes; an unknown level and a zero scale
  refused.

**Open**

- No dimensions, room names, level marks, north arrow or title block beyond one line.
- Per-wall identity is not kept on the merged poché (doors and windows keep theirs).
- Walls of other storeys crossing the cut plane are cut too (correct for a cut, but no
  distinction is drawn yet).

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
