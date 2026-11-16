# Vision

BrunelleschiBIM is an open-source BIM authoring tool. The long-term goal is a credible
alternative to Revit for building design. Functional parity is a multi-year target, so
the project grows in small vertical slices that work end to end and are tested.

## Who it is for (first)

Small Italian practices and individual designers working on residential and small
commercial buildings.

- Metric units, Italian/European drawing conventions.
- They need coherent plans, sections and schedules more than photorealism.
- They exchange models with consultants through IFC and drawings through DWG/DXF.
- They cannot justify a Revit seat for every desk, and they dislike being locked into a
  file format they cannot read.

## Goals

1. **Relational parametric model.** Elements know their constraints: a wall is bound to
   levels, a door is hosted by a wall. A change propagates to everything that depends on
   it.
2. **Documentation derived from the model.** Plans, sections and schedules are generated,
   never drawn by hand, so they cannot drift from the model.
3. **Open formats.** IFC is a first-class exchange format. The project file is documented
   text that other tools can read, and files stay readable across versions.
4. **Scripting first.** Everything the user interface does is possible through the API.
   The interface is a client of the core, not the other way round.
5. **Works with CartesioCAD.** Drawings exported from the model open in CartesioCAD (DXF)
   for 2D finishing. BrunelleschiBIM itself ships as a standalone executable.

## Non-goals (for now)

- MEP systems, structural analysis, rendering.
- Reading or writing `.rvt` files.
- Real-time multi-user collaboration.
- A graphical family editor.
- Writing our own geometry kernel or IFC parser.

## What "done" means for a feature

A feature is done when it has automated tests, the tests pass, and it has been run for
real from the command line or a script. A feature that only works in the interface is
not done.

## Honest expectations

- Phase 1 (levels, walls with corner joins, hosted door and window, level change
  propagation, IFC4 export, plan SVG) is a few focused sessions of work.
- A tool a practice could use for a real small project needs at least slabs, roofs,
  stairs, sections, schedules, sheets, a usable 3D interface and IFC import. That is
  many months of steady work, not weeks.
- Revit parity is years away and may never be complete. The aim is to be excellent in a
  narrow niche (model to coherent drawings and schedules for small buildings) before
  being broad.
- The largest technical risks are wall join robustness, change propagation corner cases,
  and performance of a Python core on large models. They are tracked in `ROADMAP.md`.
