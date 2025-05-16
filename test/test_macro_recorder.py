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
import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from qgis.PyQt.QtCore import Qt

from macro_test_utils import macro_utils
from macro_test_utils.utils import Dialog, WidgetInfo
from qgis_macros.macro_recorder import MacroRecorder

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
        Qt.NoModifier,
        Qt.ShiftModifier,
        Qt.ControlModifier,
        Qt.AltModifier,
        Qt.KeyboardModifiers(Qt.ControlModifier | Qt.AltModifier),
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
        dialog.button, Qt.LeftButton, pos=button.position.local_point, modifier=modifier
    )
    macro = macro_recorder.stop_recording()

    # Assert
    assert macro.events == list(
        macro_utils.widget_clicking_macro_events(button, (0, 0), int(modifier))
    )


@pytest.mark.parametrize(
    "modifier",
    [
        Qt.NoModifier,
        Qt.ShiftModifier,
        Qt.ControlModifier,
        Qt.AltModifier,
        Qt.KeyboardModifiers(Qt.ControlModifier | Qt.AltModifier),
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
        dialog.button, Qt.LeftButton, pos=button.position.local_point, modifier=modifier
    )
    macro = macro_recorder.stop_recording()

    # Assert
    assert macro.events == [
        macro_utils.widget_double_clicking_macro_event(button, modifiers=int(modifier))
    ]


@pytest.mark.parametrize(
    "modifier",
    [
        Qt.NoModifier,
        Qt.ShiftModifier,
        Qt.ControlModifier,
        Qt.AltModifier,
        Qt.KeyboardModifiers(Qt.ControlModifier | Qt.AltModifier),
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
        dialog.line_edit, Qt.LeftButton, pos=line_edit.position.local_position
    )
    qtbot.keyPress(dialog.line_edit, Qt.Key_A, modifier=modifier)
    qtbot.wait(WAIT_MS)
    qtbot.keyRelease(dialog.line_edit, Qt.Key_A, modifier=modifier)
    macro = macro_recorder.stop_recording()

    assert (
        dialog.line_edit.text() == "a"
        if modifier | Qt.ShiftModifier != modifier
        else "A"
    )

    # Assert
    assert macro.events == [
        macro_utils.mouse_move_macro_event(line_edit),
        *macro_utils.widget_clicking_macro_events(line_edit),
        *macro_utils.key_macro_events(line_edit, Qt.Key_A, modifiers=modifier),
    ]
