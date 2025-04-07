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

from typing import TYPE_CHECKING, cast

import qgis_plugin_tools
from qgis.PyQt.QtCore import QObject
from qgis.utils import iface as iface_
from qgis_plugin_tools.tools.custom_logging import (
    setup_loggers,
)
from qgis_plugin_tools.tools.i18n import tr

import macro_plugin
import qgis_macros
from macro_plugin.ui.macro_panel import MacroToolFactory

if TYPE_CHECKING:
    from qgis.gui import QgisInterface

iface = cast("QgisInterface", iface_)


class MacroPlugin(QObject):
    name = tr("Macros")

    def __init__(self) -> None:
        super().__init__(parent=None)
        self._teardown_loggers = lambda: None
        self._macro_factory = MacroToolFactory()

    def initGui(self) -> None:  # noqa: N802
        self._teardown_loggers = setup_loggers(
            qgis_macros.__name__,
            macro_plugin.__name__,
            qgis_plugin_tools.__name__,
            message_log_name=self.name,
        )

        # Register the macro panel via factory
        iface.registerDevToolWidgetFactory(self._macro_factory)

    def unload(self) -> None:
        self._teardown_loggers()
        self._teardown_loggers = lambda: None
        iface.unregisterDevToolWidgetFactory(self._macro_factory)
