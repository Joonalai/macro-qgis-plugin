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
from qgis.PyQt.QtCore import QModelIndex, Qt
from qgis_macros.macro import Macro, MacroKeyEvent, WidgetSpec

from macro_plugin.macro_storage import MacroStorage
from macro_plugin.ui.macro_model import MacroTableModel


@pytest.fixture
def storage(tmp_path: Path) -> MacroStorage:
    return MacroStorage(tmp_path / "autosave")


def _macro(name: str) -> Macro:
    return Macro(
        events=[MacroKeyEvent(WidgetSpec("QLineEdit"), key=196, text="ä")],
        name=name,
    )


def test_load_macros_returns_empty_list_if_directory_is_missing(
    storage: MacroStorage,
) -> None:
    assert storage.load_macros() == []


def test_save_and_load_macros_in_creation_order(storage: MacroStorage) -> None:
    macros = [_macro("first"), _macro("second"), _macro("third")]
    for macro in reversed(macros):
        storage.save_macro(macro)

    loaded = storage.load_macros()

    assert loaded == macros
    assert [macro.uid for macro in loaded] == [macro.uid for macro in macros]


def test_save_macro_overwrites_previous_version(storage: MacroStorage) -> None:
    macro = _macro("old name")
    storage.save_macro(macro)

    macro.name = "new name"
    storage.save_macro(macro)

    assert list(storage.directory.iterdir()) == [storage.macro_path(macro)]
    assert [m.name for m in storage.load_macros()] == ["new name"]


def test_delete_macro_removes_file(storage: MacroStorage) -> None:
    macro = _macro("macro")
    storage.save_macro(macro)

    storage.delete_macro(macro)

    assert not storage.macro_path(macro).exists()
    assert storage.load_macros() == []


def test_delete_macro_without_file_does_nothing(storage: MacroStorage) -> None:
    storage.delete_macro(_macro("never saved"))


def test_load_macros_skips_invalid_files(storage: MacroStorage) -> None:
    macro = _macro("valid")
    storage.save_macro(macro)
    (storage.directory / "0_broken.json").write_text("{not json", encoding="utf-8")
    (storage.directory / "1_wrong.json").write_text(json.dumps({}), encoding="utf-8")

    assert storage.load_macros() == [macro]


def test_model_keeps_storage_in_sync(storage: MacroStorage) -> None:
    model = MacroTableModel(storage)
    first, second = _macro("first"), _macro("second")

    model.add_macros([first, second])
    assert storage.load_macros() == [first, second]

    model.setData(model.index(1, 0), "renamed", Qt.ItemDataRole.EditRole)
    assert [m.name for m in storage.load_macros()] == ["first", "renamed"]

    model.remove_macro(0)
    assert [m.name for m in storage.load_macros()] == ["renamed"]
    assert model.rowCount(QModelIndex()) == 1


def test_model_reset_macros_does_not_modify_storage(storage: MacroStorage) -> None:
    model = MacroTableModel(storage)

    model.reset_macros([_macro("macro")])

    assert storage.load_macros() == []
