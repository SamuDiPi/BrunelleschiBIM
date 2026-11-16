"""Wall joins in plan: which wall ends meet where, and how their ends are cut.

Joins are derived from the walls' centre lines, thicknesses and vertical extents; they
are never stored. Everything here is a pure function of ``WallLine`` values.

Supported, at a point where wall ends meet (only walls whose vertical extents overlap
are considered together):

- one wall end: a square end;
- two wall ends at an angle: an L corner, cut along the line from the inner to the outer
  face intersection (a mitre; it also works for different thicknesses);
- two wall ends continuing in a straight line: both cut square at the point;
- one wall end on another wall's centre line (not at its ends): a T; the ending wall
  stops at the face of the through wall, which is not changed;
- three wall ends, two of which continue each other in a straight line with the same
  thickness (a wall split where another meets it): a straight join plus a T.

Not supported yet; the ends stay square and a ``JoinIssue`` says why:

- other cases with more than two walls at a point (crosses of four ends, two ends plus
  a through wall, a split wall of two thicknesses);
- two walls lying back on each other (angle near zero);
- corners whose cut would reach more than ``MITRE_LIMIT`` half-thicknesses from the
  point (very sharp angles, or nearly straight walls of different thickness), or would
  pass the far end of a short wall;
- walls crossing each other (X) away from their ends (see ``crossings``);
- a wall end inside another wall's thickness but not on its centre line.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from brunelleschi.model.units import LENGTH_TOLERANCE

Vec = tuple[float, float]

# Wall ends meet when their coordinates are equal on this grid (one micrometre). Points
# typed or snapped to millimetres always fall on it.
GRID = 1e-6
PointKey = tuple[int, int]

# A cut corner may lie at most this many half-thicknesses from the join point (the same
# idea as a miter limit in SVG). 10 allows L corners down to about 11.5 degrees.
MITRE_LIMIT = 10.0

# Below this |sin(angle)| two directions are taken as exactly parallel.
PARALLEL_SIN = 1e-12

START, END = 0, 1


def point_key(p: Vec) -> PointKey:
    return (round(p[0] / GRID), round(p[1] / GRID))


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1])


def _add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1])


def _mul(a: Vec, k: float) -> Vec:
    return (a[0] * k, a[1] * k)


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _cross(a: Vec, b: Vec) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _left(u: Vec) -> Vec:
    return (-u[1], u[0])


def _intersect(p1: Vec, d1: Vec, p2: Vec, d2: Vec) -> Vec | None:
    """Intersection of the lines p1 + a d1 and p2 + b d2, or None if parallel."""
    denom = _cross(d1, d2)
    if abs(denom) < PARALLEL_SIN:
        return None
    a = _cross(_sub(p2, p1), d2) / denom
    return _add(p1, _mul(d1, a))


@dataclass(frozen=True, slots=True)
class WallLine:
    """What joins need to know about a wall."""

    id: UUID
    start: Vec
    end: Vec
    thickness: float
    base_z: float
    top_z: float

    @property
    def length(self) -> float:
        return math.dist(self.start, self.end)

    @property
    def direction(self) -> Vec:
        length = self.length
        return ((self.end[0] - self.start[0]) / length, (self.end[1] - self.start[1]) / length)

    @property
    def half(self) -> float:
        return self.thickness / 2

    def endpoint(self, which: int) -> Vec:
        return self.start if which == START else self.end

    def away(self, which: int) -> Vec:
        """Direction from an end into the wall."""
        d = self.direction
        return d if which == START else (-d[0], -d[1])

    def overlaps_vertically(self, other: WallLine) -> bool:
        return min(self.top_z, other.top_z) - max(self.base_z, other.base_z) > LENGTH_TOLERANCE

    def passes_through(self, p: Vec) -> bool:
        """True if ``p`` is on the centre line, strictly between the ends."""
        d = self.direction
        rel = _sub(p, self.start)
        along = _dot(rel, d)
        return (
            abs(_cross(d, rel)) <= LENGTH_TOLERANCE
            and LENGTH_TOLERANCE < along < self.length - LENGTH_TOLERANCE
        )


class JoinKind(StrEnum):
    MITRE = "mitre"
    STRAIGHT = "straight"
    TEE = "tee"


@dataclass(frozen=True, slots=True)
class Join:
    """A join at ``point``. For a tee, ``walls`` is the ending wall followed by the wall,
    or the two straight wall pieces, that it stops against."""

    point: Vec
    kind: JoinKind
    walls: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class JoinIssue:
    """A place where walls meet but are not joined, and why."""

    point: Vec
    walls: tuple[UUID, ...]
    message: str


@dataclass(frozen=True, slots=True)
class EndCorners:
    """The two corners of a wall end; left and right as seen from the wall's start."""

    left: Vec
    right: Vec


@dataclass(frozen=True, slots=True)
class PointSolution:
    joins: tuple[Join, ...]
    issues: tuple[JoinIssue, ...]
    # Cut ends, by (wall id, START or END). Ends not listed are square.
    ends: dict[tuple[UUID, int], EndCorners]


def _end_corners(wall: WallLine, which: int, away_left: Vec, away_right: Vec) -> EndCorners:
    # Seen from the start, the away-left side of the end is the right side.
    if which == START:
        return EndCorners(left=away_left, right=away_right)
    return EndCorners(left=away_right, right=away_left)


def _corner_ok(wall: WallLine, which: int, corner: Vec, limit: float) -> bool:
    p = wall.endpoint(which)
    if math.dist(p, corner) > limit:
        return False
    # The cut must not reach the other end of the wall.
    return _dot(_sub(corner, p), wall.away(which)) < wall.length - LENGTH_TOLERANCE


def _side_lines(wall: WallLine, which: int) -> tuple[tuple[Vec, Vec], tuple[Vec, Vec]]:
    """The away-left and away-right face lines at an end, as (point, direction)."""
    p, u = wall.endpoint(which), wall.away(which)
    n = _mul(_left(u), wall.half)
    return (_add(p, n), u), (_sub(p, n), u)


def _two_ends(
    p: Vec, a: tuple[WallLine, int], b: tuple[WallLine, int]
) -> tuple[Join | None, JoinIssue | None, dict[tuple[UUID, int], EndCorners]]:
    wa, ea = a
    wb, eb = b
    ua, ub = wa.away(ea), wb.away(eb)
    ids = (wa.id, wb.id)
    if abs(_cross(ua, ub)) < PARALLEL_SIN:
        if _dot(ua, ub) > 0:
            return None, JoinIssue(p, ids, "the walls lie on each other; not joined"), {}
        ends = {}
        for w, e in (a, b):
            (ll, _), (rl, _) = _side_lines(w, e)
            ends[(w.id, e)] = _end_corners(w, e, ll, rl)
        return Join(p, JoinKind.STRAIGHT, ids), None, ends

    (a_left, a_dir), (a_right, _) = _side_lines(wa, ea)
    (b_left, b_dir), (b_right, _) = _side_lines(wb, eb)
    # The away-left face of one wall meets the away-right face of the other.
    c1 = _intersect(a_left, a_dir, b_right, b_dir)
    c2 = _intersect(a_right, a_dir, b_left, b_dir)
    assert c1 is not None and c2 is not None  # not parallel, checked above
    limit = MITRE_LIMIT * max(wa.half, wb.half)
    ok = all(_corner_ok(w, e, c, limit) for (w, e) in (a, b) for c in (c1, c2))
    if not ok:
        angle = math.degrees(math.atan2(abs(_cross(ua, ub)), _dot(ua, ub)))
        return (
            None,
            JoinIssue(
                p, ids, f"the corner at {angle:.1f} degrees is too sharp or too short to cut"
            ),
            {},
        )
    ends = {
        (wa.id, ea): _end_corners(wa, ea, c1, c2),
        (wb.id, eb): _end_corners(wb, eb, c2, c1),
    }
    return Join(p, JoinKind.MITRE, ids), None, ends


def _tee(
    p: Vec, ending: tuple[WallLine, int], host: WallLine
) -> tuple[Join | None, JoinIssue | None, dict[tuple[UUID, int], EndCorners]]:
    w, e = ending
    u = w.away(e)
    ids = (w.id, host.id)
    n_host = _left(host.direction)
    if abs(_dot(u, n_host)) < PARALLEL_SIN:
        return None, JoinIssue(p, ids, "the walls lie on each other; not joined"), {}
    side = 1.0 if _dot(u, n_host) > 0 else -1.0
    face_point = _add(host.start, _mul(n_host, side * host.half))
    (left, d), (right, _) = _side_lines(w, e)
    c1 = _intersect(left, d, face_point, host.direction)
    c2 = _intersect(right, d, face_point, host.direction)
    limit = MITRE_LIMIT * max(w.half, host.half)
    if c1 is None or c2 is None or not all(_corner_ok(w, e, c, limit) for c in (c1, c2)):
        return None, JoinIssue(p, ids, "the wall meets the other at too sharp an angle"), {}
    return Join(p, JoinKind.TEE, ids), None, {(w.id, e): _end_corners(w, e, c1, c2)}


def _split_tee(
    p: Vec, ends: list[tuple[WallLine, int]]
) -> tuple[list[Join], dict[tuple[UUID, int], EndCorners]] | None:
    """Three ends where two continue each other in a straight line (a wall split where a
    third wall meets it): a straight join plus a tee. None if that is not the case, or
    if the two straight walls differ in thickness (the face to stop at is ambiguous)."""
    for i in range(3):
        for j in range(i + 1, 3):
            (wa, ea), (wb, eb) = ends[i], ends[j]
            ua, ub = wa.away(ea), wb.away(eb)
            if abs(_cross(ua, ub)) >= PARALLEL_SIN or _dot(ua, ub) >= 0:
                continue
            if abs(wa.thickness - wb.thickness) > LENGTH_TOLERANCE:
                return None
            straight, _, straight_ends = _two_ends(p, ends[i], ends[j])
            (k,) = [e for n, e in enumerate(ends) if n not in (i, j)]
            tee, _, tee_ends = _tee(p, k, wa)
            if straight is None or tee is None:
                return None
            tee = Join(p, JoinKind.TEE, (k[0].id, wa.id, wb.id))
            return [straight, tee], straight_ends | tee_ends
    return None


def _vertical_groups(walls: Sequence[WallLine]) -> list[list[WallLine]]:
    """Walls connected through overlapping vertical extents."""
    groups: list[list[WallLine]] = []
    for wall in walls:
        joined = [g for g in groups if any(wall.overlaps_vertically(o) for o in g)]
        merged = [wall]
        for g in joined:
            merged.extend(g)
            groups.remove(g)
        groups.append(merged)
    return groups


def solve_point(key: PointKey, walls: Sequence[WallLine]) -> PointSolution:
    """The joins at one point, given every wall that might take part."""
    ends = [(w, e) for w in walls for e in (START, END) if point_key(w.endpoint(e)) == key]
    if not ends:
        return PointSolution((), (), {})
    point = ends[0][0].endpoint(ends[0][1])
    ending = {w.id for w, _ in ends}
    throughs = [w for w in walls if w.id not in ending and w.passes_through(point)]

    joins: list[Join] = []
    issues: list[JoinIssue] = []
    cut: dict[tuple[UUID, int], EndCorners] = {}
    members = [w for w, _ in ends] + throughs
    for group in _vertical_groups(list({w.id: w for w in members}.values())):
        ids = {w.id for w in group}
        g_ends = [(w, e) for w, e in ends if w.id in ids]
        g_through = [w for w in throughs if w.id in ids]
        join: Join | None = None
        issue: JoinIssue | None = None
        corners: dict[tuple[UUID, int], EndCorners] = {}
        if not g_ends:
            continue
        if len(g_ends) == 1 and not g_through:
            continue
        if len(g_ends) == 2 and not g_through:
            if g_ends[0][0].id == g_ends[1][0].id:
                continue  # both ends of one wall: a degenerate wall, rejected by the model
            join, issue, corners = _two_ends(point, g_ends[0], g_ends[1])
        elif len(g_ends) == 1 and len(g_through) == 1:
            join, issue, corners = _tee(point, g_ends[0], g_through[0])
        elif len(g_ends) == 3 and not g_through and (split := _split_tee(point, g_ends)):
            joins.extend(split[0])
            cut.update(split[1])
            continue
        else:
            all_ids = tuple(sorted({w.id for w, _ in g_ends} | {w.id for w in g_through}))
            issue = JoinIssue(
                point,
                all_ids,
                f"{len(all_ids)} walls meet here; joins of more than two walls "
                "are not supported yet",
            )
        if join:
            joins.append(join)
        if issue:
            issues.append(issue)
        cut.update(corners)
    return PointSolution(tuple(joins), tuple(issues), cut)


def footprint(wall: WallLine, start: EndCorners | None, end: EndCorners | None) -> list[Vec]:
    """The wall's plan outline, counter-clockwise: start right, end right, end left, start
    left. Square ends where no corners are given."""
    n = _mul(_left(wall.direction), wall.half)
    s = start or EndCorners(left=_add(wall.start, n), right=_sub(wall.start, n))
    e = end or EndCorners(left=_add(wall.end, n), right=_sub(wall.end, n))
    return [s.right, e.right, e.left, s.left]


def crossings(walls: Sequence[WallLine]) -> list[JoinIssue]:
    """Pairs of walls whose centre lines cross away from their ends (not joined)."""
    issues: list[JoinIssue] = []
    for i, a in enumerate(walls):
        for b in walls[i + 1 :]:
            if not a.overlaps_vertically(b):
                continue
            p = _intersect(a.start, a.direction, b.start, b.direction)
            if p is not None and a.passes_through(p) and b.passes_through(p):
                issues.append(
                    JoinIssue(p, (a.id, b.id), "the walls cross; crossings are not joined yet")
                )
    return issues
