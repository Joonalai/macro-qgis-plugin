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
"""Qt tree model for building macro workflows in the macro panel.

Workflows are the top level items of the tree and their steps are the child
items. Each step refers to a macro of a :class:`MacroTableModel` by uid, so
renaming a macro is reflected in every workflow that uses it.
"""

import json
from collections.abc import Iterable
from typing import Any

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import (
    NULL,
    QAbstractItemModel,
    QMimeData,
    QModelIndex,
    QObject,
    Qt,
    QVariant,
)
from qgis.PyQt.QtGui import QBrush, QFont, QPalette
from qgis.PyQt.QtWidgets import QApplication
from qgis_macros.macro import Macro
from qgis_macros.macro_workflow import MacroWorkflow
from qgis_plugin_tools.tools.i18n import tr

from macro_plugin.macro_storage import WorkflowStorage
from macro_plugin.ui.macro_model import MACRO_UIDS_MIME_TYPE, MacroTableModel


class MacroWorkflowTreeModel(QAbstractItemModel):
    """Tree model for a list of :class:`~qgis_macros.macro_workflow.MacroWorkflow`.

    Macros can be dropped on a workflow to append them or between the steps of
    a workflow to insert them. Steps can be dragged to reorder them or to move
    them to another workflow.
    """

    def __init__(
        self,
        macro_model: MacroTableModel,
        storage: WorkflowStorage | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the model with an empty workflow list.

        :param macro_model: Model of the macros the workflow steps refer to.
        :param storage: Optional storage that is kept in sync with the model.
        :param parent: Optional parent QObject.
        """
        super().__init__(parent)
        self.workflows: list[MacroWorkflow] = []
        self._macro_model = macro_model
        self._storage = storage
        self._playing_step: tuple[MacroWorkflow, int] | None = None

        self._macro_model.rowsAboutToBeRemoved.connect(self._remove_deleted_macros)
        for signal in (
            self._macro_model.dataChanged,
            self._macro_model.rowsInserted,
            self._macro_model.modelReset,
        ):
            signal.connect(self._refresh_steps)

    # Public API

    def workflow_row(self, workflow: MacroWorkflow) -> int:
        """Return the row of *workflow*."""
        return next(i for i, w in enumerate(self.workflows) if w is workflow)

    def workflow_index(self, workflow: MacroWorkflow) -> QModelIndex:
        """Return the top level index of *workflow*."""
        return self.index(self.workflow_row(workflow), 0)

    def workflow_for_index(self, index: QModelIndex) -> MacroWorkflow | None:
        """Return the workflow of a workflow index or of a step index."""
        if not index.isValid():
            return None
        parent_workflow = self._parent_workflow(index)
        if parent_workflow is not None:
            return parent_workflow
        return self.workflows[index.row()]

    def is_step(self, index: QModelIndex) -> bool:
        """Return whether *index* points to a step of a workflow."""
        return index.isValid() and self._parent_workflow(index) is not None

    def macro_for_step(self, index: QModelIndex) -> Macro | None:
        """Return the macro of a step index, or None if it does not exist."""
        workflow = self._parent_workflow(index)
        if workflow is None:
            return None
        return self.macros_by_uid().get(workflow.macro_uids[index.row()])

    def macros_by_uid(self) -> dict[str, Macro]:
        """Return the available macros keyed by their uid."""
        return {macro.uid: macro for macro in self._macro_model.macros}

    def add_workflow(self, name: str, macro_uids: Iterable[str] = ()) -> QModelIndex:
        """Append a new workflow and return its index."""
        return self.add_workflows([MacroWorkflow(name, list(macro_uids))])[0]

    def add_workflows(self, workflows: list[MacroWorkflow]) -> list[QModelIndex]:
        """Append workflows and return their indexes."""
        if not workflows:
            return []
        row = len(self.workflows)
        self.beginInsertRows(QModelIndex(), row, row + len(workflows) - 1)
        self.workflows.extend(workflows)
        self.endInsertRows()
        for workflow in workflows:
            self._save(workflow)
        return [self.index(row + i, 0) for i in range(len(workflows))]

    def reset_workflows(self, workflows: list[MacroWorkflow]) -> None:
        """Replace the entire workflow list and reset the model.

        The storage is not modified.
        """
        self.beginResetModel()
        self.workflows = workflows
        self.endResetModel()

    def insert_steps(
        self, workflow: MacroWorkflow, row: int, macro_uids: list[str]
    ) -> None:
        """Insert steps for *macro_uids* to *workflow* starting at *row*.

        A negative *row* appends the steps to the end of the workflow.
        """
        if not macro_uids:
            return
        if row < 0 or row > len(workflow.macro_uids):
            row = len(workflow.macro_uids)
        self.beginInsertRows(
            self.workflow_index(workflow), row, row + len(macro_uids) - 1
        )
        workflow.macro_uids[row:row] = macro_uids
        self.endInsertRows()
        self._refresh_step_numbers(workflow)
        self._save(workflow)

    def move_step(self, index: QModelIndex, offset: int) -> QModelIndex:
        """Move the step at *index* by *offset* rows inside its workflow.

        :returns: The new index of the step, or *index* if it cannot move.
        """
        workflow = self._parent_workflow(index)
        if workflow is None:
            return index
        source = index.row()
        target = source + offset
        if offset == 0 or not 0 <= target < len(workflow.macro_uids):
            return index

        parent = self.parent(index)
        # Qt expects the destination row to be given as if the source row
        # was still in place.
        destination = target + 1 if offset > 0 else target
        self.beginMoveRows(parent, source, source, parent, destination)
        workflow.macro_uids.insert(target, workflow.macro_uids.pop(source))
        self.endMoveRows()
        self._refresh_step_numbers(workflow)
        self._save(workflow)
        return self.index(target, 0, parent)

    def set_playing_step(self, workflow: MacroWorkflow | None, row: int = 0) -> None:
        """Mark the step at *row* of *workflow* as playing.

        :param workflow: Workflow of the playing step, or None to clear the mark.
        :param row: Row of the playing step.
        """
        previous_index = self._playing_step_index()
        self._playing_step = (workflow, row) if workflow is not None else None
        for index in (previous_index, self._playing_step_index()):
            if index.isValid():
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])

    # Qt model implementation

    def index(  # noqa: D102
        self, row: int, column: int, parent: QModelIndex | None = None
    ) -> QModelIndex:
        parent = parent or QModelIndex()
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            return self.createIndex(row, column)
        return self.createIndex(row, column, self.workflows[parent.row()])

    def parent(self, index: QModelIndex) -> QModelIndex:  # type: ignore[override]  # noqa: D102
        workflow = self._parent_workflow(index)
        if workflow is None:
            return QModelIndex()
        return self.createIndex(self.workflow_row(workflow), 0)

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802, D102
        parent = parent or QModelIndex()
        if not parent.isValid():
            return len(self.workflows)
        if parent.column() != 0 or self.is_step(parent):
            return 0
        return len(self.workflows[parent.row()].macro_uids)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802, ARG002, D102
        return 1

    def headerData(  # noqa: N802, D102
        self,
        section: int,
        orientation: Qt.Orientation,
        role: Qt.ItemDataRole = Qt.ItemDataRole.DisplayRole,
    ) -> QVariant:
        if (
            section == 0
            and role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return QVariant(tr("Macro workflow"))
        return NULL

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Return the flags for the given index."""
        default_flags = super().flags(index)
        if not index.isValid():
            return default_flags
        if self.is_step(index):
            return default_flags | Qt.ItemFlag.ItemIsDragEnabled
        return (
            default_flags | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsDropEnabled
        )

    def data(
        self, index: QModelIndex, role: Qt.ItemDataRole = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        """Return the data for the given index and role."""
        if not index.isValid():
            return NULL
        workflow = self._parent_workflow(index)
        if workflow is None:
            return self._workflow_data(self.workflows[index.row()], role)
        return self._step_data(workflow, index.row(), role)

    def setData(  # noqa: N802
        self,
        index: QModelIndex,
        value: str,
        role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """Rename the workflow at *index*."""
        if (
            not index.isValid()
            or self.is_step(index)
            or role != Qt.ItemDataRole.EditRole
        ):
            return False
        name = value.strip()
        if not name:
            return False
        workflow = self.workflows[index.row()]
        workflow.name = name
        self.dataChanged.emit(index, index, [role])
        self._save(workflow)
        return True

    def removeRows(  # noqa: N802
        self, row: int, count: int, parent: QModelIndex | None = None
    ) -> bool:
        """Remove workflows, or steps if *parent* is a workflow."""
        parent = parent or QModelIndex()
        if count <= 0 or row < 0 or row + count > self.rowCount(parent):
            return False

        self.beginRemoveRows(parent, row, row + count - 1)
        if parent.isValid():
            workflow = self.workflows[parent.row()]
            del workflow.macro_uids[row : row + count]
            removed_workflows = []
        else:
            removed_workflows = self.workflows[row : row + count]
            del self.workflows[row : row + count]
        self.endRemoveRows()

        if parent.isValid():
            self._refresh_step_numbers(workflow)
            self._save(workflow)
        elif self._storage is not None:
            for removed in removed_workflows:
                self._storage.delete_workflow(removed)
        return True

    # Drag and drop

    def supportedDragActions(self) -> Qt.DropAction:  # noqa: N802, D102
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction

    def supportedDropActions(self) -> Qt.DropAction:  # noqa: N802, D102
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction

    def mimeTypes(self) -> list[str]:  # noqa: N802, D102
        return [MACRO_UIDS_MIME_TYPE]

    def mimeData(self, indexes: Iterable[QModelIndex]) -> QMimeData:  # noqa: N802, D102
        steps = sorted(
            (index for index in indexes if self.is_step(index)),
            key=lambda index: (self.parent(index).row(), index.row()),
        )
        uids = [
            self.workflows[self.parent(index).row()].macro_uids[index.row()]
            for index in steps
        ]
        mime_data = QMimeData()
        mime_data.setData(MACRO_UIDS_MIME_TYPE, json.dumps(uids).encode("utf-8"))
        return mime_data

    def canDropMimeData(  # noqa: N802, D102
        self,
        data: QMimeData,
        action: Qt.DropAction,  # noqa: ARG002
        row: int,  # noqa: ARG002
        column: int,  # noqa: ARG002
        parent: QModelIndex,
    ) -> bool:
        return data.hasFormat(MACRO_UIDS_MIME_TYPE) and (
            parent.isValid() and not self.is_step(parent)
        )

    def dropMimeData(  # noqa: N802
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        """Insert the dropped macros to the workflow at *parent*.

        When steps are moved, the view removes the original steps after a
        successful drop.
        """
        if action == Qt.DropAction.IgnoreAction:
            return True
        if not self.canDropMimeData(data, action, row, column, parent):
            return False
        try:
            uids = json.loads(bytes(data.data(MACRO_UIDS_MIME_TYPE)).decode("utf-8"))
        except ValueError:
            return False
        if not isinstance(uids, list) or not uids:
            return False
        self.insert_steps(self.workflows[parent.row()], row, [str(u) for u in uids])
        return True

    # Private helpers

    def _parent_workflow(self, index: QModelIndex) -> MacroWorkflow | None:
        if not index.isValid():
            return None
        return index.internalPointer()

    def _workflow_data(self, workflow: MacroWorkflow, role: int) -> Any:
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return QVariant(workflow.name)
        if role == Qt.ItemDataRole.ToolTipRole:
            return QVariant(
                tr("{}: {} macros", workflow.name, len(workflow.macro_uids))
            )
        if role == Qt.ItemDataRole.FontRole:
            font = QFont()
            font.setBold(True)
            return font
        return NULL

    def _step_data(self, workflow: MacroWorkflow, row: int, role: int) -> Any:
        macro = self.macros_by_uid().get(workflow.macro_uids[row])
        if role == Qt.ItemDataRole.DecorationRole and self._is_playing(workflow, row):
            return QgsApplication.getThemeIcon("/mActionPlay.svg")
        if role == Qt.ItemDataRole.DisplayRole:
            name = macro.name if macro is not None else tr("Missing macro")
            return QVariant(f"{row + 1}. {name}")
        if role == Qt.ItemDataRole.ToolTipRole:
            if macro is None:
                return QVariant(
                    tr("The macro of this step has been deleted or failed to load.")
                )
            return QVariant(macro.name)
        if macro is None:
            return self._missing_step_style(role)
        return NULL

    @staticmethod
    def _missing_step_style(role: int) -> Any:
        """Return the style of a step whose macro does not exist."""
        if role == Qt.ItemDataRole.ForegroundRole:
            return QBrush(
                QApplication.palette().color(QPalette.ColorRole.PlaceholderText)
            )
        if role == Qt.ItemDataRole.FontRole:
            font = QFont()
            font.setItalic(True)
            return font
        return NULL

    def _playing_step_index(self) -> QModelIndex:
        if self._playing_step is None:
            return QModelIndex()
        workflow, row = self._playing_step
        if not any(w is workflow for w in self.workflows):
            return QModelIndex()
        return self.index(row, 0, self.workflow_index(workflow))

    def _is_playing(self, workflow: MacroWorkflow, row: int) -> bool:
        return (
            self._playing_step is not None
            and self._playing_step[0] is workflow
            and self._playing_step[1] == row
        )

    def _save(self, workflow: MacroWorkflow) -> None:
        if self._storage is not None:
            self._storage.save_workflow(workflow)

    def _refresh_step_numbers(self, workflow: MacroWorkflow) -> None:
        """Notify views that the steps of *workflow* need to be redrawn."""
        if not workflow.macro_uids:
            return
        parent = self.workflow_index(workflow)
        self.dataChanged.emit(
            self.index(0, 0, parent),
            self.index(len(workflow.macro_uids) - 1, 0, parent),
        )

    def _refresh_steps(self, *args: object) -> None:  # noqa: ARG002
        for workflow in self.workflows:
            self._refresh_step_numbers(workflow)

    def _remove_deleted_macros(
        self, parent: QModelIndex, first: int, last: int
    ) -> None:
        """Remove the steps that refer to macros that are about to be deleted."""
        if parent.isValid():
            return
        deleted_macros = self._macro_model.macros[first : last + 1]
        deleted_uids = {macro.uid for macro in deleted_macros}
        for workflow in self.workflows:
            workflow_index = self.workflow_index(workflow)
            for row in reversed(range(len(workflow.macro_uids))):
                if workflow.macro_uids[row] in deleted_uids:
                    self.removeRows(row, 1, workflow_index)
