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
    print(f"added wall {_describe_wall(project, wall)}")
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
    wall = api.delete_wall(project, args.wall)
    api.save(project, args.file)
    print(f"deleted wall {api.short_id(wall.id)}")
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
