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
import dataclasses
from typing import TYPE_CHECKING

import pytest
from macro_test_utils.utils import Dialog
from qgis.gui import QgsMapCanvas
from qgis.PyQt.QtCore import QPoint, Qt
from qgis.PyQt.QtWidgets import QApplication, QWidget
from qgis_macros.exceptions import WidgetNotFoundError
from qgis_macros.macro import (
    Macro,
    MacroKeyEvent,
    MacroMenuActionEvent,
    MacroMouseEvent,
    Position,
    WidgetPath,
    WidgetSpec,
)
from qgis_macros.utils import enum_value
from qgis_plugin_tools.utils.typing_utils import require

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

pytest_plugins = [
    "macro_test_utils.macro_fixture",
]


def test_macro_locale_is_serialized() -> None:
    macro = Macro(events=[], locale="fi")

    deserialized = Macro.deserialize(macro.serialize())

    assert deserialized.locale == "fi"


def test_macro_without_locale_deserializes_with_empty_locale() -> None:
    data = {"name": "old", "speed": 1.0, "qgis_version": 33800, "events": []}

    assert Macro.deserialize(data).locale == ""


def _create_test_position(x: int, y: int) -> Position:
    return Position((x, y), (x + 10, y + 10))


def test_macro_serialization_and_deserialization(
    digitize_polygon_macro: Macro,
):
    serialized = digitize_polygon_macro.serialize()
    assert serialized
    assert isinstance(serialized, dict)

    deserialized = Macro.deserialize(serialized)
    assert deserialized == digitize_polygon_macro


@pytest.mark.parametrize(
    ("positions", "number_of_positions", "expected_positions"),
    [
        ([_create_test_position(0, 0)], 2, [_create_test_position(0, 0)]),
        (
            [
                _create_test_position(*point)
                for point in [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
            ],
            2,
            [_create_test_position(*point) for point in [(0, 0), (5, 5)]],
        ),
        (
            [
                _create_test_position(*point)
                for point in [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
            ],
            3,
            [_create_test_position(*point) for point in [(0, 0), (2, 2), (5, 5)]],
        ),
        (
            [
                _create_test_position(*point)
                for point in [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
            ],
            4,
            [
                _create_test_position(*point)
                for point in [(0, 0), (1, 1), (3, 3), (5, 5)]
            ],
        ),
    ],
)
def test_position_interpolation(
    positions: list[Position],
    number_of_positions: int,
    expected_positions: list[Position],
):
    assert Position.interpolate(positions, number_of_positions) == expected_positions


def test_menu_action_event_serialization() -> None:
    macro = Macro(
        events=[
            MacroMenuActionEvent(
                WidgetSpec("QMenu"), ms_since_last_event=5, action_path=["A", "b"]
            )
        ],
        name="menu",
    )

    deserialized = Macro.deserialize(macro.serialize())

    assert deserialized == macro
    event = deserialized.events[0]
    assert isinstance(event, MacroMenuActionEvent)
    assert event.action_path == ["A", "b"]


def _canvas_click(canvas_size: tuple[int, int] | None) -> MacroMouseEvent:
    return MacroMouseEvent(
        widget_spec=WidgetSpec("QWidget", ""),
        widget_path=WidgetPath("", [], is_map_canvas=True, canvas_size=canvas_size),
        position=Position((20, 30), (0, 0)),
    )


def test_canvas_size_is_serialized_only_on_map_canvas() -> None:
    on_canvas = Macro([_canvas_click((400, 300))])
    elsewhere = Macro(
        [
            MacroMouseEvent(
                widget_spec=WidgetSpec("QPushButton", "OK"),
                widget_path=WidgetPath("Dialog", []),
            )
        ]
    )

    deserialized = Macro.deserialize(on_canvas.serialize())
    assert deserialized == on_canvas
    [click] = deserialized.events
    assert isinstance(click, MacroMouseEvent)
    assert require(click.widget_path).canvas_size == (400, 300)
    assert "canvas_size" not in elsewhere.serialize()["events"][0]["widget_path"]


def test_position_on_map_canvas_keeps_its_offset_from_the_center(
    qgis_canvas: QgsMapCanvas,
) -> None:
    viewport = require(qgis_canvas.viewport())
    width, height = viewport.width(), viewport.height()

    same_size = _canvas_click((width, height)).corrected_position(
        viewport, Position((20, 30), (0, 0))
    )
    larger = _canvas_click((width + 100, height + 50)).corrected_position(
        viewport, Position((120, 80), (0, 0))
    )

    assert same_size.local_point == QPoint(20, 30)
    assert larger.local_point == QPoint(70, 55)
    assert larger.global_point == viewport.mapToGlobal(QPoint(70, 55))


def test_position_without_canvas_size_is_not_moved(qgis_canvas: QgsMapCanvas) -> None:
    viewport = require(qgis_canvas.viewport())
    position = Position((20, 30), (0, 0))

    assert _canvas_click(None).corrected_position(
        viewport, position
    ).local_point == QPoint(20, 30)
    assert _canvas_click((10, 10)).corrected_position(
        QWidget(), position
    ).local_point == QPoint(20, 30)


def test_key_event_without_focus_is_sent_to_its_window(
    dialog: Dialog, mocker: "MockerFixture"
) -> None:
    mocker.patch.object(QApplication, "focusWidget", return_value=None)
    qtest = mocker.patch("qgis_macros.macro._qtest")
    event = MacroKeyEvent(
        WidgetSpec.create(dialog),
        widget_path=WidgetPath.create(dialog),
        key=enum_value(Qt.Key.Key_Return),
        is_release=True,
    )

    event.perform_event_action(lambda: None)

    assert qtest.keyRelease.call_args.args[0] is dialog


def test_key_event_fails_if_its_window_is_closed(
    dialog: Dialog, mocker: "MockerFixture"
) -> None:
    qtest = mocker.patch("qgis_macros.macro._qtest")
    event = MacroKeyEvent(
        WidgetSpec.create(dialog.line_edit),
        widget_path=WidgetPath.create(dialog.line_edit),
        key=enum_value(Qt.Key.Key_A),
    )
    dialog.close()

    with pytest.raises(WidgetNotFoundError):
        event.perform_event_action(lambda: None)
    qtest.keyPress.assert_not_called()


def test_key_event_falls_back_to_focus_in_its_window(
    dialog: Dialog, mocker: "MockerFixture"
) -> None:
    mocker.patch.object(QApplication, "focusWidget", return_value=dialog.combobox)
    qtest = mocker.patch("qgis_macros.macro._qtest")
    path = WidgetPath.create(dialog.line_edit)
    assert path is not None
    # The widget has been replaced in the window
    path.nodes[-1] = dataclasses.replace(
        path.nodes[-1], widget_class="QSpinBox", object_name="renamedEdit"
    )
    event = MacroKeyEvent(
        WidgetSpec("QSpinBox"), widget_path=path, key=enum_value(Qt.Key.Key_A)
    )

    event.perform_event_action(lambda: None)

    assert qtest.keyPress.call_args.args[0] is dialog.combobox


def test_key_event_without_target_fails(mocker: "MockerFixture") -> None:
    mocker.patch.object(QApplication, "focusWidget", return_value=None)
    qtest = mocker.patch("qgis_macros.macro._qtest")
    event = MacroKeyEvent(WidgetSpec("QLineEdit"), key=enum_value(Qt.Key.Key_A))

    with pytest.raises(WidgetNotFoundError):
        event.perform_event_action(lambda: None)
    qtest.keyPress.assert_not_called()
