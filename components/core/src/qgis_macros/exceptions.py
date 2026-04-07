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

"""Custom exception classes for macro plugin error handling."""

from qgis_plugin_tools.tools.custom_logging import bar_msg
from qgis_plugin_tools.tools.exceptions import QgsPluginException
from qgis_plugin_tools.tools.i18n import tr


class MacroPluginError(QgsPluginException):
    """Base class for exceptions in this module."""


class WidgetNotFoundError(MacroPluginError):
    """Exception raised when a widget is not found."""

    def __init__(self, widget_class: str = "", text: str = "") -> None:
        """Initialize with optional widget class name and text identifier."""
        widget_text = ""
        if widget_class:
            widget_text += f"{widget_class} - "
        widget_text += text

        super().__init__(
            tr("Widget {} not found.", widget_text),
        )


class MacroPlaybackEndedError(MacroPluginError):
    """Raised when macro playback ends due to an error."""

    def __init__(self, e: Exception) -> None:
        """Initialize with the underlying exception."""
        super().__init__(tr("Macro playback ended"), bar_msg(details=str(e)))


class InvalidSettingValueError(MacroPluginError):
    """Raised when a setting receives an invalid value."""

    def __init__(self, setting_name: str, setting_value: str) -> None:
        """Initialize with the setting name and invalid value."""
        super().__init__(
            tr("Invalid value for {} setting: {}", setting_name, setting_value)
        )
