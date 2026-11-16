"""Shared test options and environment."""

from __future__ import annotations

import os

import pytest

# Interface tests never open a window on the screen: Qt draws into memory. This must be
# set before any test creates the Qt application.
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        help="rewrite the golden files in tests/golden instead of comparing with them",
    )


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-golden"))
