"""Regeneration of derived state, recomputing only what a change affects.

Derived state (wall joins and footprints for now) is kept per project in a cache. Before
each query the cache compares what every wall's derived state depends on with what it
saw last time, and recomputes only the join points around walls that changed. Commands
do not notify the cache, so nothing can be forgotten: a value whose inputs are unchanged
is reused, everything else is recomputed.
"""

from brunelleschi.regen.walls import (
    WallFootprint,
    WallGeometry,
    WallGeometryCache,
    wall_geometry,
)

__all__ = ["WallFootprint", "WallGeometry", "WallGeometryCache", "wall_geometry"]
