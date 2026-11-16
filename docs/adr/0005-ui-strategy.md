# ADR 0005: Standalone desktop executable, client of the core; CartesioCAD through files

Status: proposed (2026-11-16). The interface is not built in Phase 1.

## Context

The owner wants a standalone `.exe` and integration with CartesioCAD (the project's 2D
CAD, C++/Qt, GPL-3.0). The core is headless first.

## Decision

- The interface will be a **desktop application in PySide6 (Qt 6)**, packaged as a
  standalone executable (one folder, launched by double click).
- It uses only the public `api` module. No model logic lives in the interface.
- **Integration with CartesioCAD is through files**, not shared code:
  - drawings (plans, later sections and sheets) export to **DXF**, which CartesioCAD
    opens for 2D finishing and printing;
  - later, an "Open in CartesioCAD" action can launch CartesioCAD on the exported file.
- The 3D viewport technology is **not decided now**. It is chosen in the first interface
  milestone, after a short comparison on a real model.

## Why

- Qt gives the same look and conventions as CartesioCAD without sharing a code base or a
  licence (CartesioCAD is GPL, this project is LGPL).
- A file boundary keeps both programs independently releasable.
- Deferring the 3D viewport avoids choosing a rendering stack before we know model sizes.

## Costs we accept

- A PySide6 executable is large (order of 150 MB or more) and starts slower than a native
  one.
- DXF exchange is one-way at first: edits made in CartesioCAD do not flow back into the
  model.

## Amendment (2026-11-16, M8)

- 3D view: our own OpenGL 3.3 view in Qt, behind a `Viewport` interface (ADR 0008).
  Qt Quick 3D is GPLv3-only and Qt 3D is deprecated; both are excluded.
- Packaging: PyInstaller, one-folder build (ADR 0009). Measured size 269 MB, smaller
  than estimated above; start-up about 1 s.

## Alternatives rejected

- **Blender add-on (like Bonsai).** Excellent viewport for free, but not a standalone
  executable and it ties the product to Blender's interface.
- **Local web interface.** Easy to build, awkward as a double-click desktop program and
  for large models.
- **BIM features inside CartesioCAD.** One program, but it would force the C++ stack and
  GPL on the core and abandon headless-first.
- **C++/Qt interface embedding the Python core.** Smallest executable, most complex
  build.
