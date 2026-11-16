"""The ``bbim`` command-line tool.

A thin client of ``brunelleschi.api``: it parses arguments, calls the API and prints the
result. It holds no model logic of its own.

Examples::

    bbim new house.bbim --name "House"
    bbim level add house.bbim "Ground floor" 0
    bbim level add house.bbim "First floor" 3.00
    bbim level move house.bbim "First floor" 3.20
    bbim level list house.bbim
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from brunelleschi import __version__, api

EXIT_OK = 0
EXIT_ERROR = 1  # the command was understood but could not be carried out
EXIT_USAGE = 2  # argparse's own code for invalid arguments


def _elevation(text: str) -> float:
    """Metres. A decimal comma is accepted, as Italian users type it."""
    try:
        return float(text.replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number of metres: {text!r}") from None


def _fmt(value: float) -> str:
    return f"{value:+.3f} m"


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


def _cmd_schema(args: argparse.Namespace) -> int:
    print(json.dumps(api.json_schema(), indent=2, sort_keys=True, ensure_ascii=False))
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
    p.set_defaults(func=_cmd_schema)

    level = sub.add_parser("level", help="add, change, delete and list levels")
    lsub = level.add_subparsers(dest="level_command", metavar="ACTION", required=True)

    p = lsub.add_parser("add", help="add a level")
    p.add_argument("file")
    p.add_argument("name")
    p.add_argument("elevation", type=_elevation, help="metres from the project zero")
    p.set_defaults(func=_cmd_level_add)

    p = lsub.add_parser("rename", help="rename a level")
    p.add_argument("file")
    p.add_argument("level", help="current name")
    p.add_argument("new_name")
    p.set_defaults(func=_cmd_level_rename)

    p = lsub.add_parser("move", help="change the elevation of a level")
    p.add_argument("file")
    p.add_argument("level", help="level name")
    p.add_argument("elevation", type=_elevation, help="new elevation in metres")
    p.set_defaults(func=_cmd_level_move)

    p = lsub.add_parser("delete", help="delete a level")
    p.add_argument("file")
    p.add_argument("level", help="level name")
    p.set_defaults(func=_cmd_level_delete)

    p = lsub.add_parser("list", help="list levels, highest first")
    p.add_argument("file")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=_cmd_level_list)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line tool and return the process exit code."""
    # Level names can hold any character; on Windows a redirected stream would otherwise
    # use the legacy code page and fail on them.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
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
