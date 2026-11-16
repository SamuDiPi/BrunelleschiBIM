"""Version 3 of the project file: version 2 plus doors and windows.

Classes of earlier versions that did not change are reused as they are. A version's
classes are never edited once released: a change means a new version and a migration.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from brunelleschi.storage.schema_v1 import LevelV1
from brunelleschi.storage.schema_v2 import WallV2

NonNegativeLength = Annotated[float, Field(allow_inf_nan=False, ge=0, le=1e6)]
PositiveLength = Annotated[float, Field(allow_inf_nan=False, gt=0, le=1e6)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SwingV3(_Strict):
    """How a door opens."""

    side: Literal["left", "right"] = Field(
        description="Side of the wall the leaf swings into, seen from the wall's start."
    )
    hinge: Literal["start", "end"] = Field(
        description="Jamb carrying the hinges: the one nearer the wall's start or its end."
    )


class _HostedV3(_Strict):
    id: UUID = Field(description="Stable identifier.")
    host: UUID = Field(description="Id of the host wall.")
    position: NonNegativeLength = Field(
        description="Distance in metres from the wall's start to the centre, along the wall."
    )
    width: PositiveLength = Field(description="Width of the opening in metres.")
    height: PositiveLength = Field(description="Height of the opening in metres.")
    sill_height: NonNegativeLength = Field(
        description="Height in metres of the bottom of the opening above the wall's base."
    )


class DoorV3(_HostedV3):
    """A door hosted in a wall."""

    swing: SwingV3


class WindowV3(_HostedV3):
    """A window hosted in a wall."""


class ProjectFileV3(_Strict):
    """A BrunelleschiBIM project, schema version 3."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title="BrunelleschiBIM project file, schema version 3",
        json_schema_extra={
            "$id": "https://github.com/SamuDiPi/BrunelleschiBIM/schemas/bbim-3.schema.json",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
        },
    )

    format: Literal["brunelleschi-project"] = Field(
        description="Identifies the file as a BrunelleschiBIM project."
    )
    schema_version: Literal[3] = Field(description="Version of this file format.")
    name: str = Field(min_length=1, max_length=200, description="Project name.")
    levels: list[LevelV1] = Field(description="Levels, in creation order.")
    walls: list[WallV2] = Field(description="Walls, in creation order.")
    doors: list[DoorV3] = Field(description="Doors, in creation order.")
    windows: list[WindowV3] = Field(description="Windows, in creation order.")
