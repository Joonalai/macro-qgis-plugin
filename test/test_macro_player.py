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
from qgis.core import QgsFeature
from qgis.gui import QgsMapToolDigitizeFeature

from macro_test_utils.utils import WidgetEventListener
from qgis_macros.exceptions import WidgetNotFoundError
from qgis_macros.macro import (
    Macro,
    WidgetSpec,
)
from qgis_macros.macro_player import (
    MacroPlaybackReport,
    MacroPlaybackStatus,
    MacroPlayer,
)

TIMEOUT = 1000

WAIT_MS = 5

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from pytestqt.qtbot import QtBot

    from macro_test_utils.utils import Dialog

pytest_plugins = [
    "macro_test_utils.macro_fixture",
]


def _check_successfull(playback_report: MacroPlaybackReport):
    assert playback_report.status == MacroPlaybackStatus.SUCCESS
    return True


checkers = [_check_successfull, None]


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
    with qtbot.waitSignals(
        [macro_player.playback_ended, dialog.button.clicked],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(button_click_macro)


def test_macro_player_should_click_radio_button(
    radio_button_click_macro: Macro,
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
):
    assert not dialog.radio_button.isChecked()
    with qtbot.waitSignals(
        [macro_player.playback_ended, dialog.radio_button.clicked],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(radio_button_click_macro)
    assert dialog.radio_button.isChecked()


def test_macro_player_should_click_check_button(
    check_box_click_macro: Macro,
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
):
    assert not dialog.check_box.isChecked()
    with qtbot.waitSignals(
        [macro_player.playback_ended, dialog.check_box.clicked],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(check_box_click_macro)
    assert dialog.check_box.isChecked()


def test_macro_player_should_raise_if_widget_not_found(
    button_click_macro: Macro,
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
):
    # Arrange
    dialog.close()

    # Act and assert
    with qtbot.waitSignal(macro_player.playback_ended, timeout=TIMEOUT) as blocker:
        macro_player.play(button_click_macro)

    report = blocker.args[0]
    assert report.status == MacroPlaybackStatus.FAILURE
    assert isinstance(report.error, WidgetNotFoundError)


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
    with qtbot.waitSignals(
        [macro_player.playback_ended, dialog.button.clicked],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(button_click_macro)

    assert spy_get_suitable_widget.call_count == 3


def test_macro_player_should_menu_action(
    menu_action_click_macro: Macro,
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
):
    with qtbot.waitSignals(
        [macro_player.playback_ended, dialog.action2.triggered],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(menu_action_click_macro)


def test_macro_player_should_click_list_widget_item(
    list_view_item_click_macro: Macro,
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
):
    assert dialog.list_widget.selectedItems() == []
    with qtbot.waitSignals(
        [macro_player.playback_ended, dialog.list_widget.clicked],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(list_view_item_click_macro)
    assert dialog.list_widget.selectedItems() == [dialog.list_widget.item(1)]


def test_macro_player_should_click_combobox_item(
    combobox_item_click_macro: Macro,
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
):
    assert dialog.combobox.currentIndex() == 0
    with qtbot.waitSignals(
        [macro_player.playback_ended, dialog.combobox.currentIndexChanged],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(combobox_item_click_macro)
    assert dialog.combobox.currentIndex() == 1


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
    with qtbot.waitSignals(
        [macro_player.playback_ended, widget_listener.double_clicked],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(button_double_click_macro)


def test_macro_player_play_line_edit_macro(
    line_edit_macro: Macro,
    macro_player: MacroPlayer,
    dialog: "Dialog",
    widget_listener: WidgetEventListener,
    qtbot: "QtBot",
):
    with qtbot.waitSignals(
        [macro_player.playback_ended, dialog.line_edit.textEdited],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(line_edit_macro)
    assert dialog.line_edit.text() == "a"


@pytest.mark.skip("Causes segmentation faults in CI")
@pytest.mark.usefixtures("digitize_feature_map_tool", "empty_layer")
@pytest.mark.qgis_show_map(timeout=0)
def test_macro_recorder_should_record_digitizing_polygon(
    macro_player: MacroPlayer,
    digitize_polygon_macro: Macro,
    qtbot: "QtBot",
    digitize_feature_map_tool: QgsMapToolDigitizeFeature,
):
    with qtbot.waitSignal(digitize_feature_map_tool.digitizingCompleted) as blocker:
        macro_player.play(digitize_polygon_macro)
    feature = blocker.args[0]
    assert isinstance(feature, QgsFeature)
    assert feature.isValid()
    # Asserting geometry causes segfault
    # assert feature.geometry()
