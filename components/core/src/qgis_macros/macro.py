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
"""Macro data structures for recording and playing back user interactions.

This module defines the core event types (key, mouse, wheel) and the
:class:`Macro` container that serializes/deserializes recorded sessions.

Example usage::

    from qgis_macros.macro import Macro

    # Deserialize a macro from a dict (e.g. loaded from JSON)
    macro = Macro.deserialize(data)

    # Serialize back
    data = macro.serialize()
"""

import dataclasses
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from qgis.core import Qgis, QgsApplication, QgsLineString
from qgis.PyQt.QtCore import QEvent, QPoint, Qt
from qgis.PyQt.QtGui import QCursor, QMouseEvent, QWheelEvent
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QApplication, QWidget

from qgis_macros import utils
from qgis_macros.constants import (
    MAXIMUM_NEAREST_CANDIDATES,
    MAXIMUM_PARENT_DEPTH,
)
from qgis_macros.exceptions import WidgetNotFoundError
from qgis_macros.utils import enum_value

LOGGER = logging.getLogger(__name__)


@dataclass
class WidgetSpec:
    """Identify a widget by its class name and display text."""

    widget_class: str
    text: str = ""

    @staticmethod
    def create(widget: QWidget) -> "WidgetSpec":
        """Create a WidgetSpec from an existing widget."""
        return WidgetSpec(widget.__class__.__name__, utils.get_widget_text(widget))

    def matches(self, widget: QWidget) -> bool:
        """Return True if *widget* matches this spec's class and text."""
        return (
            widget.__class__.__name__ == self.widget_class
            and self.text == utils.get_widget_text(widget)
        )

    def get_suitable_widget(
        self, point: QPoint, widget: QWidget, level: int = 1
    ) -> QWidget:
        """Find the nearest child widget matching this spec.

        Walk up the widget hierarchy (up to ``MAXIMUM_PARENT_DEPTH`` levels)
        searching for a visible child whose class and text match.

        Raises:
            WidgetNotFoundError: If no matching widget is found.

        """
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
    """Single macro event for Macros."""

    ms_since_last_event: int

    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        """Perform macro event action (e.g., moving mouse, clicking widget)."""
        ...


@dataclass(frozen=True)
class Position:
    """Screen position represented as local and global coordinate pairs."""

    local_position: tuple[int, int]
    global_position: tuple[int, int]

    @staticmethod
    def from_event(event: QMouseEvent | QWheelEvent) -> "Position":
        """Create a Position from a Qt mouse or wheel event."""
        position = utils.event_pos(event)
        global_position = utils.event_global_pos(event)
        return Position(
            (position.x(), position.y()),
            (global_position.x(), global_position.y()),
        )

    @staticmethod
    def from_points(local_point: QPoint, global_point: QPoint) -> "Position":
        """Create a Position from local and global QPoint objects."""
        return Position(
            (local_point.x(), local_point.y()),
            (global_point.x(), global_point.y()),
        )

    @staticmethod
    def interpolate(
        positions: list["Position"], number_of_positions: int
    ) -> list["Position"]:
        """Reduce *positions* to *number_of_positions* by linear interpolation."""
        if len(positions) <= number_of_positions:
            return positions

        def _interpolate(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
            x, y = list(zip(*points, strict=False))
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
            for local_point, global_point in zip(
                local_positions, global_positions, strict=False
            )
        ]

    @property
    def local_point(self) -> QPoint:
        """Return the local position as a QPoint."""
        return QPoint(*self.local_position)

    @property
    def global_point(self) -> QPoint:
        """Return the global position as a QPoint."""
        return QPoint(*self.global_position)

    def widget_corrected_position(self, widget: QWidget) -> "Position":
        """Return a new Position corrected for the widget's current screen location."""
        return Position.from_points(
            self.local_point, widget.mapToGlobal(self.local_point)
        )


default_position = Position((0, 0), (0, 0))


@dataclass
class BaseMacroEvent(ABC):
    """Base class for all macro events."""

    widget_spec: WidgetSpec
    ms_since_last_event: int = 0

    @staticmethod
    def move_cursor(position: tuple[int, int] | QPoint) -> None:
        """Move the mouse cursor to the given screen position."""
        if not isinstance(position, QPoint):
            position = QPoint(*position)
        QCursor.setPos(position)
        QgsApplication.processEvents()

    def get_widget(self, position: Position) -> QWidget:
        """Resolve the target widget at *position*.

        Fall back to a spec-based search if the widget at *position* does not match.
        """
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
        """Return the target widget and a screen-corrected position."""
        widget = self.get_widget(position)
        corrected_position = position.widget_corrected_position(widget)
        return widget, corrected_position

    @abstractmethod
    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        """Execute the event action and call *schedule_next* when done."""
        ...

    def __eq__(self, other: object) -> bool:  # noqa: D105
        if not isinstance(other, BaseMacroEvent):
            return NotImplemented

        return self.widget_spec == other.widget_spec


@dataclass
class MacroKeyEvent(BaseMacroEvent):
    """Keyboard press or release event."""

    key: int = 0
    is_release: bool = False
    modifiers: int = enum_value(Qt.KeyboardModifier.NoModifier)

    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        """Replay the key press or release on the currently focused widget."""
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

    def __eq__(self, other: object) -> bool:  # noqa: D105
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
    """Mouse movement event containing a sequence of positions."""

    positions: list[Position] = field(default_factory=list)
    buttons: int = enum_value(Qt.MouseButton.NoButton)
    modifiers: int = enum_value(Qt.KeyboardModifier.NoModifier)

    def add_position(self, position: Position) -> None:
        """Append a position, ignoring duplicates of the last position."""
        if self.positions and position == self.positions[-1]:
            return
        self.positions.append(position)

    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        """Replay the mouse movement along the recorded positions."""
        if self.buttons != enum_value(Qt.MouseButton.NoButton):
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
        """Replay movement by posting QMouseEvent objects (when buttons are held)."""
        if not self.positions:
            return
        widget = self.get_widget(self.positions[0])

        for position in self.positions:
            corrected_position = position.widget_corrected_position(widget)
            # Create and send mouse move events
            event = QMouseEvent(
                QEvent.Type.MouseMove,
                corrected_position.local_point,
                corrected_position.global_point,
                Qt.MouseButton.NoButton,
                Qt.MouseButtons(self.buttons),
                Qt.KeyboardModifiers(self.modifiers),
            )
            QApplication.postEvent(widget, event)
            QApplication.processEvents()

    def interpolate_positions(self, number_of_positions: int) -> None:
        """Interpolate the positions to a given number of positions."""
        self.positions = Position.interpolate(self.positions, number_of_positions)

    def __eq__(self, other: object) -> bool:  # noqa: D105
        if not isinstance(other, MacroMouseMoveEvent):
            return NotImplemented
        return super().__eq__(other) and (
            self.positions == other.positions
            and self.buttons == other.buttons
            and self.modifiers == other.modifiers
        )

    def __repr__(self) -> str:  # noqa: D105
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
    """Mouse button press or release event."""

    position: Position = default_position
    is_release: bool = False
    button: int = enum_value(Qt.MouseButton.LeftButton)
    modifiers: int = enum_value(Qt.KeyboardModifier.NoModifier)

    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        """Replay the mouse press or release at the recorded position."""
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

    def __eq__(self, other: object) -> bool:  # noqa: D105
        if not isinstance(other, MacroMouseEvent):
            return NotImplemented
        return super().__eq__(other) and (
            self.position == other.position
            and self.button == other.button
            and self.modifiers == other.modifiers
            and self.is_release == other.is_release
        )


@dataclass
class MacroWheelEvent(BaseMacroEvent):
    """Mouse wheel scroll event."""

    position: Position = default_position
    delta: int = 0
    phase: int = 0
    inverted: bool = False
    source: int = 0

    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        """Replay the wheel scroll at the recorded position."""
        widget, corrected_position = self.get_widget_and_corrected_position(
            self.position
        )
        self.move_cursor(corrected_position.global_point)
        schedule_next()
        event = QWheelEvent(
            corrected_position.local_point,
            corrected_position.global_point,
            QPoint(0, self.delta),
            QPoint(0, self.delta),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            self.phase,
            self.inverted,
            self.source,
        )
        QApplication.postEvent(widget, event)
        QApplication.processEvents()

    def __eq__(self, other: object) -> bool:  # noqa: D105
        if not isinstance(other, MacroWheelEvent):
            return NotImplemented
        return super().__eq__(other) and (
            self.position == other.position
            and self.delta == other.delta
            and self.phase == other.phase
            and self.inverted == other.inverted
            and self.source == other.source
        )


@dataclass
class MacroMouseDoubleClickEvent(BaseMacroEvent):
    """Mouse double-click event."""

    position: Position = default_position
    button: int = enum_value(Qt.MouseButton.LeftButton)
    modifiers: int = enum_value(Qt.KeyboardModifier.NoModifier)

    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        """Replay the double-click at the recorded position."""
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

    def __eq__(self, other: object) -> bool:  # noqa: D105
        if not isinstance(other, MacroMouseDoubleClickEvent):
            return NotImplemented
        return super().__eq__(other) and (
            self.position == other.position
            and self.button == other.button
            and self.modifiers == other.modifiers
        )


@dataclass
class Macro:
    """A recorded sequence of user interaction events.

    Example::

        import json
        from pathlib import Path

        from qgis_macros.macro import Macro

        # Load macros from a JSON file
        with Path("macros.json").open() as f:
            data = json.load(f)
        macros = [Macro.deserialize(d) for d in data]

        # Serialize macros back to JSON
        serialized = [m.serialize() for m in macros]
    """

    events: list[MacroEvent]
    name: str | None = None
    speed: float = 1.0
    qgis_version: int = Qgis.versionInt()

    def serialize(self) -> dict:
        """Serialize the macro to a JSON-compatible dict."""
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
        """Construct a Macro from a dict previously produced by :meth:`serialize`."""
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
