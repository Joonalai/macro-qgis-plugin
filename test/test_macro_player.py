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

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest

from macro_test_utils.utils import WidgetEventListener
from qgis_macros.exceptions import WidgetNotFoundError
from qgis_macros.macro import (
    Macro,
    WidgetSpec,
)
from qgis_macros.macro_player import MacroPlayer

WAIT_MS = 5

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from pytestqt.qtbot import QtBot

    from macro_test_utils.utils import Dialog

pytest_plugins = [
    "macro_test_utils.macro_fixture",
]


@pytest.fixture
def macro_player() -> MacroPlayer:
    return MacroPlayer()


@pytest.fixture
def widget_listener() -> Iterator[WidgetEventListener]:
    listener = WidgetEventListener()
    try:
        yield listener
    finally:
        listener.stop_listening()


def test_macro_player_should_click_button(
    button_click_macro: Macro,
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
):
    with qtbot.waitSignal(dialog.button.clicked, timeout=10):
        macro_player.play(button_click_macro)


def test_macro_player_should_raise_if_widget_not_found(
    button_click_macro: Macro,
    macro_player: MacroPlayer,
    dialog: "Dialog",
):
    # Arrange
    dialog.close()

    # Act and assert
    with pytest.raises(WidgetNotFoundError):
        macro_player.play(button_click_macro)


def test_macro_player_should_click_moved_button(
    button_click_macro: Macro,
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
    mocker: "MockerFixture",
):
    # Arrange
    initial_position = dialog.pos()
    # Move the dialog slightly. The correct button should still be found
    dialog.move(initial_position.x(), initial_position.y() - 50)
    spy_get_suitable_widget = mocker.spy(WidgetSpec, "get_suitable_widget")

    # Act and assert
    with qtbot.waitSignal(dialog.button.clicked, timeout=10):
        macro_player.play(button_click_macro)

    assert spy_get_suitable_widget.call_count == 2


def test_macro_player_play_button_double_click_macro(
    button_double_click_macro: Macro,
    macro_player: MacroPlayer,
    dialog: "Dialog",
    widget_listener: WidgetEventListener,
    qtbot: "QtBot",
):
    # Arrange
    widget_listener.start_listening(dialog.button)

    # Act and assert
    with qtbot.waitSignal(widget_listener.double_clicked, timeout=10):
        macro_player.play(button_double_click_macro)


def test_macro_player_play_line_edit_macro(
    line_edit_macro: Macro,
    macro_player: MacroPlayer,
    dialog: "Dialog",
    widget_listener: WidgetEventListener,
    qtbot: "QtBot",
):
    with qtbot.waitSignal(dialog.line_edit.textEdited, timeout=10):
        macro_player.play(line_edit_macro)
    assert dialog.line_edit.text() == "a"
