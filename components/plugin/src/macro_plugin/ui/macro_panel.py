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
"""Macro panel UI with recording, playback, and file I/O controls."""

import json
import re
from collections.abc import Callable, Iterable
from functools import partial
from pathlib import Path
from typing import Any

from qgis.core import QgsApplication
from qgis.gui import QgsDevToolWidget, QgsDevToolWidgetFactory
from qgis.PyQt.QtCore import QModelIndex, QPoint, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QHeaderView,
    QMenu,
    QTableView,
    QTabWidget,
    QToolButton,
    QTreeView,
    QWidget,
)
from qgis_macros.exceptions import MacroNotFoundError, MacroPluginError
from qgis_macros.macro import Macro
from qgis_macros.macro_player import (
    MacroPlaybackReport,
    MacroPlaybackStatus,
    MacroPlayer,
)
from qgis_macros.macro_recorder import MacroRecorder
from qgis_macros.macro_workflow import MacroWorkflow
from qgis_macros.settings import Settings
from qgis_plugin_tools.tools.custom_logging import bar_msg
from qgis_plugin_tools.tools.decorations import log_if_fails
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.tools.messages import MsgBar
from qgis_plugin_tools.tools.resources import load_ui_from_file, resources_path

from macro_plugin.macro_storage import (
    MacroStorage,
    WorkflowStorage,
    default_autosave_directory,
    default_workflow_directory,
)
from macro_plugin.ui.macro_model import MacroTableModel
from macro_plugin.ui.settings_dialog import SettingsDialog
from macro_plugin.ui.workflow_model import MacroWorkflowTreeModel

MACRO_GROUP = "Macro"
MACRO_NAME_PREFIX = "macro"
WORKFLOW_NAME_PREFIX = "workflow"

UI_CLASS: QWidget = load_ui_from_file(
    str(Path(__file__).parent.joinpath("macro_panel.ui"))
)


class MacroPanel(UI_CLASS, QgsDevToolWidget):  # type: ignore
    """A dev tool widget for macro recording, playing, and deletion.

    Provides a table view to display macros and buttons to record, play, and delete
    macros. Macros can be combined into macro workflows in a tree view, where each
    workflow is played back by playing its macros one after another.
    """

    button_record: QToolButton
    button_play: QToolButton
    button_delete: QToolButton
    button_play_workflow: QToolButton
    button_delete_workflow_item: QToolButton
    button_open: QToolButton
    button_save: QToolButton
    button_settings: QToolButton
    button_new_workflow: QToolButton
    button_add_step: QToolButton
    button_move_step_up: QToolButton
    button_move_step_down: QToolButton
    tab_widget: QTabWidget
    tab_macros: QWidget
    tab_macro_workflows: QWidget
    table_view: QTableView
    tree_view_workflows: QTreeView

    def __init__(
        self,
        macro_recorder: MacroRecorder,
        macro_player: MacroPlayer,
        macro_storage: MacroStorage | None = None,
        parent: QWidget | None = None,
        workflow_storage: WorkflowStorage | None = None,
    ) -> None:
        """Initialize the panel.

        :param macro_recorder: Instance of MacroRecorder to handle macro
            recording interactions.
        :param macro_player: Instance of MacroPlayer to handle macro
            playback functionality.
        :param macro_storage: Optional storage for autosaving macros. Stored
            macros are loaded into the panel.
        :param parent: Optional parent QWidget for UI hierarchy.
        :param workflow_storage: Optional storage for autosaving macro
            workflows. Stored workflows are loaded into the panel.
        """
        super().__init__(parent)
        self.setupUi(self)
        self._recorder = macro_recorder
        self._recorder.add_widget_to_filter_events_out(self)
        self._recorder.add_widget_to_filter_events_out(self.button_record)

        self._player = macro_player
        self._player.playback_ended.connect(self._macro_playback_ended)
        self._last_played_macro_name: str | None = None
        # Macros waiting for playback with their workflow step numbers
        self._play_queue: list[tuple[Macro, int | None]] = []
        self._played_workflow: MacroWorkflow | None = None
        self._played_step: int | None = None

        self._model = MacroTableModel(macro_storage)
        if macro_storage is not None:
            self._model.reset_macros(macro_storage.load_macros())

        self._workflow_model = MacroWorkflowTreeModel(
            self._model, workflow_storage, self
        )
        if workflow_storage is not None:
            self._workflow_model.reset_workflows(workflow_storage.load_workflows())

        self._configure_table()
        self._configure_workflow_tree()
        self._configure_buttons()
        self._update_ui_state()

    def _configure_table(self) -> None:
        """Set up the table view with appropriate settings."""
        self.table_view.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table_view.setModel(self._model)
        self.table_view.selectionModel().selectionChanged.connect(self._update_ui_state)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(
            self._show_macro_context_menu
        )

    def _configure_workflow_tree(self) -> None:
        """Set up the workflow tree view and the tabs."""
        self.tree_view_workflows.setModel(self._workflow_model)
        self.tree_view_workflows.expandAll()
        self.tree_view_workflows.selectionModel().selectionChanged.connect(
            self._update_ui_state
        )
        self.tree_view_workflows.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.tree_view_workflows.customContextMenuRequested.connect(
            self._show_workflow_context_menu
        )
        for signal in (
            self._workflow_model.rowsRemoved,
            self._workflow_model.rowsMoved,
            self._workflow_model.modelReset,
        ):
            signal.connect(self._update_ui_state)
        self._workflow_model.rowsInserted.connect(self._workflow_rows_inserted)

        # Switch to the workflows tab when macros are dragged over it
        tab_bar = self.tab_widget.tabBar()
        tab_bar.setChangeCurrentOnDrag(True)
        tab_bar.setAcceptDrops(True)

        self._add_step_menu = QMenu(self)
        self._add_step_menu.aboutToShow.connect(self._populate_add_step_menu)
        self.button_add_step.setMenu(self._add_step_menu)

    def _configure_buttons(self) -> None:
        """Configure buttons with icons, tooltips, and connect them to actions."""
        button_config = {
            self.button_record: (
                self._toggle_recording,
                "/mActionRecord.svg",
            ),
            self.button_play: (
                self._play_macro,
                "/mActionPlay.svg",
            ),
            self.button_delete: (
                self._delete_macros,
                "/mActionDeleteSelected.svg",
            ),
            self.button_open: (
                self._load_macros_from_file,
                "/mActionFileOpen.svg",
            ),
            self.button_save: (
                self._save_macros_to_file,
                "/mActionFileSave.svg",
            ),
            self.button_settings: (
                self._open_settings,
                "/console/iconSettingsConsole.svg",
            ),
            self.button_play_workflow: (
                self._play_selected_workflow,
                "/mActionPlay.svg",
            ),
            self.button_delete_workflow_item: (
                self._delete_selected_workflow_item,
                "/mActionDeleteSelected.svg",
            ),
            self.button_new_workflow: (
                self._new_workflow,
                "/mActionAdd.svg",
            ),
            self.button_add_step: (
                None,
                "/symbologyAdd.svg",
            ),
            self.button_move_step_up: (
                partial(self._move_selected_step, -1),
                "/mActionArrowUp.svg",
            ),
            self.button_move_step_down: (
                partial(self._move_selected_step, 1),
                "/mActionArrowDown.svg",
            ),
        }

        for button, (action, icon) in button_config.items():
            button.setAutoRaise(True)
            button.setIcon(QgsApplication.getThemeIcon(icon))
            if action is not None:
                # The checked argument of the signal must not reach the action
                button.clicked.connect(lambda *_, action=action: action())

    def _validate_macro_selection(self) -> bool:
        """Check if there are selected macros available for operations."""
        return bool(self._model.macros and self.table_view.selectedIndexes())

    def _selected_macro_rows(self) -> list[int]:
        return sorted({index.row() for index in self.table_view.selectedIndexes()})

    def _selected_workflow_index(self) -> QModelIndex:
        """Return the selected workflow or step index of the tree."""
        indexes = self.tree_view_workflows.selectionModel().selectedIndexes()
        return indexes[0] if indexes else QModelIndex()

    @staticmethod
    def _generate_name(prefix: str, names: Iterable[str | None]) -> str:
        """Return the next unused ``<prefix>_<number>`` name."""
        pattern = re.compile(rf"{re.escape(prefix)}_(\d+)")
        numbers = [
            int(match.group(1))
            for name in names
            if name and (match := pattern.fullmatch(name))
        ]
        return f"{prefix}_{max(numbers, default=0) + 1}"

    def _generate_macro_name(self) -> str:
        """Return the next unused ``macro_<number>`` name."""
        return self._generate_name(
            MACRO_NAME_PREFIX, (macro.name for macro in self._model.macros)
        )

    def _generate_workflow_name(self) -> str:
        """Return the next unused ``workflow_<number>`` name."""
        return self._generate_name(
            WORKFLOW_NAME_PREFIX,
            (workflow.name for workflow in self._workflow_model.workflows),
        )

    def _toggle_recording(self) -> None:
        if not self._recorder.is_recording():
            self._recorder.start_recording()
        else:
            macro = self._recorder.stop_recording()
            macro.name = self._generate_macro_name()
            self._model.add_macro(macro)

            # The new macro is shown with its name editor open
            self.tab_widget.setCurrentWidget(self.tab_macros)
            new_index = self._model.index(len(self._model.macros) - 1, 0)
            self.table_view.setCurrentIndex(new_index)
            self.table_view.edit(new_index)
        self._update_ui_state()

    def _play_macro(self) -> None:
        if not self._validate_macro_selection():
            return

        macro = self._model.macros[self.table_view.selectedIndexes()[0].row()]
        self._play_macros([(macro, None)])

    def _play_selected_workflow(self) -> None:
        workflow = self._workflow_model.workflow_for_index(
            self._selected_workflow_index()
        )
        if workflow is not None:
            self._play_workflow(workflow)

    @log_if_fails
    def _play_workflow(self, workflow: MacroWorkflow, start_step: int = 0) -> None:
        """Play the macros of *workflow* starting from step *start_step*."""
        try:
            macros = workflow.resolve_macros(self._workflow_model.macros_by_uid())
        except MacroNotFoundError as e:
            raise MacroPluginError(
                tr("Macro workflow '{}' refers to a missing macro.", workflow.name),
                bar_msg(details=str(e)),
            ) from e
        steps = list(enumerate(macros))[start_step:]
        if not steps:
            raise MacroPluginError(
                tr("Macro workflow '{}' does not contain any macros.", workflow.name)
            )
        self._play_macros([(macro, step) for step, macro in steps], workflow)

    def _play_macros(
        self,
        macros: list[tuple[Macro, int | None]],
        workflow: MacroWorkflow | None = None,
    ) -> None:
        """Play *macros* one after another.

        :param macros: Macros to play with their step numbers in *workflow*.
        :param workflow: The played workflow, if any.
        """
        self._play_queue = list(macros)
        self._played_workflow = workflow
        self._play_next_macro()

    def _play_next_macro(self) -> None:
        macro, self._played_step = self._play_queue.pop(0)
        if Settings.profile_macros.get():
            QgsApplication.profiler().start(
                f"Macro: {macro.name}", Settings.profile_macro_group.get()
            )

        self._last_played_macro_name = macro.name
        if self._played_workflow is not None and self._played_step is not None:
            self._workflow_model.set_playing_step(
                self._played_workflow, self._played_step
            )
        self._player.play(macro)

    def _finish_playback(self) -> None:
        self._play_queue.clear()
        self._played_workflow = None
        self._played_step = None
        self._workflow_model.set_playing_step(None)

    @log_if_fails
    def _macro_playback_ended(self, macro_report: MacroPlaybackReport) -> None:
        if Settings.profile_macros.get():
            QgsApplication.profiler().end(Settings.profile_macro_group.get())
        workflow = self._played_workflow
        step = self._played_step
        if macro_report.status == MacroPlaybackStatus.FAILURE:
            self._finish_playback()
            error = macro_report.error or MacroPluginError(
                tr("Playback ended with failure.")
            )
            if workflow is None or step is None:
                raise error
            raise MacroPluginError(
                tr(
                    "Macro workflow '{}' stopped at step {} (macro '{}').",
                    workflow.name,
                    step + 1,
                    self._last_played_macro_name,
                ),
                bar_msg(details=str(error)),
            ) from error

        if self._play_queue:
            self._play_next_macro()
            return

        self._finish_playback()
        if workflow is not None:
            MsgBar.info(
                tr("Macro workflow playback ended"),
                tr("Macro workflow '{}' playback ended successfully.", workflow.name),
            )
            return
        MsgBar.info(
            tr("Macro playback ended"),
            tr(
                "Macro '{}' playback ended successfully.",
                self._last_played_macro_name,
            ),
        )

    def _delete_selected_workflow_item(self) -> None:
        self._delete_workflow_item(self._selected_workflow_index())

    def _delete_workflow_item(self, index: QModelIndex) -> None:
        """Delete the workflow or the workflow step at *index*."""
        if not index.isValid():
            return
        self._workflow_model.removeRows(
            index.row(), 1, self._workflow_model.parent(index)
        )
        self._update_ui_state()

    def _new_workflow(self, macro_uids: Iterable[str] = ()) -> None:
        """Create a workflow, select it and start editing its name."""
        index = self._workflow_model.add_workflow(
            self._generate_workflow_name(), macro_uids
        )
        self.tab_widget.setCurrentWidget(self.tab_macro_workflows)
        self.tree_view_workflows.expand(index)
        self.tree_view_workflows.setCurrentIndex(index)
        self.tree_view_workflows.edit(index)

    def _add_macros_to_workflow(
        self, workflow: MacroWorkflow, macro_uids: list[str], row: int = -1
    ) -> None:
        """Insert *macro_uids* to *workflow* at *row* and select the last step."""
        if row < 0:
            row = len(workflow.macro_uids)
        self._workflow_model.insert_steps(workflow, row, macro_uids)
        parent = self._workflow_model.workflow_index(workflow)
        self.tree_view_workflows.setCurrentIndex(
            self._workflow_model.index(row + len(macro_uids) - 1, 0, parent)
        )

    def _add_macro_to_selected_workflow(self, macro: Macro) -> None:
        """Add *macro* after the selected step or to the end of the workflow."""
        index = self._selected_workflow_index()
        workflow = self._workflow_model.workflow_for_index(index)
        if workflow is None:
            return
        row = index.row() + 1 if self._workflow_model.is_step(index) else -1
        self._add_macros_to_workflow(workflow, [macro.uid], row)

    def _move_selected_step(self, offset: int) -> None:
        index = self._workflow_model.move_step(self._selected_workflow_index(), offset)
        self.tree_view_workflows.setCurrentIndex(index)
        self._update_ui_state()

    def _workflow_rows_inserted(self, parent: QModelIndex, *args: Any) -> None:  # noqa: ARG002
        if parent.isValid():
            self.tree_view_workflows.expand(parent)
        self._update_ui_state()

    def _populate_add_step_menu(self) -> None:
        self._add_step_menu.clear()
        self._add_macro_actions(self._add_step_menu)

    @staticmethod
    def _add_action(
        menu: QMenu,
        text: str,
        callback: Callable[[], object],
        icon: str | None = None,
    ) -> None:
        """Add an action to *menu* that calls *callback* without arguments."""
        action = (
            menu.addAction(QgsApplication.getThemeIcon(icon), text)
            if icon
            else menu.addAction(text)
        )
        # The checked argument of the signal must not reach the callback
        action.triggered.connect(lambda *_: callback())

    def _add_macro_actions(self, menu: QMenu) -> None:
        """Add an action for each macro that adds it to the selected workflow."""
        if not self._model.macros:
            menu.addAction(tr("No macros recorded")).setEnabled(False)
        for macro in self._model.macros:
            self._add_action(
                menu,
                macro.name or "",
                partial(self._add_macro_to_selected_workflow, macro),
            )

    def _create_macro_context_menu(self) -> QMenu | None:
        """Create the context menu of the selected macros."""
        rows = self._selected_macro_rows()
        if not rows:
            return None
        macro_uids = [self._model.macros[row].uid for row in rows]

        menu = QMenu(self)
        add_menu = menu.addMenu(
            QgsApplication.getThemeIcon("/symbologyAdd.svg"), tr("Add to workflow")
        )
        for workflow in self._workflow_model.workflows:
            self._add_action(
                add_menu,
                workflow.name or "",
                partial(self._add_macros_to_workflow, workflow, macro_uids),
            )
        if self._workflow_model.workflows:
            add_menu.addSeparator()
        self._add_action(
            add_menu,
            tr("New workflow"),
            partial(self._new_workflow, macro_uids),
            "/mActionAdd.svg",
        )
        return menu

    def _create_workflow_context_menu(self, index: QModelIndex) -> QMenu:
        """Create the context menu of the workflow or step at *index*."""
        workflow = self._workflow_model.workflow_for_index(index)
        menu = QMenu(self)
        if workflow is None:
            self._add_action(
                menu, tr("New workflow"), self._new_workflow, "/mActionAdd.svg"
            )
            return menu

        is_step = self._workflow_model.is_step(index)
        self._add_action(
            menu,
            tr("Play workflow"),
            partial(self._play_workflow, workflow),
            "/mActionPlay.svg",
        )
        if is_step:
            self._add_action(
                menu,
                tr("Play workflow from this step"),
                partial(self._play_workflow, workflow, index.row()),
                "/mActionPlay.svg",
            )
        menu.addSeparator()
        self._add_macro_actions(
            menu.addMenu(
                QgsApplication.getThemeIcon("/symbologyAdd.svg"), tr("Add macro")
            )
        )
        if is_step:
            self._add_action(
                menu,
                tr("Duplicate step"),
                partial(
                    self._add_macros_to_workflow,
                    workflow,
                    [workflow.macro_uids[index.row()]],
                    index.row() + 1,
                ),
            )
            self._add_action(
                menu,
                tr("Remove step"),
                partial(self._delete_workflow_item, index),
                "/mActionDeleteSelected.svg",
            )
        else:
            self._add_action(
                menu, tr("Rename"), partial(self.tree_view_workflows.edit, index)
            )
            self._add_action(
                menu,
                tr("Delete workflow"),
                partial(self._delete_workflow_item, index),
                "/mActionDeleteSelected.svg",
            )
        return menu

    def _show_macro_context_menu(self, position: QPoint) -> None:
        menu = self._create_macro_context_menu()
        if menu is not None:
            menu.exec(self.table_view.viewport().mapToGlobal(position))

    def _show_workflow_context_menu(self, position: QPoint) -> None:
        index = self.tree_view_workflows.indexAt(position)
        # The menu actions work on the clicked item, so select it to show that
        self.tree_view_workflows.setCurrentIndex(index)
        menu = self._create_workflow_context_menu(index)
        menu.exec(self.tree_view_workflows.viewport().mapToGlobal(position))

    def _delete_macros(self) -> None:
        if not self._validate_macro_selection():
            return
        for index in reversed(self.table_view.selectedIndexes()):
            self._model.remove_macro(index.row())
        self._update_ui_state()

    def _open_settings(self) -> None:
        SettingsDialog().exec()
        self._player.set_speed(Settings.speed.get())
        self._update_ui_state()

    def _load_macros_from_file(self) -> None:
        default_path = Path(Settings.macro_save_path.get())
        default_path.mkdir(parents=True, exist_ok=True)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Load Macros"),
            str(default_path),
            tr("Macro Files (*.json);;All Files (*)"),
        )
        if file_path:
            with Path(file_path).open("r") as path:
                data = json.load(path)
                macros = [Macro.deserialize(macro_data) for macro_data in data]
                self._model.add_macros(macros)

    def _save_macros_to_file(self) -> None:
        default_path = Path(Settings.macro_save_path.get())
        default_path.mkdir(parents=True, exist_ok=True)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Save Macros"),
            str(default_path),
            tr("Macro Files (*.json);;All Files (*)"),
        )
        if file_path:
            path = Path(file_path)
            if not path.suffix:
                path = path.with_name(path.name + ".json")
            serialized_macros = [macro.serialize() for macro in self._model.macros]
            with path.open("w") as f:
                json.dump(serialized_macros, f, indent=4)
            MsgBar.info(
                tr("Macros saved"),
                tr("File saved to {}", str(path)),
                success=True,
            )

    def _update_ui_state(self, *args: Any) -> None:  # noqa: ARG002
        """Update button enabled/checked states to reflect current status."""
        self.button_record.setChecked(self._recorder.is_recording())
        self.button_save.setEnabled(bool(self._model.macros))

        self.button_play.setEnabled(len(self.table_view.selectedIndexes()) == 1)
        self.button_delete.setEnabled(bool(self.table_view.selectedIndexes()))

        workflow_index = self._selected_workflow_index()
        workflow = self._workflow_model.workflow_for_index(workflow_index)
        is_step = self._workflow_model.is_step(workflow_index)
        self.button_play_workflow.setEnabled(
            workflow is not None and bool(workflow.macro_uids)
        )
        self.button_delete_workflow_item.setEnabled(workflow is not None)
        self.button_add_step.setEnabled(workflow is not None)
        self.button_move_step_up.setEnabled(is_step and workflow_index.row() > 0)
        self.button_move_step_down.setEnabled(
            is_step
            and workflow is not None
            and workflow_index.row() < len(workflow.macro_uids) - 1
        )


class MacroToolFactory(QgsDevToolWidgetFactory):
    """Factory class for creating Macro tool widgets.

    This class is responsible for creating instances of MacroPanel
    within the QGIS development tool framework.
    """

    def __init__(self) -> None:
        """Initialize the factory with a name and icon."""
        super().__init__(tr("Macro dev tool"), QIcon(resources_path("icons/icon.svg")))

    def createWidget(self, parent: QWidget | None = None) -> MacroPanel:  # noqa: N802
        """Create a new MacroPanel instance."""
        autosave = Settings.autosave_macros.get()
        storage = MacroStorage(default_autosave_directory()) if autosave else None
        workflow_storage = (
            WorkflowStorage(default_workflow_directory()) if autosave else None
        )
        return MacroPanel(
            MacroRecorder(),
            MacroPlayer(Settings.speed.get()),
            storage,
            parent,
            workflow_storage,
        )
