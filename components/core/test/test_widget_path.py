#  Copyright (c) 2026 macro-qgis-plugin contributors.
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

from macro_test_utils.utils import Dialog
from qgis.PyQt.QtWidgets import QDialogButtonBox, QMenu, QPushButton, QWidget
from qgis_macros import widget_lookup
from qgis_macros.macro import (
    Macro,
    MacroMouseEvent,
    MacroMouseMoveEvent,
    Position,
    WidgetPath,
    WidgetPathNode,
    WidgetSpec,
)
from qgis_plugin_tools.utils.typing_utils import require


def test_widget_path_create_and_find(dialog: Dialog) -> None:
    widget_path = require(WidgetPath.create(dialog.button))

    assert widget_path.window_title == dialog.windowTitle()
    assert widget_path.window_object_name == dialog.objectName()
    assert not widget_path.is_map_canvas
    assert len(widget_path.nodes) > 0
    # Last node should be the button itself
    assert widget_path.nodes[-1].widget_class == "QPushButton"

    found_widget = widget_path.find_widget()
    assert found_widget is dialog.button


def test_widget_path_finds_correct_sibling(dialog: Dialog) -> None:
    path1 = require(WidgetPath.create(dialog.button))
    path2 = require(WidgetPath.create(dialog.button2))

    assert path1.find_widget() is dialog.button
    assert path2.find_widget() is dialog.button2
    assert path1.find_widget() is not path2.find_widget()


def test_widget_path_finds_non_button_widgets(dialog: Dialog) -> None:
    for widget_name in ("combobox", "line_edit", "radio_button", "check_box"):
        widget = getattr(dialog, widget_name)
        path = require(WidgetPath.create(widget))
        found = path.find_widget()
        assert found is widget, f"Failed to find {widget_name}"


def test_widget_path_leads_to_its_widget_only(dialog: Dialog) -> None:
    path = require(WidgetPath.create(dialog.button))

    assert widget_lookup.path_leads_to(path, dialog.button)
    assert not widget_lookup.path_leads_to(path, dialog.button2)
    assert not widget_lookup.path_leads_to(path, dialog.line_edit)
    assert not widget_lookup.path_leads_to(path, dialog)


def test_widget_path_leads_to_widget_by_window_object_name(dialog: Dialog) -> None:
    dialog.setObjectName("test_dialog")
    path = require(WidgetPath.create(dialog.line_edit))
    dialog.setWindowTitle("Changed title")

    assert widget_lookup.path_leads_to(path, dialog.line_edit)


def test_widget_path_returns_none_for_missing_window(dialog: Dialog) -> None:
    path = WidgetPath(
        window_title="nonexistent window title",
        nodes=[WidgetPathNode("QPushButton", 0, "Click Me")],
    )
    assert path.find_widget() is None


def test_widget_path_finds_window_by_object_name_when_title_changes(
    dialog: Dialog,
) -> None:
    dialog.setObjectName("test_dialog")
    path = require(WidgetPath.create(dialog.button))
    dialog.setWindowTitle("Changed title")

    assert path.find_widget() is dialog.button


def test_widget_path_prefers_window_with_matching_title(dialog: Dialog) -> None:
    # Dialogs often keep the generic object name from Qt Designer
    dialog.setObjectName("Dialog")
    other = Dialog()
    other.setObjectName("Dialog")
    other.setWindowTitle("Other dialog")
    other.show()
    try:
        path = require(WidgetPath.create(dialog.button))
        other_path = require(WidgetPath.create(other.button))

        assert path.find_widget() is dialog.button
        assert other_path.find_widget() is other.button
    finally:
        other.close()


def test_resolved_widget_gets_focus(dialog: Dialog) -> None:
    # e.g. key events after a wheel or a drag go to the widget
    dialog.button.setFocus()
    event = MacroMouseMoveEvent(
        WidgetSpec.create(dialog.line_edit),
        widget_path=WidgetPath.create(dialog.line_edit),
    )

    event.get_widget(Position((0, 0), (0, 0)))

    assert dialog.focusWidget() is dialog.line_edit


def test_find_child_tells_apart_widgets_sharing_object_name(dialog: Dialog) -> None:
    parent = QWidget(dialog)
    buttons = [QPushButton(text, parent) for text in ("a", "b", "c")]
    for button in buttons:
        button.setObjectName("same")
    # The buttons were reordered after recording
    node = WidgetPathNode("QPushButton", 0, "c", "same")

    assert widget_lookup.find_child(parent, node) is buttons[2]


def test_widget_path_is_not_created_for_popups(dialog: Dialog) -> None:
    menu = QMenu(dialog)
    menu.addAction("Action")
    menu.popup(dialog.mapToGlobal(dialog.rect().center()))
    try:
        assert WidgetPath.create(menu) is None
    finally:
        menu.close()


def test_find_by_path_ignores_hidden_widget(dialog: Dialog) -> None:
    path = require(WidgetPath.create(dialog.button))
    spec = WidgetSpec.create(dialog.button)
    position = Position((0, 0), (0, 0))
    assert widget_lookup.find_by_path(spec, path, position) is dialog.button

    dialog.button.hide()

    assert widget_lookup.find_by_path(spec, path, position) is None


def test_widget_spec_matches_by_object_name_when_text_differs(dialog: Dialog) -> None:
    dialog.button.setObjectName("button_ok")
    spec = WidgetSpec.create(dialog.button)
    assert spec.object_name == "button_ok"

    dialog.button.setText("Translated")

    assert spec.matches(dialog.button)
    dialog.button.setObjectName("other")
    assert not spec.matches(dialog.button)


def test_widget_spec_matches_standard_dialog_button_by_role(dialog: Dialog) -> None:
    button_box = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        dialog,
    )
    ok_button = require(button_box.button(QDialogButtonBox.StandardButton.Ok))
    cancel_button = require(button_box.button(QDialogButtonBox.StandardButton.Cancel))
    spec = WidgetSpec.create(ok_button)
    assert spec.object_name

    ok_button.setText("Translated")

    assert spec.matches(ok_button)
    assert not spec.matches(cancel_button)


def test_find_by_path_finds_button_with_translated_text(dialog: Dialog) -> None:
    spec = WidgetSpec.create(dialog.button)
    path = require(WidgetPath.create(dialog.button))
    position = Position((0, 0), (0, 0))

    dialog.button.setText("Translated")

    assert widget_lookup.find_by_path(spec, path, position) is dialog.button


def test_widget_path_serialization_roundtrip(dialog: Dialog) -> None:
    widget_path = require(WidgetPath.create(dialog.button))
    dialog.setObjectName("test_dialog")
    widget_path = require(WidgetPath.create(dialog.button))
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
    assert (
        deserialized_event.widget_path.window_object_name
        == widget_path.window_object_name
    )
    assert deserialized_event.widget_path.is_map_canvas == widget_path.is_map_canvas
    assert len(deserialized_event.widget_path.nodes) == len(widget_path.nodes)
    for original, restored in zip(
        widget_path.nodes, deserialized_event.widget_path.nodes, strict=True
    ):
        assert original.widget_class == restored.widget_class
        assert original.sibling_index == restored.sibling_index
        assert original.text == restored.text
        assert original.object_name == restored.object_name


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
