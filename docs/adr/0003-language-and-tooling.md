# ADR 0003: Python core, managed with uv

Status: proposed (2026-11-16)

## Decision

- The core is written in **Python**, minimum version **3.11**, developed on 3.13.
- **uv** manages Python versions, the virtual environment and the lock file.
- **pytest** for tests, **ruff** for lint and formatting, **mypy** (strict on the core)
  for types.
- Code, comments, commit messages and documentation are in English.

## Why Python

- IfcOpenShell's authoring API is Python-first.
- "Scripting as a first-class citizen" is free: the scripting language is the
  implementation language, and users can read the code that runs their model.
- Fast iteration matters more than raw speed while the design is still moving.

## Costs we accept

- Slower than C++ on large models. Hot spots can move to compiled code later behind the
  same API.
- Packaging a Python desktop application as an executable is heavier than a native one
  (see ADR 0005).
- A different stack from CartesioCAD (C++/Qt), so no code is shared. The two programs
  talk through files (ADR 0006).

## Alternatives rejected

- **C++ and Qt, like CartesioCAD.** Shared skills and a small executable, but IFC and
  parametric modelling would take much longer to reach a first working slice, and
  scripting would need a binding layer.
- **TypeScript in the browser.** Easy to share, weaker for offline desktop work and
  heavy models.
- **Rust.** Attractive for a kernel, but the IFC ecosystem is thin.

## Open point

Model definitions and JSON Schema generation will probably use pydantic v2. To be
confirmed and pinned in milestone M0 after checking its current version and licence.
