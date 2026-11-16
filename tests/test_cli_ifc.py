"""The ``bbim ifc`` commands, end to end."""

from __future__ import annotations

from pathlib import Path

import pytest

from brunelleschi.cli import main


@pytest.fixture
def house(tmp_path: Path) -> Path:
    path = tmp_path / "house.bbim"
    main(["new", str(path)])
    main(["level", "add", str(path), "Piano terra", "0"])
    main(["level", "add", str(path), "Primo piano", "3"])
    args = ["wall", "add", str(path), "--start", "0", "0", "--end", "6", "0", "--thickness"]
    main([*args, "0,3", "--base", "Piano terra", "--top", "Primo piano"])
    return path


def test_export_and_validate(
    house: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "house.ifc"
    capsys.readouterr()
    assert main(["ifc", "export", str(house), str(out), "--validate"]) == 0
    text = capsys.readouterr().out
    assert "2 storeys, 1 walls, 0 doors, 0 windows" in text
    assert "valid IFC4 (schema and rules)" in text
    assert out.read_text(encoding="utf-8").startswith("ISO-10303-21;")
    assert main(["ifc", "validate", str(out)]) == 0


def test_validate_reports_problems(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.ifc"
    bad.write_text(
        "ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION((''),'2;1');\n"
        "FILE_NAME('','',(''),(''),'','','');\nFILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\n"
        # The GlobalId is mandatory; every other IfcWall attribute is optional in IFC4.
        "#1=IFCWALL($,$,$,$,$,$,$,$,$);\nENDSEC;\nEND-ISO-10303-21;\n",
        encoding="utf-8",
    )
    capsys.readouterr()
    assert main(["ifc", "validate", str(bad)]) == 1
    assert "problem(s) found" in capsys.readouterr().err


def test_validate_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["ifc", "validate", str(tmp_path / "nope.ifc")]) == 1
    assert "file not found" in capsys.readouterr().err
