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
from qgis.PyQt.QtCore import Qt

from macro_test_utils import macro_utils
from macro_test_utils.utils import WidgetInfo
from qgis_macros.macro import Macro, MacroEvent


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
def line_edit_key_macro_event(
    dialog_widget_positions: dict[str, WidgetInfo],
) -> list[MacroEvent]:
    widget = dialog_widget_positions["line_edit"]
    return macro_utils.key_macro_events(widget, Qt.Key_A)


@pytest.fixture
def button_click_macro(button_click_macro_event: list[MacroEvent]) -> Macro:
    return Macro(events=button_click_macro_event)


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
