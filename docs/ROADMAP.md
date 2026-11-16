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
- [ ] Export contains project, site, building, storeys, walls, opening elements, door and
      window with correct void/fill relationships.
- [ ] `ifcopenshell.validate` (schema + EXPRESS rules) reports zero issues in the test
      suite.
- [ ] Exporting the same project twice gives the same GlobalIds.
- [ ] Checked by hand: buildingSMART validation service result and one external viewer;
      both recorded in `JOURNAL.md`.

### M6 Plan in SVG
- [ ] `bbim plan` writes an SVG of a level cut 1.20 m above it: wall poché with joins,
      door with swing, window symbol.
- [ ] Output is deterministic and compared against golden files.
- [ ] Scale and paper size options produce the stated dimensions in millimetres.

### M7 Phase 1 demonstration
- [ ] One script and one CLI session create levels, four walls with corners, a door and a
      window, raise a level, then export IFC4 and SVG.
- [ ] The end-to-end test runs that scenario and checks the before/after elevations.
- [ ] `README.md` shows the scenario.

## Later (not yet broken down)

In rough order: undo/redo exposed in the API; DXF export of plans for CartesioCAD; slabs
and roofs; rooms and areas; sections and elevations; schedules; sheets and title blocks;
IFC import (non-parametric); first interface milestone (including the 3D viewport
choice); standalone executable; wall types with layers.

## Risks being tracked

| Risk | Where it bites | Mitigation |
|---|---|---|
| Wall joins are fragile in corner cases | M3 | GEOS for polygon work, area-based tests, explicit list of unsupported cases |
| Propagation corner cases (cycles, deletions) | M2-M4 | joins as separate nodes, constraint check at commit |
| IfcOpenShell API changes before 1.0 | M5 and every upgrade | pinned version, thin wrapper, validation in tests |
| Python performance on large models | after Phase 1 | measure first; compiled hot spots behind the same API |
| Licence combination in a bundled executable | first binary release | review before release (ADR 0004) |
| One main developer | always | small milestones, docs updated every session |
