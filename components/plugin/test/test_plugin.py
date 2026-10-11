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

from typing import TYPE_CHECKING

import pytest
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis_macros.macro import Macro
from qgis_macros.macro_workflow import MacroWorkflow
from qgis_macros.settings import Settings
from qgis_plugin_tools.utils.typing_utils import require

from macro_plugin import env
from macro_plugin import plugin as plugin_module
from macro_plugin.macro_storage import MacroStorage, WorkflowStorage
from macro_plugin.plugin import MacroPlugin
from macro_plugin.processing_provider import (
    MACRO_PROVIDER_ID,
    WORKFLOW_PROVIDER_ID,
)
from macro_plugin.ui import macro_panel as macro_panel_module

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture


class StubIfaceSignals(QObject):
    initializationCompleted = pyqtSignal()  # noqa: N815


@pytest.fixture(autouse=True)
def _disable_development_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(env.IS_DEVELOPMENT_MODE.key, raising=False)


@pytest.fixture
def iface_signals() -> StubIfaceSignals:
    return StubIfaceSignals()


@pytest.fixture
def mock_iface(mocker: "MockerFixture", iface_signals: StubIfaceSignals) -> "MagicMock":
    mock_iface = mocker.patch.object(plugin_module, "iface")
    mock_iface.initializationCompleted = iface_signals.initializationCompleted
    return mock_iface


def test_macro_panel_is_not_registered_before_qgis_initialization_completes(
    mock_iface: "MagicMock",
) -> None:
    # Arrange
    plugin = MacroPlugin()

    # Act
    plugin.initGui()

    # Assert
    mock_iface.registerDevToolWidgetFactory.assert_not_called()
    plugin.unload()


def test_macro_panel_is_registered_after_qgis_initialization_completes(
    mock_iface: "MagicMock",
    iface_signals: StubIfaceSignals,
) -> None:
    # Arrange
    plugin = MacroPlugin()
    plugin.initGui()

    # Act
    iface_signals.initializationCompleted.emit()

    # Assert
    mock_iface.registerDevToolWidgetFactory.assert_called_once()
    plugin.unload()
    mock_iface.unregisterDevToolWidgetFactory.assert_called_once()


def test_macro_panel_is_registered_immediately_in_development_mode(
    monkeypatch: pytest.MonkeyPatch,
    mock_iface: "MagicMock",
) -> None:
    # Arrange
    # Plugin reloads do not emit initializationCompleted again
    monkeypatch.setenv(env.IS_DEVELOPMENT_MODE.key, "1")
    plugin = MacroPlugin()

    # Act
    plugin.initGui()

    # Assert
    mock_iface.registerDevToolWidgetFactory.assert_called_once()
    plugin.unload()


@pytest.fixture
def storage(mocker: "MockerFixture", tmp_path: "Path") -> MacroStorage:
    """Autosave storage in a temporary directory, used by the plugin and panel."""
    mocker.patch.object(Settings.autosave_macros, "get", return_value=True)
    storage = MacroStorage(tmp_path / "autosave")
    workflow_directory = tmp_path / "workflows"
    for module in (plugin_module, macro_panel_module):
        mocker.patch.object(
            module, "default_autosave_directory", return_value=storage.directory
        )
        mocker.patch.object(
            module, "default_workflow_directory", return_value=workflow_directory
        )
    return storage


def test_processing_providers_are_registered_between_init_and_unload(
    mock_iface: "MagicMock",
    storage: MacroStorage,
) -> None:
    registry = require(QgsApplication.processingRegistry())
    plugin = MacroPlugin()

    plugin.initGui()

    assert registry.providerById(MACRO_PROVIDER_ID) is plugin._macro_provider
    assert registry.providerById(WORKFLOW_PROVIDER_ID) is plugin._workflow_provider

    plugin.unload()

    assert registry.providerById(MACRO_PROVIDER_ID) is None
    assert registry.providerById(WORKFLOW_PROVIDER_ID) is None


def test_processing_providers_load_autosaved_macros_without_the_panel(
    mock_iface: "MagicMock",
    storage: MacroStorage,
    tmp_path: "Path",
) -> None:
    macro = Macro(events=[], name="autosaved")
    storage.save_macro(macro)
    workflow = MacroWorkflow("stored workflow", [macro.uid])
    WorkflowStorage(tmp_path / "workflows").save_workflow(workflow)
    plugin = MacroPlugin()

    plugin.initGui()

    mock_iface.registerDevToolWidgetFactory.assert_not_called()
    assert [alg.name() for alg in plugin._macro_provider.algorithms()] == [macro.uid]
    workflow_algorithms = plugin._workflow_provider.algorithms()
    assert [alg.displayName() for alg in workflow_algorithms] == ["stored workflow"]
    assert "autosaved" in workflow_algorithms[0].shortHelpString()
    plugin.unload()


def test_macro_panel_registers_loaded_macros_as_algorithms(
    mock_iface: "MagicMock",
    iface_signals: StubIfaceSignals,
    storage: MacroStorage,
) -> None:
    plugin = MacroPlugin()
    plugin.initGui()
    # Saved after the providers loaded the autosaved macros
    storage.save_macro(Macro(events=[], name="autosaved"))
    # The dev tools dock creates the panel when the factory is registered
    mock_iface.registerDevToolWidgetFactory.side_effect = lambda factory: (
        factory.createWidget()
    )

    iface_signals.initializationCompleted.emit()

    algorithms = plugin._macro_provider.algorithms()
    assert [alg.displayName() for alg in algorithms] == ["autosaved"]
    plugin.unload()


def test_startup_macros_are_requested_on_plugin_load(
    mocker: "MockerFixture",
    mock_iface: "MagicMock",
) -> None:
    # Arrange
    mock_play = mocker.patch.object(plugin_module.startup, "play_from_environment")
    plugin = MacroPlugin()

    # Act
    plugin.initGui()

    # Assert
    mock_play.assert_called_once_with()
    plugin.unload()
