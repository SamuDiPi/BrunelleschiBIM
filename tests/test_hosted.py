"""Doors and windows hosted in walls: placement, fit, propagation, openings."""

from __future__ import annotations

import pytest
from shapely import MultiPolygon, Polygon

from brunelleschi import api
from brunelleschi.errors import ModelError, NotFoundError


@pytest.fixture
def project() -> api.Project:
    p = api.new_project("House")
    api.add_level(p, "Ground floor", 0.0)
    api.add_level(p, "First floor", 3.0)
    return p


@pytest.fixture
def wall(project: api.Project) -> api.Wall:
    return api.add_wall(project, (0, 0), (6, 0), 0.3, "Ground floor", top_level="First floor")


def opening(project: api.Project, element: api.HostedElement) -> api.OpeningGeometry:
    return api.wall_geometry(project).openings[element.id]


def x_range(o: api.OpeningGeometry) -> tuple[float, float]:
    xs = [c[0] for c in o.corners]
    return round(min(xs), 9), round(max(xs), 9)


# ------------------------------------------------------------------ placing


def test_door_and_window(project: api.Project, wall: api.Wall) -> None:
    door = api.add_door(project, wall.id, 1.0, 0.9, 2.1)
    window = api.add_window(project, wall.id, 4.0, 1.2, 1.4, 0.9)
    assert isinstance(door, api.Door)
    assert (door.position, door.width, door.height, door.sill_height) == (1.0, 0.9, 2.1, 0.0)
    assert door.swing_side == api.Side.LEFT
    assert door.hinge == api.Jamb.START
    assert window.vertical() == (0.9, 2.3)
    assert project.hosted == [door, window]
    assert project.doors == [door]
    assert project.windows == [window]
    assert project.hosted_in(wall.id) == [door, window]
    assert project.hosted_element(api.short_id(door.id)) is door


def test_opening_follows_the_element(project: api.Project, wall: api.Wall) -> None:
    window = api.add_window(project, wall.id, 4.0, 1.2, 1.4, 0.9)
    o = opening(project, window)
    assert o.host_id == wall.id
    assert x_range(o) == (3.4, 4.6)
    assert {round(c[1], 9) for c in o.corners} == {-0.15, 0.15}  # the full thickness
    assert (o.z_bottom, o.z_top) == pytest.approx((0.9, 2.3))
    api.modify_hosted(project, window.id, position=2.5, width=1.0, sill_height=1.0, height=1.2)
    o = opening(project, window)
    assert x_range(o) == (2.0, 3.0)
    assert (o.z_bottom, o.z_top) == pytest.approx((1.0, 2.2))


def test_opening_follows_the_wall(project: api.Project, wall: api.Wall) -> None:
    door = api.add_door(project, wall.id, 1.0, 0.9, 2.1)
    api.modify_wall(project, wall.id, start=(0, 2), end=(0, 8), base_offset=0.2, thickness=0.4)
    o = opening(project, door)
    ys = sorted({round(c[1], 9) for c in o.corners})
    xs = sorted({round(c[0], 9) for c in o.corners})
    assert ys == [2.55, 3.45]  # 1.0 from the new start, along +y
    assert xs == [-0.2, 0.2]
    assert o.z_bottom == pytest.approx(0.2)


def test_raising_a_level_raises_the_opening(project: api.Project, wall: api.Wall) -> None:
    window = api.add_window(project, wall.id, 3.0, 1.0, 1.2, 1.0)
    api.set_level_elevation(project, "Ground floor", 0.5)
    assert opening(project, window).z_bottom == pytest.approx(1.5)


# ----------------------------------------------------------------- fitting


@pytest.mark.parametrize(
    ("position", "width", "message"),
    [(0.4, 0.9, "spans -0.050 .. 0.850 m"), (5.6, 0.9, "spans 5.150 .. 6.050 m")],
)
def test_element_must_fit_along_the_wall(
    project: api.Project, wall: api.Wall, position: float, width: float, message: str
) -> None:
    with pytest.raises(ModelError, match=message):
        api.add_door(project, wall.id, position, width, 2.1)
    assert project.hosted == []


def test_element_may_touch_the_wall_ends(project: api.Project, wall: api.Wall) -> None:
    api.add_door(project, wall.id, 0.45, 0.9, 2.1)
    api.add_door(project, wall.id, 5.55, 0.9, 2.1)


def test_element_must_fit_in_height(project: api.Project, wall: api.Wall) -> None:
    with pytest.raises(ModelError, match=r"its top is 3.100 m above the wall base"):
        api.add_window(project, wall.id, 3.0, 1.0, 1.2, 1.9)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"width": 0.0}, "width and height must be greater than zero"),
        ({"height": -1.0}, "width and height must be greater than zero"),
        ({"sill_height": -0.1}, "sill height must not be negative"),
        ({"position": float("nan")}, "position must be a finite number"),
    ],
)
def test_invalid_parameters(
    project: api.Project, wall: api.Wall, kwargs: dict[str, float], message: str
) -> None:
    args = {"position": 3.0, "width": 1.0, "height": 1.2, "sill_height": 0.9} | kwargs
    with pytest.raises(ModelError, match=message):
        api.add_window(project, wall.id, **args)  # type: ignore[arg-type]


def test_overlapping_elements_are_refused(project: api.Project, wall: api.Wall) -> None:
    api.add_door(project, wall.id, 2.0, 0.9, 2.1)
    with pytest.raises(ModelError, match="overlap in wall"):
        api.add_window(project, wall.id, 2.5, 1.0, 1.0, 1.0)
    # Above the door is fine.
    api.add_window(project, wall.id, 2.0, 0.9, 0.5, 2.3)


def test_door_options(project: api.Project, wall: api.Wall) -> None:
    door = api.add_door(project, wall.id, 2.0, 0.9, 2.1, swing_side="right", hinge="end")
    assert (door.swing_side, door.hinge) == (api.Side.RIGHT, api.Jamb.END)
    api.modify_hosted(project, door.id, swing_side=api.Side.LEFT)
    assert door.swing_side == api.Side.LEFT
    with pytest.raises(ModelError, match="swing side must be left or right"):
        api.add_door(project, wall.id, 4.5, 0.9, 2.1, swing_side="up")
    with pytest.raises(ModelError, match="hinge must be start or end"):
        api.modify_hosted(project, door.id, hinge="middle")
    window = api.add_window(project, wall.id, 4.5, 1.0, 1.0, 1.0)
    with pytest.raises(ModelError, match="only doors"):
        api.modify_hosted(project, window.id, hinge="end")


def test_unknown_wall(project: api.Project, wall: api.Wall) -> None:
    with pytest.raises(NotFoundError):
        api.add_door(project, "ffffffff", 1.0, 0.9, 2.1)


# ------------------------------------------- the wall changes (M4 criteria)


def test_lengthening_the_wall_keeps_the_distance(project: api.Project, wall: api.Wall) -> None:
    door = api.add_door(project, wall.id, 1.0, 0.9, 2.1)
    api.modify_wall(project, wall.id, end=(10, 0))
    assert door.position == 1.0
    assert x_range(opening(project, door)) == (0.55, 1.45)


def test_moving_the_wall_moves_the_elements(project: api.Project, wall: api.Wall) -> None:
    door = api.add_door(project, wall.id, 1.0, 0.9, 2.1)
    api.modify_wall(project, wall.id, start=(2, 5), end=(8, 5))
    o = opening(project, door)
    assert x_range(o) == (2.55, 3.45)
    assert {round(c[1], 9) for c in o.corners} == {4.85, 5.15}


def test_shortening_so_an_element_no_longer_fits_is_refused(
    project: api.Project, wall: api.Wall
) -> None:
    window = api.add_window(project, wall.id, 5.0, 1.2, 1.4, 0.9)
    with pytest.raises(ModelError, match=f"window {api.short_id(window.id)} does not fit"):
        api.modify_wall(project, wall.id, end=(5, 0))
    assert project.wall(wall.id).end == api.Point(6, 0)
    assert project.windows == [window]  # never silently dropped


def test_lowering_a_level_below_a_window_top_is_refused(
    project: api.Project, wall: api.Wall
) -> None:
    window = api.add_window(project, wall.id, 3.0, 1.0, 1.4, 1.2)
    with pytest.raises(ModelError, match=f"window {api.short_id(window.id)} does not fit"):
        api.set_level_elevation(project, "First floor", 2.4)
    assert project.level("First floor").elevation == 3.0


def test_deleting_a_wall_deletes_its_elements(project: api.Project, wall: api.Wall) -> None:
    other = api.add_wall(project, (0, 5), (6, 5), 0.3, "Ground floor", height=3)
    api.add_door(project, wall.id, 1.0, 0.9, 2.1)
    api.add_window(project, wall.id, 4.0, 1.2, 1.4, 0.9)
    kept = api.add_window(project, other.id, 3.0, 1.2, 1.4, 0.9)
    api.delete_wall(project, wall.id)
    assert project.hosted == [kept]


def test_deleting_a_wall_is_one_transaction(project: api.Project, wall: api.Wall) -> None:
    door = api.add_door(project, wall.id, 1.0, 0.9, 2.1)
    with pytest.raises(RuntimeError), api.transaction(project):
        api.delete_wall(project, wall.id)
        raise RuntimeError("boom")
    assert project.walls == [wall]
    assert project.hosted == [door]


def test_moving_an_element_to_another_wall(project: api.Project, wall: api.Wall) -> None:
    other = api.add_wall(project, (0, 5), (3, 5), 0.3, "Ground floor", height=3)
    door = api.add_door(project, wall.id, 4.0, 0.9, 2.1)
    with pytest.raises(ModelError, match="does not fit"):  # 4.0 is past the end of a 3 m wall
        api.modify_hosted(project, door.id, wall=other.id)
    api.modify_hosted(project, door.id, wall=api.short_id(other.id), position=1.5)
    assert door.host_id == other.id


def test_delete_element(project: api.Project, wall: api.Wall) -> None:
    door = api.add_door(project, wall.id, 1.0, 0.9, 2.1)
    assert api.delete_hosted(project, api.short_id(door.id)) is door
    assert project.hosted == []
    assert api.wall_geometry(project).openings == {}


# --------------------------------------------------------------- plan cut


def test_plan_cut_has_the_openings(project: api.Project, wall: api.Wall) -> None:
    api.add_door(project, wall.id, 1.0, 0.9, 2.1)
    api.add_window(project, wall.id, 4.0, 1.2, 1.4, 0.9)
    geometry = api.wall_geometry(project)

    at_door_only = geometry.plan_cut(0.5)[wall.id]  # below the window sill
    assert isinstance(at_door_only, MultiPolygon)
    assert len(at_door_only.geoms) == 2
    assert at_door_only.area == pytest.approx(0.3 * (6 - 0.9))

    at_both = geometry.plan_cut(1.2)[wall.id]
    assert isinstance(at_both, MultiPolygon)
    assert len(at_both.geoms) == 3
    assert at_both.area == pytest.approx(0.3 * (6 - 0.9 - 1.2))

    above = geometry.plan_cut(2.5)[wall.id]
    assert isinstance(above, Polygon)
    assert above.area == pytest.approx(0.3 * 6)

    assert geometry.plan_cut(3.5) == {}  # above the wall


def test_plan_cut_of_a_mitred_corner(project: api.Project, wall: api.Wall) -> None:
    side = api.add_wall(project, (0, 0), (0, 4), 0.3, "Ground floor", top_level="First floor")
    api.add_door(project, side.id, 2.0, 0.9, 2.1)
    cut = api.wall_geometry(project).plan_cut(1.0)
    pieces = cut[side.id]
    assert isinstance(pieces, MultiPolygon)
    assert pieces.area == pytest.approx(0.3 * (4 - 0.9))
    assert all(p.is_valid for p in pieces.geoms)


# ------------------------------------------------------------- warnings


def test_opening_reaching_into_a_corner_is_reported(project: api.Project, wall: api.Wall) -> None:
    api.add_wall(project, (0, 0), (0, 4), 0.3, "Ground floor", top_level="First floor")
    door = api.add_door(project, wall.id, 0.5, 0.9, 2.1)  # 0.05 .. 0.95: inside the mitre
    issues = api.wall_geometry(project).issues
    assert [i.message for i in issues if door.id in i.walls] == [
        f"door {api.short_id(door.id)} reaches into the join at an end of wall "
        f"{api.short_id(wall.id)}"
    ]
    api.modify_hosted(project, door.id, position=1.0)  # 0.55 .. 1.45: clear of it
    assert not [i for i in api.wall_geometry(project).issues if door.id in i.walls]


def test_opening_blocked_by_a_tee_is_reported(project: api.Project, wall: api.Wall) -> None:
    api.add_wall(project, (3, 0), (3, 4), 0.12, "Ground floor", top_level="First floor")
    door = api.add_door(project, wall.id, 3.0, 0.9, 2.1)
    (issue,) = [i for i in api.wall_geometry(project).issues if door.id in i.walls]
    assert "is blocked by wall" in issue.message


def test_window_above_a_lower_wall_is_not_blocked(project: api.Project, wall: api.Wall) -> None:
    api.add_wall(project, (3, 0), (3, 4), 0.12, "Ground floor", height=0.8)  # a low wall
    window = api.add_window(project, wall.id, 3.0, 1.0, 1.2, 1.0)
    assert not [i for i in api.wall_geometry(project).issues if window.id in i.walls]
