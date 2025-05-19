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
from typing import TYPE_CHECKING, Optional

from qgis_plugin_tools.tools.exceptions import QgsPluginException
from qgis_plugin_tools.tools.i18n import tr

if TYPE_CHECKING:
    from qgis.PyQt.QtWidgets import QWidget


class MacroPluginError(QgsPluginException):
    """Base class for exceptions in this module."""


class WidgetNotFoundError(MacroPluginError):
    """Exception raised when a widget is not found."""

    def __init__(
        self, widget: Optional[type["QWidget"]] = None, text: str = ""
    ) -> None:
        widget_text = ""
        if widget:
            widget_text += f"{widget} - "
        widget_text += text

        super().__init__(tr("Widget {} not found.", widget_text))


class InvalidSettingValueError(MacroPluginError):
    def __init__(self, setting_name: str, setting_value: str) -> None:
        super().__init__(
            tr("Invalid value for {} setting: {}", setting_name, setting_value)
        )
