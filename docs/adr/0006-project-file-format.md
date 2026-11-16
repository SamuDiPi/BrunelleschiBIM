# ADR 0006: Documented JSON project file; IFC, DXF and SVG as exchange formats

Status: proposed (2026-11-16)

## Context

The owner asked for a format that lets programs "talk to each other". There are two
separate needs: saving the project with all its design intent, and exchanging data with
other software.

## Decision

**Project file: `.bbim`, a single UTF-8 JSON document.**

- Contains `schema_version`, project settings, and the list of elements with their
  parameters and references. No derived geometry.
- Written deterministically (stable element order, sorted keys, fixed number
  formatting), so two saves of the same model are identical and `git diff` is readable.
- A **JSON Schema** for each schema version is published in the repository. Any program,
  CartesioCAD included, can read a `.bbim` file with an ordinary JSON parser and validate
  it against the schema.
- Older files are upgraded by **migrations**, one small function per version step, each
  with a test and a sample file. A newer file opened by older software fails with a clear
  message instead of loading wrongly.

**Exchange formats:**

| Format | Direction | Purpose |
|---|---|---|
| IFC4 | export first, import later | the BIM model, for consultants and viewers |
| DXF | export | drawings, for CartesioCAD and other CAD programs |
| SVG | export | drawings for the web, documents and tests |

## Why

- Text is inspectable, diffable and recoverable by hand. That matters for trust in a new
  tool and for long-term readability.
- A published schema is what makes a format something other software can speak.
- Keeping derived geometry out of the file keeps it small and removes a class of
  inconsistency bugs.

## Costs we accept

- JSON is slow and large for very big models. If measurements show a problem, a binary
  container can be added later with the same schema; the JSON form stays as the
  interchange and debugging format.
- Every schema change needs a migration and a test.

## Alternatives rejected

- **SQLite file.** Good for partial loading and large models, opaque to diff and to other
  tools.
- **IFC as the project file.** See ADR 0001.
- **Python pickle or another binary dump.** Not readable across versions, unsafe to load.
- **A folder of many small files.** Diff-friendly but awkward for users to move around.
