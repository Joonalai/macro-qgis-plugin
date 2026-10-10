#  Copyright (c) 2026 macro-qgis-plugin contributors.
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
"""Settings dialog for configuring macro plugin options and logging levels."""

import logging
from pathlib import Path

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
from qgis_macros.settings import (
    SettingCategory,
    Settings,
    WidgetConfig,
    WidgetType,
)
from qgis_plugin_tools.tools.custom_logging import (
    LogTarget,
    get_log_level_key,
    get_log_level_name,
)
from qgis_plugin_tools.tools.resources import load_ui_from_file
from qgis_plugin_tools.tools.settings import set_setting
from qgis_plugin_tools.utils.typing_utils import require

UI_CLASS: QWidget = load_ui_from_file(
    str(Path(__file__).parent.joinpath("settings_dialog.ui"))
)

LOGGER = logging.getLogger(__name__)
CALIBRATION_COEFFICIENT = 1.05

LOGGING_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class SettingsDialog(QDialog, UI_CLASS):  # type: ignore
    """Dialog for editing plugin settings and logging levels.

    Originally adapted from https://github.com/nlsfi/pickLayer (GPL v3).
    """

    layout_setting_items: QVBoxLayout
    combo_box_log_level_file: QComboBox
    combo_box_log_level_console: QComboBox
    button_box: QDialogButtonBox

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the dialog and populate settings widgets."""
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowIcon(QgsApplication.getThemeIcon("/propertyicons/settings.svg"))
        self._widgets: dict[Settings, QWidget] = {}
        self._groups: dict[SettingCategory, QgsCollapsibleGroupBox] = {}

        self._setup_plugin_settings()
        self._setup_logging_settings()

        self.button_box.accepted.connect(self.close)
        reset_button = require(
            self.button_box.button(QDialogButtonBox.StandardButton.Reset)
        )
        reset_button.clicked.connect(self._reset_settings)

    def _setup_plugin_settings(self) -> None:
        for setting in Settings:
            self._add_setting(setting)

    def _reset_settings(self) -> None:
        # Clear all items from the settings layout
        while self.layout_setting_items.count():
            child = self.layout_setting_items.takeAt(0)
            widget = child.widget() if child is not None else None
            if widget is not None:
                widget.deleteLater()

        # Clear stored widgets and group boxes
        self._widgets.clear()
        self._groups.clear()

        # Reset settings and re-add them
        Settings.reset()
        for setting in Settings:
            self._add_setting(setting)

    def _add_setting(self, setting: Settings) -> None:
        """Add a widget to the appropriate group box based on the category."""
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
            widget = self._create_spin_box(setting_meta.default, widget_config)
            widget.setValue(setting.get())  # noqa: QGS202
            widget.valueChanged.connect(setting.set)
        else:
            raise NotImplementedError

        # Store widget and add it to the group layout
        self._widgets[setting] = widget
        group_layout.addRow(label, widget)

    @staticmethod
    def _create_spin_box(
        default: object, config: WidgetConfig | None
    ) -> QSpinBox | QDoubleSpinBox:
        """Create a spin box for an int default or a double spin box otherwise."""
        if isinstance(default, int):
            spin_box = QSpinBox()
            if config is not None:
                if config.minimum is not None:
                    spin_box.setMinimum(int(config.minimum))
                if config.maximum is not None:
                    spin_box.setMaximum(int(config.maximum))
                if config.step is not None:
                    spin_box.setSingleStep(int(config.step))
            return spin_box
        double_spin_box = QDoubleSpinBox()
        double_spin_box.setDecimals(3)
        if config is not None:
            if config.minimum is not None:
                double_spin_box.setMinimum(config.minimum)
            if config.maximum is not None:
                double_spin_box.setMaximum(config.maximum)
            if config.step is not None:
                double_spin_box.setSingleStep(config.step)
        return double_spin_box

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
