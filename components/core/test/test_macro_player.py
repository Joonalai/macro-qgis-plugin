#  Copyright (c) 2025-2026 macro-qgis-plugin contributors.
#
#
#  This file is part of macro-qgis-plugin.
#
#  macro-qgis-plugin is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as published
#  by the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  macro-qgis-plugin is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied warranty
#  of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with macro-qgis-plugin. If not, see <https://www.gnu.org/licenses/>.

import itertools
import math
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from macro_test_utils import macro_utils
from macro_test_utils.utils import WidgetEventListener, WidgetInfo
from qgis.core import Qgis, QgsFeature
from qgis.gui import QgsMapToolDigitizeFeature
from qgis.PyQt.QtCore import QPoint, QRect, QSize, Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QLineEdit,
    QMenu,
    QVBoxLayout,
)
from qgis_macros import widget_lookup
from qgis_macros.exceptions import MacroPlaybackEndedError
from qgis_macros.macro import (
    BaseMacroEvent,
    Macro,
    MacroEvent,
    MacroMenuActionEvent,
    MacroMouseEvent,
    MacroMouseMoveEvent,
    MacroWheelEvent,
    Position,
    WidgetSpec,
)
from qgis_macros.macro_player import (
    SMOOTH_STEP_MS,
    SMOOTH_STEP_PX,
    MacroPlaybackReport,
    MacroPlaybackStatus,
    MacroPlayer,
)
from qgis_macros.settings import Settings
from qgis_macros.utils import enum_value
from qgis_plugin_tools.utils.typing_utils import require

TIMEOUT = 1000

WAIT_MS = 5

if TYPE_CHECKING:
    from macro_test_utils.utils import Dialog
    from pytest_mock import MockerFixture
    from pytestqt.qtbot import QtBot
    from qgis.gui import QgsMapCanvas
    from qgis.PyQt.QtGui import QAction
    from qgis.PyQt.QtWidgets import QWidget

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


def test_macro_player_stop_should_end_playback_without_playing_remaining_events(
    button_click_macro: Macro,
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
):
    assert not macro_player.is_playing()

    with (
        qtbot.assertNotEmitted(dialog.button.clicked, wait=100),
        qtbot.waitSignal(macro_player.playback_ended, timeout=TIMEOUT) as blocker,
    ):
        macro_player.play(button_click_macro)
        assert macro_player.is_playing()
        macro_player.stop()

    assert blocker.args[0].status == MacroPlaybackStatus.STOPPED
    assert not macro_player.is_playing()


@dataclass
class _RecordingEvent:
    """Event that records its action, optionally running *before* first."""

    name: str
    actions: list[str]
    ms_since_last_event: int = 0
    before: Callable[[], None] | None = None

    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        if self.before is not None:
            self.before()
        schedule_next()
        self.actions.append(self.name)


def test_macro_player_should_wait_for_playbacks_started_by_its_events(
    macro_player: MacroPlayer,
    qtbot: "QtBot",
):
    # E.g. a click on the run button of a processing algorithm plays a workflow
    actions: list[str] = []
    inner_player = MacroPlayer()
    inner = Macro(
        events=[
            _RecordingEvent("b1", actions, ms_since_last_event=300),
            _RecordingEvent("b2", actions),
        ]
    )
    outer = Macro(
        events=[
            _RecordingEvent("start", actions, before=lambda: inner_player.play(inner)),
            _RecordingEvent("end", actions),
        ]
    )

    with qtbot.waitSignal(macro_player.playback_ended, timeout=TIMEOUT):
        macro_player.play(outer)

    assert actions == ["b1", "start", "b2", "end"]


def test_macro_player_should_not_play_events_scheduled_before_stop(
    macro_player: MacroPlayer,
    qtbot: "QtBot",
):
    actions: list[str] = []
    first = Macro(
        events=[_RecordingEvent("a1", actions), _RecordingEvent("a2", actions)]
    )
    second = Macro(
        events=[
            # The player waits the delay of an event before playing it
            _RecordingEvent("b1", actions),
            _RecordingEvent("b2", actions, ms_since_last_event=300),
        ]
    )

    # Waits past the STOPPED report of the first playback
    with qtbot.waitSignal(
        macro_player.playback_ended,
        timeout=TIMEOUT,
        check_params_cb=lambda report: report.status == MacroPlaybackStatus.SUCCESS,
    ):
        macro_player.play(first)
        macro_player.stop()
        macro_player.play(second)
        # The event scheduled by the stopped playback would play b2 now
        qtbot.wait(100)
        assert actions == ["a1", "b1"]

    assert actions == ["a1", "b1", "b2"]


def test_macro_player_should_skip_action_of_event_when_stopped_during_it(
    macro_player: MacroPlayer,
    qtbot: "QtBot",
):
    actions: list[str] = []
    macro = Macro(
        events=[
            _RecordingEvent("first", actions),
            _RecordingEvent("second", actions, before=macro_player.stop),
        ]
    )

    with qtbot.waitSignal(macro_player.playback_ended, timeout=TIMEOUT) as blocker:
        macro_player.play(macro)

    assert blocker.args[0].status == MacroPlaybackStatus.STOPPED
    qtbot.wait(50)
    assert actions == ["first"]


def test_macro_player_wait_time_should_scale_with_macro_speed(
    macro_player: MacroPlayer,
    qtbot: "QtBot",
):
    with qtbot.waitSignal(macro_player.playback_ended, timeout=TIMEOUT):
        macro_player.play(Macro([], speed=2.0))

    assert macro_player._wait_time(1000) == 500 + 15
    macro_player.set_speed(2.0)
    assert macro_player._wait_time(1000) == 250 + 15


def test_smooth_steps_follow_the_path_a_few_pixels_apart():
    event = MacroMouseMoveEvent(
        widget_spec=WidgetSpec("QWidget", ""),
        ms_since_last_event=300,
        positions=[Position((0, 0), (100, 100)), Position((60, 0), (160, 100))],
    )

    steps = MacroPlayer._smooth_steps(event)

    assert len(steps) == 1 + math.ceil(60 / SMOOTH_STEP_PX)
    assert all(len(step.positions) == 1 for step in steps)
    assert steps[0].positions == [event.positions[0]]
    assert steps[-1].positions == [event.positions[-1]]
    # The movement keeps its recorded delay before it starts
    assert steps[0].ms_since_last_event == 300
    assert [step.ms_since_last_event for step in steps[1:]] == [SMOOTH_STEP_MS] * (
        len(steps) - 1
    )
    xs = [step.positions[0].global_position[0] for step in steps]
    assert xs == sorted(xs)
    assert max(b - a for a, b in itertools.pairwise(xs)) <= SMOOTH_STEP_PX


@pytest.mark.parametrize(
    ("argument", "setting", "expected"),
    [(None, True, True), (None, False, False), (False, True, False)],
    ids=["setting on", "setting off", "argument overrides"],
)
def test_macro_player_smooth_mouse_movement_option(
    mocker: "MockerFixture",
    qtbot: "QtBot",
    argument: bool | None,
    setting: bool,
    expected: bool,
):
    mocker.patch.object(Settings.smooth_mouse_movement, "get", return_value=setting)
    player = MacroPlayer(smooth_mouse_movement=argument)

    with qtbot.waitSignal(player.playback_ended, timeout=TIMEOUT):
        player.play(Macro([]))

    assert player._smooth == expected


def test_macro_player_stop_should_do_nothing_if_not_playing(
    macro_player: MacroPlayer,
    qtbot: "QtBot",
):
    with qtbot.assertNotEmitted(macro_player.playback_ended):
        macro_player.stop()


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
    # Test the position based lookup, which is used when there is no widget path
    for event in button_click_macro.events:
        if isinstance(event, BaseMacroEvent):
            event.widget_path = None
    initial_position = dialog.pos()
    # Move the dialog slightly. The correct button should still be found
    dialog.move(initial_position.x(), initial_position.y() - 50)
    spy_nearest = mocker.spy(widget_lookup, "find_nearest_matching_widget")

    # Act and assert
    with qtbot.waitSignals(
        [macro_player.playback_ended, dialog.button.clicked],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(button_click_macro)

    assert spy_nearest.call_count == len(button_click_macro.events)


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


@pytest.mark.parametrize("modal", [False, True], ids=["active_window", "modal_window"])
def test_macro_player_should_type_into_recorded_widget_when_other_window_is_active(
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qgis_parent: "QWidget",
    qtbot: "QtBot",
    modal: bool,
):
    # Arrange
    dialog.setWindowTitle("Macro dialog")
    other_window = QDialog(qgis_parent)
    other_window.setWindowTitle("Other window")
    if modal:
        other_window.setWindowModality(Qt.WindowModality.ApplicationModal)
    other_line_edit = QLineEdit(other_window)
    QVBoxLayout(other_window).addWidget(other_line_edit)
    other_window.move(dialog.x() + dialog.width() + 100, dialog.y())
    qtbot.addWidget(other_window)
    other_window.show()
    qtbot.waitExposed(other_window)
    other_window.activateWindow()
    other_line_edit.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() is other_line_edit)
    line_edit = WidgetInfo.from_widget("line_edit", dialog.line_edit)
    macro = Macro(
        events=[
            macro_utils.mouse_move_macro_event(line_edit),
            *macro_utils.widget_clicking_macro_events(line_edit),
            *macro_utils.key_macro_events(
                line_edit, enum_value(Qt.Key.Key_A), text="a"
            ),
        ]
    )

    # Act
    with qtbot.waitSignal(macro_player.playback_ended, timeout=TIMEOUT):
        macro_player.play(macro)

    # Assert
    assert dialog.line_edit.text() == "a"
    assert other_line_edit.text() == ""


@pytest.mark.parametrize("state", ["hidden", "disabled"])
def test_macro_player_should_type_into_focused_widget_if_recorded_is_unusable(
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
    state: str,
):
    # Arrange
    recorded = WidgetInfo.from_widget("line_edit", dialog.line_edit)
    other_line_edit = QLineEdit(dialog)
    other_line_edit.setObjectName("other_line_edit")
    require(dialog.layout()).addWidget(other_line_edit)
    other_line_edit.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() is other_line_edit)
    if state == "hidden":
        dialog.line_edit.hide()
    else:
        dialog.line_edit.setEnabled(False)
    macro = Macro(
        events=macro_utils.key_macro_events(
            recorded, enum_value(Qt.Key.Key_A), text="a"
        )
    )

    # Act
    with qtbot.waitSignal(macro_player.playback_ended, timeout=TIMEOUT):
        macro_player.play(macro)

    # Assert
    assert dialog.line_edit.text() == ""
    assert other_line_edit.text() == "a"


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


@pytest.mark.parametrize("obstacle", ["window_moved", "modal_dialog_over_canvas"])
@pytest.mark.usefixtures("empty_layer")
@pytest.mark.qgis_show_map(timeout=0)
def test_macro_player_should_play_canvas_macro_regardless_of_screen_position(
    macro_player: MacroPlayer,
    digitize_polygon_macro: Macro,
    qtbot: "QtBot",
    digitize_feature_map_tool: QgsMapToolDigitizeFeature,
    qgis_canvas: "QgsMapCanvas",
    obstacle: str,
):
    # Arrange
    first_event = digitize_polygon_macro.events[0]
    assert isinstance(first_event, MacroMouseEvent)
    recorded_point = first_event.position.global_point
    window = require(qgis_canvas.window())
    if obstacle == "window_moved":
        window.move(window.x() + 500, window.y() + 500)
    else:
        dialog = QDialog(window)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setGeometry(QRect(recorded_point - QPoint(50, 50), QSize(200, 200)))
        qtbot.addWidget(dialog)
        dialog.show()
        qtbot.waitExposed(dialog)
    qtbot.waitUntil(
        lambda: QApplication.widgetAt(recorded_point) is not qgis_canvas.viewport()
    )
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
    assert features[0].geometry().wkbType() == Qgis.WkbType.Polygon


@pytest.mark.usefixtures("empty_layer")
@pytest.mark.qgis_show_map(timeout=0)
def test_macro_player_should_play_hover_moves_on_covered_canvas(
    macro_player: MacroPlayer,
    digitize_polygon_macro: Macro,
    qtbot: "QtBot",
    qgis_canvas: "QgsMapCanvas",
    mocker: "MockerFixture",
):
    # Arrange
    move_event = next(
        event
        for event in digitize_polygon_macro.events
        if isinstance(event, MacroMouseMoveEvent)
    )
    move_event.buttons = enum_value(Qt.MouseButton.NoButton)
    recorded_point = move_event.positions[0].global_point
    dialog = QDialog(require(qgis_canvas.window()))
    dialog.setGeometry(QRect(recorded_point - QPoint(50, 50), QSize(200, 200)))
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    # The cursor moves over the dialog, so the canvas gets no events from it
    mocker.patch.object(BaseMacroEvent, "move_cursor")

    # Act and assert
    with qtbot.waitSignals(
        [macro_player.playback_ended, qgis_canvas.xyCoordinates],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(Macro([move_event]))


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


def _menu_action_macro(
    *action_path: str, action_names: list[str] | None = None
) -> Macro:
    return Macro(
        events=[
            MacroMenuActionEvent(
                WidgetSpec("QMenu"),
                action_path=list(action_path),
                action_names=action_names or [],
            )
        ]
    )


def test_macro_player_should_activate_menu_item_by_object_name(
    styles_menu: "tuple[QMenu, QAction]",
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
):
    menu, fast = styles_menu
    fast.setObjectName("mActionFast")
    # The texts are translated after recording
    fast.setText("nopea")
    menu.popup(dialog.mapToGlobal(QPoint(10, 10)))
    qtbot.waitExposed(menu)

    with qtbot.waitSignals(
        [macro_player.playback_ended, fast.triggered],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(
            _menu_action_macro("Styles", "fast", action_names=["", "mActionFast"])
        )

    assert not menu.isVisible()


def test_macro_player_should_tell_apart_menu_items_sharing_object_name(
    styles_menu: "tuple[QMenu, QAction]",
    macro_player: MacroPlayer,
    dialog: "Dialog",
    qtbot: "QtBot",
):
    menu, fast = styles_menu
    styles = fast.parent()
    assert isinstance(styles, QMenu)
    for action in styles.actions():
        action.setObjectName("mActionStyle")
    menu.popup(dialog.mapToGlobal(QPoint(10, 10)))
    qtbot.waitExposed(menu)

    with qtbot.waitSignals(
        [macro_player.playback_ended, fast.triggered],
        check_params_cbs=checkers,
        timeout=TIMEOUT,
    ):
        macro_player.play(
            _menu_action_macro("Styles", "fast", action_names=["", "mActionStyle"])
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


def test_macro_player_waits_the_delay_of_an_event_before_playing_it(
    macro_player: MacroPlayer,
    qtbot: "QtBot",
):
    actions: list[str] = []
    times: dict[str, float] = {}

    def timed(name: str) -> _RecordingEvent:
        def record_time() -> None:
            times[name] = time.monotonic()

        return _RecordingEvent(name, actions, before=record_time)

    first, second = timed("first"), timed("second")
    second.ms_since_last_event = 400
    third = timed("third")

    with qtbot.waitSignal(macro_player.playback_ended, timeout=TIMEOUT):
        macro_player.play(Macro(events=[first, second, third]))

    assert actions == ["first", "second", "third"]
    assert times["second"] - times["first"] >= 0.35
    assert times["third"] - times["second"] < 0.3
