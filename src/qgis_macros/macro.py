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
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Protocol, Union

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QEvent, QPoint, Qt
from qgis.PyQt.QtGui import QCursor, QMouseEvent
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QApplication, QWidget

from qgis_macros import utils
from qgis_macros.constants import (
    MAXIMUM_NEAREST_CANDIDATES,
    MAXIMUM_PARENT_DEPTH,
    MS_EPSILON,
)
from qgis_macros.exceptions import WidgetNotFoundError

LOGGER = logging.getLogger(__name__)


@dataclass
class WidgetSpec:
    widget_type: type[QWidget]
    text: str = ""

    @staticmethod
    def create(widget: QWidget) -> "WidgetSpec":
        return WidgetSpec(type(widget), utils.get_widget_text(widget))

    def matches(self, widget: QWidget) -> bool:
        return isinstance(
            widget, self.widget_type
        ) and self.text == utils.get_widget_text(widget)

    def get_suitable_widget(
        self, point: QPoint, widget: QWidget, level: int = 1
    ) -> QWidget:
        nearest_candidates = utils.find_nearest_visible_children_of_type(
            point, widget, self.widget_type
        )
        for i, candidate in enumerate(nearest_candidates):
            if self.matches(candidate):
                return candidate
            if i > MAXIMUM_NEAREST_CANDIDATES:
                break
        if level < MAXIMUM_PARENT_DEPTH and (parent := widget.parent()) is not None:
            return self.get_suitable_widget(point, parent, level + 1)
        raise WidgetNotFoundError


class MacroEvent(Protocol):
    """Single macro event for Macros"""

    ms_since_last_event: int

    def perform_event_action(self) -> None:
        """
        Perform macro event action (e.g., moving mouse, clicking widget)
        """
        ...


@dataclass
class BaseMacroEvent(ABC):
    widget_spec: WidgetSpec
    ms_since_last_event: int = 0

    @staticmethod
    def move_cursor(position: Union[tuple[int, int], QPoint]) -> None:
        if not isinstance(position, QPoint):
            position = QPoint(*position)
        QCursor.setPos(position)
        QgsApplication.processEvents()

    def get_widget_and_relative_position(
        self, position: tuple[int, int]
    ) -> tuple[QWidget, QPoint]:
        position = QPoint(*position)
        widget = QApplication.widgetAt(position)
        if not widget:
            raise WidgetNotFoundError
        if not self.widget_spec.matches(widget):
            # Sometimes dialogs might appear in a slightly different position
            widget = self.widget_spec.get_suitable_widget(position, widget.parent())
            position = widget.mapToGlobal(widget.geometry().center())
        widget.setFocus()
        self.move_cursor(position)
        return widget, widget.mapFromGlobal(position)

    @abstractmethod
    def perform_event_action(self) -> None: ...

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseMacroEvent):
            return NotImplemented

        return (
            self.widget_spec == other.widget_spec
            and abs(self.ms_since_last_event - other.ms_since_last_event) < MS_EPSILON
        )


@dataclass
class MacroKeyEvent(BaseMacroEvent):
    key: int = 0
    is_release: bool = False
    modifiers: int = Qt.NoModifier

    def perform_event_action(self) -> None:
        widget = QApplication.focusWidget()
        QgsApplication.processEvents()
        # TODO: shift is not working
        if not self.is_release:
            QTest.keyPress(
                widget, Qt.Key(self.key), Qt.KeyboardModifiers(self.modifiers)
            )
        else:
            QTest.keyRelease(
                widget, Qt.Key(self.key), Qt.KeyboardModifiers(self.modifiers)
            )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MacroKeyEvent):
            return NotImplemented
        return super().__eq__(other) and (
            self.ms_since_last_event == other.ms_since_last_event
            and self.key == other.key
            and self.is_release == other.is_release
            and self.modifiers == other.modifiers
        )


@dataclass
class MacroMouseMoveEvent(BaseMacroEvent):
    positions: list[tuple[int, int]] = field(default_factory=list)
    buttons: int = Qt.NoButton
    modifiers: int = Qt.NoModifier

    def add_position(self, position: tuple[int, int]) -> None:
        if self.positions and position == self.positions[-1]:
            return
        self.positions.append(position)

    def perform_event_action(self) -> None:
        if self.buttons != Qt.NoButton:
            return self.perform_event_action_with_event()

        for position in self.positions:
            self.move_cursor(position)
        return None

    def perform_event_action_with_event(self) -> None:
        for position in self.positions:
            global_pos = QPoint(*position)
            widget = QApplication.widgetAt(global_pos)
            local_pos = widget.mapFromGlobal(global_pos) if widget else global_pos
            # Create and send mouse move events
            event = QMouseEvent(
                QEvent.MouseMove,
                local_pos,
                global_pos,
                Qt.NoButton,
                Qt.MouseButtons(self.buttons),
                Qt.KeyboardModifiers(self.modifiers),
            )
            QApplication.postEvent(widget, event)
            QApplication.processEvents()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MacroMouseMoveEvent):
            return NotImplemented
        return super().__eq__(other) and (
            self.positions == other.positions
            and self.buttons == other.buttons
            and self.modifiers == other.modifiers
        )

    def __repr__(self) -> str:
        if len(self.positions) == 1:
            positions = self.positions
        else:
            positions = [self.positions[0], self.positions[-1]]
        return (
            f"MacroMouseMoveEvent(ms_since_last_event={self.ms_since_last_event}, "
            f"widget_spec={self.widget_spec}, "
            f"modifiers={self.modifiers}, "
            f"buttons={self.buttons}, "
            f"positions={positions})"
        )


@dataclass
class MacroMouseEvent(BaseMacroEvent):
    position: tuple[int, int] = (0, 0)
    is_release: bool = False
    button: int = Qt.LeftButton
    modifiers: int = Qt.NoModifier

    def perform_event_action(self) -> None:
        widget, position = self.get_widget_and_relative_position(self.position)
        if not self.is_release:
            # Ensure the widget under the mouse cursor is focused
            QTest.mousePress(
                widget,
                Qt.MouseButton(self.button),
                Qt.KeyboardModifiers(self.modifiers),
                position,
            )
        else:
            QTest.mouseRelease(
                widget,
                Qt.MouseButton(self.button),
                Qt.KeyboardModifiers(self.modifiers),
                position,
            )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MacroMouseEvent):
            return NotImplemented
        return super().__eq__(other) and (
            self.position == other.position
            and self.button == other.button
            and self.modifiers == other.modifiers
            and self.is_release == other.is_release
        )


@dataclass
class MacroMouseDoubleClickEvent(BaseMacroEvent):
    position: tuple[int, int] = (0, 0)
    button: int = Qt.LeftButton
    modifiers: int = Qt.NoModifier

    def perform_event_action(self) -> None:
        widget, position = self.get_widget_and_relative_position(self.position)
        QTest.mouseDClick(
            widget,
            Qt.MouseButton(self.button),
            Qt.KeyboardModifiers(self.modifiers),
            position,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MacroMouseDoubleClickEvent):
            return NotImplemented
        return super().__eq__(other) and (
            self.position == other.position
            and self.button == other.button
            and self.modifiers == other.modifiers
        )


@dataclass
class Macro:
    events: list[MacroEvent]
    name: Optional[str] = None
    speed: float = 1.0
