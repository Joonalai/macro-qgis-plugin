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
from typing import TYPE_CHECKING

import pytest
from qgis.PyQt.QtCore import QMimeData, QModelIndex, Qt
from qgis.PyQt.QtWidgets import QTreeView
from qgis_macros.macro import Macro
from qgis_macros.macro_workflow import MacroWorkflow

from macro_plugin.macro_storage import WorkflowStorage
from macro_plugin.ui.macro_model import MACRO_UIDS_MIME_TYPE, MacroTableModel
from macro_plugin.ui.workflow_model import MacroWorkflowTreeModel

if TYPE_CHECKING:
    from pytestqt.modeltest import ModelTester
    from pytestqt.qtbot import QtBot


@pytest.fixture
def macros() -> list[Macro]:
    return [Macro(events=[], name=name) for name in ("first", "second", "third")]


@pytest.fixture
def macro_model(macros: list[Macro]) -> MacroTableModel:
    model = MacroTableModel()
    model.reset_macros(list(macros))
    return model


@pytest.fixture
def workflow_storage(tmp_path: Path) -> WorkflowStorage:
    return WorkflowStorage(tmp_path / "workflows")


@pytest.fixture
def model(
    macro_model: MacroTableModel, workflow_storage: WorkflowStorage
) -> MacroWorkflowTreeModel:
    return MacroWorkflowTreeModel(macro_model, workflow_storage)


@pytest.fixture
def workflow(model: MacroWorkflowTreeModel, macros: list[Macro]) -> MacroWorkflow:
    model.add_workflow("workflow", [macros[0].uid, macros[1].uid, macros[0].uid])
    return model.workflows[0]


def _step_names(model: MacroWorkflowTreeModel, row: int = 0) -> list[str]:
    parent = model.index(row, 0)
    return [
        model.data(model.index(i, 0, parent)) for i in range(model.rowCount(parent))
    ]


def _uids_mime_data(uids: list[str]) -> QMimeData:
    mime_data = QMimeData()
    mime_data.setData(MACRO_UIDS_MIME_TYPE, json.dumps(uids).encode("utf-8"))
    return mime_data


def test_workflow_tree_structure(
    model: MacroWorkflowTreeModel, workflow: MacroWorkflow
) -> None:
    workflow_index = model.index(0, 0)
    step_index = model.index(1, 0, workflow_index)

    assert model.rowCount(QModelIndex()) == 1
    assert model.rowCount(workflow_index) == 3
    assert model.rowCount(step_index) == 0
    assert model.parent(workflow_index) == QModelIndex()
    assert model.parent(step_index) == workflow_index
    assert model.workflow_for_index(step_index) is workflow
    assert model.workflow_for_index(workflow_index) is workflow
    assert model.is_step(step_index)
    assert not model.is_step(workflow_index)
    assert model.data(workflow_index) == "workflow"
    assert _step_names(model) == ["1. first", "2. second", "3. first"]


def test_only_workflows_are_editable_and_accept_drops(
    model: MacroWorkflowTreeModel, workflow: MacroWorkflow
) -> None:
    workflow_flags = model.flags(model.index(0, 0))
    step_flags = model.flags(model.index(0, 0, model.index(0, 0)))

    assert workflow_flags & Qt.ItemFlag.ItemIsEditable
    assert workflow_flags & Qt.ItemFlag.ItemIsDropEnabled
    assert not workflow_flags & Qt.ItemFlag.ItemIsDragEnabled
    assert step_flags & Qt.ItemFlag.ItemIsDragEnabled
    assert not step_flags & Qt.ItemFlag.ItemIsEditable
    assert not step_flags & Qt.ItemFlag.ItemIsDropEnabled


def test_rename_workflow(
    model: MacroWorkflowTreeModel,
    workflow: MacroWorkflow,
    workflow_storage: WorkflowStorage,
) -> None:
    assert not model.setData(model.index(0, 0), "  ")
    assert model.setData(model.index(0, 0), " renamed ")

    assert workflow.name == "renamed"
    assert [w.name for w in workflow_storage.load_workflows()] == ["renamed"]


def test_insert_steps(
    model: MacroWorkflowTreeModel,
    workflow: MacroWorkflow,
    macros: list[Macro],
    workflow_storage: WorkflowStorage,
) -> None:
    model.insert_steps(workflow, 1, [macros[2].uid])
    model.insert_steps(workflow, -1, [macros[1].uid])

    expected = ["1. first", "2. third", "3. second", "4. first", "5. second"]
    assert _step_names(model) == expected
    assert workflow_storage.load_workflows()[0].macro_uids == workflow.macro_uids


@pytest.mark.parametrize(
    ("row", "offset", "expected_row", "expected_names"),
    [
        (0, 1, 1, ["1. second", "2. first", "3. first"]),
        (1, -1, 0, ["1. second", "2. first", "3. first"]),
        (1, 1, 2, ["1. first", "2. first", "3. second"]),
        (0, -1, 0, ["1. first", "2. second", "3. first"]),
        (2, 1, 2, ["1. first", "2. second", "3. first"]),
    ],
    ids=["down", "up", "down_to_end", "first_up", "last_down"],
)
def test_move_step(
    model: MacroWorkflowTreeModel,
    workflow: MacroWorkflow,
    workflow_storage: WorkflowStorage,
    row: int,
    offset: int,
    expected_row: int,
    expected_names: list[str],
) -> None:
    new_index = model.move_step(model.index(row, 0, model.index(0, 0)), offset)

    assert new_index.row() == expected_row
    assert _step_names(model) == expected_names
    assert workflow_storage.load_workflows()[0].macro_uids == workflow.macro_uids


def test_remove_step_and_workflow(
    model: MacroWorkflowTreeModel,
    workflow: MacroWorkflow,
    workflow_storage: WorkflowStorage,
) -> None:
    assert model.removeRows(1, 1, model.index(0, 0))
    assert _step_names(model) == ["1. first", "2. first"]
    assert workflow_storage.load_workflows()[0].macro_uids == workflow.macro_uids

    assert model.removeRows(0, 1, QModelIndex())
    assert model.workflows == []
    assert workflow_storage.load_workflows() == []


def test_drop_macros_from_macro_table(
    model: MacroWorkflowTreeModel,
    macro_model: MacroTableModel,
    workflow: MacroWorkflow,
) -> None:
    mime_data = macro_model.mimeData([macro_model.index(2, 0), macro_model.index(1, 0)])
    workflow_index = model.index(0, 0)

    assert not model.canDropMimeData(
        mime_data, Qt.DropAction.CopyAction, 0, 0, QModelIndex()
    )
    assert not model.canDropMimeData(
        mime_data, Qt.DropAction.CopyAction, -1, 0, model.index(0, 0, workflow_index)
    )
    assert model.dropMimeData(mime_data, Qt.DropAction.CopyAction, 1, 0, workflow_index)
    assert model.dropMimeData(
        mime_data, Qt.DropAction.CopyAction, -1, 0, workflow_index
    )

    assert _step_names(model) == [
        "1. first",
        "2. second",
        "3. third",
        "4. second",
        "5. first",
        "6. second",
        "7. third",
    ]


def test_drag_step_to_another_workflow(
    model: MacroWorkflowTreeModel, workflow: MacroWorkflow
) -> None:
    model.add_workflow("other")
    source = model.index(1, 0, model.index(0, 0))

    # The view drops the data and removes the source rows on a move
    mime_data = model.mimeData([source])
    assert model.dropMimeData(
        mime_data, Qt.DropAction.MoveAction, -1, 0, model.index(1, 0)
    )
    model.removeRows(source.row(), 1, source.parent())

    assert _step_names(model, 0) == ["1. first", "2. first"]
    assert _step_names(model, 1) == ["1. second"]


def test_drop_rejects_invalid_data(
    model: MacroWorkflowTreeModel, workflow: MacroWorkflow
) -> None:
    mime_data = QMimeData()
    mime_data.setData(MACRO_UIDS_MIME_TYPE, b"{not json")

    assert not model.dropMimeData(
        mime_data, Qt.DropAction.CopyAction, -1, 0, model.index(0, 0)
    )
    assert not model.dropMimeData(
        _uids_mime_data([]), Qt.DropAction.CopyAction, -1, 0, model.index(0, 0)
    )
    assert len(workflow.macro_uids) == 3


def test_deleting_macro_removes_its_steps(
    model: MacroWorkflowTreeModel,
    macro_model: MacroTableModel,
    workflow: MacroWorkflow,
    workflow_storage: WorkflowStorage,
) -> None:
    macro_model.remove_macro(0)

    assert _step_names(model) == ["1. second"]
    assert workflow_storage.load_workflows()[0].macro_uids == workflow.macro_uids


def test_renaming_macro_updates_steps(
    model: MacroWorkflowTreeModel,
    macro_model: MacroTableModel,
    workflow: MacroWorkflow,
    qtbot: "QtBot",
) -> None:
    with qtbot.waitSignal(model.dataChanged):
        macro_model.setData(macro_model.index(0, 0), "renamed")

    assert _step_names(model) == ["1. renamed", "2. second", "3. renamed"]


def test_missing_macro_is_shown_as_missing(model: MacroWorkflowTreeModel) -> None:
    model.add_workflow("workflow", ["missing"])
    step_index = model.index(0, 0, model.index(0, 0))

    assert model.data(step_index) == "1. Missing macro"
    assert model.macro_for_step(step_index) is None
    assert model.data(step_index, Qt.ItemDataRole.FontRole).italic()


def test_reset_workflows_does_not_modify_storage(
    model: MacroWorkflowTreeModel, workflow_storage: WorkflowStorage
) -> None:
    model.reset_workflows([MacroWorkflow("workflow")])

    assert model.rowCount(QModelIndex()) == 1
    assert workflow_storage.load_workflows() == []


def test_playing_step_mark_survives_workflow_deletion(
    model: MacroWorkflowTreeModel, workflow: MacroWorkflow
) -> None:
    step_index = model.index(1, 0, model.index(0, 0))
    model.set_playing_step(workflow, 1)
    assert model.data(step_index, Qt.ItemDataRole.DecorationRole)

    model.removeRows(0, 1, QModelIndex())
    model.set_playing_step(None)

    assert model.workflows == []


def test_model_passes_qt_model_checks(
    model: MacroWorkflowTreeModel,
    workflow: MacroWorkflow,
    qtmodeltester: "ModelTester",
) -> None:
    model.add_workflow("missing", ["missing"])
    model.set_playing_step(workflow, 1)

    qtmodeltester.check(model, force_py=True)


def test_rows_have_height_in_tree_view(
    model: MacroWorkflowTreeModel, workflow: MacroWorkflow, qtbot: "QtBot"
) -> None:
    # Unhandled roles must return an invalid value. A null but valid
    # QVariant as a size hint collapses the rows on Qt 5.
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)
    view.expandAll()
    view.show()
    qtbot.waitExposed(view)

    workflow_index = model.index(0, 0)
    assert view.visualRect(workflow_index).height() > 0
    assert view.visualRect(model.index(0, 0, workflow_index)).height() > 0
