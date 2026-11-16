"""The project: the container of every element and the place where invariants are checked."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import ClassVar, TypeVar
from uuid import UUID, uuid4

from brunelleschi.errors import AmbiguousReferenceError, ModelError, NotFoundError
from brunelleschi.model.hosted import Door, HostedElement, Window
from brunelleschi.model.level import Level
from brunelleschi.model.reference import IfcReference
from brunelleschi.model.units import LENGTH_TOLERANCE, MAX_ABS_COORDINATE, is_valid_length
from brunelleschi.model.wall import TopAtLevel, Wall

MAX_NAME_LENGTH = 200

# Shortest id prefix accepted when an element is referred to by a short id.
MIN_ID_PREFIX = 4


def normalize_name(name: str) -> str:
    """Names are compared without surrounding spaces and without case."""
    return name.strip().casefold()


def short_id(element_id: UUID) -> str:
    """The first eight hex digits of an id, as shown to users (like a short git hash)."""
    return str(element_id)[:8]


@dataclass(slots=True, weakref_slot=True)
class Project:
    """All the elements of one building project.

    Elements keep the order in which they were created, which makes saved files stable.
    Mutating methods are for ``brunelleschi.commands`` only; other code reads.
    """

    # The attributes that hold elements, by id. Transactions snapshot exactly these.
    STORES: ClassVar[tuple[str, ...]] = ("_levels", "_walls", "_hosted", "_references")

    name: str
    # Stable identity of the project itself (IFC project, site and building derive from it).
    id: UUID = field(default_factory=uuid4)
    _levels: dict[UUID, Level] = field(default_factory=dict)
    _walls: dict[UUID, Wall] = field(default_factory=dict)
    _hosted: dict[UUID, HostedElement] = field(default_factory=dict)
    _references: dict[UUID, IfcReference] = field(default_factory=dict)

    # ------------------------------------------------------------------ levels

    @property
    def levels(self) -> list[Level]:
        """Levels in creation order."""
        return list(self._levels.values())

    def levels_by_elevation(self) -> list[Level]:
        """Levels from the lowest to the highest (name breaks ties, for a stable order)."""
        return sorted(self._levels.values(), key=lambda lv: (lv.elevation, lv.name.casefold()))

    def level(self, ref: UUID | str) -> Level:
        """A level by id, or by name (ignoring case and surrounding spaces)."""
        if isinstance(ref, UUID):
            try:
                return self._levels[ref]
            except KeyError:
                raise NotFoundError(f"no level with id {ref}") from None
        wanted = normalize_name(ref)
        for level in self._levels.values():
            if normalize_name(level.name) == wanted:
                return level
        raise NotFoundError(f"no level named {ref!r}")

    def __iter__(self) -> Iterator[Level]:
        return iter(self._levels.values())

    # ------------------------------------------------------------------- walls

    @property
    def walls(self) -> list[Wall]:
        """Walls in creation order."""
        return list(self._walls.values())

    def wall(self, ref: UUID | str) -> Wall:
        """A wall by id, or by a unique prefix of its id (at least four characters)."""
        return _by_id(self._walls, ref, "wall")

    def walls_on_level(self, level_id: UUID) -> list[Wall]:
        """Walls whose base or top is bound to a level, in creation order."""
        return [w for w in self._walls.values() if level_id in w.level_ids()]

    def wall_z_range(self, wall: Wall) -> tuple[float, float]:
        """Absolute elevations of the wall's base and top, derived from its levels."""
        base = self.level(wall.base_level_id).elevation + wall.base_offset
        if isinstance(wall.top, TopAtLevel):
            top = self.level(wall.top.level_id).elevation + wall.top.offset
        else:
            top = base + wall.top.height
        return base, top

    def wall_height(self, wall: Wall) -> float:
        base, top = self.wall_z_range(wall)
        return top - base

    # -------------------------------------------------------- doors and windows

    @property
    def hosted(self) -> list[HostedElement]:
        """Doors and windows in creation order."""
        return list(self._hosted.values())

    @property
    def doors(self) -> list[Door]:
        return [e for e in self._hosted.values() if isinstance(e, Door)]

    @property
    def windows(self) -> list[Window]:
        return [e for e in self._hosted.values() if isinstance(e, Window)]

    def hosted_element(self, ref: UUID | str) -> HostedElement:
        """A door or window by id, or by a unique id prefix."""
        return _by_id(self._hosted, ref, "door or window")

    def hosted_in(self, wall_id: UUID) -> list[HostedElement]:
        """The doors and windows of a wall, in creation order."""
        return [e for e in self._hosted.values() if e.host_id == wall_id]

    # -------------------------------------------------------- IFC references

    @property
    def references(self) -> list[IfcReference]:
        """Linked IFC files, in the order they were linked."""
        return list(self._references.values())

    def reference(self, ref: UUID | str) -> IfcReference:
        """A reference by id, or by a unique id prefix."""
        return _by_id(self._references, ref, "IFC reference")

    # --------------------------------------------------------------- mutations

    def _add_level(self, level: Level) -> None:
        if level.id in self._levels:
            raise ModelError(f"a level with id {level.id} already exists")
        self._levels[level.id] = level

    def _remove_level(self, level_id: UUID) -> Level:
        try:
            return self._levels.pop(level_id)
        except KeyError:
            raise NotFoundError(f"no level with id {level_id}") from None

    def _add_wall(self, wall: Wall) -> None:
        if wall.id in self._walls:
            raise ModelError(f"a wall with id {wall.id} already exists")
        self._walls[wall.id] = wall

    def _remove_wall(self, wall_id: UUID) -> Wall:
        try:
            return self._walls.pop(wall_id)
        except KeyError:
            raise NotFoundError(f"no wall with id {wall_id}") from None

    def _add_hosted(self, element: HostedElement) -> None:
        if element.id in self._hosted:
            raise ModelError(f"an element with id {element.id} already exists")
        self._hosted[element.id] = element

    def _remove_hosted(self, element_id: UUID) -> HostedElement:
        try:
            return self._hosted.pop(element_id)
        except KeyError:
            raise NotFoundError(f"no door or window with id {element_id}") from None

    def _add_reference(self, reference: IfcReference) -> None:
        if reference.id in self._references:
            raise ModelError(f"a reference with id {reference.id} already exists")
        self._references[reference.id] = reference

    def _remove_reference(self, reference_id: UUID) -> IfcReference:
        try:
            return self._references.pop(reference_id)
        except KeyError:
            raise NotFoundError(f"no IFC reference with id {reference_id}") from None

    # --------------------------------------------------------------- invariants

    def check(self) -> None:
        """Raise ``ModelError`` describing every broken invariant, or return silently."""
        problems: list[str] = []
        if not self.name.strip():
            problems.append("the project name is empty")
        self._check_levels(problems)
        bad_walls = self._check_walls(problems)
        self._check_hosted(problems, bad_walls)
        self._check_references(problems)
        if problems:
            raise ModelError("; ".join(problems))

    def _check_levels(self, problems: list[str]) -> None:
        seen: dict[str, Level] = {}
        for level in self._levels.values():
            label = f"level {level.name!r}"
            if not level.name.strip():
                problems.append(f"level {level.id} has an empty name")
                label = f"level {level.id}"
            elif len(level.name) > MAX_NAME_LENGTH:
                problems.append(f"{label}: name longer than {MAX_NAME_LENGTH} characters")
            if not is_valid_length(level.elevation):
                problems.append(f"{label}: elevation {_LENGTH_RULE}")
            key = normalize_name(level.name)
            if key and key in seen:
                problems.append(
                    f"level name {level.name!r} clashes with {seen[key].name!r} "
                    "(names must be unique, ignoring case)"
                )
            seen.setdefault(key, level)

    def _check_walls(self, problems: list[str]) -> set[UUID]:
        """Record wall problems; return the ids of walls too broken to host anything."""
        bad: set[UUID] = set()
        for wall in self._walls.values():
            label = f"wall {short_id(wall.id)}"
            numbers = {
                "start x": wall.start.x,
                "start y": wall.start.y,
                "end x": wall.end.x,
                "end y": wall.end.y,
                "thickness": wall.thickness,
                "base offset": wall.base_offset,
            }
            if isinstance(wall.top, TopAtLevel):
                numbers["top offset"] = wall.top.offset
            else:
                numbers["height"] = wall.top.height
            invalid = [k for k, v in numbers.items() if not is_valid_length(v)]
            if invalid:
                problems.append(f"{label}: {', '.join(invalid)} {_LENGTH_RULE}")
                bad.add(wall.id)
                continue
            if wall.length <= LENGTH_TOLERANCE:
                problems.append(f"{label}: start and end are the same point")
            if wall.thickness <= LENGTH_TOLERANCE:
                problems.append(f"{label}: thickness must be greater than zero")
            missing = [lid for lid in wall.level_ids() if lid not in self._levels]
            if missing:
                problems.append(f"{label}: bound to a level that does not exist")
                bad.add(wall.id)
                continue
            base, top = self.wall_z_range(wall)
            if top - base <= LENGTH_TOLERANCE:
                problems.append(f"{label}: top ({top:+.3f} m) must be above base ({base:+.3f} m)")
        return bad

    def _check_hosted(self, problems: list[str], bad_walls: set[UUID]) -> None:
        tol = LENGTH_TOLERANCE
        by_host: dict[UUID, list[HostedElement]] = {}
        for e in self._hosted.values():
            label = f"{e.kind} {short_id(e.id)}"
            numbers = {
                "position": e.position,
                "width": e.width,
                "height": e.height,
                "sill height": e.sill_height,
            }
            invalid = [k for k, v in numbers.items() if not is_valid_length(v)]
            if invalid:
                problems.append(f"{label}: {', '.join(invalid)} {_LENGTH_RULE}")
                continue
            if e.width <= tol or e.height <= tol:
                problems.append(f"{label}: width and height must be greater than zero")
                continue
            if e.sill_height < -tol:
                problems.append(f"{label}: sill height must not be negative")
                continue
            wall = self._walls.get(e.host_id)
            if wall is None:
                problems.append(f"{label}: its host wall does not exist")
                continue
            if wall.id in bad_walls or wall.length <= tol:
                continue  # the wall's own problem is already reported
            where = f"wall {short_id(wall.id)}"
            a, b = e.along()
            if a < -tol or b > wall.length + tol:
                problems.append(
                    f"{label} does not fit in {where}: it spans {a:.3f} .. {b:.3f} m "
                    f"along a wall {wall.length:.3f} m long"
                )
                continue
            height = self.wall_height(wall)
            if e.vertical()[1] > height + tol:
                problems.append(
                    f"{label} does not fit in {where}: its top is {e.vertical()[1]:.3f} m "
                    f"above the wall base, the wall is {height:.3f} m high"
                )
                continue
            by_host.setdefault(wall.id, []).append(e)
        for wall_id, elements in by_host.items():
            for i, e in enumerate(elements):
                for f in elements[i + 1 :]:
                    if _overlap(e.along(), f.along()) and _overlap(e.vertical(), f.vertical()):
                        problems.append(
                            f"{e.kind} {short_id(e.id)} and {f.kind} {short_id(f.id)} "
                            f"overlap in wall {short_id(wall_id)}"
                        )

    def _check_references(self, problems: list[str]) -> None:
        for r in self._references.values():
            label = f"IFC reference {short_id(r.id)}"
            if not r.name.strip():
                problems.append(f"{label}: the name is empty")
            if not r.path.strip():
                problems.append(f"{label}: the path is empty")
            if len(r.name) > MAX_NAME_LENGTH:
                problems.append(f"{label}: name longer than {MAX_NAME_LENGTH} characters")


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return min(a[1], b[1]) - max(a[0], b[0]) > LENGTH_TOLERANCE


_LENGTH_RULE = f"must be a finite number of metres within ±{MAX_ABS_COORDINATE:g}"


T = TypeVar("T")


def _by_id(store: dict[UUID, T], ref: UUID | str, kind: str) -> T:
    if isinstance(ref, UUID):
        try:
            return store[ref]
        except KeyError:
            raise NotFoundError(f"no {kind} with id {ref}") from None
    prefix = ref.strip().lower()
    if len(prefix) < MIN_ID_PREFIX:
        raise NotFoundError(f"{kind} id {ref!r} is too short (at least {MIN_ID_PREFIX} characters)")
    matches = [item for key, item in store.items() if str(key).startswith(prefix)]
    if not matches:
        raise NotFoundError(f"no {kind} with id {ref!r}")
    if len(matches) > 1:
        raise AmbiguousReferenceError(f"{kind} id {ref!r} matches {len(matches)} {kind}s")
    return matches[0]
