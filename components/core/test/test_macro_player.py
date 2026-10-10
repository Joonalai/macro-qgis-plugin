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

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import pytest
from macro_test_utils import macro_utils
from macro_test_utils.utils import WidgetEventListener, WidgetInfo
from qgis.core import Qgis, QgsFeature
from qgis.gui import QgsMapToolDigitizeFeature
from qgis.PyQt.QtCore import QPoint, Qt, QTimer
from qgis.PyQt.QtWidgets import QMenu
from qgis_macros.exceptions import MacroPlaybackEndedError
from qgis_macros.macro import (
    Macro,
    MacroEvent,
    MacroMenuActionEvent,
    MacroMouseMoveEvent,
    MacroWheelEvent,
    WidgetSpec,
)
from qgis_macros.macro_player import (
    MacroPlaybackReport,
    MacroPlaybackStatus,
    MacroPlayer,
)
from qgis_macros.utils import enum_value
from qgis_plugin_tools.utils.typing_utils import require

TIMEOUT = 1000

WAIT_MS = 5

if TYPE_CHECKING:
    from macro_test_utils.utils import Dialog
    from pytest_mock import MockerFixture
    from pytestqt.qtbot import QtBot
    from qgis.PyQt.QtGui import QAction

pytest_plugins = [
    "macro_test_utils.macro_fixture",
]


def _check_successfull(playback_report: MacroPlaybackReport):
    assert playback_report.status == MacroPlaybackStatus.SUCCESS
    return True


# pytest-qt accepts None as a callback, which its type hints do not allow
checkers: list[Any] = [_check_successfull, None]


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


@pytest.mark.parametrize(
    ("speed", "expected"),
    [(1.0, 1015), (2.0, 515), (0.5, 2015), (0.0, 10015)],
    ids=["normal", "faster", "slower", "zero_clamped"],
)
def test_macro_player_wait_time_should_scale_inversely_with_speed(
    speed: float, expected: int
):
    assert MacroPlayer(speed)._wait_time(1000) == expected


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
    assert isinstance(report.error, MacroPlaybackEndedError)


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


def test_macro_player_right_click_should_request_context_menu(
    dialog_widget_positions: dict[str, WidgetInfo],
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
):
    # Widgets such as the QGIS layer tree open their context menu from the
    # context menu event that Qt creates for a right click
    dialog.button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    macro = Macro(
        events=macro_utils.widget_clicking_macro_events(
            dialog_widget_positions["button"],
            button=enum_value(Qt.MouseButton.RightButton),
        )
    )

    with qtbot.waitSignals(
        [macro_player.playback_ended, dialog.button.customContextMenuRequested],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(macro)


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


@pytest.mark.parametrize(
    ("key", "modifier", "text"),
    [
        (Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier, "A"),
        (Qt.Key.Key_Adiaeresis, Qt.KeyboardModifier.NoModifier, "ä"),
        (Qt.Key.Key_Adiaeresis, Qt.KeyboardModifier.ShiftModifier, "Ä"),
        (Qt.Key.Key_4, Qt.KeyboardModifier.AltModifier, "€"),
    ],
    ids=["shift", "latin1", "latin1_shift", "non_latin1"],
)
def test_macro_player_play_line_edit_macro_with_text(
    line_edit_click_macro_event: list[MacroEvent],
    dialog_widget_positions: dict[str, WidgetInfo],
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
    key: Qt.Key,
    modifier: Qt.KeyboardModifier,
    text: str,
):
    macro = Macro(
        events=[
            *line_edit_click_macro_event,
            *macro_utils.key_macro_events(
                dialog_widget_positions["line_edit"],
                enum_value(key),
                modifiers=enum_value(modifier),
                text=text,
            ),
        ]
    )
    with qtbot.waitSignals(
        [macro_player.playback_ended, dialog.line_edit.textEdited],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(macro)
    assert dialog.line_edit.text() == text


def test_macro_player_play_mouse_move_with_button_held(
    dialog_widget_positions: dict[str, WidgetInfo],
    macro_player: MacroPlayer,
    dialog: "Dialog",
    widget_listener: WidgetEventListener,
    qtbot: "QtBot",
):
    # Arrange
    widget_listener.start_listening(dialog.button)
    macro = Macro(
        events=[
            macro_utils.mouse_move_macro_event(
                dialog_widget_positions["button"],
                buttons=enum_value(Qt.MouseButton.LeftButton),
            )
        ]
    )

    # Act and assert
    with qtbot.waitSignals(
        [macro_player.playback_ended, widget_listener.mouse_moved],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(macro)


def test_macro_player_play_wheel_event(
    dialog_widget_positions: dict[str, WidgetInfo],
    macro_player: MacroPlayer,
    dialog: "Dialog",
    widget_listener: WidgetEventListener,
    qtbot: "QtBot",
):
    # Arrange
    widget_listener.start_listening(dialog.button)
    button = dialog_widget_positions["button"]
    macro = Macro(
        events=[
            MacroWheelEvent(
                widget_spec=button.widget_spec,
                position=button.position,
                delta=120,
            )
        ]
    )

    # Act and assert
    with qtbot.waitSignals(
        [macro_player.playback_ended, widget_listener.wheeled],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(macro)


@pytest.mark.parametrize(
    "move_buttons",
    [Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton],
    ids=["no_button", "left_button_held"],
)
@pytest.mark.usefixtures("empty_layer")
@pytest.mark.qgis_show_map(timeout=0)
def test_macro_player_should_play_digitizing_polygon(
    macro_player: MacroPlayer,
    digitize_polygon_macro: Macro,
    qtbot: "QtBot",
    digitize_feature_map_tool: QgsMapToolDigitizeFeature,
    move_buttons: Qt.MouseButton,
):
    # Arrange
    for event in digitize_polygon_macro.events:
        if isinstance(event, MacroMouseMoveEvent):
            event.buttons = enum_value(move_buttons)
    # The signal argument is a temporary, so copy it while it is alive
    features: list[QgsFeature] = []
    digitize_feature_map_tool.digitizingCompleted.connect(
        lambda feature: features.append(QgsFeature(feature))
    )

    # Act
    with qtbot.waitSignals(
        [macro_player.playback_ended, digitize_feature_map_tool.digitizingCompleted],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(digitize_polygon_macro)

    # Assert
    assert len(features) == 1
    assert features[0].isValid()
    assert features[0].geometry().wkbType() == Qgis.WkbType.Polygon


@pytest.fixture
def styles_menu(dialog: "Dialog") -> "Iterator[tuple[QMenu, QAction]]":
    menu = QMenu(dialog)
    menu.addAction("Zoom to Layer")
    menu.addSeparator()
    styles = require(menu.addMenu("&Styles"))
    styles.addAction("slow")
    fast = require(styles.addAction("fast"))
    yield menu, fast
    menu.close()


def _menu_action_macro(*action_path: str) -> Macro:
    return Macro(
        events=[
            MacroMenuActionEvent(WidgetSpec("QMenu"), action_path=list(action_path))
        ]
    )


def test_macro_player_should_activate_submenu_item(
    styles_menu: "tuple[QMenu, QAction]",
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
):
    menu, fast = styles_menu
    menu.popup(dialog.mapToGlobal(QPoint(10, 10)))
    qtbot.waitExposed(menu)

    with qtbot.waitSignals(
        [macro_player.playback_ended, fast.triggered],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(_menu_action_macro("Styles", "fast"))

    assert not menu.isVisible()


def test_macro_player_menu_exec_should_return_activated_item(
    styles_menu: "tuple[QMenu, QAction]",
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
):
    menu, fast = styles_menu
    QTimer.singleShot(
        0, lambda: macro_player.play(_menu_action_macro("Styles", "fast"))
    )

    with qtbot.waitSignal(macro_player.playback_ended, timeout=TIMEOUT):
        result = menu.exec(dialog.mapToGlobal(QPoint(10, 10)))

    assert result is fast


def test_macro_player_should_activate_context_menu_item(
    styles_menu: "tuple[QMenu, QAction]",
    dialog_widget_positions: dict[str, WidgetInfo],
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
):
    # Like the QGIS layer tree, open a context menu with QMenu.exec
    menu, fast = styles_menu
    dialog.button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    dialog.button.customContextMenuRequested.connect(
        lambda point: menu.exec(dialog.button.mapToGlobal(point))
    )
    macro = Macro(
        events=[
            *macro_utils.widget_clicking_macro_events(
                dialog_widget_positions["button"],
                button=enum_value(Qt.MouseButton.RightButton),
            ),
            *_menu_action_macro("Styles", "fast").events,
        ]
    )

    with qtbot.waitSignals(
        [macro_player.playback_ended, fast.triggered],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(macro)


@pytest.mark.parametrize(
    "action_path",
    [["Styles", "missing"], ["missing"], ["Styles"], ["Zoom to Layer", "fast"]],
    ids=["missing_item", "missing_root", "submenu", "not_a_submenu"],
)
def test_macro_player_should_fail_if_menu_item_not_found(
    styles_menu: "tuple[QMenu, QAction]",
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
    action_path: list[str],
):
    menu, fast = styles_menu
    triggered: list[bool] = []
    fast.triggered.connect(triggered.append)
    menu.popup(dialog.mapToGlobal(QPoint(10, 10)))
    qtbot.waitExposed(menu)

    with qtbot.waitSignal(macro_player.playback_ended, timeout=TIMEOUT) as blocker:
        macro_player.play(_menu_action_macro(*action_path))

    report = blocker.args[0]
    assert report.status == MacroPlaybackStatus.FAILURE
    assert isinstance(report.error, MacroPlaybackEndedError)
    assert not triggered
