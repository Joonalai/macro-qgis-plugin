#  Copyright (c) 2025 profiler-qgis-plugin contributors.
#
#
#  This file is part of profiler-qgis-plugin.
#
#  profiler-qgis-plugin is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  profiler-qgis-plugin is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty
#  of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with profiler-qgis-plugin. If not, see <https://www.gnu.org/licenses/>.
import logging
from pathlib import Path
from typing import Optional

from qgis.core import QgsApplication
from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from qgis_plugin_tools.tools.custom_logging import (
    LogTarget,
    get_log_level_key,
    get_log_level_name,
)
from qgis_plugin_tools.tools.resources import load_ui_from_file
from qgis_plugin_tools.tools.settings import set_setting

from qgis_macros.settings import SettingCategory, Settings, WidgetType

UI_CLASS: QWidget = load_ui_from_file(
    str(Path(__file__).parent.joinpath("settings_dialog.ui"))
)

LOGGER = logging.getLogger(__name__)
CALIBRATION_COEFFICIENT = 1.05

LOGGING_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class SettingsDialog(QDialog, UI_CLASS):  # type: ignore
    """
    This file is originally adapted from
    https://github.com/nlsfi/pickLayer licensed under GPL version 3
    """

    layout_setting_items: QVBoxLayout
    combo_box_log_level_file: QComboBox
    combo_box_log_level_console: QComboBox
    button_box: QDialogButtonBox

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowIcon(QgsApplication.getThemeIcon("/propertyicons/settings.svg"))
        self._widgets: dict[Settings, QWidget] = {}
        self._groups: dict[SettingCategory, QgsCollapsibleGroupBox] = {}

        self._setup_plugin_settings()
        self._setup_logging_settings()

        self.button_box.accepted.connect(self.close)
        self.button_box.button(QDialogButtonBox.Reset).clicked.connect(
            self._reset_settings
        )

    def _setup_plugin_settings(self) -> None:
        for setting in Settings:
            self._add_setting(setting)

    def _reset_settings(self) -> None:
        # Clear all items from the settings layout
        while self.layout_setting_items.count():
            child = self.layout_setting_items.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Clear stored widgets and group boxes
        self._widgets.clear()
        self._groups.clear()

        # Reset settings and re-add them
        Settings.reset()
        for setting in Settings:
            self._add_setting(setting)

    def _add_setting(self, setting: Settings) -> None:
        """Adds a widget to the appropriate group box based on the category."""
        setting_meta = setting.value
        widget_type = setting_meta.widget_type
        widget_config = setting_meta.widget_config
        category = setting_meta.category

        if category not in self._groups:
            group_box = QgsCollapsibleGroupBox(category.value)
            group_box.setLayout(QFormLayout())
            self._groups[category] = group_box
            self.layout_setting_items.addWidget(group_box)

        group_layout = self._groups[category].layout()

        label = QLabel(setting_meta.description)

        # Create the appropriate widget based on the widget type
        if widget_type == WidgetType.LINE_EDIT:
            widget = QLineEdit()
            widget.setText(setting.get())
            widget.textChanged.connect(setting.set)
        elif widget_type == WidgetType.CHECKBOX:
            widget = QCheckBox()
            widget.setChecked(setting.get())
            widget.stateChanged.connect(setting.set)
        elif widget_type == WidgetType.SPIN_BOX:
            if isinstance(setting_meta.default, int):
                widget = QSpinBox()
            else:
                widget = QDoubleSpinBox()
                widget.setDecimals(3)
            if widget_config:
                if widget_config.minimum is not None:
                    widget.setMinimum(widget_config.minimum)
                if widget_config.maximum is not None:
                    widget.setMaximum(widget_config.maximum)
                if widget_config.step is not None:
                    widget.setSingleStep(widget_config.step)
            widget.setValue(setting.get())
            widget.valueChanged.connect(setting.set)
        else:
            raise NotImplementedError

        # Store widget and add it to the group layout
        self._widgets[setting] = widget
        group_layout.addRow(label, widget)

    def _setup_logging_settings(self) -> None:
        self.combo_box_log_level_file.addItems(LOGGING_LEVELS)
        self.combo_box_log_level_console.addItems(LOGGING_LEVELS)
        self.combo_box_log_level_file.setCurrentText(get_log_level_name(LogTarget.FILE))
        self.combo_box_log_level_console.setCurrentText(
            get_log_level_name(LogTarget.STREAM)
        )
        self.combo_box_log_level_file.currentTextChanged.connect(
            lambda level: set_setting(get_log_level_key(LogTarget.FILE), level)
        )
        self.combo_box_log_level_console.currentTextChanged.connect(
            lambda level: set_setting(get_log_level_key(LogTarget.STREAM), level)
        )
