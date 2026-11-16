# ADR 0009: Packaging the desktop executable

Status: accepted (2026-11-16) by the owner, as recommended below.

## Context

ADR 0005 wants a standalone executable, started by double click, on machines without
Python. M8 built a probe program (`spikes/m8/pkg_app.py`) that imports the whole stack
(PySide6 6.12, the core, IfcOpenShell 0.9, Shapely, PyOpenGL), builds the M7 house,
exports IFC and SVG and opens an OpenGL context, and ran it with no Python on the PATH
(`spikes/m8/runexe.py`).

## Result with PyInstaller 6.22.3 (one-folder build)

- Works: exit 0, the IFC it wrote validates with schema and EXPRESS rules (checked from
  the development environment), and its SVG is byte-identical to the core's output.
- Size: 269 MB folder (PySide6 is most of it; PyInstaller keeps only the Qt modules in
  use, so this is smaller than ADR 0005's estimate). Build time: about 90 s.
- Start-up: imports 0.30 s, the whole self-test 0.6 s, about 1.1 s wall clock.

Problems found, each with its fix, all needed in the real build:

1. IfcOpenShell data files (schema maps, EXPRESS files, rule modules) are not found by
   PyInstaller's analysis: build with `--collect-all ifcopenshell`.
2. `ifcopenshell.express` imports `codegen` and `express_parser` as top-level modules
   from its own folder and, if `express_parser.py` is missing, **runs
   `sys.executable bootstrap.py`** to generate it. In a frozen program `sys.executable` is
   the program itself, which then relaunched and opened its main window. Fix: add that
   folder to the search path, declare both modules as hidden imports and ship
   `express_parser.py` as a file. Any import of `brunelleschi.ifc` triggers this.
3. The executable must refuse arguments it does not recognise and exit without opening
   a window, so that any library repeating that trick cannot open a window.
4. A windowed build shows PyInstaller's own dialog on an unhandled exception at start-up.
   The real program installs its own handler (log file and a readable message).
5. EXPRESS rule checks need pytest at run time (ADR 0007). The shipped program validates
   IFC against the schema only and says so; full validation stays in the test suite.

Licence: PyInstaller's bootloader exception allows distributing bundled programs under
our licence. A one-folder build keeps the Qt and PySide6 libraries as separate,
replaceable files, which suits the LGPL obligations (to be confirmed in the release
review of ADR 0004).

## Not tried

- **Nuitka** (compiles Python to C: faster start, longer builds, needs a C compiler).
- **Briefcase** (makes installers; less control over the frozen layout).

Both remain options if start-up time or antivirus false positives (a known nuisance with
PyInstaller executables) become a problem.

## Recommendation: PyInstaller, one-folder build

- It worked on the first full stack with problems that are now understood and listed.
- One folder rather than one file: one-file builds unpack to a temporary folder at each
  start (slower, and more often flagged by antivirus).
- A build script and a smoke test (the self-test above, run with no Python on the PATH)
  come with M15; an installer (for example Inno Setup) is a later, separate decision.

## Amendment (2026-11-16): the first real build

Built early, at the owner's request, after M14. `tools/build_exe.py` runs PyInstaller with
the fixes listed above (all five were needed and worked first time) on
`packaging/entry.py`; `--check` then runs the program's own self-tests
(`brunelleschi.gui.selftest`) with no Python on the PATH, no console and a timeout.

- 291 MB folder, built in about two minutes.
- Frozen self-test: save and load, IFC export valid with schema and EXPRESS rules (pytest
  ends up bundled by `--collect-all ifcopenshell`, so the rules do run), the IFC read back
  as a reference through IfcOpenShell's geometry iterator, SVG, DXF, the main window built
  in memory; and, separately, the 3D view drawn with OpenGL off screen. All pass.
- An unknown argument exits with code 2 in half a second, without a window.
- Unexpected errors, at start-up or inside Qt slots, go to
  `%LOCALAPPDATA%\BrunelleschiBIM\logs\crash-*.log` with a short message box; never
  PyInstaller's dialog.

Still for M16: an installer (Start menu entry, `.bbim` association, icon), version
information in the executable, and a build in CI.
