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

"""Main QGIS plugin class that registers the macro dev tool."""

import logging
from typing import TYPE_CHECKING, cast

import qgis_macros
import qgis_plugin_tools
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QObject
from qgis.utils import iface as iface_
from qgis_macros.settings import Settings
from qgis_plugin_tools.tools.custom_logging import (
    setup_loggers,
)
from qgis_plugin_tools.tools.i18n import tr

import macro_plugin
from macro_plugin import env, startup
from macro_plugin.macro_storage import (
    MacroStorage,
    WorkflowStorage,
    default_autosave_directory,
    default_workflow_directory,
)
from macro_plugin.processing_provider import (
    MacroProcessingProvider,
    MacroWorkflowProcessingProvider,
)
from macro_plugin.ui.macro_panel import MacroToolFactory

if TYPE_CHECKING:
    from qgis.gui import QgisInterface

iface = cast("QgisInterface", iface_)
LOGGER = logging.getLogger(__name__)


class MacroPlugin(QObject):
    """QGIS plugin that provides macro recording and playback in dev tools."""

    name = tr("Macros")

    def __init__(self) -> None:
        """Initialize the plugin and create the macro tool factory."""
        super().__init__(parent=None)
        self._teardown_loggers = lambda: None
        self._macro_provider = MacroProcessingProvider()
        self._workflow_provider = MacroWorkflowProcessingProvider()
        self._macro_factory = MacroToolFactory(
            self._macro_provider, self._workflow_provider
        )

    def initGui(self) -> None:  # noqa: N802
        """Set up loggers, processing providers and the macro panel factory."""
        self._teardown_loggers = setup_loggers(
            qgis_macros.__name__,
            macro_plugin.__name__,
            qgis_plugin_tools.__name__,
            message_log_name=self.name,
        )
        self.initProcessing()
        startup.play_from_environment()

        if hasattr(iface, "initializationCompleted"):
            iface.initializationCompleted.connect(self.iface_initialization_completed)

        if bool(env.IS_DEVELOPMENT_MODE):
            self.iface_initialization_completed()

    def initProcessing(self) -> None:  # noqa: N802
        """Register the processing providers of macros and macro workflows.

        The providers start with the autosaved macros and workflows, so models
        using them work without the macro panel. The panel keeps them in sync
        with its macros once created.
        """
        registry = QgsApplication.processingRegistry()
        if registry is None:
            return
        if Settings.autosave_macros.get():
            macros = MacroStorage(default_autosave_directory()).load_macros()
            self._macro_provider.set_macros(macros)
            self._workflow_provider.set_workflows(
                WorkflowStorage(default_workflow_directory()).load_workflows(),
                {macro.uid: macro for macro in macros},
            )
        for provider in (self._macro_provider, self._workflow_provider):
            if not registry.addProvider(provider):
                LOGGER.warning(
                    "Could not register processing provider %s", provider.id()
                )

    def iface_initialization_completed(self) -> None:
        """Run additional setup for the plugin.

        Executed after initializationCompleted signal is emitted.
        """
        # Register the macro panel via factory
        iface.registerDevToolWidgetFactory(self._macro_factory)

    def unload(self) -> None:
        """Tear down loggers, the macro panel factory and processing providers."""
        self._teardown_loggers()
        self._teardown_loggers = lambda: None
        iface.unregisterDevToolWidgetFactory(self._macro_factory)
        registry = QgsApplication.processingRegistry()
        if registry is None:
            return
        for provider in (self._macro_provider, self._workflow_provider):
            if registry.providerById(provider.id()) is provider:
                registry.removeProvider(provider)
