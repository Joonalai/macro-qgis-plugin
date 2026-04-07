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

from macro_test_utils.utils import Dialog
from qgis_macros.macro import (
    Macro,
    MacroMouseEvent,
    Position,
    WidgetPath,
    WidgetPathNode,
    WidgetSpec,
)


def test_widget_path_create_and_find(dialog: Dialog) -> None:
    widget_path = WidgetPath.create(dialog.button)

    assert widget_path.window_title == dialog.windowTitle()
    assert not widget_path.is_map_canvas
    assert len(widget_path.nodes) > 0
    # Last node should be the button itself
    assert widget_path.nodes[-1].widget_class == "QPushButton"

    found_widget = widget_path.find_widget()
    assert found_widget is dialog.button


def test_widget_path_finds_correct_sibling(dialog: Dialog) -> None:
    path1 = WidgetPath.create(dialog.button)
    path2 = WidgetPath.create(dialog.button2)

    assert path1.find_widget() is dialog.button
    assert path2.find_widget() is dialog.button2
    assert path1.find_widget() is not path2.find_widget()


def test_widget_path_finds_non_button_widgets(dialog: Dialog) -> None:
    for widget_name in ("combobox", "line_edit", "radio_button", "check_box"):
        widget = getattr(dialog, widget_name)
        path = WidgetPath.create(widget)
        found = path.find_widget()
        assert found is widget, f"Failed to find {widget_name}"


def test_widget_path_returns_none_for_missing_window(dialog: Dialog) -> None:
    path = WidgetPath(
        window_title="nonexistent window title",
        nodes=[WidgetPathNode("QPushButton", 0, "Click Me")],
    )
    assert path.find_widget() is None


def test_widget_path_serialization_roundtrip(dialog: Dialog) -> None:
    widget_path = WidgetPath.create(dialog.button)
    position = Position((10, 10), (100, 100))
    event = MacroMouseEvent(
        widget_spec=WidgetSpec.create(dialog.button),
        position=position,
        widget_path=widget_path,
    )
    macro = Macro(events=[event], name="test")

    serialized = macro.serialize()
    deserialized = Macro.deserialize(serialized)

    deserialized_event = deserialized.events[0]
    assert isinstance(deserialized_event, MacroMouseEvent)
    assert deserialized_event.widget_path is not None
    assert deserialized_event.widget_path.window_title == widget_path.window_title
    assert deserialized_event.widget_path.is_map_canvas == widget_path.is_map_canvas
    assert len(deserialized_event.widget_path.nodes) == len(widget_path.nodes)
    for original, restored in zip(
        widget_path.nodes, deserialized_event.widget_path.nodes, strict=True
    ):
        assert original.widget_class == restored.widget_class
        assert original.sibling_index == restored.sibling_index
        assert original.text == restored.text


def test_widget_path_backwards_compatible_deserialization() -> None:
    """Macros saved without widget_path should still deserialize."""
    data = {
        "name": "old_macro",
        "speed": 1.0,
        "qgis_version": 33800,
        "events": [
            {
                "type": "MacroMouseEvent",
                "widget_spec": {"widget_class": "QPushButton", "text": "OK"},
                "ms_since_last_event": 0,
                "position": {
                    "local_position": [10, 10],
                    "global_position": [100, 100],
                },
                "is_release": False,
                "button": 1,
                "modifiers": 0,
            }
        ],
    }
    macro = Macro.deserialize(data)
    event = macro.events[0]
    assert isinstance(event, MacroMouseEvent)
    assert event.widget_path is None
