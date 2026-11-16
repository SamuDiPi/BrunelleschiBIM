"""Commands on IFC references (links to IFC files of others)."""

from __future__ import annotations

from pathlib import PurePath
from uuid import UUID, uuid4

from brunelleschi.commands.transaction import transaction
from brunelleschi.model import IfcReference, Project


def add_reference(
    project: Project,
    path: str,
    name: str | None = None,
    *,
    reference_id: UUID | None = None,
) -> IfcReference:
    """Link an IFC file. ``path`` is stored as given (with "/" separators): pass a path
    relative to the project file's folder to keep the project movable."""
    stored = path.strip().replace("\\", "/")
    reference = IfcReference(
        id=reference_id or uuid4(),
        name=(name or PurePath(stored).stem).strip(),
        path=stored,
    )
    with transaction(project, f"Link IFC {reference.name!r}"):
        project._add_reference(reference)
    return reference


def remove_reference(project: Project, ref: UUID | str) -> IfcReference:
    """Remove a link. The IFC file itself is not touched."""
    with transaction(project, "Remove IFC link"):
        return project._remove_reference(project.reference(ref).id)
