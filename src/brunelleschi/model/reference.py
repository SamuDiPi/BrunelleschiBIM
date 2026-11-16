"""Links to IFC files of others, shown as read-only references (a background to draw on).

The model keeps only the link: a name and the path as the user chose it, relative to the
project file when possible. The referenced file is read when the project is opened; its
content is never copied into the project.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True)
class IfcReference:
    id: UUID
    name: str
    path: str  # as stored: relative to the project file's folder, or absolute; "/" separators
