"""Version 4 of the project file: version 3 plus a stable project id.

Classes of earlier versions that did not change are reused as they are. A version's
classes are never edited once released: a change means a new version and a migration.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from brunelleschi.storage.schema_v1 import LevelV1
from brunelleschi.storage.schema_v2 import WallV2
from brunelleschi.storage.schema_v3 import DoorV3, WindowV3


class ProjectFileV4(BaseModel):
    """A BrunelleschiBIM project, schema version 4."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title="BrunelleschiBIM project file, schema version 4",
        json_schema_extra={
            "$id": "https://github.com/SamuDiPi/BrunelleschiBIM/schemas/bbim-4.schema.json",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
        },
    )

    format: Literal["brunelleschi-project"] = Field(
        description="Identifies the file as a BrunelleschiBIM project."
    )
    schema_version: Literal[4] = Field(description="Version of this file format.")
    id: UUID = Field(
        description="Stable identifier of the project; exported IFC project, site and "
        "building identifiers derive from it."
    )
    name: str = Field(min_length=1, max_length=200, description="Project name.")
    levels: list[LevelV1] = Field(description="Levels, in creation order.")
    walls: list[WallV2] = Field(description="Walls, in creation order.")
    doors: list[DoorV3] = Field(description="Doors, in creation order.")
    windows: list[WindowV3] = Field(description="Windows, in creation order.")
