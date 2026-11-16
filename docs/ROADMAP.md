# Roadmap

Milestones are small and each has acceptance criteria that can be checked by running
something. A milestone is closed only when its tests pass and the scenario has been run
for real. Update this file at the end of every session.

Legend: `[ ]` not started, `[~]` in progress, `[x]` done.

## Phase 0: design

- [x] Library versions and status checked online and with a local probe (2026-11-16).
- [x] VISION, ARCHITECTURE, ADRs 0001-0007, ROADMAP, CLAUDE.md written.
- [x] **Owner approval of Phase 0** (2026-11-16). Forking Bonsai was considered and
      rejected: the project keeps its own parametric core.

## Phase 1: first vertical slice

Goal: from the command line and from a script, build a small model, change a level and
get a valid IFC4 file and a plan in SVG.

### M0 Repository scaffolding
- [x] `uv sync` creates the environment from a lock file on a clean machine.
- [x] `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and
      `uv run mypy` all pass on an (almost) empty package.
- [x] `uv run bbim --version` prints the version.
- [x] `LICENSE` (LGPL-3.0) and `README.md` present.
- [~] CI runs the four commands on Windows and Linux for every push. The workflow is
      in place; its result could not be read from here (private repository), so the
      owner checks the Actions tab.

### M1 Project and levels
- [x] API and CLI create a project and add, rename, move and delete levels.
- [x] Save to `.bbim` and load back gives an equal model; saving twice gives identical
      bytes.
- [x] A file with an unknown newer `schema_version` is refused with a clear error.
- [x] JSON Schema for version 1 is generated, published in `schemas/bbim-1.schema.json`
      (a test keeps it in sync) and a saved file validates against it.

### M2 Walls bound to levels
- [x] A straight wall has start, end, thickness, base level + offset, and either a top
      level + offset or an unconnected height.
- [x] Changing a level elevation changes the Z extent of every wall bound to it, and of
      no other wall (tested).
- [x] Deleting a level that walls depend on is refused, listing the walls.
- [x] Invalid walls (zero length, top below base) are rejected at commit; so is a level
      move that would put a wall top at or below its base. File format version 2
      (with the first real migration, 1 -> 2) stores walls.

### M3 Wall joins
- [x] Two walls meeting at an end point form a mitred L corner; footprints do not overlap
      and leave no gap (area test).
- [x] A wall ending on another wall's side forms a T join (butt); so does a wall
      ending where a wall is split in two straight pieces.
- [x] Moving a wall end regenerates only the joins it takes part in (cache in `regen/`,
      tested by the exact set of recomputed join points).
- [x] Documented behaviour for the cases we do not handle yet (X crossings, more than two
      walls at a point, non-zero-angle near-parallel walls).

### M4 Hosted door and window
- [x] A door and a window are placed in a wall by distance along the wall; windows have a
      sill height.
- [x] The host wall's derived geometry has the opening; moving or resizing the hosted
      element moves or resizes the opening.
- [x] Moving or lengthening the wall keeps the hosted elements at their distance; an
      element that no longer fits is reported, not silently dropped.
- [x] Deleting a wall deletes its hosted elements in the same transaction. File format
      version 3 stores doors and windows.

### M5 IFC4 export
- [x] Export contains project, site, building, storeys, walls, opening elements, door and
      window with correct void/fill relationships.
- [x] `ifcopenshell.validate` (schema + EXPRESS rules) reports zero issues in the test
      suite.
- [x] Exporting the same project twice gives the same GlobalIds (project id added in file
      format version 4).
- [~] Checked by hand: buildingSMART validation service result and one external viewer;
      both recorded in `JOURNAL.md`.

### M6 Plan in SVG
- [x] `bbim plan` writes an SVG of a level cut 1.20 m above it: wall poché with joins,
      door with swing, window symbol.
- [x] Output is deterministic and compared against golden files (reviewed as images
      before being accepted).
- [x] Scale and paper size options produce the stated dimensions in millimetres.

### M7 Phase 1 demonstration
- [x] One script and one CLI session create levels, four walls with corners, a door and a
      window, raise a level, then export IFC4 and SVG (`examples/`: Python, PowerShell,
      POSIX shell).
- [x] The end-to-end test runs that scenario and checks the before/after elevations, in
      the model and in the IFC geometry.
- [x] `README.md` shows the scenario (both snippets run as written).

## Phase 2: first interface

Goal (approved by the owner on 2026-11-16, who chose the interface before more model
content): a desktop application that opens, edits and saves the Phase 1 model with the
mouse, with undo, a 3D view, IFC files of others as references, DXF export to CartesioCAD,
rooms with the Italian checks, packaged as a standalone Windows executable.

Rules specific to this phase: the interface uses only `brunelleschi.api`; it is tested
headless (pytest-qt) and looked at through window captures saved as images, never by
driving the owner's screen. Editing stays minimal: walls with endpoint and grid snaps
and ortho, doors and windows by clicking a wall, select, move, delete.

### M8 Spikes and decisions (no product code)
- [x] 3D view: two or three candidates tried on the M7 house and on a larger generated
      model; measured install size, start time, frame rate, picking, licence.
- [x] Executable: at least one packaging tool builds the core with PySide6, IfcOpenShell
      and Shapely into a folder that runs without Python installed; measured size and
      start time.
- [x] ADRs written with the numbers (0008, 0009); the owner decided (own OpenGL view,
      PyInstaller one-folder); ADR 0005 updated.

### M9 Undo and redo in the core
- [x] Every command can be undone and redone through the API; a transaction is one step.
- [x] Property-based test: random command sequences, undo all gives the initial file
      bytes, redo all gives the final ones.

### M10 Main window
- [x] Open and save `.bbim`; levels and elements browser; properties panel that edits
      parameters through commands; read-only 2D plan of the current level.
- [x] Opens the M7 house; changing a level elevation in the panel updates the plan and
      can be undone. Checked with pytest-qt and window captures.

### M11 Editing in plan
- [x] Draw walls with endpoint and grid snaps and ortho; place doors and windows by
      clicking a wall; select, move and delete.
- [x] The M7 house can be rebuilt with the mouse (scripted with pytest-qt); every step
      undoes.

### M12 3D view
- [x] Read-only 3D view with the technology chosen in M8, synchronised with the model:
      raising a level in the plan updates the 3D. Orbit, pan, zoom, fit, click to select
      (shared with plan and browser); a clear message where OpenGL 3.3 is missing.
- [ ] Follow-up: draw element edges and slabs, so storeys read apart (today walls of
      stacked storeys merge visually).

### M13 IFC files as references
Added on 2026-11-16 at the owner's request: BrunelleschiBIM exported IFC but could not
open one.
- [ ] Open an IFC file (any authoring tool) as a reference: its elements appear in the
      plan of the level they belong to and in the 3D view, read-only, as a background to
      draw on; storeys are matched to our levels by elevation or name.
- [ ] Large or unusual files load without blocking the interface; elements that cannot be
      shown are counted and reported, not hidden.
- [ ] Whether the reference is remembered in the `.bbim` file (a link) is decided with the
      owner before it is coded (file format).

### M14 DXF export for CartesioCAD
- [ ] Editable plan in DXF: separate layers, cut walls as HATCH, doors and windows as
      blocks, at real size in metres or millimetres (to decide with CartesioCAD's units).
- [ ] The file is read without errors by CartesioCAD's `DxfReader` and looked at as an
      image; `bbim plan --dxf` and a menu command.

### M15 Rooms, areas and Italian checks
- [ ] Rooms derived from walls on a level: name, net area, perimeter, height; IfcSpace in
      the export; room tags in the plan.
- [ ] Checks as warnings (CLI and interface): window-to-floor ratio of at least 1/8,
      minimum room areas and heights (DM 5 July 1975); thresholds verified with the
      owner on the text of the decree before they are coded.

### M16 Executable and demonstration
- [ ] A Windows executable that starts on a machine without Python, opens and edits the
      demo house, exports IFC, SVG and DXF.

## Later (not yet broken down)

In rough order: wall types with layers; slabs and roofs; dimensions, room tags and title
blocks in plans; schedules; sections and elevations; sheets; IFC import as editable
elements (simple walls, doors and windows first).

## Risks being tracked

| Risk | Where it bites | Mitigation |
|---|---|---|
| Wall joins are fragile in corner cases | M3 | GEOS for polygon work, area-based tests, explicit list of unsupported cases |
| Propagation corner cases (cycles, deletions) | M2-M4 | joins as separate nodes, constraint check at commit |
| IfcOpenShell API changes before 1.0 | M5 and every upgrade | pinned version, thin wrapper, validation in tests |
| Python performance on large models | after Phase 1 | measure first; compiled hot spots behind the same API |
| Licence combination in a bundled executable | first binary release | review before release (ADR 0004) |
| One main developer | always | small milestones, docs updated every session |
