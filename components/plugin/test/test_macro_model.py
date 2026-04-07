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
from typing import TYPE_CHECKING

from macro_plugin.ui.macro_model import MacroTableModel
from qgis.PyQt.QtCore import NULL, QModelIndex, Qt
from qgis_macros.macro import Macro

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_macro_table_model_initialization() -> None:
    model = MacroTableModel()

    assert model.rowCount(QModelIndex()) == 0
    assert model.columnCount(QModelIndex()) == 1
    assert (
        model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        == "Macro"
    )


def test_macro_table_model_add_macro(mocker: "MockerFixture") -> None:
    model = MacroTableModel()
    macro_mock = mocker.Mock(spec=Macro)
    macro_mock.name = "Test Macro"

    model.add_macro(macro_mock)

    assert model.rowCount(QModelIndex()) == 1
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == "Test Macro"


def test_macro_table_model_remove_macro(mocker: "MockerFixture") -> None:
    model = MacroTableModel()
    macro_mock_1 = mocker.Mock(spec=Macro)
    macro_mock_1.name = "Macro 1"
    macro_mock_2 = mocker.Mock(spec=Macro)
    macro_mock_2.name = "Macro 2"

    model.add_macro(macro_mock_1)
    model.add_macro(macro_mock_2)

    assert model.rowCount(QModelIndex()) == 2

    model.remove_macro(0)

    assert model.rowCount(QModelIndex()) == 1
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == "Macro 2"


def test_macro_table_model_header_data() -> None:
    model = MacroTableModel()

    assert (
        model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        == "Macro"
    )
    assert (
        model.headerData(0, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole)
        == NULL
    )
    assert (
        model.headerData(
            0, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole
        )
        == Qt.AlignmentFlag.AlignLeft
    )


def test_macro_table_model_data_invalid_index() -> None:
    model = MacroTableModel()

    invalid_index = QModelIndex()
    assert model.data(invalid_index, Qt.ItemDataRole.DisplayRole) == NULL


def test_macro_table_model_data_text_alignment(mocker: "MockerFixture") -> None:
    model = MacroTableModel()
    macro_mock = mocker.Mock(spec=Macro)
    macro_mock.name = "Macro for Alignment"

    model.add_macro(macro_mock)

    index = model.index(0, 0)

    assert (
        model.data(index, Qt.ItemDataRole.TextAlignmentRole)
        == Qt.AlignmentFlag.AlignLeft
    )


def test_macro_table_model_data_tooltip_role(mocker: "MockerFixture") -> None:
    model = MacroTableModel()
    macro_mock = mocker.Mock(spec=Macro)
    macro_mock.name = "Tooltip Macro"

    model.add_macro(macro_mock)

    index = model.index(0, 0)

    assert model.data(index, Qt.ItemDataRole.ToolTipRole) == "Tooltip Macro"


def test_macro_table_model_flags_editable(mocker: "MockerFixture") -> None:
    model = MacroTableModel()
    macro_mock = mocker.Mock(spec=Macro)
    macro_mock.name = "Editable Macro"
    model.add_macro(macro_mock)

    index = model.index(0, 0)
    flags = model.flags(index)

    assert flags & Qt.ItemFlag.ItemIsEditable


def test_macro_table_model_set_data(mocker: "MockerFixture") -> None:
    model = MacroTableModel()
    macro_mock = mocker.Mock(spec=Macro)
    macro_mock.name = "Old Name"
    model.add_macro(macro_mock)

    index = model.index(0, 0)
    result = model.setData(index, "New Name", Qt.ItemDataRole.EditRole)

    assert result is True
    assert macro_mock.name == "New Name"


def test_macro_table_model_set_data_rejects_empty(mocker: "MockerFixture") -> None:
    model = MacroTableModel()
    macro_mock = mocker.Mock(spec=Macro)
    macro_mock.name = "Keep This"
    model.add_macro(macro_mock)

    index = model.index(0, 0)
    result = model.setData(index, "   ", Qt.ItemDataRole.EditRole)

    assert result is False
    assert macro_mock.name == "Keep This"


def test_macro_table_model_set_data_invalid_index() -> None:
    model = MacroTableModel()

    result = model.setData(QModelIndex(), "Name", Qt.ItemDataRole.EditRole)

    assert result is False
