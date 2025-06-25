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
import dataclasses
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol, Union

from qgis.core import Qgis, QgsApplication, QgsLineString
from qgis.PyQt.QtCore import QEvent, QPoint, Qt
from qgis.PyQt.QtGui import QCursor, QMouseEvent
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QApplication, QWidget

from qgis_macros import utils
from qgis_macros.constants import (
    MAXIMUM_NEAREST_CANDIDATES,
    MAXIMUM_PARENT_DEPTH,
)
from qgis_macros.exceptions import WidgetNotFoundError

LOGGER = logging.getLogger(__name__)


@dataclass
class WidgetSpec:
    widget_class: str
    text: str = ""

    @staticmethod
    def create(widget: QWidget) -> "WidgetSpec":
        return WidgetSpec(widget.__class__.__name__, utils.get_widget_text(widget))

    def matches(self, widget: QWidget) -> bool:
        return (
            widget.__class__.__name__ == self.widget_class
            and self.text == utils.get_widget_text(widget)
        )

    def get_suitable_widget(
        self, point: QPoint, widget: QWidget, level: int = 1
    ) -> QWidget:
        nearest_candidates = utils.find_nearest_visible_children_of_type(
            point, widget, self.widget_class
        )
        for i, candidate in enumerate(nearest_candidates):
            if self.matches(candidate):
                return candidate
            if i > MAXIMUM_NEAREST_CANDIDATES:
                break
        if level < MAXIMUM_PARENT_DEPTH and (parent := widget.parent()) is not None:
            return self.get_suitable_widget(point, parent, level + 1)
        raise WidgetNotFoundError(self.widget_class, self.text)


class MacroEvent(Protocol):
    """Single macro event for Macros"""

    ms_since_last_event: int

    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        """
        Perform macro event action (e.g., moving mouse, clicking widget)
        """
        ...


@dataclass(frozen=True)
class Position:
    local_position: tuple[int, int]
    global_position: tuple[int, int]

    @staticmethod
    def from_event(event: QMouseEvent) -> "Position":
        return Position(
            (event.x(), event.y()),
            (event.globalX(), event.globalY()),
        )

    @staticmethod
    def from_points(local_point: QPoint, global_point: QPoint) -> "Position":
        return Position(
            (local_point.x(), local_point.y()),
            (global_point.x(), global_point.y()),
        )

    @staticmethod
    def interpolate(
        positions: list["Position"], number_of_positions: int
    ) -> list["Position"]:
        if len(positions) <= number_of_positions:
            return positions

        def _interpolate(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
            x, y = list(zip(*points))
            line = QgsLineString(x, y)
            distance = line.length() / (number_of_positions - 1)
            interpolated_points = [
                line.interpolatePoint(point_distance)
                for point_distance in [
                    distance * i for i in range(1, number_of_positions - 1)
                ]
            ]
            interpolated_points = [
                (int(point.x()), int(point.y())) for point in interpolated_points
            ]
            return [points[0], *interpolated_points, points[-1]]

        local_positions = _interpolate([pos.local_position for pos in positions])
        global_positions = _interpolate([pos.global_position for pos in positions])
        return [
            Position(local_point, global_point)
            for local_point, global_point in zip(local_positions, global_positions)
        ]

    @property
    def local_point(self) -> QPoint:
        return QPoint(*self.local_position)

    @property
    def global_point(self) -> QPoint:
        return QPoint(*self.global_position)

    def widget_corrected_position(self, widget: QWidget) -> "Position":
        return Position.from_points(
            self.local_point, widget.mapToGlobal(self.local_point)
        )


default_position = Position((0, 0), (0, 0))


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

    def get_widget(self, position: Position) -> QWidget:
        global_point = position.global_point
        widget = QApplication.widgetAt(global_point)
        if not widget:
            raise WidgetNotFoundError(
                self.widget_spec.widget_class, self.widget_spec.text
            )
        if not self.widget_spec.matches(widget):
            # Sometimes dialogs might appear in a slightly different position
            widget = self.widget_spec.get_suitable_widget(global_point, widget.parent())
        widget.setFocus()
        return widget

    def get_widget_and_corrected_position(
        self, position: Position
    ) -> tuple[QWidget, Position]:
        widget = self.get_widget(position)
        corrected_position = position.widget_corrected_position(widget)
        return widget, corrected_position

    @abstractmethod
    def perform_event_action(self, schedule_next: Callable[[], None]) -> None: ...

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseMacroEvent):
            return NotImplemented

        return self.widget_spec == other.widget_spec


@dataclass
class MacroKeyEvent(BaseMacroEvent):
    key: int = 0
    is_release: bool = False
    modifiers: int = Qt.NoModifier

    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        widget = QApplication.focusWidget()
        QgsApplication.processEvents()
        # TODO: shift is not working
        schedule_next()
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
    positions: list[Position] = field(default_factory=list)
    buttons: int = Qt.NoButton
    modifiers: int = Qt.NoModifier

    def add_position(self, position: Position) -> None:
        if self.positions and position == self.positions[-1]:
            return
        self.positions.append(position)

    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        if self.buttons != Qt.NoButton:
            self.perform_event_action_with_event()
            schedule_next()
            return

        if not self.positions:
            return
        widget = self.get_widget(self.positions[0])

        for position in self.positions:
            self.move_cursor(position.widget_corrected_position(widget).global_point)
        schedule_next()
        return

    def perform_event_action_with_event(self) -> None:
        if not self.positions:
            return
        widget = self.get_widget(self.positions[0])

        for position in self.positions:
            corrected_position = position.widget_corrected_position(widget)
            # Create and send mouse move events
            event = QMouseEvent(
                QEvent.MouseMove,
                corrected_position.local_point,
                corrected_position.global_point,
                Qt.NoButton,
                Qt.MouseButtons(self.buttons),
                Qt.KeyboardModifiers(self.modifiers),
            )
            QApplication.postEvent(widget, event)
            QApplication.processEvents()

    def interpolate_positions(self, number_of_positions: int) -> None:
        """Interpolate the positions to a given number of positions."""
        self.positions = Position.interpolate(self.positions, number_of_positions)

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
    position: Position = default_position
    is_release: bool = False
    button: int = Qt.LeftButton
    modifiers: int = Qt.NoModifier

    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        widget, corrected_position = self.get_widget_and_corrected_position(
            self.position
        )
        self.move_cursor(corrected_position.global_point)
        schedule_next()
        if not self.is_release:
            # Ensure the widget under the mouse cursor is focused
            QTest.mousePress(
                widget,
                Qt.MouseButton(self.button),
                Qt.KeyboardModifiers(self.modifiers),
                corrected_position.local_point,
            )
        else:
            QTest.mouseRelease(
                widget,
                Qt.MouseButton(self.button),
                Qt.KeyboardModifiers(self.modifiers),
                corrected_position.local_point,
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
    position: Position = default_position
    button: int = Qt.LeftButton
    modifiers: int = Qt.NoModifier

    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        widget, corrected_position = self.get_widget_and_corrected_position(
            self.position
        )
        self.move_cursor(corrected_position.global_point)
        schedule_next()
        QTest.mouseDClick(
            widget,
            Qt.MouseButton(self.button),
            Qt.KeyboardModifiers(self.modifiers),
            corrected_position.local_point,
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
    qgis_version: int = Qgis.versionInt()

    def serialize(self) -> dict:
        events: list[dict] = []
        data = {
            "name": self.name,
            "speed": self.speed,
            "events": events,
            "qgis_version": self.qgis_version,
        }
        for event in self.events:
            class_name = event.__class__.__name__
            serialized_event = dataclasses.asdict(event)  # type: ignore[call-overload]
            serialized_event["type"] = class_name
            events.append(serialized_event)
        return data

    @classmethod
    def deserialize(cls, data: dict) -> "Macro":
        events = []
        for event_data in data["events"]:
            class_name = event_data.pop("type")
            widget_spec_ = event_data.pop("widget_spec")
            widget_spec = WidgetSpec(widget_spec_["widget_class"], widget_spec_["text"])
            event_data["widget_spec"] = widget_spec
            if "position" in event_data:
                position_ = event_data.pop("position")
                position = Position(
                    position_["local_position"], position_["global_position"]
                )
                event_data["position"] = position
            if "positions" in event_data:
                positions_ = event_data.pop("positions")
                positions = [
                    Position(position_["local_position"], position_["global_position"])
                    for position_ in positions_
                ]
                event_data["positions"] = positions

            event_cls = globals()[class_name]
            event = event_cls(**event_data)
            events.append(event)
        return cls(events, data["name"], data["speed"], data["qgis_version"])
