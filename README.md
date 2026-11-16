# BrunelleschiBIM

Open-source BIM authoring. The aim is a relational parametric building model, with
drawings, schedules and IFC always derived from it.

> Status: **pre-alpha**. The repository holds the design and the project scaffolding.
> There is no modelling functionality yet. See [the roadmap](docs/ROADMAP.md).

## Ideas

- **Elements know their constraints.** A wall is bound to levels, a door is hosted by a
  wall, and a change propagates.
- **Documentation comes from the model.** Plans, sections and schedules are generated.
- **Open formats.** IFC for exchange; a documented text project file.
- **Scripting first.** The core is a Python library and a command-line tool. A graphical
  interface comes later and is only a client of the core.

Read [the vision](docs/VISION.md), [the architecture](docs/ARCHITECTURE.md) and
[the decision records](docs/adr/README.md).

## Development

Requires [uv](https://docs.astral.sh/uv/). It installs the right Python version itself.

```
uv sync                 # create the environment from the lock file
uv run pytest           # tests
uv run ruff check       # lint
uv run ruff format      # format
uv run mypy             # type check
uv run bbim --version   # the command-line tool
```

## Licence

LGPL-3.0-or-later. See [LICENSE](LICENSE) (GNU Lesser General Public License) and
[COPYING](COPYING) (GNU General Public License, which the LGPL builds on).
