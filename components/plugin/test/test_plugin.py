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
from qgis.PyQt.QtCore import QObject, pyqtSignal

from macro_plugin import env
from macro_plugin import plugin as plugin_module
from macro_plugin.plugin import MacroPlugin

if TYPE_CHECKING:
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
