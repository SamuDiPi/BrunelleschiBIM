"""The ``bbim`` command-line tool.

A thin client of the public API: it parses arguments and prints results, and holds no
model logic of its own.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from brunelleschi import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bbim",
        description="BrunelleschiBIM: build and query a parametric building model.",
    )
    parser.add_argument("--version", action="version", version=f"bbim {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line tool and return the process exit code."""
    parser = build_parser()
    parser.parse_args(argv)
    # No subcommands exist yet (they arrive with milestone M1): show what is available.
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
