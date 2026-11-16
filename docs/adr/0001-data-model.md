# ADR 0001: Internal parametric model as the source of truth, IFC derived

Status: proposed (2026-11-16)

## Context

A BIM model can be stored in two ways.

- **Native IFC.** The IFC file is the model. The program edits IFC entities directly in
  memory and saves them. Bonsai works this way.
- **Internal model.** The program has its own data structure and translates to and from
  IFC on export and import. Revit and Archicad work this way.

What differs in practice is where *design intent* lives. IFC describes the result well:
this wall, this hole, this door filling the hole. It does not describe the rules that
produced it: "the wall goes up to Level 2", "the door is 0.90 m from the corner", "these
two walls meet in a mitre". Our first goal is exactly those rules and their propagation.

## Decision

The source of truth is our own parametric model (elements, parameters, references,
constraints). IFC4 is generated from it on export and validated. IFC import is added
later.

## Why

- Constraints need a home. In native IFC they would have to be hidden in custom property
  sets, which other programs ignore or destroy on re-export, so the "native" file would
  not be portable in the way that matters.
- Export as a pure function is easy to test: same model, same IFC, stable GlobalIds.
- We are free to change the internal schema with migrations without waiting for, or
  bending, an ISO schema.
- IfcOpenShell's authoring API still changes between versions (the opening functions
  moved from `void.*` to `feature.*` in 0.9). Keeping it behind an export module limits
  the damage.

## Costs we accept

- Importing someone else's IFC gives non-parametric elements at first. Recognising walls
  and openings as parametric objects is a later, partial effort.
- Two representations must stay consistent. Mitigated by validating every export in the
  test suite.
- We do not get Bonsai's "open any IFC and edit it" for free.

## Alternatives rejected

- **Native IFC (Bonsai approach).** Proven and elegant for IFC round-trips, weak for
  parametric propagation. Also a second native-IFC authoring tool adds little next to
  Bonsai.
- **Hybrid: IFC plus a sidecar file for constraints.** Two files that must never get out
  of sync, with IFC GlobalIds as the only link. Fragile.

## Revisit when

IFC gains a standard, widely implemented way to carry parametric constraints, or IFC
import/round-trip becomes more important to users than propagation.
