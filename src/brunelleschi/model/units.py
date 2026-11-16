"""Units and tolerances shared by the whole model.

All lengths are in metres, stored as ``float``.
"""

from __future__ import annotations

import math

# Two lengths closer than this are the same length (one micrometre).
LENGTH_TOLERANCE = 1e-6

# Largest coordinate or elevation accepted, in metres. Beyond this, float precision at
# the tolerance above starts to degrade, and no building needs it.
MAX_ABS_COORDINATE = 1e6


def lengths_equal(a: float, b: float) -> bool:
    """True if two lengths are equal within ``LENGTH_TOLERANCE``."""
    return abs(a - b) <= LENGTH_TOLERANCE


def is_valid_length(value: float) -> bool:
    """True for a finite length within the supported range."""
    return math.isfinite(value) and abs(value) <= MAX_ABS_COORDINATE
