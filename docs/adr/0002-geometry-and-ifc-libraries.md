# ADR 0002: IfcOpenShell for IFC and 3D, Shapely for 2D, no kernel of our own

Status: proposed (2026-11-16)

## Context

We will not write a geometry kernel or an IFC parser. We need: IFC4 read/write and
validation, 3D evaluation of solids with openings, and robust 2D polygon operations for
wall joins and plans.

## Decision

- **IfcOpenShell** (pinned to `0.9.0.post1`) for IFC reading, writing, validation and 3D
  evaluation. It bundles Open CASCADE.
- **Shapely** (GEOS) for 2D footprints, joins and plan geometry.
- All use of both libraries is confined to `geometry/`, `ifc/` and `drawings/`. The
  `model/` module does not import them.

## Verified on 2026-11-16 (Windows, Python 3.13.18)

- `ifcopenshell==0.9.0.post1` installs from PyPI. PyPI metadata says Python
  `>=3.10,<3.16`.
- Creating an IFC4 file with a wall, an `IfcOpeningElement`
  (`feature.add_feature`) and a door filling it (`feature.add_filling`) works.
- `ifcopenshell.validate` reports schema and EXPRESS rule violations. It needs `pytest`
  installed at runtime for the EXPRESS rules.
- `ifcopenshell.geom.create_shape` returns the wall mesh with the opening cut.
- `shapely==2.2.0` and `ezdxf==1.4.5` install and import.

## Risks

- IfcOpenShell is pre-1.0 and renames API functions between releases. Mitigation: pinned
  version, a thin wrapper in `ifc/`, upgrade as a deliberate task with the test suite.
- Moving a hosted element through the IfcOpenShell API does not update the host's cut.
  That is fine for us: we regenerate from our own model and never edit IFC in place.
- Performance of a Python core on large models is unknown. We measure before optimising.

## Alternatives rejected

- **pythonocc / direct Open CASCADE.** More control over solids, far more code, and not
  needed while walls are extrusions.
- **CGAL or Manifold for booleans.** Not needed yet; IFC viewers perform the opening cut.
- **web-ifc, xBIM.** Tied to JavaScript and .NET respectively.
- **Our own 2D polygon code.** Wall joins are where robustness matters most; GEOS is
  battle-tested.
