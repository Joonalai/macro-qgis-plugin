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
import contextlib
import json
from collections.abc import Iterator
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest
from qgis.PyQt.QtCore import QModelIndex, Qt
from qgis.PyQt.QtWidgets import QApplication, QToolButton
from qgis_macros.exceptions import InvalidMacroFileError, MacroPluginError
from qgis_macros.macro import Macro
from qgis_macros.macro_file import MacroFile
from qgis_macros.macro_player import (
    MacroPlaybackReport,
    MacroPlaybackStatus,
    MacroPlayer,
)
from qgis_macros.macro_recorder import MacroRecorder
from qgis_macros.macro_workflow import MacroWorkflow
from qgis_macros.settings import Settings

from macro_plugin.macro_storage import MacroStorage, WorkflowStorage
from macro_plugin.ui.macro_model import MacroTableModel
from macro_plugin.ui.macro_panel import (
    MACRO_GROUP,
    MacroPanel,
    MacroToolFactory,
    QgsApplication,
)
from macro_plugin.ui.workflow_model import MacroWorkflowTreeModel

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture
    from pytest_subtests import SubTests
    from pytestqt.qtbot import QtBot
    from qgis.PyQt.QtWidgets import QAction, QMenu


@pytest.fixture
def mock_macro(mocker: "MockerFixture") -> MagicMock:
    mock_macro = mocker.create_autospec(Macro, instance=True)
    mock_macro.name = None
    # Dataclass fields with a default factory are not part of the spec
    mock_macro.uid = "mock_macro_uid"
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
    panel.tree_view_workflows.setCurrentIndex(QModelIndex())
    panel.tree_view_workflows.selectionModel().selectionChanged.disconnect(
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
    buttons = [
        button
        for button in macro_panel.findChildren(QToolButton)
        if button.objectName().startswith("button_")
    ]
    assert buttons
    for button in buttons:
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
    mocker.patch(
        "macro_plugin.ui.macro_panel.default_workflow_directory",
        return_value=macro_storage.directory.parent / "workflows",
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


@pytest.fixture
def workflow_model(macro_panel: MacroPanel) -> MacroWorkflowTreeModel:
    model = macro_panel.tree_view_workflows.model()
    assert model is not None
    return cast("MacroWorkflowTreeModel", model)


@pytest.fixture
def macros(macro_model: MacroTableModel) -> list[Macro]:
    macros = [Macro(events=[], name=name) for name in ("first", "second")]
    macro_model.add_macros(macros)
    return macros


@pytest.fixture
def workflow(
    macro_panel: MacroPanel,
    workflow_model: MacroWorkflowTreeModel,
    macros: list[Macro],
) -> MacroWorkflow:
    workflow_model.add_workflow(
        "workflow", [macros[1].uid, macros[0].uid, macros[1].uid]
    )
    macro_panel.tab_widget.setCurrentWidget(macro_panel.tab_macro_workflows)
    return workflow_model.workflows[0]


def _select_workflow_item(panel: MacroPanel, row: int, step: int | None = None) -> None:
    model = panel.tree_view_workflows.model()
    assert model is not None
    index = model.index(row, 0)
    if step is not None:
        index = model.index(step, 0, index)
    panel.tree_view_workflows.setCurrentIndex(index)


def test_new_workflow_with_selected_macros(
    macro_panel: MacroPanel,
    workflow_model: MacroWorkflowTreeModel,
    macros: list[Macro],
) -> None:
    macro_panel._new_workflow([macros[0].uid])
    macro_panel._new_workflow()

    assert macro_panel.tab_widget.currentWidget() is macro_panel.tab_macro_workflows
    assert [w.name for w in workflow_model.workflows] == ["workflow_1", "workflow_2"]
    assert workflow_model.workflows[0].macro_uids == [macros[0].uid]
    assert workflow_model.workflows[1].macro_uids == []
    assert macro_panel.tree_view_workflows.currentIndex() == workflow_model.index(1, 0)


def test_add_macros_to_workflow_after_selected_step(
    macro_panel: MacroPanel,
    workflow: MacroWorkflow,
    macros: list[Macro],
) -> None:
    _select_workflow_item(macro_panel, 0, 0)

    macro_panel._add_macro_to_selected_workflow(macros[0])

    assert workflow.macro_uids == [
        macros[1].uid,
        macros[0].uid,
        macros[0].uid,
        macros[1].uid,
    ]
    assert macro_panel.tree_view_workflows.currentIndex().row() == 1


def test_workflow_buttons_follow_selection(
    macro_panel: MacroPanel, workflow: MacroWorkflow, subtests: "SubTests"
) -> None:
    with subtests.test("Nothing selected"):
        assert not macro_panel.button_play_workflow.isEnabled()
        assert not macro_panel.button_delete_workflow_item.isEnabled()
        assert not macro_panel.button_add_step.isEnabled()
        assert not macro_panel.button_move_step_up.isEnabled()

    with subtests.test("Workflow selected"):
        _select_workflow_item(macro_panel, 0)
        assert macro_panel.button_play_workflow.isEnabled()
        assert macro_panel.button_delete_workflow_item.isEnabled()
        assert macro_panel.button_add_step.isEnabled()
        assert not macro_panel.button_move_step_up.isEnabled()
        assert not macro_panel.button_move_step_down.isEnabled()

    with subtests.test("First step selected"):
        _select_workflow_item(macro_panel, 0, 0)
        assert not macro_panel.button_move_step_up.isEnabled()
        assert macro_panel.button_move_step_down.isEnabled()

    with subtests.test("Last step selected"):
        _select_workflow_item(macro_panel, 0, 2)
        assert macro_panel.button_move_step_up.isEnabled()
        assert not macro_panel.button_move_step_down.isEnabled()

    with subtests.test("Macro buttons ignore the tree selection"):
        assert not macro_panel.button_play.isEnabled()
        assert not macro_panel.button_delete.isEnabled()


def test_move_step_with_buttons(
    macro_panel: MacroPanel,
    workflow: MacroWorkflow,
    macros: list[Macro],
    qtbot: "QtBot",
) -> None:
    _select_workflow_item(macro_panel, 0, 0)

    qtbot.mouseClick(macro_panel.button_move_step_down, Qt.MouseButton.LeftButton)

    assert workflow.macro_uids == [macros[0].uid, macros[1].uid, macros[1].uid]
    assert macro_panel.tree_view_workflows.currentIndex().row() == 1


@pytest.mark.parametrize(
    ("step", "expected_uids"),
    [(1, [1, 1]), (None, None)],
    ids=["step", "workflow"],
)
def test_delete_workflow_item(
    macro_panel: MacroPanel,
    workflow_model: MacroWorkflowTreeModel,
    workflow: MacroWorkflow,
    macros: list[Macro],
    macro_model: MacroTableModel,
    qtbot: "QtBot",
    step: int | None,
    expected_uids: list[int] | None,
) -> None:
    _select_workflow_item(macro_panel, 0, step)

    qtbot.mouseClick(macro_panel.button_delete_workflow_item, Qt.MouseButton.LeftButton)

    if expected_uids is None:
        assert workflow_model.workflows == []
    else:
        assert workflow.macro_uids == [macros[i].uid for i in expected_uids]
    # Macros are never deleted from the workflow tab
    assert macro_model.macros == macros


def _playing_steps(model: MacroWorkflowTreeModel) -> list[int]:
    parent = model.index(0, 0)
    return [
        row
        for row in range(model.rowCount(parent))
        if model.data(model.index(row, 0, parent), Qt.ItemDataRole.DecorationRole)
    ]


def test_play_workflow_plays_macros_in_sequence(
    macro_panel: MacroPanel,
    workflow_model: MacroWorkflowTreeModel,
    workflow: MacroWorkflow,
    macros: list[Macro],
    mock_macro_player: "MagicMock",
    mocker: "MockerFixture",
    qtbot: "QtBot",
) -> None:
    msg_bar = mocker.patch("macro_plugin.ui.macro_panel.MsgBar")
    _select_workflow_item(macro_panel, 0)

    qtbot.mouseClick(macro_panel.button_play_workflow, Qt.MouseButton.LeftButton)
    # The playing step is marked in the tree
    for step in range(3):
        assert _playing_steps(workflow_model) == [step]
        macro_panel._macro_playback_ended(MacroPlaybackReport())
    assert _playing_steps(workflow_model) == []

    assert [c.args[0] for c in mock_macro_player.play.call_args_list] == [
        macros[1],
        macros[0],
        macros[1],
    ]
    msg_bar.info.assert_called_once()
    assert "workflow" in msg_bar.info.call_args.args[1]


def test_play_workflow_from_step(
    macro_panel: MacroPanel,
    workflow: MacroWorkflow,
    macros: list[Macro],
    mock_macro_player: "MagicMock",
) -> None:
    macro_panel._play_workflow(workflow, 2)

    mock_macro_player.play.assert_called_once_with(macros[1])


def test_play_workflow_stops_on_failure(
    macro_panel: MacroPanel,
    workflow_model: MacroWorkflowTreeModel,
    workflow: MacroWorkflow,
    mock_macro_player: "MagicMock",
    mocker: "MockerFixture",
) -> None:
    mocker.patch("macro_plugin.ui.macro_panel.MsgBar")
    macro_panel._play_workflow(workflow, 1)

    with pytest.raises(MacroPluginError, match="stopped at step 2"):
        macro_panel._macro_playback_ended.__wrapped__(  # type: ignore[attr-defined]
            macro_panel,
            MacroPlaybackReport(MacroPlaybackStatus.FAILURE, ValueError("boom")),
        )

    assert mock_macro_player.play.call_count == 1
    assert macro_panel._play_queue == []
    assert _playing_steps(workflow_model) == []


def test_play_workflow_with_missing_macro_does_not_play(
    macro_panel: MacroPanel,
    workflow_model: MacroWorkflowTreeModel,
    mock_macro_player: "MagicMock",
) -> None:
    workflow_model.add_workflow("broken", ["missing"])

    with pytest.raises(MacroPluginError):
        macro_panel._play_workflow.__wrapped__(  # type: ignore[attr-defined]
            macro_panel, workflow_model.workflows[0]
        )

    mock_macro_player.play.assert_not_called()


def test_deleting_macro_removes_it_from_workflows(
    macro_panel: MacroPanel,
    workflow: MacroWorkflow,
    macros: list[Macro],
    qtbot: "QtBot",
) -> None:
    macro_panel.tab_widget.setCurrentWidget(macro_panel.tab_macros)
    macro_panel.table_view.selectRow(1)

    qtbot.mouseClick(macro_panel.button_delete, Qt.MouseButton.LeftButton)

    assert workflow.macro_uids == [macros[0].uid]


def test_macro_panel_loads_and_autosaves_workflows(
    mock_macro_recorder: "MagicMock",
    mock_macro_player: "MagicMock",
    macro_storage: MacroStorage,
    tmp_path: "Path",
    qtbot: "QtBot",
) -> None:
    workflow_storage = WorkflowStorage(tmp_path / "workflows")
    macro = Macro(events=[], name="macro")
    macro_storage.save_macro(macro)
    workflow_storage.save_workflow(MacroWorkflow("stored", [macro.uid]))

    panel = MacroPanel(
        mock_macro_recorder,
        mock_macro_player,
        macro_storage,
        workflow_storage=workflow_storage,
    )
    qtbot.addWidget(panel)
    model = cast("MacroWorkflowTreeModel", panel.tree_view_workflows.model())
    stored = model.workflows[0]
    assert model.macro_for_step(model.index(0, 0, model.index(0, 0))) is not None

    panel._new_workflow([macro.uid, macro.uid])
    panel.tree_view_workflows.setCurrentIndex(QModelIndex())

    loaded = workflow_storage.load_workflows()
    assert [w.name for w in loaded] == ["stored", "workflow_1"]
    assert loaded[0].uid == stored.uid
    assert loaded[1].macro_uids == [macro.uid, macro.uid]


def _find_action(menu: "QMenu", text: str) -> "QAction":
    for action in menu.actions():
        if action.text() == text:
            return action
        if action.menu() is not None:
            with contextlib.suppress(LookupError):
                return _find_action(action.menu(), text)
    raise LookupError(text)


def test_macro_context_menu_appends_to_existing_workflow(
    macro_panel: MacroPanel,
    workflow: MacroWorkflow,
    macros: list[Macro],
) -> None:
    macro_panel.tab_widget.setCurrentWidget(macro_panel.tab_macros)
    macro_panel.table_view.selectRow(0)
    menu = macro_panel._create_macro_context_menu()
    assert menu is not None

    _find_action(menu, "workflow").trigger()

    assert workflow.macro_uids[-1] == macros[0].uid
    assert len(workflow.macro_uids) == 4


def test_macro_context_menu_creates_workflow(
    macro_panel: MacroPanel,
    workflow_model: MacroWorkflowTreeModel,
    macros: list[Macro],
) -> None:
    macro_panel.table_view.selectAll()
    menu = macro_panel._create_macro_context_menu()
    assert menu is not None

    _find_action(menu, "New workflow").trigger()

    assert workflow_model.workflows[0].macro_uids == [m.uid for m in macros]
    assert macro_panel.tab_widget.currentWidget() is macro_panel.tab_macro_workflows


def test_workflow_context_menu_step_actions(
    macro_panel: MacroPanel,
    workflow_model: MacroWorkflowTreeModel,
    workflow: MacroWorkflow,
    macros: list[Macro],
    mock_macro_player: "MagicMock",
    subtests: "SubTests",
) -> None:
    step_index = workflow_model.index(1, 0, workflow_model.index(0, 0))

    with subtests.test("Duplicate step"):
        _find_action(
            macro_panel._create_workflow_context_menu(step_index), "Duplicate step"
        ).trigger()
        assert workflow.macro_uids == [
            macros[1].uid,
            macros[0].uid,
            macros[0].uid,
            macros[1].uid,
        ]

    with subtests.test("Play from step"):
        _find_action(
            macro_panel._create_workflow_context_menu(step_index),
            "Play workflow from this step",
        ).trigger()
        assert mock_macro_player.play.call_args.args[0] is macros[0]
        assert len(macro_panel._play_queue) == 2

    with subtests.test("Add macro after step"):
        _select_workflow_item(macro_panel, 0, 0)
        _find_action(
            macro_panel._create_workflow_context_menu(step_index), "second"
        ).trigger()
        assert workflow.macro_uids[1] == macros[1].uid

    with subtests.test("Remove step"):
        _find_action(
            macro_panel._create_workflow_context_menu(step_index), "Remove step"
        ).trigger()
        assert len(workflow.macro_uids) == 4


def test_new_workflow_button(
    macro_panel: MacroPanel,
    workflow_model: MacroWorkflowTreeModel,
    qtbot: "QtBot",
) -> None:
    macro_panel.tab_widget.setCurrentWidget(macro_panel.tab_macro_workflows)

    qtbot.mouseClick(macro_panel.button_new_workflow, Qt.MouseButton.LeftButton)
    _find_action(
        macro_panel._create_workflow_context_menu(QModelIndex()), "New workflow"
    ).trigger()

    assert [w.name for w in workflow_model.workflows] == ["workflow_1", "workflow_2"]
    assert all(w.macro_uids == [] for w in workflow_model.workflows)


def test_stopping_recording_shows_new_macro(
    macro_panel: MacroPanel, macro_model: MacroTableModel, qtbot: "QtBot"
) -> None:
    macro_panel.tab_widget.setCurrentWidget(macro_panel.tab_macro_workflows)

    qtbot.mouseClick(macro_panel.button_record, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(macro_panel.button_record, Qt.MouseButton.LeftButton)

    assert macro_panel.tab_widget.currentWidget() is macro_panel.tab_macros
    assert macro_panel.table_view.currentIndex() == macro_model.index(0, 0)


@pytest.fixture
def macro_file_path(tmp_path: "Path", mocker: "MockerFixture") -> "Path":
    mocker.patch.object(Settings.macro_save_path, "get", return_value=str(tmp_path))
    path = tmp_path / "macros.json"
    for method in ("getSaveFileName", "getOpenFileName"):
        mocker.patch(
            f"macro_plugin.ui.macro_panel.QFileDialog.{method}",
            return_value=(str(path), ""),
        )
    return path


@pytest.fixture
def msg_bar(mocker: "MockerFixture") -> "MagicMock":
    return mocker.patch("macro_plugin.ui.macro_panel.MsgBar")


@pytest.mark.usefixtures("msg_bar")
def test_save_writes_macros_and_workflows(
    macro_panel: MacroPanel,
    workflow: MacroWorkflow,
    macros: list[Macro],
    macro_file_path: "Path",
    qtbot: "QtBot",
) -> None:
    qtbot.mouseClick(macro_panel.button_save, Qt.MouseButton.LeftButton)

    saved = MacroFile.load(macro_file_path)
    assert saved.macros == macros
    assert [m.uid for m in saved.macros] == [m.uid for m in macros]
    assert saved.workflows == [workflow]


@pytest.mark.usefixtures("msg_bar")
def test_export_workflow_writes_only_used_macros(
    macro_panel: MacroPanel,
    macro_model: MacroTableModel,
    workflow: MacroWorkflow,
    macros: list[Macro],
    macro_file_path: "Path",
    qtbot: "QtBot",
) -> None:
    macro_model.add_macro(Macro(events=[], name="unused"))
    _select_workflow_item(macro_panel, 0, 1)

    qtbot.mouseClick(macro_panel.button_export_workflow, Qt.MouseButton.LeftButton)

    saved = MacroFile.load(macro_file_path)
    assert saved.macros == [macros[1], macros[0]]
    assert saved.workflows == [workflow]


@pytest.mark.usefixtures("msg_bar")
def test_export_selected_macros(
    macro_panel: MacroPanel,
    workflow: MacroWorkflow,
    macros: list[Macro],
    macro_file_path: "Path",
) -> None:
    macro_panel.table_view.selectRow(1)
    menu = macro_panel._create_macro_context_menu()
    assert menu is not None

    _find_action(menu, "Export selected macros...").trigger()

    saved = MacroFile.load(macro_file_path)
    assert saved.macros == [macros[1]]
    assert saved.workflows == []


def test_load_file_reuses_existing_items(
    macro_panel: MacroPanel,
    macro_model: MacroTableModel,
    workflow_model: MacroWorkflowTreeModel,
    workflow: MacroWorkflow,
    macros: list[Macro],
    macro_file_path: "Path",
    msg_bar: "MagicMock",
    qtbot: "QtBot",
    subtests: "SubTests",
) -> None:
    new_macro = Macro(events=[], name="new")
    identical_workflow = MacroWorkflow(workflow.name, list(workflow.macro_uids))
    identical_workflow.uid = workflow.uid
    changed_workflow = MacroWorkflow("changed", [macros[0].uid, new_macro.uid])
    changed_workflow.uid = workflow.uid
    new_workflow = MacroWorkflow("new", [new_macro.uid])
    MacroFile(
        [*macros, new_macro], [identical_workflow, changed_workflow, new_workflow]
    ).save(macro_file_path)
    macro_panel.tab_widget.setCurrentWidget(macro_panel.tab_macros)

    with subtests.test("First load"):
        qtbot.mouseClick(macro_panel.button_open, Qt.MouseButton.LeftButton)

        assert macro_model.macros == [*macros, new_macro]
        assert [w.name for w in workflow_model.workflows] == [
            "workflow",
            "changed",
            "new",
        ]
        assert workflow_model.workflows[1].uid != workflow.uid
        assert workflow_model.workflows[1].macro_uids == [
            macros[0].uid,
            new_macro.uid,
        ]
        assert macro_panel.tab_widget.currentWidget() is macro_panel.tab_macro_workflows
        msg_bar.warning.assert_not_called()

    with subtests.test("Second load adds nothing new"):
        qtbot.mouseClick(macro_panel.button_open, Qt.MouseButton.LeftButton)

        assert len(macro_model.macros) == 3
        assert [w.name for w in workflow_model.workflows] == [
            "workflow",
            "changed",
            "new",
        ]


def test_load_first_format_file(
    macro_panel: MacroPanel,
    macro_model: MacroTableModel,
    macro_file_path: "Path",
    msg_bar: "MagicMock",
    qtbot: "QtBot",
) -> None:
    macro = Macro(events=[], name="old")
    macro_file_path.write_text(json.dumps([macro.serialize()]), encoding="utf-8")

    qtbot.mouseClick(macro_panel.button_open, Qt.MouseButton.LeftButton)

    assert macro_model.macros == [macro]
    assert macro_panel.tab_widget.currentWidget() is macro_panel.tab_macros
    msg_bar.info.assert_called_once()


def test_load_warns_about_missing_macros(
    macro_panel: MacroPanel,
    workflow_model: MacroWorkflowTreeModel,
    macro_file_path: "Path",
    msg_bar: "MagicMock",
    qtbot: "QtBot",
) -> None:
    MacroFile([], [MacroWorkflow("broken", ["missing", "missing"])]).save(
        macro_file_path
    )

    qtbot.mouseClick(macro_panel.button_open, Qt.MouseButton.LeftButton)

    assert [w.name for w in workflow_model.workflows] == ["broken"]
    msg_bar.warning.assert_called_once()
    assert "2" in msg_bar.warning.call_args.args[1]


def test_load_invalid_file_adds_nothing(
    macro_panel: MacroPanel,
    macro_model: MacroTableModel,
    macro_file_path: "Path",
    qtbot: "QtBot",
) -> None:
    macro_file_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(InvalidMacroFileError):
        macro_panel._load_macros_from_file.__wrapped__(macro_panel)  # type: ignore[attr-defined]

    assert macro_model.macros == []
