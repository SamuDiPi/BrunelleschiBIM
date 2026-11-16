"""Validation of IFC files with IfcOpenShell's validator.

Schema validation (types, cardinalities, inverse attributes) always runs. Checking the
EXPRESS ``WHERE`` rules and functions as well needs ``pytest`` at run time, because
IfcOpenShell generates and runs the rules with it; without it the rules are skipped and
``rules_checked`` is false.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from typing import Any

import ifcopenshell
import ifcopenshell.validate


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    level: str
    message: str
    instance: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    issues: tuple[ValidationIssue, ...]
    rules_checked: bool


def rules_available() -> bool:
    return importlib.util.find_spec("pytest") is not None


def validate_ifc(source: ifcopenshell.file | str | os.PathLike[str]) -> ValidationResult:
    """Validate an IFC model or file against its schema, and its rules when possible."""
    model: Any = source if isinstance(source, ifcopenshell.file) else ifcopenshell.open(str(source))
    logger = ifcopenshell.validate.json_logger()
    rules = rules_available()
    ifcopenshell.validate.validate(model, logger, express_rules=rules)
    issues = tuple(
        ValidationIssue(
            level=str(s.get("level", "")),
            message=str(s.get("message", "")),
            instance=str(s.get("instance", "")),
        )
        for s in logger.statements
    )
    return ValidationResult(issues, rules)
