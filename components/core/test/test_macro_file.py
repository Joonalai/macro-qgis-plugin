#  Copyright (c) 2025-2026 macro-qgis-plugin contributors.
#
#
#  This file is part of macro-qgis-plugin.
#
#  macro-qgis-plugin is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  macro-qgis-plugin is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty
#  of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with macro-qgis-plugin. If not, see <https://www.gnu.org/licenses/>.
import json
from pathlib import Path

import pytest
from qgis_macros.exceptions import InvalidMacroFileError
from qgis_macros.macro import Macro, MacroKeyEvent, WidgetSpec
from qgis_macros.macro_file import FORMAT_VERSION, MacroFile
from qgis_macros.macro_workflow import MacroWorkflow


def _macro(name: str) -> Macro:
    return Macro(
        events=[MacroKeyEvent(WidgetSpec("QLineEdit"), key=196, text="ä")],
        name=name,
    )


@pytest.fixture
def macros() -> list[Macro]:
    return [_macro("first"), _macro("second"), _macro("unused")]


def test_save_and_load_keeps_uids_and_links(
    tmp_path: Path, macros: list[Macro]
) -> None:
    workflow = MacroWorkflow("workflow", [macros[1].uid, macros[0].uid, macros[1].uid])
    path = tmp_path / "macros.json"

    MacroFile(macros, [workflow]).save(path)
    loaded = MacroFile.load(path)

    assert loaded.macros == macros
    assert [m.uid for m in loaded.macros] == [m.uid for m in macros]
    assert loaded.workflows == [workflow]
    assert loaded.workflows[0].uid == workflow.uid
    assert json.loads(path.read_text(encoding="utf-8"))["format_version"] == (
        FORMAT_VERSION
    )


def test_for_workflows_includes_used_macros_once(macros: list[Macro]) -> None:
    workflow = MacroWorkflow(
        "workflow", [macros[1].uid, "missing", macros[0].uid, macros[1].uid]
    )

    macro_file = MacroFile.for_workflows([workflow], {m.uid: m for m in macros})

    assert macro_file.macros == [macros[1], macros[0]]
    assert macro_file.workflows == [workflow]


def test_load_first_format_list_of_macros(tmp_path: Path, macros: list[Macro]) -> None:
    path = tmp_path / "old.json"
    path.write_text(json.dumps([m.serialize() for m in macros]), encoding="utf-8")

    loaded = MacroFile.load(path)

    assert loaded.macros == macros
    assert all(
        new.uid != old.uid for new, old in zip(loaded.macros, macros, strict=True)
    )
    assert loaded.workflows == []


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        json.dumps("text"),
        json.dumps({"format_version": 99, "macros": []}),
        json.dumps({"format_version": FORMAT_VERSION}),
        json.dumps({"format_version": FORMAT_VERSION, "macros": [{"name": "x"}]}),
        json.dumps(
            {
                "format_version": FORMAT_VERSION,
                "macros": [],
                "workflows": [{"name": "w", "macro_uids": "a"}],
            }
        ),
    ],
    ids=[
        "invalid_json",
        "wrong_type",
        "unknown_version",
        "no_macros",
        "broken_macro",
        "broken_workflow",
    ],
)
def test_load_invalid_file_raises(tmp_path: Path, content: str) -> None:
    path = tmp_path / "broken.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(InvalidMacroFileError):
        MacroFile.load(path)


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(InvalidMacroFileError):
        MacroFile.load(tmp_path / "missing.json")
