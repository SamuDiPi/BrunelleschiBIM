# BrunelleschiBIM: working notes for Claude

Open-source BIM authoring tool. Headless Python core first, interface later. Read
`docs/VISION.md`, `docs/ARCHITECTURE.md` and `docs/ROADMAP.md` before starting work, and
the ADRs in `docs/adr/` before changing anything they cover.

## Language

- Conversation with the owner: **Italian**.
- Code, comments, commit messages, documentation: **English**.

## Current state

Phase 0 approved. Phase 2 (first interface, M8-M15) is planned and approved; M8 is done
(ADRs 0008 own OpenGL view, 0009 PyInstaller) and M9 (undo/redo) is next; see
`docs/ROADMAP.md`. Phase 1: M0, M1 (project, levels, `.bbim` file), M2 (walls bound to levels,
file version 2), M3 (wall joins, `regen/` cache), M4 (doors and windows, file version 3)
M5 (IFC4 export, file version 4), M6 (plan in SVG) and M7 (demonstration, `examples/`)
done. Phase 1 still waits for M5's manual checks by the owner and a look at CI.

Look at drawings, do not only test them: render with `tools/render_svg.py` (see its
docstring) and read the PNG. Golden files are accepted only after such a look.

File format changes: add `storage/schema_v<n>.py`, a migration in
`storage/migrations.py`, a sample of the previous version in `tests/data/`, and publish
the schema with `bbim schema -o schemas/bbim-<n>.schema.json`. Released schema files
never change; `tests/test_schema.py` checks every version.

## Commands

The project uses `uv`.

```
uv sync                      # create/update the environment from the lock file
uv run pytest                # tests
uv run ruff check            # lint
uv run ruff format           # format (use --check in CI)
uv run mypy                  # type check
uv run bbim --help           # command-line tool
```

On the owner's Windows machine `uv` was installed with winget; if it is not on `PATH` in
a shell, it is under
`%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*\uv.exe`.

## Conventions

- Python 3.11 minimum, developed on 3.13. Type hints everywhere; mypy strict on the core.
- Package name `brunelleschi`, CLI name `bbim`, project file extension `.bbim`.
- `model/` imports nothing from `geometry/`, `ifc/`, `drawings/`, `storage/`.
- The model is changed only through commands inside a transaction.
- Derived geometry is never stored in the project file.
- Lengths are metres (float). Never compare floats without the shared tolerance.
- IfcOpenShell is pinned; all calls to it live in `brunelleschi/ifc/` (and 3D evaluation
  helpers). Its API changes between versions: check the installed version's docs, not
  memory.
- Every schema change to `.bbim` needs a migration, a sample file and a test.

## Rules of work with the owner

- Vertical slices: small, working, tested. No large horizontal layers.
- Before each milestone: a short plan, then implementation.
- A feature is not finished without green tests **and** having been run for real.
- Small, descriptive commits. Push only when the owner asks.
- Ask before decisions that are hard to undo (file format, public API, dependencies,
  licence).
- If a library cannot do what is needed, say so at once. No fragile workarounds.
- Be frank about what is realistic. No courtesy optimism. Disagree when there is a solid
  argument.
- Verify library versions and behaviour online or with a probe; do not trust memory.
- At the end of each session: update `docs/ROADMAP.md`, add an entry to
  `docs/JOURNAL.md`, and add or amend ADRs for decisions taken.
- Do not drive the owner's screen (mouse, keyboard, screenshots) while they are using the
  computer. Test headless.

## Out of scope for now

MEP, structural analysis, rendering, `.rvt` files, real-time collaboration, graphical
family editor.
