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
from typing import Optional

from qgis.PyQt.QtCore import Qt

from macro_test_utils.utils import WidgetInfo
from qgis_macros.macro import (
    MacroEvent,
    MacroKeyEvent,
    MacroMouseDoubleClickEvent,
    MacroMouseEvent,
    MacroMouseMoveEvent,
)

"""
Helper functions to create macro events for testing
"""


def widget_clicking_macro_events(
    widget: WidgetInfo,
    elapsed: tuple[int, int] = (0, 0),
    modifiers: int = Qt.NoModifier,
) -> list[MacroEvent]:
    return [
        MacroMouseEvent(
            widget_spec=widget.widget_spec,
            ms_since_last_event=elapsed[0],
            position=widget.global_xy,
            modifiers=modifiers,
        ),
        MacroMouseEvent(
            widget_spec=widget.widget_spec,
            ms_since_last_event=elapsed[1],
            position=widget.global_xy,
            is_release=True,
            modifiers=modifiers,
        ),
    ]


def widget_double_clicking_macro_event(
    widget: WidgetInfo, elapsed: int = 0, modifiers: int = Qt.NoModifier
) -> MacroEvent:
    return MacroMouseDoubleClickEvent(
        widget_spec=widget.widget_spec,
        ms_since_last_event=elapsed,
        position=widget.global_xy,
        modifiers=modifiers,
    )


def key_macro_events(
    widget: WidgetInfo,
    key: int,
    elapsed: tuple[int, int] = (0, 0),
    modifiers: int = Qt.NoModifier,
) -> list[MacroEvent]:
    return [
        MacroKeyEvent(
            widget_spec=widget.widget_spec,
            ms_since_last_event=elapsed[0],
            key=key,
            modifiers=modifiers,
        ),
        MacroKeyEvent(
            widget_spec=widget.widget_spec,
            ms_since_last_event=elapsed[1],
            key=key,
            modifiers=modifiers,
            is_release=True,
        ),
    ]


def mouse_move_macro_event(
    widget: WidgetInfo,
    positions: Optional[list[tuple[int, int]]] = None,
    elapsed: int = 0,
    modifiers: int = Qt.NoModifier,
) -> MacroEvent:
    positions = positions if positions else [widget.global_xy]
    return MacroMouseMoveEvent(
        widget_spec=widget.widget_spec,
        ms_since_last_event=elapsed,
        positions=positions,
        modifiers=modifiers,
    )
