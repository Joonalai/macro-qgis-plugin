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

import pytest
from qgis.PyQt.QtCore import QPoint, Qt

from macro_test_utils import macro_utils
from macro_test_utils.utils import Dialog, WidgetInfo
from qgis_macros.macro import Macro, MacroEvent, Position


@pytest.fixture
def button_click_macro_event(
    dialog_widget_positions: dict[str, WidgetInfo],
) -> list[MacroEvent]:
    button = dialog_widget_positions["button"]
    return [
        macro_utils.mouse_move_macro_event(button),
        *macro_utils.widget_clicking_macro_events(button),
    ]


@pytest.fixture
def radio_button_click_macro_event(
    dialog_widget_positions: dict[str, WidgetInfo],
) -> list[MacroEvent]:
    button = dialog_widget_positions["radio_button"]
    return [
        macro_utils.mouse_move_macro_event(button),
        *macro_utils.widget_clicking_macro_events(button),
    ]


@pytest.fixture
def check_box_click_macro_event(
    dialog_widget_positions: dict[str, WidgetInfo],
) -> list[MacroEvent]:
    button = dialog_widget_positions["check_box"]
    return [
        macro_utils.mouse_move_macro_event(button),
        *macro_utils.widget_clicking_macro_events(button),
    ]


@pytest.fixture
def button_double_click_macro_event(
    dialog_widget_positions: dict[str, WidgetInfo],
) -> list[MacroEvent]:
    button = dialog_widget_positions["button"]
    return [
        macro_utils.mouse_move_macro_event(button),
        macro_utils.widget_double_clicking_macro_event(button),
    ]


@pytest.fixture
def line_edit_click_macro_event(
    dialog_widget_positions: dict[str, WidgetInfo],
) -> list[MacroEvent]:
    widget = dialog_widget_positions["line_edit"]
    return [
        macro_utils.mouse_move_macro_event(widget),
        macro_utils.widget_double_clicking_macro_event(widget),
    ]


@pytest.fixture
def menu_action_click_macro_event(
    dialog: Dialog,
    dialog_widget_positions: dict[str, WidgetInfo],
) -> list[MacroEvent]:
    menu_button = dialog_widget_positions["menu_button"]
    menu = dialog_widget_positions["menu"]
    point = dialog.menu.actionGeometry(dialog.action2).center()

    position = Position.from_points(point, dialog.menu_button.mapToGlobal(point))
    return [
        macro_utils.mouse_move_macro_event(menu_button),
        *macro_utils.widget_clicking_macro_events(menu_button),
        macro_utils.mouse_move_macro_event(menu, positions=[position]),
        *macro_utils.widget_clicking_macro_events(menu, position=position),
    ]


@pytest.fixture
def list_item_click_macro_event(
    dialog: Dialog,
    dialog_widget_positions: dict[str, WidgetInfo],
) -> list[MacroEvent]:
    point = dialog.list_widget.visualRect(
        dialog.list_widget.indexFromItem(dialog.list_widget.item(1))
    ).center()
    # List widget positions match viewport positions
    position = Position.from_points(point, dialog.list_widget.mapToGlobal(point))
    list_widget_viewport = dialog_widget_positions["list_widget_viewport"]
    return [
        macro_utils.mouse_move_macro_event(list_widget_viewport, [position]),
        *macro_utils.widget_clicking_macro_events(
            list_widget_viewport, position=position
        ),
    ]


@pytest.fixture
def combobox_item_click_macro_event(
    dialog: Dialog,
    dialog_widget_positions: dict[str, WidgetInfo],
) -> list[MacroEvent]:
    combobox = dialog.combobox
    combobox_info = dialog_widget_positions["combobox"]
    # Center gives a result with a suspicious x...
    y_coordinate = combobox.view().visualRect(combobox.model().index(1, 0)).y()

    point = QPoint(combobox_info.position.local_position[0], y_coordinate)
    position = Position.from_points(point, combobox.mapToGlobal(point))

    combobox_viewport = dialog_widget_positions["combobox_viewport"]

    return [
        macro_utils.mouse_move_macro_event(combobox_info),
        *macro_utils.widget_clicking_macro_events(combobox_info),
        *macro_utils.widget_clicking_macro_events(combobox_viewport, position=position),
    ]


@pytest.fixture
def line_edit_key_macro_event(
    dialog_widget_positions: dict[str, WidgetInfo],
) -> list[MacroEvent]:
    widget = dialog_widget_positions["line_edit"]
    return macro_utils.key_macro_events(widget, Qt.Key_A)


@pytest.fixture
def button_click_macro(button_click_macro_event: list[MacroEvent]) -> Macro:
    return Macro(events=button_click_macro_event)


@pytest.fixture
def radio_button_click_macro(radio_button_click_macro_event: list[MacroEvent]) -> Macro:
    return Macro(events=radio_button_click_macro_event)


@pytest.fixture
def check_box_click_macro(check_box_click_macro_event: list[MacroEvent]) -> Macro:
    return Macro(events=check_box_click_macro_event)


@pytest.fixture
def button_double_click_macro(
    button_double_click_macro_event: list[MacroEvent],
) -> Macro:
    return Macro(events=button_double_click_macro_event)


@pytest.fixture
def line_edit_macro(
    line_edit_click_macro_event: list[MacroEvent],
    line_edit_key_macro_event: list[MacroEvent],
) -> Macro:
    return Macro(events=[*line_edit_click_macro_event, *line_edit_key_macro_event])


@pytest.fixture
def menu_action_click_macro(
    menu_action_click_macro_event: list[MacroEvent],
) -> Macro:
    return Macro(events=menu_action_click_macro_event)


@pytest.fixture
def list_view_item_click_macro(
    list_item_click_macro_event: list[MacroEvent],
) -> Macro:
    return Macro(events=list_item_click_macro_event)


@pytest.fixture
def combobox_item_click_macro(
    combobox_item_click_macro_event: list[MacroEvent],
) -> Macro:
    return Macro(events=combobox_item_click_macro_event)
