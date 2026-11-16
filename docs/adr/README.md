# Architecture Decision Records

One record per decision that is expensive to reverse. Each states the decision, why, the
costs accepted and the alternatives rejected. A decision is changed by adding a new
record that supersedes the old one, not by editing history.

| No. | Decision | Status |
|---|---|---|
| [0001](0001-data-model.md) | Internal parametric model as the source of truth, IFC derived | proposed |
| [0002](0002-geometry-and-ifc-libraries.md) | IfcOpenShell for IFC and 3D, Shapely for 2D, no kernel of our own | proposed |
| [0003](0003-language-and-tooling.md) | Python core, managed with uv | proposed |
| [0004](0004-license.md) | LGPL-3.0-or-later | proposed |
| [0005](0005-ui-strategy.md) | Standalone desktop executable; CartesioCAD through files | proposed |
| [0006](0006-project-file-format.md) | Documented JSON project file; IFC, DXF, SVG for exchange | proposed |
| [0007](0007-ifc-version-and-validation.md) | Export IFC4, validate every export | proposed |
| [0008](0008-3d-view.md) | 3D view: own OpenGL 3.3 behind a small `Viewport` interface | accepted |
| [0009](0009-packaging.md) | Executable: PyInstaller, one-folder build | accepted |
