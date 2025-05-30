#  Copyright (c) 2025 macro-qgis-plugin contributors.
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
from typing import Any, Optional

from qgis.core import QgsApplication
from qgis.gui import QgsDevToolWidget, QgsDevToolWidgetFactory
from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QHeaderView,
    QInputDialog,
    QTableView,
    QToolButton,
    QWidget,
)
from qgis_plugin_tools.tools.decorations import log_if_fails
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.tools.messages import MsgBar
from qgis_plugin_tools.tools.resources import load_ui_from_file

from macro_plugin.ui.macro_model import MacroTableModel
from macro_plugin.ui.settings_dialog import SettingsDialog
from qgis_macros.exceptions import MacroPluginError
from qgis_macros.macro import Macro
from qgis_macros.macro_player import (
    MacroPlaybackReport,
    MacroPlaybackStatus,
    MacroPlayer,
)
from qgis_macros.macro_recorder import MacroRecorder
from qgis_macros.settings import Settings

MACRO_GROUP = "Macro"

UI_CLASS: QWidget = load_ui_from_file(
    str(Path(__file__).parent.joinpath("macro_panel.ui"))
)


class MacroPanel(UI_CLASS, QgsDevToolWidget):  # type: ignore
    """
    A dev tool widget for macro recording, playing, and deletion.

    Provides a table view to display macros and buttons to record, play, and delete
    macros.
    """

    button_record: QToolButton
    button_play: QToolButton
    button_delete: QToolButton
    button_open: QToolButton
    button_save: QToolButton
    button_settings: QToolButton
    table_view: QTableView

    def __init__(
        self,
        macro_recorder: MacroRecorder,
        macro_player: MacroPlayer,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        :param macro_recorder: Instance of MacroRecorder to handle macro
            recording interactions.
        :param macro_player: Instance of MacroPlayer to handle macro
            playback functionality.
        :param parent: Optional parent QWidget for UI hierarchy.
        """
        super().__init__(parent)
        self.setupUi(self)
        self._recorder = macro_recorder
        self._recorder.add_widget_to_filter_events_out(self)
        self._recorder.add_widget_to_filter_events_out(self.button_record)

        self._player = macro_player
        self._player.playback_ended.connect(self._macro_playback_ended)

        self._model = MacroTableModel()

        self._configure_table()
        self._configure_buttons()
        self._update_ui_state()

    def _configure_table(self) -> None:
        """
        Set up the table view with appropriate settings.
        """
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_view.setModel(self._model)
        self.table_view.selectionModel().selectionChanged.connect(self._update_ui_state)

    def _configure_buttons(self) -> None:
        """
        Configures the buttons with icons, tooltips, and connect them to their actions.
        """
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
        }

        for button, (action, icon) in button_config.items():
            button.setAutoRaise(True)
            button.setIcon(QgsApplication.getThemeIcon(icon))
            button.clicked.connect(action)

    def _validate_macro_selection(self) -> bool:
        """Check if there are selected macros available for operations."""
        return bool(self._model.macros and self.table_view.selectedIndexes())

    def _toggle_recording(self) -> None:
        if not self._recorder.is_recording():
            self._recorder.start_recording()
        else:
            macro = self._recorder.stop_recording()

            name, ok = QInputDialog.getText(
                self, tr("Macro Name"), tr("Enter the name of the macro:")
            )
            if ok:
                macro.name = name
                self._model.add_macro(macro)
        self._update_ui_state()

    def _play_macro(self) -> None:
        if not self._validate_macro_selection():
            return

        macro = self._model.macros[self.table_view.selectedIndexes()[0].row()]
        if Settings.profile_macros.get():
            QgsApplication.profiler().start(
                f"Macro: {macro.name}", Settings.profile_macro_group.get()
            )

        self._player.play(macro)

    @log_if_fails
    def _macro_playback_ended(self, macro_report: MacroPlaybackReport) -> None:
        if Settings.profile_macros.get():
            QgsApplication.profiler().end(Settings.profile_macro_group.get())
        if macro_report.status == MacroPlaybackStatus.FAILURE:
            raise macro_report.error or MacroPluginError(
                tr("Playback ended with failure.")
            )
        MsgBar.info(
            tr("Macro playback ended"), tr("Macro playback ended successfully.")
        )

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
            tr("Profiler Files (*.json);;All Files (*)"),
        )
        if file_path:
            with Path(file_path).open("r") as path:
                data = json.load(path)
                macros = [Macro.deserialize(macro_data) for macro_data in data]
                self._model.reset_macros(macros)

    def _save_macros_to_file(self) -> None:
        default_path = Path(Settings.macro_save_path.get())
        default_path.mkdir(parents=True, exist_ok=True)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Save Macros"),
            str(default_path),
            tr("Profiler Files (*.json);;All Files (*)"),
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

    def _update_ui_state(self, *args: Any) -> None:
        """
        Updates the state of the UI components based on the current status.
        """
        self.button_record.setChecked(self._recorder.is_recording())
        self.button_play.setEnabled(len(self.table_view.selectedIndexes()) == 1)
        self.button_save.setEnabled(bool(self._model.macros))
        self.button_delete.setEnabled(bool(self.table_view.selectedIndexes()))


class MacroToolFactory(QgsDevToolWidgetFactory):
    """
    Factory class for creating Macro tool widgets.

    This class is responsible for creating instances of MacroPanel
    within the QGIS development tool framework.
    """

    def __init__(self) -> None:
        super().__init__(
            tr("Macro dev tool"),
            QgsApplication.getThemeIcon("/mActionRecord.svg"),
        )

    def createWidget(self, parent: Optional[QWidget] = None) -> MacroPanel:  # noqa: N802
        return MacroPanel(MacroRecorder(), MacroPlayer(Settings.speed.get()), parent)
