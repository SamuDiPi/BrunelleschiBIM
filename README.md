# BrunelleschiBIM

Open-source BIM authoring. The aim is a relational parametric building model, with
drawings, schedules and IFC always derived from it.

> Status: **pre-alpha**, Phase 1 of [the roadmap](docs/ROADMAP.md). The core works from
> Python and from the command line: levels, walls bound to levels with mitred and T
> joins, doors and windows hosted in walls, IFC4 export, plans in SVG. There is no
> graphical interface yet. File formats and APIs may still change (with migrations for
> project files).

## Ideas

- **Elements know their constraints.** A wall is bound to levels, a door is hosted by a
  wall, and a change propagates.
- **Documentation comes from the model.** Plans, sections and schedules are generated.
- **Open formats.** IFC for exchange; a documented text project file
  ([JSON Schema](schemas/)).
- **Scripting first.** The core is a Python library and a command-line tool. A graphical
  interface comes later and is only a client of the core.

Read [the vision](docs/VISION.md), [the architecture](docs/ARCHITECTURE.md) and
[the decision records](docs/adr/README.md).

## Phase 1 in two minutes

A 6 x 4 m room on two levels, with a door and a window. Raise the first floor by 20 cm:
the four walls follow, and the IFC and the plan are regenerated.

### From Python

```python
from brunelleschi import api
from brunelleschi.ifc import write_ifc

project = api.new_project("Casa")
ground = api.add_level(project, "Piano terra", 0.00)
first = api.add_level(project, "Primo piano", 3.00)

corners = [(0, 0), (6, 0), (6, 4), (0, 4)]
south, east, north, west = [
    api.add_wall(project, c, corners[(i + 1) % 4], 0.30, ground.id, top_level=first.id)
    for i, c in enumerate(corners)
]
api.add_door(project, south.id, 1.50, 0.90, 2.10, swing_side="left", hinge="start")
api.add_window(project, north.id, 3.00, 1.20, 1.40, 0.90)

write_ifc(project, "casa-before.ifc")
api.set_level_elevation(project, "Primo piano", 3.20)  # every bound wall follows
write_ifc(project, "casa-after.ifc")
api.write_plan_svg(project, "Piano terra", "casa.svg", api.Sheet("A4", scale=50))
api.save(project, "casa.bbim")
```

The full script, with output: [examples/phase1_demo.py](examples/phase1_demo.py).

### From the command line (PowerShell)

```powershell
bbim new casa.bbim --name Casa
bbim level add casa.bbim "Piano terra" 0
bbim level add casa.bbim "Primo piano" "3,00"        # a decimal comma works; quote it

$o = @("--thickness", "0,30", "--base", "Piano terra", "--top", "Primo piano")
$south = bbim wall add casa.bbim --start 0 0 --end 6 0 @o --quiet   # --quiet: print the id
bbim wall add casa.bbim --start 6 0 --end 6 4 @o
$north = bbim wall add casa.bbim --start 6 4 --end 0 4 @o --quiet
bbim wall add casa.bbim --start 0 4 --end 0 0 @o

bbim door add casa.bbim $south --position "1,50" --width "0,90" --height "2,10"
bbim window add casa.bbim $north --position 3 --width "1,20" --height "1,40" --sill "0,90"
bbim wall joins casa.bbim                             # four mitred corners

bbim level move casa.bbim "Primo piano" "3,20"        # "4 wall(s) follow: ..."
bbim ifc export casa.bbim casa.ifc --validate         # valid IFC4 (schema and rules)
bbim plan casa.bbim "Piano terra" casa.svg --scale 1:50 --paper A4
```

The same session as a script: [phase1_demo.ps1](examples/phase1_demo.ps1), and for a
POSIX shell [phase1_demo.sh](examples/phase1_demo.sh). `bbim --help` and
`bbim COMMAND --help` list every command: `new`, `info`, `level`, `wall`, `door`,
`window`, `check`, `ifc`, `plan`, `schema`.

Both forms are run by the test suite ([tests/test_demo.py](tests/test_demo.py)), which
checks the elevations before and after in the model and in the IFC geometry.

## Development

Requires [uv](https://docs.astral.sh/uv/). It installs the right Python version itself.

```
uv sync                 # create the environment from the lock file
uv run pytest           # tests (--update-golden rewrites the plan golden files)
uv run ruff check       # lint
uv run ruff format      # format
uv run mypy             # type check
uv run bbim --version   # the command-line tool
```

To look at an SVG drawing as an image, see [tools/render_svg.py](tools/render_svg.py).

## Licence

LGPL-3.0-or-later. See [LICENSE](LICENSE) (GNU Lesser General Public License) and
[COPYING](COPYING) (GNU General Public License, which the LGPL builds on).
