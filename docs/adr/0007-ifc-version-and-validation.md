# ADR 0007: Export IFC4, validate every export

Status: proposed (2026-11-16)

## Decision

- Phase 1 exports **IFC4** (ISO 16739-1:2018, ADD2 TC1).
- "Valid" has a concrete meaning, checked at three levels:
  1. **Automated, in every test run:** `ifcopenshell.validate` with schema and EXPRESS
     rules reports zero issues.
  2. **Per milestone, by hand:** the file is uploaded to the buildingSMART validation
     service and the result is recorded in `docs/JOURNAL.md`.
  3. **Per milestone, by hand:** the file is opened in at least one external viewer and
     the walls, openings, door and window are in the right place.
- IFC length unit is the metre in Phase 1. A millimetre option is a later setting.

## Why IFC4 and not IFC4.3

- IFC4.3 is the current ISO standard (16739-1:2024) and adds mostly infrastructure
  content. For buildings, IFC4 is what viewers and consultants handle most reliably. The
  claim that most authoring tools still export IFC4 comes from one secondary source and
  should be confirmed.
- The export module is isolated, so adding IFC4.3 later is a contained task.

## Notes from the Phase 0 probe

- `ifcopenshell.validate` needs `pytest` available at runtime for the EXPRESS rules.
- An element with a representation but no placement is reported as an error, so the
  validator does catch real mistakes.

## Alternatives rejected

- **IFC2x3.** Still widely exchanged, but lacks classes we want and is being retired.
- **IFC4.3 only.** Weaker viewer support for buildings today.
- **Trusting "it opens in a viewer" alone.** Viewers are forgiving; a file can display
  and still be invalid.
