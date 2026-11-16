"""Wall joins and footprints: L, straight and T joins, unsupported cases, incremental
regeneration."""

from __future__ import annotations

import math

import pytest
from shapely import Polygon, box, unary_union

from brunelleschi import api
from brunelleschi.geometry.joins import point_key
from brunelleschi.regen.walls import cache_for

AREA_TOL = 1e-9


@pytest.fixture
def project() -> api.Project:
    p = api.new_project("House")
    api.add_level(p, "Ground floor", 0.0)
    api.add_level(p, "First floor", 3.0)
    api.add_level(p, "Second floor", 6.0)
    return p


def wall(
    p: api.Project,
    start: tuple[float, float],
    end: tuple[float, float],
    thickness: float = 0.3,
    base: str = "Ground floor",
    top: str = "First floor",
) -> api.Wall:
    return api.add_wall(p, start, end, thickness, base, top_level=top)


def polys(p: api.Project) -> list[Polygon]:
    return [f.polygon for f in api.wall_geometry(p).footprints.values()]


def assert_no_overlap(p: api.Project) -> None:
    shapes = polys(p)
    for i, a in enumerate(shapes):
        assert a.is_valid
        for b in shapes[i + 1 :]:
            assert a.intersection(b).area < AREA_TOL


def union_of(p: api.Project) -> Polygon:
    shape = unary_union(polys(p))
    assert isinstance(shape, Polygon), f"expected one piece, got {shape.geom_type}"
    return shape


def kinds(p: api.Project) -> list[str]:
    return [str(j.kind) for j in api.wall_geometry(p).joins]


# ------------------------------------------------------------------------ L


def test_l_corner_is_mitred_without_overlap_or_gap(project: api.Project) -> None:
    wall(project, (0, 0), (5, 0))
    wall(project, (0, 0), (0, 4))
    assert kinds(project) == ["mitre"]
    assert_no_overlap(project)
    union = unary_union(polys(project))
    # A mitred band has exactly thickness x centre-line length.
    assert union.area == pytest.approx(0.3 * 9)
    expected = Polygon([(-0.15, -0.15), (5, -0.15), (5, 0.15), (0.15, 0.15), (0.15, 4), (-0.15, 4)])
    assert union.symmetric_difference(expected).area < AREA_TOL


@pytest.mark.parametrize("angle", [30, 60, 90, 120, 150, 179])
@pytest.mark.parametrize("flip", [False, True])
def test_l_corner_at_any_angle(project: api.Project, angle: float, flip: bool) -> None:
    a = math.radians(angle)
    far = (4 * math.cos(a), 4 * math.sin(a))
    # Walls drawn towards or away from the corner must give the same result.
    if flip:
        wall(project, (5, 0), (0, 0))
        wall(project, far, (0, 0))
    else:
        wall(project, (0, 0), (5, 0))
        wall(project, (0, 0), far)
    assert kinds(project) == ["mitre"]
    assert_no_overlap(project)
    union = union_of(project)
    assert union.area == pytest.approx(0.3 * 9)


def test_l_corner_with_different_thicknesses(project: api.Project) -> None:
    wall(project, (0, 0), (5, 0), thickness=0.4)
    wall(project, (0, 0), (0, 4), thickness=0.12)
    assert kinds(project) == ["mitre"]
    assert_no_overlap(project)
    union = union_of(project)
    assert not union.interiors
    # No gap: the whole corner square is covered.
    assert union.covers(box(-0.06, -0.2, 0.06, 0.2))
    assert union.covers(box(-0.06, -0.2, 0.06, 0.06))


def test_closed_room_is_a_ring(project: api.Project) -> None:
    corners = [(0, 0), (6, 0), (6, 4), (0, 4)]
    for i, c in enumerate(corners):
        wall(project, c, corners[(i + 1) % 4])
    assert kinds(project) == ["mitre"] * 4
    assert_no_overlap(project)
    union = union_of(project)
    assert len(union.interiors) == 1
    assert union.area == pytest.approx(0.3 * 20)
    assert Polygon(union.interiors[0]).area == pytest.approx(5.7 * 3.7)


# ----------------------------------------------------------------- straight


@pytest.mark.parametrize("thickness", [0.3, 0.2])
def test_straight_continuation(project: api.Project, thickness: float) -> None:
    wall(project, (0, 0), (3, 0))
    wall(project, (3, 0), (7, 0), thickness=thickness)
    assert kinds(project) == ["straight"]
    assert_no_overlap(project)
    assert unary_union(polys(project)).area == pytest.approx(0.3 * 3 + thickness * 4)


# ------------------------------------------------------------------------ T


@pytest.mark.parametrize("side", [1, -1])
def test_tee_stops_at_the_face_of_the_through_wall(project: api.Project, side: int) -> None:
    host = wall(project, (0, 0), (6, 0))
    stem = wall(project, (2.5, 0), (2.5, 3 * side), thickness=0.2)
    geometry = api.wall_geometry(project)
    (join,) = geometry.joins
    assert join.kind == "tee"
    assert join.walls == (stem.id, host.id)
    assert_no_overlap(project)
    host_poly = geometry.footprints[host.id].polygon
    stem_poly = geometry.footprints[stem.id].polygon
    assert host_poly.area == pytest.approx(0.3 * 6)  # the through wall is not changed
    assert stem_poly.area == pytest.approx(0.2 * (3 - 0.15))
    assert host_poly.touches(stem_poly)  # no gap
    assert unary_union([host_poly, stem_poly]).geom_type == "Polygon"


def test_slanted_tee(project: api.Project) -> None:
    wall(project, (0, 0), (6, 0))
    wall(project, (3, 0), (5, 2), thickness=0.2)
    assert kinds(project) == ["tee"]
    assert_no_overlap(project)
    assert unary_union(polys(project)).geom_type == "Polygon"


# --------------------------------------------------------- vertical extents


def test_walls_on_different_storeys_do_not_join(project: api.Project) -> None:
    wall(project, (0, 0), (5, 0))
    wall(project, (0, 0), (0, 4), base="First floor", top="Second floor")
    geometry = api.wall_geometry(project)
    assert geometry.joins == ()
    assert geometry.issues == ()


def test_storeys_join_separately_at_the_same_corner(project: api.Project) -> None:
    for base, top in (("Ground floor", "First floor"), ("First floor", "Second floor")):
        wall(project, (0, 0), (5, 0), base=base, top=top)
        wall(project, (0, 0), (0, 4), base=base, top=top)
    assert kinds(project) == ["mitre", "mitre"]
    assert api.wall_geometry(project).issues == ()


def test_moving_a_level_can_create_a_join(project: api.Project) -> None:
    wall(project, (0, 0), (5, 0))  # ground -> first
    api.add_wall(project, (0, 0), (0, 4), 0.3, "First floor", base_offset=0.5, height=2.0)
    assert kinds(project) == []
    api.set_level_elevation(project, "First floor", 2.0)  # now 2.5 .. 4.5 overlaps 0 .. 2
    assert kinds(project) == []
    api.set_level_elevation(project, "First floor", 3.0)
    api.modify_wall(project, project.walls[1].id, base_level="Ground floor", base_offset=0.0)
    assert kinds(project) == ["mitre"]


# --------------------------------------------------------- unsupported cases


def test_three_walls_at_a_point_are_reported(project: api.Project) -> None:
    for far in ((5, 0), (0, 4), (-3, -3)):  # no two of them in line
        wall(project, (0, 0), far)
    geometry = api.wall_geometry(project)
    assert geometry.joins == ()
    (issue,) = geometry.issues
    assert "3 walls meet here" in issue.message
    assert len(issue.walls) == 3


def test_two_ends_on_a_through_wall_are_reported(project: api.Project) -> None:
    wall(project, (-3, 0), (3, 0))
    wall(project, (0, 0), (0, 3))
    wall(project, (0, 0), (0, -3))
    (issue,) = api.wall_geometry(project).issues
    assert "3 walls meet here" in issue.message


def test_crossing_walls_are_reported(project: api.Project) -> None:
    wall(project, (-3, 0), (3, 0))
    wall(project, (0, -3), (0, 3))
    geometry = api.wall_geometry(project)
    assert geometry.joins == ()
    (issue,) = geometry.issues
    assert "cross" in issue.message
    assert issue.point == pytest.approx((0, 0))


def test_walls_lying_on_each_other_are_reported(project: api.Project) -> None:
    wall(project, (0, 0), (5, 0))
    wall(project, (0, 0), (3, 0))  # also ends on the first wall's centre line at (3, 0)
    issues = api.wall_geometry(project).issues
    assert [i.point for i in issues] == [(0, 0), (3, 0)]
    assert all("lie on each other" in i.message for i in issues)


def test_very_sharp_corner_is_reported(project: api.Project) -> None:
    wall(project, (0, 0), (5, 0))
    a = math.radians(5)
    wall(project, (0, 0), (5 * math.cos(a), 5 * math.sin(a)))
    geometry = api.wall_geometry(project)
    assert geometry.joins == ()
    (issue,) = geometry.issues
    assert "too sharp" in issue.message
    assert "5.0 degrees" in issue.message


def test_nearly_straight_walls_of_different_thickness_are_reported(
    project: api.Project,
) -> None:
    wall(project, (0, 0), (5, 0), thickness=0.3)
    wall(project, (5, 0), (10, 0.01), thickness=0.1)  # 0.11 degrees off straight
    (issue,) = api.wall_geometry(project).issues
    assert "too sharp or too short" in issue.message


def test_corner_with_a_short_wall_is_reported(project: api.Project) -> None:
    wall(project, (0, 0), (5, 0), thickness=0.6)
    wall(project, (0, 0), (0, 0.2), thickness=0.1)  # shorter than the half-thickness
    (issue,) = api.wall_geometry(project).issues
    assert "too short" in issue.message


def test_short_wall_between_two_joins_keeps_a_valid_outline(project: api.Project) -> None:
    # A 0.2 m wall joined at both ends by 90 degree corners of 0.3 m walls: the cuts
    # of its two ends cross. It is drawn with square ends and reported.
    wall(project, (0, 0), (0, 3))
    short = wall(project, (0, 3), (0.2, 3))
    wall(project, (0.2, 3), (0.2, 0))
    geometry = api.wall_geometry(project)
    assert all(f.polygon.is_valid for f in geometry.footprints.values())
    assert any(short.id in i.walls for i in geometry.issues)


# ------------------------------------------------------------ regeneration


def test_footprints_follow_every_change(project: api.Project) -> None:
    a = wall(project, (0, 0), (5, 0))
    b = wall(project, (0, 0), (0, 4))
    assert kinds(project) == ["mitre"]
    api.modify_wall(project, b.id, start=(1, 1))
    assert kinds(project) == []
    assert api.wall_geometry(project).footprints[a.id].polygon.area == pytest.approx(1.5)
    api.modify_wall(project, b.id, start=(2, 0))  # now a tee on a
    assert kinds(project) == ["tee"]
    api.modify_wall(project, a.id, end=(2, 0))  # now an L again
    assert kinds(project) == ["mitre"]
    api.delete_wall(project, b.id)
    geometry = api.wall_geometry(project)
    assert geometry.joins == ()
    assert list(geometry.footprints) == [a.id]
    assert geometry.footprints[a.id].polygon.area == pytest.approx(0.3 * 2)


def test_moving_a_wall_end_regenerates_only_its_joins(project: api.Project) -> None:
    """The M3 acceptance test."""
    room = [(0, 0), (6, 0), (6, 4), (0, 4)]
    walls = [wall(project, c, room[(i + 1) % 4]) for i, c in enumerate(room)]
    other = [(20, 0), (26, 0), (26, 4), (20, 4)]
    for i, c in enumerate(other):
        wall(project, c, other[(i + 1) % 4])
    api.wall_geometry(project)
    cache = cache_for(project)
    before = dict(cache.footprints)

    # Move the corner (6, 4): the end of walls[1] and the start of walls[2].
    with api.transaction(project):
        api.modify_wall(project, walls[1].id, end=(7, 5))
        api.modify_wall(project, walls[2].id, start=(7, 5))
    geometry = api.wall_geometry(project)

    recomputed = cache.last_recomputed
    # walls[1]: (6, 0) and the old and new corner; walls[2]: the corners and (0, 4).
    assert recomputed == {point_key(p) for p in [(6, 0), (6, 4), (7, 5), (0, 4)]}
    unchanged = [w.id for w in project.walls if w.id not in (walls[1].id, walls[2].id)]
    # Footprints of the walls sharing those joins changed; the other room's are reused.
    for wid in unchanged[3:]:
        assert geometry.footprints[wid] is before[wid]
    assert kinds(project) == ["mitre"] * 8
    assert_no_overlap(project)


def test_no_change_recomputes_nothing(project: api.Project) -> None:
    wall(project, (0, 0), (5, 0))
    wall(project, (0, 0), (0, 4))
    api.wall_geometry(project)
    api.rename_level(project, "Second floor", "Roof")  # walls do not depend on its name
    api.wall_geometry(project)
    assert cache_for(project).last_recomputed == set()


def test_failed_transaction_leaves_geometry_consistent(project: api.Project) -> None:
    a = wall(project, (0, 0), (5, 0))
    wall(project, (0, 0), (0, 4))
    first = api.wall_geometry(project)
    with pytest.raises(api.ModelError):
        api.modify_wall(project, a.id, start=(9, 9), thickness=-1)
    again = api.wall_geometry(project)
    assert again.joins == first.joins
    assert again.footprints[a.id].corners == first.footprints[a.id].corners


def test_each_project_has_its_own_cache(project: api.Project) -> None:
    wall(project, (0, 0), (5, 0))
    copy = api.loads(api.dumps(project))
    api.add_wall(copy, (0, 0), (0, 4), 0.3, "Ground floor", top_level="First floor")
    assert kinds(project) == []
    assert kinds(copy) == ["mitre"]


def test_split_wall_with_a_partition_is_straight_plus_tee(project: api.Project) -> None:
    left = wall(project, (0, 0), (3, 0))
    right = wall(project, (3, 0), (7, 0))
    stem = wall(project, (3, 0), (3, 4), thickness=0.12)
    geometry = api.wall_geometry(project)
    assert sorted((str(j.kind), j.walls) for j in geometry.joins) == [
        ("straight", (left.id, right.id)),
        ("tee", (stem.id, left.id, right.id)),
    ]
    assert geometry.issues == ()
    assert_no_overlap(project)
    union = union_of(project)
    assert union.area == pytest.approx(0.3 * 7 + 0.12 * (4 - 0.15))


def test_split_wall_of_two_thicknesses_is_reported(project: api.Project) -> None:
    wall(project, (0, 0), (3, 0))
    wall(project, (3, 0), (7, 0), thickness=0.2)
    wall(project, (3, 0), (3, 4), thickness=0.12)
    (issue,) = api.wall_geometry(project).issues
    assert "3 walls meet here" in issue.message


def test_closed_rooms_sharing_split_walls(project: api.Project) -> None:
    """Two rooms side by side, every wall a separate piece: L corners and split tees."""
    pts = {"a": (0, 0), "b": (4, 0), "c": (9, 0), "d": (9, 5), "e": (4, 5), "f": (0, 5)}
    for s, e in ("ab", "bc", "cd", "de", "ef", "fa", "be"):
        wall(project, pts[s], pts[e])
    geometry = api.wall_geometry(project)
    assert geometry.issues == ()
    assert (
        sorted(str(j.kind) for j in geometry.joins)
        == ["mitre"] * 4 + ["straight"] * 2 + ["tee"] * 2
    )
    assert_no_overlap(project)
    union = union_of(project)
    assert len(union.interiors) == 2
    assert union.area == pytest.approx(0.3 * (2 * 9 + 2 * 5) + 0.3 * (5 - 0.3))
