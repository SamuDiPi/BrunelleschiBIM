"""BrunelleschiBIM: a relational parametric building model.

The package is headless: everything is usable from Python and from the ``bbim``
command-line tool, without a graphical interface.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("brunelleschi")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
