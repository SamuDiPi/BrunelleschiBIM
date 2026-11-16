# Journal

One entry per working session: what was decided, what was verified, what is open. Newest
first.

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
