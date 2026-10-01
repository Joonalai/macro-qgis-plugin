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
from collections.abc import Iterator
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest
from qgis.PyQt.QtCore import QModelIndex, Qt
from qgis.PyQt.QtWidgets import QApplication, QToolButton
from qgis_macros.macro import Macro
from qgis_macros.macro_player import MacroPlayer
from qgis_macros.macro_recorder import MacroRecorder
from qgis_macros.settings import Settings

from macro_plugin.macro_storage import MacroStorage
from macro_plugin.ui.macro_model import MacroTableModel
from macro_plugin.ui.macro_panel import (
    MACRO_GROUP,
    MacroPanel,
    MacroToolFactory,
    QgsApplication,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture
    from pytest_subtests import SubTests
    from pytestqt.qtbot import QtBot


@pytest.fixture
def mock_macro(mocker: "MockerFixture") -> MagicMock:
    mock_macro = mocker.create_autospec(Macro, instance=True)
    mock_macro.name = None
    return mock_macro


@pytest.fixture
def mock_macro_recorder(
    mocker: "MockerFixture", mock_macro: "MagicMock"
) -> "MagicMock":
    mock_macro_recorder = mocker.create_autospec(MacroRecorder, instance=True)
    mock_macro_recorder.is_recording = lambda: (
        mock_macro_recorder.start_recording.call_count
        > mock_macro_recorder.stop_recording.call_count
    )
    mock_macro_recorder.stop_recording.return_value = mock_macro
    return mock_macro_recorder


@pytest.fixture
def mock_macro_player(mocker: "MockerFixture", mock_macro: "MagicMock") -> "MagicMock":
    mock_player = mocker.create_autospec(MacroPlayer, instance=True)
    mock_player.playback_ended = mocker.MagicMock()
    return mock_player


@pytest.fixture
def macro_panel(
    mock_macro_recorder: "MagicMock",
    mock_macro_player: "MagicMock",
    qtbot: "QtBot",
) -> Iterator[MacroPanel]:
    panel = MacroPanel(mock_macro_recorder, mock_macro_player)
    panel.setFixedSize(200, 300)
    qtbot.addWidget(panel)
    panel.show()
    yield panel
    # Close any open inline editor and clear selection before destruction
    # to prevent signals firing on already-deleted child widgets.
    panel.table_view.setCurrentIndex(QModelIndex())
    panel.table_view.selectionModel().selectionChanged.disconnect(
        panel._update_ui_state
    )
    panel.close()
    QgsApplication.processEvents()
    QApplication.sendPostedEvents(None, 0)
    if MACRO_GROUP in QgsApplication.profiler().groups():
        QgsApplication.profiler().clear(MACRO_GROUP)


@pytest.fixture
def macro_model(macro_panel: MacroPanel) -> MacroTableModel:
    model = macro_panel.table_view.model()
    assert model is not None
    return cast("MacroTableModel", model)


@pytest.fixture
def mock_index(mocker: "MockerFixture") -> "MagicMock":
    mock_index = mocker.create_autospec(QModelIndex)
    mock_index.isValid.return_value = False
    return mock_index


@pytest.fixture
def record_macro(macro_panel: MacroPanel, qtbot: "QtBot") -> None:
    qtbot.mouseClick(macro_panel.button_record, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(macro_panel.button_record, Qt.MouseButton.LeftButton)


@pytest.fixture
def set_macro_selected(macro_panel: MacroPanel) -> None:
    macro_panel.table_view.selectRow(0)


def test_macro_panel_initialization(
    macro_panel: MacroPanel,
    macro_model: MacroTableModel,
    mock_index: "MagicMock",
    mock_macro_recorder: MagicMock,
) -> None:
    assert macro_panel.button_record.isEnabled()
    assert not macro_panel.button_record.isChecked()
    assert not macro_panel.button_play.isEnabled()
    assert not macro_panel.button_delete.isChecked()
    assert not macro_model.macros

    # All buttons should have icons and be auto-risen
    for button in macro_panel.findChildren(QToolButton):
        assert button.icon() is not None
        assert button.autoRaise()

    # No macros should exist in the table
    assert macro_model.rowCount(mock_index) == 0

    # Recorder has been set to filter out macro panel events
    mock_macro_recorder.add_widget_to_filter_events_out.assert_any_call(macro_panel)
    mock_macro_recorder.add_widget_to_filter_events_out.assert_any_call(
        macro_panel.button_record
    )


def test_macro_panel_toggle_recording(
    macro_panel: MacroPanel,
    macro_model: MacroTableModel,
    mock_macro_recorder: "MagicMock",
    mock_macro: "MagicMock",
    qtbot: "QtBot",
    subtests: "SubTests",
) -> None:
    with subtests.test("Start recording"):
        # Act
        qtbot.mouseClick(macro_panel.button_record, Qt.MouseButton.LeftButton)

        # Assert
        mock_macro_recorder.start_recording.assert_called_once()
        assert macro_panel.button_record.isChecked()

    with subtests.test("Stop recording"):
        # Act
        qtbot.mouseClick(macro_panel.button_record, Qt.MouseButton.LeftButton)

        # Assert
        mock_macro_recorder.stop_recording.assert_called_once()
        assert not macro_panel.button_record.isChecked()
        assert mock_macro.name == "macro_1"
        assert macro_model.macros == [mock_macro]


@pytest.mark.usefixtures("record_macro")
def test_macro_panel_recording_should_add_macro_to_table(
    macro_panel: MacroPanel,
    macro_model: MacroTableModel,
    mock_macro: "MagicMock",
    mock_index: "MagicMock",
) -> None:
    assert macro_model.macros == [mock_macro]
    assert macro_model.rowCount(mock_index) == 1
    # Macro should be selected after recording
    assert macro_panel.table_view.currentIndex() == macro_model.index(0, 0)


@pytest.mark.usefixtures("record_macro", "set_macro_selected")
def test_selecting_macro_should_make_macro_buttons_enabled(
    macro_panel: MacroPanel,
    macro_model: MacroTableModel,
) -> None:
    assert macro_panel.table_view.selectedIndexes() == [macro_model.index(0, 0)]
    assert macro_panel.button_play.isEnabled()
    assert macro_panel.button_delete.isEnabled()


def test_macro_panel_generates_incremental_names(
    macro_panel: MacroPanel,
    macro_model: MacroTableModel,
    mock_macro_recorder: "MagicMock",
    mocker: "MockerFixture",
    qtbot: "QtBot",
) -> None:
    mock_macro_1 = mocker.create_autospec(Macro, instance=True)
    mock_macro_1.name = None
    mock_macro_2 = mocker.create_autospec(Macro, instance=True)
    mock_macro_2.name = None
    mock_macro_recorder.stop_recording.side_effect = [mock_macro_1, mock_macro_2]

    # Record first macro
    qtbot.mouseClick(macro_panel.button_record, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(macro_panel.button_record, Qt.MouseButton.LeftButton)
    assert mock_macro_1.name == "macro_1"

    # Record second macro
    qtbot.mouseClick(macro_panel.button_record, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(macro_panel.button_record, Qt.MouseButton.LeftButton)
    assert mock_macro_2.name == "macro_2"


@pytest.mark.parametrize(
    ("existing_names", "expected_name"),
    [
        (["macro_2"], "macro_3"),
        (["macro_1", "macro_3"], "macro_4"),
        (["renamed", "macro_x", "my_macro_5"], "macro_1"),
    ],
    ids=["after_delete", "gap", "custom_names"],
)
def test_macro_panel_does_not_reuse_existing_names(
    macro_panel: MacroPanel,
    macro_model: MacroTableModel,
    mock_macro: "MagicMock",
    qtbot: "QtBot",
    existing_names: list[str],
    expected_name: str,
) -> None:
    macro_model.reset_macros([Macro(events=[], name=name) for name in existing_names])

    qtbot.mouseClick(macro_panel.button_record, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(macro_panel.button_record, Qt.MouseButton.LeftButton)

    assert mock_macro.name == expected_name


@pytest.mark.usefixtures("record_macro", "set_macro_selected")
def test_macro_panel_play_macro(
    macro_panel: MacroPanel,
    mock_macro_player: "MagicMock",
    mock_macro: "MagicMock",
    qtbot: "QtBot",
) -> None:
    # Arrange
    Settings.profile_macros.set(True)

    # Act
    qtbot.mouseClick(macro_panel.button_play, Qt.MouseButton.LeftButton)

    # Assert
    mock_macro_player.play.assert_called_once_with(mock_macro)


@pytest.mark.usefixtures("record_macro", "set_macro_selected")
def test_macro_panel_delete_macro(
    macro_panel: MacroPanel,
    macro_model: MacroTableModel,
    mock_index: "MagicMock",
    qtbot: "QtBot",
) -> None:
    # Act
    qtbot.mouseClick(macro_panel.button_delete, Qt.MouseButton.LeftButton)

    # Assert
    assert macro_panel.table_view.selectedIndexes() == []
    assert macro_model.macros == []
    assert macro_model.rowCount(mock_index) == 0


@pytest.fixture
def macro_storage(tmp_path: "Path") -> MacroStorage:
    return MacroStorage(tmp_path / "autosave")


@pytest.fixture
def autosaving_macro_panel(
    mock_macro_recorder: "MagicMock",
    mock_macro_player: "MagicMock",
    macro_storage: MacroStorage,
    qtbot: "QtBot",
) -> Iterator[MacroPanel]:
    mock_macro_recorder.stop_recording.side_effect = lambda: Macro(events=[])
    panel = MacroPanel(mock_macro_recorder, mock_macro_player, macro_storage)
    qtbot.addWidget(panel)
    panel.show()
    yield panel
    panel.table_view.setCurrentIndex(QModelIndex())
    panel.close()
    QgsApplication.processEvents()


def test_macro_panel_loads_autosaved_macros(
    mock_macro_recorder: "MagicMock",
    mock_macro_player: "MagicMock",
    macro_storage: MacroStorage,
    qtbot: "QtBot",
) -> None:
    macros = [Macro(events=[], name="first"), Macro(events=[], name="second")]
    for macro in macros:
        macro_storage.save_macro(macro)

    panel = MacroPanel(mock_macro_recorder, mock_macro_player, macro_storage)
    qtbot.addWidget(panel)

    assert panel.table_view.model().macros == macros  # type: ignore[union-attr]


def test_macro_panel_autosaves_recorded_macro(
    autosaving_macro_panel: MacroPanel,
    macro_storage: MacroStorage,
    qtbot: "QtBot",
) -> None:
    qtbot.mouseClick(autosaving_macro_panel.button_record, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(autosaving_macro_panel.button_record, Qt.MouseButton.LeftButton)

    assert [macro.name for macro in macro_storage.load_macros()] == ["macro_1"]


def test_macro_panel_delete_removes_autosaved_files(
    autosaving_macro_panel: MacroPanel,
    macro_storage: MacroStorage,
    qtbot: "QtBot",
) -> None:
    for _ in range(3):
        qtbot.mouseClick(
            autosaving_macro_panel.button_record, Qt.MouseButton.LeftButton
        )
        qtbot.mouseClick(
            autosaving_macro_panel.button_record, Qt.MouseButton.LeftButton
        )
    autosaving_macro_panel.table_view.selectAll()

    qtbot.mouseClick(autosaving_macro_panel.button_delete, Qt.MouseButton.LeftButton)

    assert macro_storage.load_macros() == []
    assert not list(macro_storage.directory.iterdir())


@pytest.mark.parametrize("autosave", [True, False], ids=["enabled", "disabled"])
def test_macro_tool_factory_uses_autosave_setting(
    mocker: "MockerFixture",
    macro_storage: MacroStorage,
    qtbot: "QtBot",
    autosave: bool,
) -> None:
    mocker.patch(
        "macro_plugin.ui.macro_panel.default_autosave_directory",
        return_value=macro_storage.directory,
    )
    macro_storage.save_macro(Macro(events=[], name="autosaved"))
    # Settings set here would be stored under a different key than the one the
    # plugin reads, because qgis_plugin_tools resolves the key from the call stack
    mocker.patch.object(Settings.autosave_macros, "get", return_value=autosave)

    panel = MacroToolFactory().createWidget()
    qtbot.addWidget(panel)
    model = cast("MacroTableModel", panel.table_view.model())
    model.add_macro(Macro(events=[], name="new"))

    expected_names = ["autosaved", "new"] if autosave else ["autosaved"]
    assert [macro.name for macro in macro_storage.load_macros()] == expected_names
    assert [macro.name for macro in model.macros] == (
        ["autosaved", "new"] if autosave else ["new"]
    )
