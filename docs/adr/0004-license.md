# ADR 0004: LGPL-3.0-or-later

Status: proposed (2026-11-16)

## Decision

BrunelleschiBIM is licensed **LGPL-3.0-or-later**.

## Why

- Others can use the core as a library, including in closed programs, while changes to
  the library itself stay open. That suits a headless core meant to be scripted and
  embedded.
- It matches IfcOpenShell (LGPL-3.0-or-later), so there is no licence friction with our
  main dependency.

## Dependency licences (as checked on 2026-11-16)

| Dependency | Licence | Note |
|---|---|---|
| IfcOpenShell | LGPL-3.0-or-later | from PyPI metadata |
| Open CASCADE (inside IfcOpenShell) | LGPL-2.1 with OCCT exception | bundled binary |
| Shapely | BSD-3-Clause | GEOS inside is LGPL-2.1 |
| ezdxf | MIT | DXF writer |
| PySide6 (future interface) | LGPL-3.0 / GPL | to re-check when adopted |

## Open point (not legal advice)

When we ship an executable that bundles these libraries we must include their licence
texts and keep the LGPL parts replaceable. With Python packaging the libraries stay
separate files, which is the easy case, but nobody has reviewed the exact combination of
LGPL-3.0, LGPL-2.1 with the OCCT exception, and our own LGPL-3.0 in one installer. This
needs a proper check before the first binary release.

## Alternatives rejected

- **GPL-3.0** (used by CartesioCAD). Stronger copyleft, but it would stop the core being
  used as a library in closed tools, which works against adoption of an open format.
- **MIT/Apache-2.0.** Allows closed forks of the core with no obligation to share
  improvements.
