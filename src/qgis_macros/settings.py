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
import enum
import logging
from dataclasses import dataclass
from typing import Any, Optional, Union

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.tools.resources import profile_path
from qgis_plugin_tools.tools.settings import (
    get_setting,
    set_setting,
)

from qgis_macros.exceptions import InvalidSettingValueError

LOGGER = logging.getLogger(__name__)

"""
This module is heavily inspired with profiler-qgis-plugin
licensed under GPLv3.
"""
# TODO: move to a common library


class WidgetType(enum.Enum):
    LINE_EDIT = "line_edit"
    CHECKBOX = "checkbox"
    SPIN_BOX = "spin_box"


class SettingCategory(enum.Enum):
    MACRO = tr("Macro")


@dataclass
class WidgetConfig:
    """Configuration options for different widget types."""

    minimum: Optional[Union[int, float]] = None
    maximum: Optional[Union[int, float]] = None
    step: Optional[Union[int, float]] = None


@dataclass
class Setting(QObject):
    description: str
    default: Any
    category: SettingCategory = SettingCategory.MACRO
    widget_config: Optional[WidgetConfig] = None
    widget_type: Optional[WidgetType] = None
    changed = pyqtSignal()

    def __post_init__(self) -> None:
        """Deduces the widget type based on the default value's type."""
        super().__init__()
        if isinstance(self.default, bool):
            self.widget_type = WidgetType.CHECKBOX
        elif isinstance(self.default, (int, float)):
            self.widget_type = WidgetType.SPIN_BOX
            # Provide default widget configuration for numeric inputs if not set
            if self.widget_config is None:
                self.widget_config = WidgetConfig(
                    minimum=0,
                    maximum=100,
                    step=1 if isinstance(self.default, int) else 0.1,
                )
        elif isinstance(self.default, str):
            self.widget_type = WidgetType.LINE_EDIT
        else:
            raise NotImplementedError


class Settings(enum.Enum):
    speed = Setting(
        description=tr("Macro playback speed"),
        default=1.0,
        widget_config=WidgetConfig(minimum=0.0, maximum=100.0, step=0.1),
    )
    profile_macros = Setting(
        description=tr("Profile macro runtime"),
        default=False,
    )
    profile_macro_group = Setting(
        description=tr("Group name for macro profiles"),
        default="Macro",
    )
    macro_save_path = Setting(
        description=tr("Default save path for macros."),
        default=profile_path("macros"),
    )
    move_event_interpolation_count = Setting(
        description=tr(
            "How many points mouse move events should have. "
            "If point count is higher, "
            "points are interpolated along the line."
        ),
        default=4,
        widget_config=WidgetConfig(minimum=2, maximum=10000),
    )

    @staticmethod
    def reset() -> None:
        """
        Resets the state of the application or relevant subsystem to its initial default
        state.
        """
        for setting in Settings:
            setting.set(setting.value.default)

    def get(self) -> Any:
        """Gets the setting value."""
        setting = self.value
        value = get_setting(self.name, setting.default)
        if not isinstance(value, type(setting.default)):
            if isinstance(self.value.default, bool) and isinstance(value, str):
                value = value.lower() == "true"
            else:
                value = type(setting.default)(value)
        return value

    def set(self, value: Any) -> None:
        """Sets the setting value."""
        if not isinstance(value, type(self.value.default)):
            if isinstance(self.value.default, bool):
                value = bool(value)
            else:
                raise InvalidSettingValueError(self.name, value)
        set_setting(self.name, value)
        self.value.changed.emit()
