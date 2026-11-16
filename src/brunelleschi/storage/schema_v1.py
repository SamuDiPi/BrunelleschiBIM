"""Version 1 of the project file, as pydantic models.

These classes describe the *file*, not the in-memory model. Keeping them separate lets
the model evolve while old file versions stay readable through migrations. A version's
classes are never edited once released: a change means a new version and a migration.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

FORMAT_NAME = "brunelleschi-project"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LevelV1(_Strict):
    """A named elevation."""

    id: UUID = Field(description="Stable identifier of the level.")
    name: str = Field(min_length=1, max_length=200, description="Unique name, ignoring case.")
    elevation: float = Field(
        allow_inf_nan=False,
        ge=-1e6,
        le=1e6,
        description="Elevation in metres from the project zero.",
    )


class ProjectFileV1(_Strict):
    """A BrunelleschiBIM project, schema version 1."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title="BrunelleschiBIM project file, schema version 1",
        json_schema_extra={
            "$id": "https://github.com/SamuDiPi/BrunelleschiBIM/schemas/bbim-1.schema.json",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
        },
    )

    format: Literal["brunelleschi-project"] = Field(
        description="Identifies the file as a BrunelleschiBIM project."
    )
    schema_version: Literal[1] = Field(description="Version of this file format.")
    name: str = Field(min_length=1, max_length=200, description="Project name.")
    levels: list[LevelV1] = Field(description="Levels, in creation order.")
