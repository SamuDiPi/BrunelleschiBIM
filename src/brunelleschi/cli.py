"""The ``bbim`` command-line tool.

A thin client of ``brunelleschi.api``: it parses arguments, calls the API and prints the
result. It holds no model logic of its own.

Examples::

    bbim new house.bbim --name "House"
    bbim level add house.bbim "Ground floor" 0
    bbim level add house.bbim "First floor" 3.00
    bbim wall add house.bbim --start 0 0 --end 5 0 --thickness 0.30 \\
        --base "Ground floor" --top "First floor"
    bbim level move house.bbim "First floor" 3.20
    bbim wall list house.bbim
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from brunelleschi import __version__, api

EXIT_OK = 0
EXIT_ERROR = 1  # the command was understood but could not be carried out
EXIT_USAGE = 2  # argparse's own code for invalid arguments


def _metres(text: str) -> float:
    """Metres. A decimal comma is accepted, as Italian users type it."""
    try:
        return float(text.replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number of metres: {text!r}") from None


def _fmt(value: float) -> str:
    return f"{value:+.3f} m"


def _wall_row(project: api.Project, wall: api.Wall) -> dict[str, object]:
    base_z, top_z = project.wall_z_range(wall)
    row: dict[str, object] = {
        "id": str(wall.id),
        "start": [wall.start.x, wall.start.y],
        "end": [wall.end.x, wall.end.y],
        "length": wall.length,
        "thickness": wall.thickness,
        "base_level": project.level(wall.base_level_id).name,
        "base_offset": wall.base_offset,
    }
    if isinstance(wall.top, api.TopAtLevel):
        row["top_level"] = project.level(wall.top.level_id).name
        row["top_offset"] = wall.top.offset
    else:
        row["height"] = wall.top.height
    row["base_z"] = base_z
    row["top_z"] = top_z
    return row


def _describe_wall(project: api.Project, wall: api.Wall) -> str:
    base_z, top_z = project.wall_z_range(wall)
    base = project.level(wall.base_level_id).name
    if isinstance(wall.top, api.TopAtLevel):
        top = f"top {project.level(wall.top.level_id).name!r}"
    else:
        top = f"height {wall.top.height:.3f} m"
    return (
        f"{api.short_id(wall.id)}  ({wall.start.x:g}, {wall.start.y:g}) -> "
        f"({wall.end.x:g}, {wall.end.y:g})  L {wall.length:.3f} m  t {wall.thickness:.3f} m  "
        f"z {base_z:+.3f} .. {top_z:+.3f} m  base {base!r}, {top}"
    )


# ----------------------------------------------------------------- commands


def _cmd_new(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if path.exists() and not args.force:
        raise api.BrunelleschiError(f"{path} already exists (use --force to overwrite it)")
    project = api.new_project(args.name or path.stem)
    api.save(project, path)
    print(f"created {path} (project {project.name!r})")
    return EXIT_OK


def _cmd_info(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    print(f"project: {project.name}")
    print(f"levels:  {len(project.levels)}")
    print(f"walls:   {len(project.walls)}")
    print(f"doors:   {len(project.doors)}")
    print(f"windows: {len(project.windows)}")
    return EXIT_OK


def _cmd_level_add(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    level = api.add_level(project, args.name, args.elevation)
    api.save(project, args.file)
    print(f"added level {level.name!r} at {_fmt(level.elevation)}")
    return EXIT_OK


def _cmd_level_rename(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    old = project.level(args.level).name
    level = api.rename_level(project, args.level, args.new_name)
    api.save(project, args.file)
    print(f"renamed level {old!r} to {level.name!r}")
    return EXIT_OK


def _cmd_level_move(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    before = project.level(args.level).elevation
    level = api.set_level_elevation(project, args.level, args.elevation)
    api.save(project, args.file)
    print(f"moved level {level.name!r} from {_fmt(before)} to {_fmt(level.elevation)}")
    walls = project.walls_on_level(level.id)
    if walls:
        print(f"{len(walls)} wall(s) follow: " + ", ".join(api.short_id(w.id) for w in walls))
    return EXIT_OK


def _cmd_level_delete(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    level = api.delete_level(project, args.level)
    api.save(project, args.file)
    print(f"deleted level {level.name!r}")
    return EXIT_OK


def _cmd_level_list(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    levels = project.levels_by_elevation()
    if args.json:
        rows = [{"id": str(lv.id), "name": lv.name, "elevation": lv.elevation} for lv in levels]
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return EXIT_OK
    if not levels:
        print("no levels")
    for lv in reversed(levels):  # highest first, as in a section
        print(f"{_fmt(lv.elevation):>14}  {lv.name}")
    return EXIT_OK


def _cmd_wall_add(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    wall = api.add_wall(
        project,
        args.start,
        args.end,
        args.thickness,
        args.base,
        base_offset=args.base_offset,
        top_level=args.top,
        top_offset=args.top_offset or 0.0,
        height=args.height,
    )
    api.save(project, args.file)
    print(wall.id if args.quiet else f"added wall {_describe_wall(project, wall)}")
    return EXIT_OK


def _cmd_wall_modify(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    wall = api.modify_wall(
        project,
        args.wall,
        start=args.start,
        end=args.end,
        thickness=args.thickness,
        base_level=args.base,
        base_offset=args.base_offset,
        top_level=args.top,
        top_offset=args.top_offset,
        height=args.height,
    )
    api.save(project, args.file)
    print(f"modified wall {_describe_wall(project, wall)}")
    return EXIT_OK


def _cmd_wall_delete(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    hosted = project.hosted_in(project.wall(args.wall).id)
    wall = api.delete_wall(project, args.wall)
    api.save(project, args.file)
    print(f"deleted wall {api.short_id(wall.id)}")
    for e in hosted:
        print(f"  and its {e.kind} {api.short_id(e.id)}")
    return EXIT_OK


def _cmd_wall_list(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    if args.json:
        footprints = api.wall_geometry(project).footprints
        rows = [
            _wall_row(project, w) | {"footprint": [list(c) for c in footprints[w.id].corners]}
            for w in project.walls
        ]
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return EXIT_OK
    if not project.walls:
        print("no walls")
    for wall in project.walls:
        print(_describe_wall(project, wall))
    return EXIT_OK


def _pt(p: tuple[float, float]) -> str:
    return f"({p[0]:.3f}, {p[1]:.3f})"


def _cmd_wall_joins(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    geometry = api.wall_geometry(project)
    if args.json:
        data = {
            "joins": [
                {
                    "kind": str(j.kind),
                    "point": list(j.point),
                    "walls": [str(w) for w in j.walls],
                }
                for j in geometry.joins
            ],
            "issues": [
                {"point": list(i.point), "walls": [str(w) for w in i.walls], "message": i.message}
                for i in geometry.issues
            ],
        }
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return EXIT_OK
    if not geometry.joins and not geometry.issues:
        print("no joins")
    for j in geometry.joins:
        print(f"{j.kind:<9} {_pt(j.point):<22} " + " ".join(api.short_id(w) for w in j.walls))
    for i in geometry.issues:
        walls = " ".join(api.short_id(w) for w in i.walls)
        print(f"{'warning':<9} {_pt(i.point):<22} {walls}: {i.message}")
    return EXIT_OK


def _hosted_row(project: api.Project, e: api.HostedElement) -> dict[str, object]:
    o = api.wall_geometry(project).openings[e.id]
    row: dict[str, object] = {
        "id": str(e.id),
        "kind": e.kind,
        "wall": str(e.host_id),
        "position": e.position,
        "width": e.width,
        "height": e.height,
        "sill_height": e.sill_height,
    }
    if isinstance(e, api.Door):
        row["swing"] = {"side": str(e.swing_side), "hinge": str(e.hinge)}
    row["z_bottom"] = o.z_bottom
    row["z_top"] = o.z_top
    return row


def _describe_hosted(project: api.Project, e: api.HostedElement) -> str:
    o = api.wall_geometry(project).openings[e.id]
    text = (
        f"{e.kind:<6} {api.short_id(e.id)}  in wall {api.short_id(e.host_id)}  "
        f"at {e.position:.3f} m  {e.width:.3f} x {e.height:.3f} m  "
        f"sill {e.sill_height:.3f} m  z {o.z_bottom:+.3f} .. {o.z_top:+.3f} m"
    )
    if isinstance(e, api.Door):
        text += f"  swings {e.swing_side}, hinge at {e.hinge}"
    return text


def _cmd_hosted_add(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    element: api.HostedElement
    if args.kind == "door":
        element = api.add_door(
            project,
            args.wall,
            args.position,
            args.width,
            args.height,
            sill_height=args.sill or 0.0,
            swing_side=args.swing or "left",
            hinge=args.hinge or "start",
        )
    else:
        element = api.add_window(
            project, args.wall, args.position, args.width, args.height, args.sill
        )
    api.save(project, args.file)
    print(element.id if args.quiet else f"added {_describe_hosted(project, element)}")
    return EXIT_OK


def _cmd_hosted_modify(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    element = project.hosted_element(args.element)
    if element.kind != args.kind:
        raise api.NotFoundError(f"{args.element!r} is a {element.kind}, not a {args.kind}")
    api.modify_hosted(
        project,
        element.id,
        wall=args.wall,
        position=args.position,
        width=args.width,
        height=args.height,
        sill_height=args.sill,
        swing_side=getattr(args, "swing", None),
        hinge=getattr(args, "hinge", None),
    )
    api.save(project, args.file)
    print(f"modified {_describe_hosted(project, element)}")
    return EXIT_OK


def _cmd_hosted_delete(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    element = project.hosted_element(args.element)
    if element.kind != args.kind:
        raise api.NotFoundError(f"{args.element!r} is a {element.kind}, not a {args.kind}")
    api.delete_hosted(project, element.id)
    api.save(project, args.file)
    print(f"deleted {element.kind} {api.short_id(element.id)}")
    return EXIT_OK


def _cmd_hosted_list(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    elements = [e for e in project.hosted if e.kind == args.kind]
    if args.json:
        print(json.dumps([_hosted_row(project, e) for e in elements], indent=2))
        return EXIT_OK
    if not elements:
        print(f"no {args.kind}s")
    for e in elements:
        print(_describe_hosted(project, e))
    return EXIT_OK


def _cmd_check(args: argparse.Namespace) -> int:
    """Warnings about the model's geometry. The model itself is always valid once loaded."""
    project = api.load(args.file)
    issues = api.wall_geometry(project).issues
    if not issues:
        print("no warnings")
    for i in issues:
        print(f"warning {_pt(i.point)}: {i.message}")
    return EXIT_OK


def _print_validation(path: str) -> int:
    from brunelleschi.ifc import validate_ifc

    result = validate_ifc(path)
    scope = "schema and rules" if result.rules_checked else "schema only (install pytest for rules)"
    for issue in result.issues:
        print(f"  {issue.level}: {issue.message} {issue.instance}".rstrip())
    if result.issues:
        print(f"{path}: {len(result.issues)} problem(s) found ({scope})", file=sys.stderr)
        return EXIT_ERROR
    print(f"{path}: valid IFC4 ({scope})")
    return EXIT_OK


def _cmd_ifc_export(args: argparse.Namespace) -> int:
    # Imported here: IfcOpenShell takes a moment to load and most commands do not need it.
    from brunelleschi.ifc import write_ifc

    project = api.load(args.file)
    write_ifc(project, args.output)
    print(
        f"wrote {args.output}: {len(project.levels)} storeys, {len(project.walls)} walls, "
        f"{len(project.doors)} doors, {len(project.windows)} windows"
    )
    return _print_validation(args.output) if args.validate else EXIT_OK


def _cmd_ifc_validate(args: argparse.Namespace) -> int:
    if not Path(args.ifc).is_file():
        raise api.BrunelleschiError(f"file not found: {args.ifc}")
    return _print_validation(args.ifc)


def _scale(text: str) -> float:
    """``50`` or ``1:50``."""
    value = text.split(":", 1)[1] if text.startswith("1:") else text
    try:
        scale = float(value.replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a scale: {text!r} (use 50 or 1:50)") from None
    if not scale > 0:
        raise argparse.ArgumentTypeError(f"the scale must be positive: {text!r}")
    return scale


def _cmd_plan(args: argparse.Namespace) -> int:
    project = api.load(args.file)
    sheet = api.Sheet(paper=args.paper, portrait=args.portrait, scale=args.scale)
    level = project.level(args.level)
    api.write_plan_svg(project, level.id, args.output, sheet, args.cut)
    print(
        f"wrote {args.output}: plan of {level.name!r} cut at {args.cut:.2f} m, "
        f"1:{args.scale:g} on {sheet.label}"
    )
    return EXIT_OK


def _cmd_schema(args: argparse.Namespace) -> int:
    schema = api.json_schema(args.schema_version)
    text = json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    return EXIT_OK


# ------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bbim",
        description="BrunelleschiBIM: build and query a parametric building model.",
    )
    parser.add_argument("--version", action="version", version=f"bbim {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("new", help="create a project file")
    p.add_argument("file", help="the .bbim file to create")
    p.add_argument("--name", help="project name (default: the file name)")
    p.add_argument("--force", action="store_true", help="overwrite an existing file")
    p.set_defaults(func=_cmd_new)

    p = sub.add_parser("info", help="summary of a project file")
    p.add_argument("file")
    p.set_defaults(func=_cmd_info)

    p = sub.add_parser("schema", help="print the JSON Schema of the project file")
    p.add_argument(
        "--schema-version",
        type=int,
        default=api.CURRENT_SCHEMA_VERSION,
        help=f"file version (default: {api.CURRENT_SCHEMA_VERSION}, the current one)",
    )
    p.add_argument("--output", "-o", help="write to a file (UTF-8, LF) instead of printing")
    p.set_defaults(func=_cmd_schema)

    _level_parsers(sub)
    _wall_parsers(sub)
    _hosted_parsers(sub, "door")
    _hosted_parsers(sub, "window")

    ifc = sub.add_parser("ifc", help="export and validate IFC4 files")
    isub = ifc.add_subparsers(dest="ifc_command", metavar="ACTION", required=True)
    p = isub.add_parser("export", help="write the project as an IFC4 file")
    p.add_argument("file", help="the .bbim project")
    p.add_argument("output", help="the .ifc file to write")
    p.add_argument("--validate", action="store_true", help="validate the written file")
    p.set_defaults(func=_cmd_ifc_export)
    p = isub.add_parser("validate", help="validate an IFC file (schema and rules)")
    p.add_argument("ifc", help="the .ifc file")
    p.set_defaults(func=_cmd_ifc_validate)

    p = sub.add_parser("plan", help="draw the plan of a level as SVG, at a scale on paper")
    p.add_argument("file", help="the .bbim project")
    p.add_argument("level", help="level name")
    p.add_argument("output", help="the .svg file to write")
    p.add_argument(
        "--cut", type=_metres, default=1.2, help="cut height above the level (default 1.20 m)"
    )
    p.add_argument("--scale", type=_scale, default=50.0, help="for example 50 or 1:50")
    p.add_argument("--paper", default="A3", choices=["A4", "A3", "A2", "A1", "A0"])
    p.add_argument("--portrait", action="store_true", help="portrait instead of landscape")
    p.set_defaults(func=_cmd_plan)

    p = sub.add_parser("check", help="list geometric warnings (joins, openings)")
    p.add_argument("file")
    p.set_defaults(func=_cmd_check)
    return parser


def _level_parsers(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    level = sub.add_parser("level", help="add, change, delete and list levels")
    lsub = level.add_subparsers(dest="level_command", metavar="ACTION", required=True)

    p = lsub.add_parser("add", help="add a level")
    p.add_argument("file")
    p.add_argument("name")
    p.add_argument("elevation", type=_metres, help="metres from the project zero")
    p.set_defaults(func=_cmd_level_add)

    p = lsub.add_parser("rename", help="rename a level")
    p.add_argument("file")
    p.add_argument("level", help="current name")
    p.add_argument("new_name")
    p.set_defaults(func=_cmd_level_rename)

    p = lsub.add_parser("move", help="change the elevation of a level; bound walls follow")
    p.add_argument("file")
    p.add_argument("level", help="level name")
    p.add_argument("elevation", type=_metres, help="new elevation in metres")
    p.set_defaults(func=_cmd_level_move)

    p = lsub.add_parser("delete", help="delete a level (refused while walls use it)")
    p.add_argument("file")
    p.add_argument("level", help="level name")
    p.set_defaults(func=_cmd_level_delete)

    p = lsub.add_parser("list", help="list levels, highest first")
    p.add_argument("file")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=_cmd_level_list)


def _wall_parsers(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    wall = sub.add_parser("wall", help="add, change, delete and list walls")
    wsub = wall.add_subparsers(dest="wall_command", metavar="ACTION", required=True)

    p = wsub.add_parser("add", help="add a straight wall")
    p.add_argument("file")
    _wall_options(p, required=True)
    p.add_argument("--quiet", "-q", action="store_true", help="print only the new id")
    p.set_defaults(func=_cmd_wall_add)

    p = wsub.add_parser("modify", help="change parameters of a wall")
    p.add_argument("file")
    p.add_argument("wall", help="wall id (a unique prefix of at least 4 characters)")
    _wall_options(p, required=False)
    p.set_defaults(func=_cmd_wall_modify)

    p = wsub.add_parser("delete", help="delete a wall")
    p.add_argument("file")
    p.add_argument("wall", help="wall id (a unique prefix of at least 4 characters)")
    p.set_defaults(func=_cmd_wall_delete)

    p = wsub.add_parser("list", help="list walls with their derived elevations")
    p.add_argument("file")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=_cmd_wall_list)

    p = wsub.add_parser("joins", help="list wall joins and walls that could not be joined")
    p.add_argument("file")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=_cmd_wall_joins)


def _hosted_parsers(sub: argparse._SubParsersAction[argparse.ArgumentParser], kind: str) -> None:
    group = sub.add_parser(kind, help=f"add, change, delete and list {kind}s")
    gsub = group.add_subparsers(dest=f"{kind}_command", metavar="ACTION", required=True)
    element_help = f"{kind} id (a unique prefix of at least 4 characters)"

    p = gsub.add_parser("add", help=f"place a {kind} in a wall")
    p.add_argument("file")
    p.add_argument("wall", help="host wall id (a unique prefix of at least 4 characters)")
    _hosted_options(p, kind, adding=True)
    p.add_argument("--quiet", "-q", action="store_true", help="print only the new id")
    p.set_defaults(func=_cmd_hosted_add, kind=kind)

    p = gsub.add_parser("modify", help=f"change parameters of a {kind}")
    p.add_argument("file")
    p.add_argument("element", metavar=kind.upper(), help=element_help)
    p.add_argument("--wall", help="move it to another wall")
    _hosted_options(p, kind, adding=False)
    p.set_defaults(func=_cmd_hosted_modify, kind=kind)

    p = gsub.add_parser("delete", help=f"delete a {kind}")
    p.add_argument("file")
    p.add_argument("element", metavar=kind.upper(), help=element_help)
    p.set_defaults(func=_cmd_hosted_delete, kind=kind)

    p = gsub.add_parser("list", help=f"list {kind}s")
    p.add_argument("file")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=_cmd_hosted_list, kind=kind)


def _hosted_options(p: argparse.ArgumentParser, kind: str, *, adding: bool) -> None:
    p.add_argument(
        "--position",
        type=_metres,
        required=adding,
        help="distance of the centre from the wall's start, in metres",
    )
    p.add_argument("--width", type=_metres, required=adding, help="metres")
    p.add_argument("--height", type=_metres, required=adding, help="metres")
    p.add_argument(
        "--sill",
        type=_metres,
        required=adding and kind == "window",
        help="height of the bottom above the wall's base, in metres"
        + (" (default 0)" if kind == "door" and adding else ""),
    )
    if kind == "door":
        p.add_argument(
            "--swing",
            choices=["left", "right"],
            help="side the leaf opens to, seen from the wall's start (default left)",
        )
        p.add_argument(
            "--hinge",
            choices=["start", "end"],
            help="jamb with the hinges: nearer the wall's start or end (default start)",
        )


def _wall_options(p: argparse.ArgumentParser, *, required: bool) -> None:
    for name, what in (("--start", "start"), ("--end", "end")):
        p.add_argument(
            name,
            nargs=2,
            type=_metres,
            metavar=("X", "Y"),
            required=required,
            help=f"{what} of the centre line, in metres",
        )
    p.add_argument("--thickness", type=_metres, required=required, help="metres")
    p.add_argument("--base", required=required, help="base level name")
    p.add_argument(
        "--base-offset",
        type=_metres,
        default=0.0 if required else None,
        help="metres above the base level",
    )
    top = p.add_mutually_exclusive_group(required=required)
    top.add_argument("--top", help="top level name (the wall top follows it)")
    top.add_argument("--height", type=_metres, help="unconnected height in metres")
    p.add_argument("--top-offset", type=_metres, help="metres above the top level")


_NEGATIVE_DECIMAL_COMMA = re.compile(r"-\d*,\d+")


def _negative_commas(argv: Sequence[str]) -> list[str]:
    """Write ``-0,20`` as ``-0.20``.

    argparse recognises ``-0.20`` as a negative number but takes ``-0,20`` for an option.
    """
    return [a.replace(",", ".") if _NEGATIVE_DECIMAL_COMMA.fullmatch(a) else a for a in argv]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line tool and return the process exit code."""
    # Level names can hold any character; on Windows a redirected stream would otherwise
    # use the legacy code page and fail on them.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(_negative_commas(sys.argv[1:] if argv is None else argv))
    func: Callable[[argparse.Namespace], int] | None = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return EXIT_OK
    try:
        return func(args)
    except api.BrunelleschiError as exc:
        print(f"bbim: error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
