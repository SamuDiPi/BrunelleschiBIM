# Journal

One entry per working session: what was decided, what was verified, what is open. Newest
first.

## 2026-11-16: IFC references moved into Phase 2; export from the window

**Decided with the owner**

- The owner asked how to open IFC files: BrunelleschiBIM only exported them. Two levels
  were explained: IFC as a read-only reference (reliable: IfcOpenShell reads and
  triangulates nearly any IFC) and IFC converted into editable parametric elements (works
  only for simple cases, a phase of its own). The owner chose references now: new M13
  after the 3D view; DXF, rooms and the executable become M14, M15 and M16. Editable IFC
  import stays in "Later".
- File menu: "Export IFC..." and "Export plan as SVG..." (A3, first scale that fits among
  1:50, 1:100, 1:200), added at once.

**Found**

- `write_ifc` on a missing folder silently created the folder (IfcOpenShell's `write`
  does that). It now behaves like saving a project: the folder must exist, and the file is
  written to a temporary file and replaced only when complete. Tested.
- The owner asked how to start the program: today, by double-clicking
  `.venv\Scripts\bbim-gui.exe` or with `uv run bbim-gui`; the standalone executable is M16.

## 2026-11-16: M11 editing in plan

**Decided**

- Core commands `move_wall(project, wall, dx, dy)` and `move_wall_end(project, wall,
  "start"|"end", point)`: by default the ends of other walls that meet the moved ends
  follow, so corners stay joined (as in Revit). In the core because scripts need them too.
  Walls meeting the moved wall in a T do not follow yet.
- Plan tools: Select (click; drag a wall, an end grip, or a door or window along its
  wall; Delete), Wall (chain of clicks, each wall one undo step; Esc or right click ends),
  Door and Window (click a wall; a door opens towards the side clicked; the position is
  kept inside the wall). Mouse: wheel zoom, middle or right drag to pan, right click to
  end. Shortcuts S, W, D, N, F8 (ortho), Delete, plus "Add level" (3 m above the highest).
- Snaps by priority: wall endpoint, point on a wall's centre line (makes T joins), grid
  (0.10 m). Ortho with Shift or F8; an endpoint still wins over ortho. Snapping, picking,
  grips and side detection are pure functions in `gui/snap.py`.
- The status bar has two parts: messages on the left (what was refused and why), cursor
  coordinates, snap kind and tool hint on the right.
- Walls drawn on a level get the next level above as their top, or a 3.00 m
  unconnected height if there is none; thickness from the toolbar (0.30 by default).

**Verified**

- 503 tests pass on Python 3.13 and 3.11; ruff and mypy strict clean. Simulated mouse
  sessions (pytest-qt, offscreen) rebuild the M7 house with clicks only: four walls with
  four mitres, an inward-opening door at 1.50 m, a window at 3.00 m, valid IFC; undoing
  gives back the empty project byte for byte, step labels in the expected order; dragging
  a corner grip, a whole wall and a door; Esc, ortho with Shift, refusals.
- Captures of a scripted session were looked at: the wall preview with the endpoint snap
  marker, and the finished house with a partition making two T joins.

**Found by looking at the captures (not by the tests)**

- A partition drawn onto walls ended at x = 3.008 and a window at 3.01 m: the point "on
  a wall" kept the cursor's position along the wall, precise only to a screen pixel
  (1.7 cm at that zoom). Now the grid point is projected onto the wall, and door and
  window positions snap to the grid; a test pins it.
- An error message was overwritten at once by the cursor coordinates in the same status
  label; a test had passed only because the tool hint contained the same words.
- Dragging a wall gave 5.999999999999999 instead of 6 (the grab point came from an "on
  wall" snap); the move is now between grid points, rounded to the micrometre.

## 2026-11-16: M10 main window

**Decided**

- `brunelleschi.gui` (PySide6) is an optional extra, `brunelleschi[gui]`, so the core and
  `bbim` install without Qt; PySide6 is also in the dev group so `uv run` keeps it.
  pytest-qt (MIT) is a dev dependency. Entry point `bbim-gui [PROJECT.bbim]`; anything
  else on the command line is refused before a window exists (ADR 0009 lesson).
- `Document` holds the project, its file, the selection and the unsaved state; every
  change is an API command through `Document.edit`, so it is undoable and a refusal
  becomes a message (properties panel in red, status bar), never an exception or a
  modal dialog. Unsaved state is derived from the undo history: undoing back to the
  saved state clears the mark. New API `current_step` for that (the interface uses only
  `api`).
- Plan view: QPainter over the same primitives as the SVG plan, cosmetic pens, wheel zoom
  at the cursor, drag to pan, fit; the selected wall or opening is outlined in blue.
- Properties panel: every parameter of levels, walls, doors and windows; decimal comma;
  the wall top switches between "bound to a level" and "unconnected height"; fields that
  do not apply are disabled. The form is replaced (deleted later by Qt) on selection
  change, never torn down inside one of its own signals.
- CI installs the system libraries PySide6 needs on Linux.

**Verified**

- 477 tests pass on Python 3.13 and 3.11; ruff and mypy strict clean. 20 interface tests
  with pytest-qt on the offscreen platform cover the M10 criterion (open the M7 house,
  edit an elevation with a decimal comma, plan regenerated, title marked, undo and redo
  from the Edit menu with labels), refusals, the wall top switch, door parameters,
  selection shared between browser, panel and plan, save, new, bad files and start-up
  arguments.
- Looked at captures of the real window on the house file (`tools/capture_gui.py`), and
  at a scripted scenario: first floor raised to 3.50 through the panel, then a door
  position that does not fit refused with the reason shown and the field reset.
- Found on the way: the offscreen platform draws text as boxes without a font
  directory, and with the Windows fonts it garbles letters of Segoe UI (a variable
  font); captures set `QT_QPA_FONTDIR` and Arial. An earlier check that counted dark
  pixels had been fooled by the boxes.

**Not done, by design**

- The interface was not started on the owner's screen. Its first real use is the owner's.
- The plan is read-only (editing is M11); no 3D yet (M12).

## 2026-11-16: M9 undo and redo in the core

**Decided**

- One undo step per committed outermost transaction; nested transactions join it; failed
  or empty transactions leave no step. Commands carry labels ("Add wall", "Change level
  elevation", "Add level 'Roof'") for menu entries; an unlabelled transaction takes the
  label of its first command.
- A step stores only the difference from the snapshot the transaction already takes:
  elements added, removed, changed (field values before and after), and the element
  order of a store when its membership changed. Undo and redo restore values on the
  same element objects and put deleted elements back in their position, so a saved file
  after undo is byte-identical to the one before the change.
- The history lives in memory per project (like the regeneration cache), is empty for a
  project just created or loaded, is not saved, and has no length limit yet. The CLI has
  no undo: each `bbim` call is its own process.
- API: `undo`, `redo`, `can_undo`, `can_redo`, `undo_label`, `redo_label`,
  `clear_history`. Undo inside a transaction is refused.
- No new dependency for the property-based test: a seeded random generator instead of
  Hypothesis.

**Verified**

- 457 tests pass on Python 3.13 and 3.11; ruff and mypy strict clean.
- 150 seeded random sequences of 40 operations (valid and invalid on purpose, including
  batches): after every operation the file and the element identities match the state
  recorded for that history position; undo all, redo all and a random undo/redo walk
  revisit exactly the recorded states.
- The first version of the generator was weak: sequences ended with 0.6 walls and 0.1
  doors on average, so doors and cascading deletes were barely exercised. Measured,
  then reworked: now 23 steps, 4.3 walls and 2.6 doors/windows on average, every
  command kind present.
- Mutation check: deliberately breaking the order restoration, and separately the object
  identity, both make the test fail.
- Real API session: built the room in one labelled transaction, added a door, raised the
  first floor, deleted a wall with its door; undid all six steps and redid them, with the
  expected state and labels at each step and the same wall object back.

## 2026-11-16: M8 spikes, 3D view and packaging

**Verified (details and numbers in ADRs 0008 and 0009, scripts in `spikes/m8/`)**

- Qt Quick 3D is GPLv3 or commercial only (Qt documentation) and Qt 3D is deprecated
  since Qt 6.8: both excluded.
- Three 3D candidates rendered the M7 house and a 480-wall model off screen, images looked
  at, picking checked on a known wall: PyVista/VTK, our own OpenGL 3.3 in a Qt context,
  pygfx/wgpu. All correct; performance does not separate VTK and our OpenGL once the scene
  is one merged mesh; VTK adds about 300 MB to the executable; pygfx needs seconds on
  first use and runs on Vulkan/D3D12.
- The mesh source is the real cost: exporting the large model to IFC takes 2.8 s and
  triangulating it 0.73 s on 22 threads (4.1 s on one). The interface must re-mesh only
  changed elements.
- PyInstaller 6.22.3 built the whole stack into a 269 MB folder that ran on this machine
  with no Python on the PATH, started in about 1.1 s, and wrote an IFC valid with schema
  and rules and an SVG identical to the core's.

**Incidents during the spike (owner's screen)**

- The first packaged builds opened windows on the owner's screen: PyInstaller's error
  dialog (windowed build), then the probe's own main window, because IfcOpenShell ran
  `sys.executable bootstrap.py`, which relaunched the frozen program. Both were closed
  within minutes by killing the process tree. Since then packaged programs are run only
  through `spikes/m8/runexe.py` (no console window, output to files, hard timeout,
  process tree killed), the probe refuses unknown arguments, and the fixes are written in
  ADR 0009 for the real build.

**Decided by the owner**

- ADR 0008 accepted: own OpenGL 3.3 view behind a `Viewport` interface.
- ADR 0009 accepted: PyInstaller, one-folder build. ADR 0005 amended. M8 closed; M9
  (undo and redo in the core) is next.

**Open**

- Not measured: a packaged VTK build (its size is estimated from the installed files),
  Nuitka and Briefcase.

## 2026-11-16: Phase 2 planned

**Decided with the owner**

- Phase 2 builds the first interface now, rather than first enriching the headless model
  (wall types, slabs, rooms, dimensions, schedules), which was the architect's
  recommendation. The costs were stated and accepted: undo/redo becomes a prerequisite,
  the 3D view and packaging decisions are taken now, and model features other than
  rooms move to a later phase while the interface is built on the Phase 1 model.
- DXF for CartesioCAD must be an editable drawing: layers, hatches, blocks.
- Rooms with the Italian checks (window-to-floor ratio, minimum areas and heights) are in
  Phase 2, as M14.
- Milestones M8-M15 in `ROADMAP.md`. M8 is spikes only: measured comparisons, then ADRs
  decided by the owner.

**Open from Phase 1**

- ADR 0007 manual checks of the IFC (owner); CI results (owner).

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
