"""Version 2 of the project file: version 1 plus walls.

Classes of earlier versions that did not change are reused as they are. A version's
classes are never edited once released: a change means a new version and a migration.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from brunelleschi.storage.schema_v1 import LevelV1

Length = Annotated[float, Field(allow_inf_nan=False, ge=-1e6, le=1e6)]
PositiveLength = Annotated[float, Field(allow_inf_nan=False, gt=0, le=1e6)]
PointV2 = Annotated[tuple[Length, Length], Field(description="Plan coordinates [x, y] in metres.")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WallBaseV2(_Strict):
    """Where the wall starts: a level plus an offset."""

    level: UUID = Field(description="Id of the base level.")
    offset: Length = Field(description="Metres above (positive) or below the base level.")


class WallTopAtLevelV2(_Strict):
    """The wall top follows a level plus an offset."""

    kind: Literal["level"]
    level: UUID = Field(description="Id of the top level.")
    offset: Length = Field(description="Metres above (positive) or below the top level.")


class WallTopHeightV2(_Strict):
    """The wall top is a fixed height above the wall base."""

    kind: Literal["height"]
    height: PositiveLength = Field(description="Height in metres above the wall base.")


class WallV2(_Strict):
    """A straight wall. Absolute elevations are derived from its levels, not stored."""

    id: UUID = Field(description="Stable identifier of the wall.")
    start: PointV2 = Field(description="Start of the centre line, [x, y] in metres.")
    end: PointV2 = Field(description="End of the centre line, [x, y] in metres.")
    thickness: PositiveLength = Field(description="Thickness in metres.")
    base: WallBaseV2
    top: Annotated[WallTopAtLevelV2 | WallTopHeightV2, Field(discriminator="kind")]


class ProjectFileV2(_Strict):
    """A BrunelleschiBIM project, schema version 2."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title="BrunelleschiBIM project file, schema version 2",
        json_schema_extra={
            "$id": "https://github.com/SamuDiPi/BrunelleschiBIM/schemas/bbim-2.schema.json",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
        },
    )

    format: Literal["brunelleschi-project"] = Field(
        description="Identifies the file as a BrunelleschiBIM project."
    )
    schema_version: Literal[2] = Field(description="Version of this file format.")
    name: str = Field(min_length=1, max_length=200, description="Project name.")
    levels: list[LevelV1] = Field(description="Levels, in creation order.")
    walls: list[WallV2] = Field(description="Walls, in creation order.")
