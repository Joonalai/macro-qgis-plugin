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
import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from macro_test_utils import macro_utils
from macro_test_utils.utils import Dialog, WidgetInfo
from qgis.core import (
    QgsFeature,
)
from qgis.gui import (
    QgsMapCanvas,
    QgsMapToolDigitizeFeature,
)
from qgis.PyQt.QtCore import QPoint, Qt
from qgis.PyQt.QtWidgets import QMenu
from qgis_macros.macro import MacroMenuActionEvent, MacroMouseEvent, Position
from qgis_macros.macro_recorder import MacroRecorder
from qgis_macros.utils import enum_value
from qgis_plugin_tools.utils.typing_utils import require

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

WAIT_MS = 5
LOGGER = logging.getLogger(__name__)


@pytest.fixture
def macro_recorder() -> Iterator[MacroRecorder]:
    recorder = MacroRecorder()
    recorder.start_recording()
    yield recorder
    recorder.stop_recording()


@pytest.mark.skip(reason="Ment for manual testing")
@pytest.mark.timeout(60)
def test_macro_recorder_manual(
    macro_recorder: MacroRecorder, dialog: Dialog, qtbot: "QtBot"
):
    while dialog.isVisible():
        qtbot.wait(100)
    macro = macro_recorder.stop_recording()
    assert macro
    LOGGER.info("\nMacro:\n%s", str(macro).replace("Macro", "\nMacro"))


@pytest.mark.parametrize(
    "modifier",
    [
        Qt.KeyboardModifier.NoModifier,
        Qt.KeyboardModifier.ShiftModifier,
        Qt.KeyboardModifier.ControlModifier,
        Qt.KeyboardModifier.AltModifier,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier,
    ],
    ids=[
        "no_modifier",
        "shift_modifier",
        "control_modifier",
        "alt_modifier",
        "control_alt_modifier",
    ],
)
def test_macro_recorder_should_record_button_clicking_macro(
    dialog: Dialog,
    macro_recorder: MacroRecorder,
    dialog_widget_positions: dict[str, WidgetInfo],
    qtbot: "QtBot",
    modifier: Qt.KeyboardModifier,
):
    # Arrange
    button = dialog_widget_positions["button"]

    # Act
    qtbot.mouseClick(
        dialog.button,
        Qt.MouseButton.LeftButton,
        pos=button.position.local_point,
        modifier=modifier,
    )
    macro = macro_recorder.stop_recording()

    # Assert
    assert macro.events == list(
        macro_utils.widget_clicking_macro_events(
            button, button.position, modifiers=enum_value(modifier)
        )
    )


@pytest.mark.parametrize(
    "modifier",
    [
        Qt.KeyboardModifier.NoModifier,
        Qt.KeyboardModifier.ShiftModifier,
        Qt.KeyboardModifier.ControlModifier,
        Qt.KeyboardModifier.AltModifier,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier,
    ],
    ids=[
        "no_modifier",
        "shift_modifier",
        "control_modifier",
        "alt_modifier",
        "control_alt_modifier",
    ],
)
def test_macro_recorder_should_record_button_double_clicking_macro(
    dialog: Dialog,
    macro_recorder: MacroRecorder,
    dialog_widget_positions: dict[str, WidgetInfo],
    qtbot: "QtBot",
    modifier: Qt.KeyboardModifier,
):
    # Arrange
    button = dialog_widget_positions["button"]

    # Act
    qtbot.mouseDClick(
        dialog.button,
        Qt.MouseButton.LeftButton,
        pos=button.position.local_point,
        modifier=modifier,
    )
    macro = macro_recorder.stop_recording()

    # Assert
    assert macro.events == [
        macro_utils.widget_double_clicking_macro_event(
            button, modifiers=enum_value(modifier)
        )
    ]


@pytest.mark.parametrize(
    "modifier",
    [
        Qt.KeyboardModifier.NoModifier,
        Qt.KeyboardModifier.ShiftModifier,
        Qt.KeyboardModifier.ControlModifier,
        Qt.KeyboardModifier.AltModifier,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier,
    ],
    ids=[
        "no_modifier",
        "shift_modifier",
        "control_modifier",
        "alt_modifier",
        "control_alt_modifier",
    ],
)
@pytest.mark.xfail(reason="Modifiers do not work properly yet")
def test_macro_recorder_should_record_key_clicking_macro(
    dialog: Dialog,
    macro_recorder: MacroRecorder,
    dialog_widget_positions: dict[str, WidgetInfo],
    qtbot: "QtBot",
    modifier: Qt.KeyboardModifier,
):
    # Arrange
    line_edit = dialog_widget_positions["line_edit"]

    # Act
    qtbot.wait(WAIT_MS)
    qtbot.mouseMove(dialog.line_edit, pos=line_edit.position.local_position)
    qtbot.wait(WAIT_MS * 5)
    qtbot.mouseClick(
        dialog.line_edit,
        Qt.MouseButton.LeftButton,
        pos=line_edit.position.local_position,
    )
    qtbot.keyPress(dialog.line_edit, Qt.Key.Key_A, modifier=modifier)
    qtbot.wait(WAIT_MS)
    qtbot.keyRelease(dialog.line_edit, Qt.Key.Key_A, modifier=modifier)
    macro = macro_recorder.stop_recording()

    assert dialog.line_edit.text() == (
        "a" if modifier | Qt.KeyboardModifier.ShiftModifier != modifier else "A"
    )

    # Assert
    assert macro.events == [
        macro_utils.mouse_move_macro_event(line_edit),
        *macro_utils.widget_clicking_macro_events(line_edit),
        *macro_utils.key_macro_events(
            line_edit, Qt.Key.Key_A, modifiers=enum_value(modifier)
        ),
    ]


@pytest.mark.usefixtures("digitize_feature_map_tool", "empty_layer")
@pytest.mark.qgis_show_map(timeout=0)
@pytest.mark.timeout(60)
def test_macro_recorder_should_record_digitizing_polygon(
    macro_recorder: MacroRecorder,
    #     dialog: Dialog,
    qtbot: "QtBot",
    digitize_feature_map_tool: QgsMapToolDigitizeFeature,
    qgis_canvas: QgsMapCanvas,
):
    # Arrange
    canvas = WidgetInfo.from_widget("viewport", require(qgis_canvas.viewport()))
    initial_position = canvas.position
    second_point = QPoint(
        initial_position.local_point.x(), initial_position.local_point.y() + 3
    )
    third_point = QPoint(
        initial_position.local_point.x() + 3, initial_position.local_point.y() + 3
    )
    second_position = Position.from_points(
        second_point, canvas.widget.mapToGlobal(second_point)
    )
    third_position = Position.from_points(
        third_point, canvas.widget.mapToGlobal(third_point)
    )

    # Act
    qtbot.mouseClick(
        canvas.widget, Qt.MouseButton.LeftButton, pos=initial_position.local_point
    )
    qtbot.mouseMove(canvas.widget, pos=second_point)
    qtbot.mouseClick(canvas.widget, Qt.MouseButton.LeftButton, pos=second_point)
    qtbot.mouseMove(canvas.widget, pos=third_point)
    qtbot.mouseClick(canvas.widget, Qt.MouseButton.LeftButton, pos=third_point)
    with qtbot.waitSignal(digitize_feature_map_tool.digitizingCompleted) as blocker:
        qtbot.mouseClick(
            canvas.widget, Qt.MouseButton.RightButton, pos=initial_position.local_point
        )
    assert isinstance(blocker.args[0], QgsFeature)

    macro = macro_recorder.stop_recording()
    assert macro.events == [
        *macro_utils.widget_clicking_macro_events(canvas, initial_position),
        macro_utils.mouse_move_macro_event(canvas, [second_position]),
        *macro_utils.widget_clicking_macro_events(canvas, second_position),
        macro_utils.mouse_move_macro_event(canvas, [third_position]),
        *macro_utils.widget_clicking_macro_events(canvas, third_position),
        *macro_utils.widget_clicking_macro_events(
            canvas, initial_position, button=enum_value(Qt.MouseButton.RightButton)
        ),
    ]


@pytest.fixture
def context_menu(dialog: Dialog) -> Iterator[tuple[QMenu, QMenu]]:
    menu = QMenu(dialog)
    menu.addAction("Zoom to Layer")
    styles = require(menu.addMenu("&Styles"))
    styles.addAction("slow")
    styles.addAction("fast")
    yield menu, styles
    menu.close()


def _open_submenu(menu: QMenu, submenu: QMenu, qtbot: "QtBot") -> None:
    menu.setActiveAction(submenu.menuAction())
    qtbot.waitExposed(submenu)


def test_macro_recorder_should_record_menu_item_by_text(
    dialog: Dialog,
    context_menu: tuple[QMenu, QMenu],
    macro_recorder: MacroRecorder,
    qtbot: "QtBot",
):
    # Arrange
    menu, styles = context_menu
    menu.popup(dialog.mapToGlobal(QPoint(10, 10)))
    qtbot.waitExposed(menu)
    _open_submenu(menu, styles, qtbot)
    fast_position = styles.actionGeometry(styles.actions()[1]).center()

    # Act
    qtbot.mouseMove(styles, fast_position)
    qtbot.mousePress(styles, Qt.MouseButton.LeftButton, pos=fast_position)
    qtbot.mouseRelease(styles, Qt.MouseButton.LeftButton, pos=fast_position)
    macro = macro_recorder.stop_recording()

    # Assert
    menu_events = [e for e in macro.events if isinstance(e, MacroMenuActionEvent)]
    assert [e.action_path for e in menu_events] == [["Styles", "fast"]]
    assert macro.events[-1] is menu_events[0]
    # No coordinate based events inside the menus are left
    assert not [
        e
        for e in macro.events
        if isinstance(e, MacroMouseEvent) and e.widget_spec.widget_class == "QMenu"
    ]


def test_macro_recorder_should_keep_context_menu_click(
    dialog: Dialog,
    context_menu: tuple[QMenu, QMenu],
    dialog_widget_positions: dict[str, WidgetInfo],
    macro_recorder: MacroRecorder,
    qtbot: "QtBot",
):
    # Arrange
    menu, styles = context_menu
    button = dialog_widget_positions["button"]

    # Act: the context menu opens on the press and the release lands on it
    qtbot.mousePress(
        dialog.button, Qt.MouseButton.RightButton, pos=button.position.local_point
    )
    menu.popup(dialog.button.mapToGlobal(button.position.local_point))
    qtbot.waitExposed(menu)
    qtbot.mouseRelease(menu, Qt.MouseButton.RightButton, pos=QPoint(1, 1))
    _open_submenu(menu, styles, qtbot)
    fast_position = styles.actionGeometry(styles.actions()[1]).center()
    qtbot.mousePress(styles, Qt.MouseButton.LeftButton, pos=fast_position)
    qtbot.mouseRelease(styles, Qt.MouseButton.LeftButton, pos=fast_position)
    macro = macro_recorder.stop_recording()

    # Assert
    press, release, menu_action = macro.events
    assert isinstance(press, MacroMouseEvent)
    assert press.button == enum_value(Qt.MouseButton.RightButton)
    assert not press.is_release
    assert press.widget_spec.widget_class == "QPushButton"
    assert isinstance(release, MacroMouseEvent)
    assert release.is_release
    assert release.button == enum_value(Qt.MouseButton.RightButton)
    assert isinstance(menu_action, MacroMenuActionEvent)
    assert menu_action.action_path == ["Styles", "fast"]
