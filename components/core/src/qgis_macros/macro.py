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
import sys
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Protocol

from qgis.core import Qgis, QgsApplication, QgsLineString
from qgis.PyQt.QtCore import QEvent, QPoint, QPointF, Qt
from qgis.PyQt.QtGui import (
    QContextMenuEvent,
    QCursor,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QWheelEvent,
)
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QApplication, QMenu, QWidget
from qgis_plugin_tools.utils.typing_utils import require

from qgis_macros import utils
from qgis_macros.constants import (
    ASCII_KEY_LIMIT,
    MAXIMUM_NEAREST_CANDIDATES,
    MAXIMUM_PARENT_DEPTH,
)
from qgis_macros.exceptions import MenuActionNotFoundError, WidgetNotFoundError
from qgis_macros.utils import enum_value

if TYPE_CHECKING:
    from qgis.PyQt.QtGui import QAction

LOGGER = logging.getLogger(__name__)

# The PyQt6 stubs declare the static QTest methods as instance methods,
# which makes the widget argument look like a wrong self argument
_qtest: Any = QTest


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
        if (
            level < MAXIMUM_PARENT_DEPTH
            and (parent := widget.parentWidget()) is not None
        ):
            return self.get_suitable_widget(point, parent, level + 1)
        raise WidgetNotFoundError(self.widget_class, self.text)


@dataclass(frozen=True)
class WidgetPathNode:
    """A single node in a widget path, identifying a widget within its parent."""

    widget_class: str
    sibling_index: int
    text: str = ""

    def matches(self, widget: QWidget) -> bool:
        """Check if the given widget matches this node's criteria."""
        return (
            widget.__class__.__name__ == self.widget_class
            and self.text == utils.get_widget_text(widget)
        )


@dataclass
class WidgetPath:
    """Path from a top-level window down to a target widget.

    Each node identifies a widget by its class name, text, and index
    among same-class siblings. This allows reliable widget lookup even
    when widgets lack objectNames or shift position on screen.
    """

    window_title: str
    nodes: list[WidgetPathNode]
    is_map_canvas: bool = False

    @staticmethod
    def create(widget: QWidget) -> "WidgetPath":
        """Create a WidgetPath from a given widget.

        by traversing its parent hierarchy.
        """
        is_map_canvas = utils.is_object_map_canvas(widget)
        nodes: list[WidgetPathNode] = []
        current = widget
        while current is not None:
            if current.isWindow():
                window_title = current.windowTitle()
                nodes.reverse()
                return WidgetPath(window_title, nodes, is_map_canvas)
            parent = current.parentWidget()
            if parent is not None:
                sibling_index = utils.get_sibling_index(current, parent)
                nodes.append(
                    WidgetPathNode(
                        widget_class=current.__class__.__name__,
                        sibling_index=sibling_index,
                        text=utils.get_widget_text(current),
                    )
                )
            current = parent
        return WidgetPath("", nodes, is_map_canvas)

    def find_widget(self) -> QWidget | None:
        """Walk the path from the top-level window to find the target widget."""
        window = self._find_window()
        if window is None:
            return None

        current = window
        for node in self.nodes:
            child = self._find_child(current, node)
            if child is None:
                return None
            current = child
        return current

    def _find_window(self) -> QWidget | None:
        for widget in QApplication.topLevelWidgets():
            if widget.isVisible() and widget.windowTitle() == self.window_title:
                return widget
        return None

    @staticmethod
    def _find_child(parent: QWidget, node: WidgetPathNode) -> QWidget | None:
        same_class_children = [
            child
            for child in parent.findChildren(QWidget)
            if child.__class__.__name__ == node.widget_class
            and child.parentWidget() is parent
        ]
        # First try exact match by sibling index and text
        if node.sibling_index < len(same_class_children):
            candidate = same_class_children[node.sibling_index]
            if node.matches(candidate):
                return candidate

        # Fallback: find by text match among same-class siblings
        if node.text:
            for child in same_class_children:
                if node.matches(child):
                    return child

        # Last resort: return by index alone
        if node.sibling_index < len(same_class_children):
            return same_class_children[node.sibling_index]
        return None


class MacroEvent(Protocol):
    """Single macro event for Macros."""

    # Events are dataclasses so that they can be serialized
    __dataclass_fields__: ClassVar[dict[str, dataclasses.Field[Any]]]
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
                require(line.interpolatePoint(point_distance))
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
class BaseMacroEvent(ABC):  # noqa: PLW1641
    """Base class for all macro events."""

    widget_spec: WidgetSpec
    ms_since_last_event: int = 0
    widget_path: WidgetPath | None = None

    @staticmethod
    def move_cursor(position: tuple[int, int] | QPoint) -> None:
        """Move the mouse cursor to the given screen position."""
        if not isinstance(position, QPoint):
            position = QPoint(*position)
        QCursor.setPos(position)
        QgsApplication.processEvents()

    def _use_coordinate_lookup(self) -> bool:
        """Check if this event targets the map canvas and should use coordinates."""
        return self.widget_path is not None and self.widget_path.is_map_canvas

    def get_widget(self, position: Position) -> QWidget:
        """Resolve the target widget at *position*.

        Fall back to a spec-based search if the widget at *position* does not match.
        """
        # Try widget path lookup first (unless targeting map canvas)
        if self.widget_path is not None and not self._use_coordinate_lookup():
            widget = self.widget_path.find_widget()
            if widget is not None:
                widget.setFocus()
                return widget
            LOGGER.debug(
                "Widget path lookup failed, falling back to position-based lookup"
            )

        # Fallback: position-based lookup
        global_point = position.global_point
        widget = QApplication.widgetAt(global_point)
        if not widget:
            raise WidgetNotFoundError(
                self.widget_spec.widget_class, self.widget_spec.text
            )
        if not self.widget_spec.matches(widget):
            # Sometimes dialogs might appear in a slightly different position
            parent = widget.parentWidget()
            if parent is None:
                raise WidgetNotFoundError(
                    self.widget_spec.widget_class, self.widget_spec.text
                )
            widget = self.widget_spec.get_suitable_widget(global_point, parent)
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseMacroEvent):
            return NotImplemented

        return self.widget_spec == other.widget_spec


@dataclass
class MacroKeyEvent(BaseMacroEvent):  # noqa: PLW1641
    """Keyboard press or release event."""

    key: int = 0
    is_release: bool = False
    modifiers: int = enum_value(Qt.KeyboardModifier.NoModifier)
    text: str = ""

    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        """Replay the key press or release on the currently focused widget."""
        widget = QApplication.focusWidget()
        QgsApplication.processEvents()
        schedule_next()
        key = Qt.Key(self.key)
        modifiers = utils.keyboard_modifiers(self.modifiers)
        if self._needs_recorded_text():
            self._send_key_event_with_text(widget, key, modifiers)
        elif not self.is_release:
            _qtest.keyPress(widget, key, modifiers)
        else:
            _qtest.keyRelease(widget, key, modifiers)

    def _needs_recorded_text(self) -> bool:
        """Check if the recorded text differs from the text QTest would use.

        QTest derives the text from the key code alone, which ignores e.g. the
        shift modifier and non-ASCII characters. Control characters (e.g. from
        Ctrl shortcuts) are left to QTest as before.
        """
        if not self.text or not self.text.isprintable():
            return False
        derived_text = chr(self.key).lower() if self.key < ASCII_KEY_LIMIT else None
        return self.text != derived_text

    def _send_key_event_with_text(
        self, widget: QWidget | None, key: Qt.Key, modifiers: Qt.KeyboardModifier
    ) -> None:
        # QTest.sendKeyEvent is not available in PyQt5 and PyQt6 only exposes
        # its single char overload, which accepts one latin-1 byte
        try:
            encoded_text = self.text.encode("latin-1")
        except UnicodeEncodeError:
            encoded_text = b""
        if len(encoded_text) == 1 and hasattr(_qtest, "sendKeyEvent"):
            action = (
                QTest.KeyAction.Release if self.is_release else QTest.KeyAction.Press
            )
            _qtest.sendKeyEvent(action, widget, key, encoded_text, modifiers)
            return

        # Shortcuts are not triggered by events sent directly to the widget
        event_type = QEvent.Type.KeyRelease if self.is_release else QEvent.Type.KeyPress
        if widget is not None:
            QApplication.sendEvent(
                widget, QKeyEvent(event_type, key, modifiers, self.text)
            )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MacroKeyEvent):
            return NotImplemented
        return super().__eq__(other) and (
            self.ms_since_last_event == other.ms_since_last_event
            and self.key == other.key
            and self.is_release == other.is_release
            and self.modifiers == other.modifiers
            and self.text == other.text
        )


@dataclass
class MacroMouseMoveEvent(BaseMacroEvent):  # noqa: PLW1641
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
            # Create and send mouse move events. Qt 6 accepts only QPointF.
            event = QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(corrected_position.local_point),
                QPointF(corrected_position.global_point),
                Qt.MouseButton.NoButton,
                utils.mouse_buttons(self.buttons),
                utils.keyboard_modifiers(self.modifiers),
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
class MacroMouseEvent(BaseMacroEvent):  # noqa: PLW1641
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
            _qtest.mousePress(
                widget,
                Qt.MouseButton(self.button),
                utils.keyboard_modifiers(self.modifiers),
                corrected_position.local_point,
            )
        else:
            _qtest.mouseRelease(
                widget,
                Qt.MouseButton(self.button),
                utils.keyboard_modifiers(self.modifiers),
                corrected_position.local_point,
            )
        if self._triggers_context_menu():
            # Qt creates the context menu event when the window receives the
            # mouse event, which QTest bypasses by sending it to the widget
            QApplication.postEvent(
                widget,
                QContextMenuEvent(
                    QContextMenuEvent.Reason.Mouse,
                    corrected_position.local_point,
                    corrected_position.global_point,
                    utils.keyboard_modifiers(self.modifiers),
                ),
            )

    def _triggers_context_menu(self) -> bool:
        """Check if Qt would open a context menu for this event."""
        return (
            self.button == enum_value(Qt.MouseButton.RightButton)
            and self.is_release == _context_menu_opens_on_release()
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
class MacroWheelEvent(BaseMacroEvent):  # noqa: PLW1641
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
            QPointF(corrected_position.local_point),
            QPointF(corrected_position.global_point),
            QPoint(0, self.delta),
            QPoint(0, self.delta),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase(self.phase),
            self.inverted,
            Qt.MouseEventSource(self.source),
        )
        QApplication.postEvent(widget, event)
        QApplication.processEvents()

    def __eq__(self, other: object) -> bool:
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
class MacroMouseDoubleClickEvent(BaseMacroEvent):  # noqa: PLW1641
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
        _qtest.mouseDClick(
            widget,
            Qt.MouseButton(self.button),
            utils.keyboard_modifiers(self.modifiers),
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
class MacroMenuActionEvent(BaseMacroEvent):  # noqa: PLW1641
    """Activation of a menu item in an open popup menu.

    The item is identified by the texts of the menu items leading to it, so
    that submenus are opened on playback regardless of the menu positions.
    """

    action_path: list[str] = field(default_factory=list)

    def perform_event_action(self, schedule_next: Callable[[], None]) -> None:
        """Open the submenus on the path and activate the menu item."""
        menu, action = self._find_root_action()
        for text in self.action_path[1:]:
            menu = self._open_submenu(menu, action)
            action = self._find_action(menu, text)
        if action.menu() is not None:
            raise MenuActionNotFoundError(self.action_path)

        menu.setActiveAction(action)
        schedule_next()
        # Activate the item like a user would, so that the menus close and
        # QMenu.exec returns the activated action
        _qtest.keyClick(menu, Qt.Key.Key_Return)

    def _find_root_action(self) -> tuple[QMenu, "QAction"]:
        if self.action_path:
            for menu in utils.visible_menus():
                action = _find_menu_action(menu, self.action_path[0])
                if action is not None:
                    return menu, action
        raise MenuActionNotFoundError(self.action_path)

    def _find_action(self, menu: QMenu, text: str) -> "QAction":
        action = _find_menu_action(menu, text)
        if action is None:
            raise MenuActionNotFoundError(self.action_path)
        return action

    def _open_submenu(self, menu: QMenu, action: "QAction") -> QMenu:
        submenu = action.menu()
        if submenu is None:
            raise MenuActionNotFoundError(self.action_path)
        # Making the item active opens its submenu
        menu.setActiveAction(action)
        QgsApplication.processEvents()
        if not submenu.isVisible():
            raise MenuActionNotFoundError(self.action_path)
        return submenu

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MacroMenuActionEvent):
            return NotImplemented
        return super().__eq__(other) and self.action_path == other.action_path


def _find_menu_action(menu: QMenu, text: str) -> "QAction | None":
    """Return the visible and enabled item of *menu* with *text*."""
    return next(
        (
            action
            for action in menu.actions()
            if action.isVisible()
            and action.isEnabled()
            and not action.isSeparator()
            and utils.menu_item_text(action) == text
        ),
        None,
    )


def _context_menu_opens_on_release() -> bool:
    """Check if context menus open on mouse release instead of press."""
    # The trigger is configurable since Qt 6.8
    context_menu_trigger = getattr(
        QGuiApplication.styleHints(), "contextMenuTrigger", None
    )
    trigger_type = getattr(Qt, "ContextMenuTrigger", None)
    if context_menu_trigger is not None and trigger_type is not None:
        return context_menu_trigger() == trigger_type.Release
    return sys.platform == "win32"


def new_macro_uid() -> str:
    """Return a unique macro identifier that sorts by creation time."""
    return f"{time.time_ns():020d}_{uuid.uuid4().hex[:8]}"


@dataclass
class Macro:
    """A recorded sequence of user interaction events.

    Example::

        from pathlib import Path

        from qgis_macros.macro_file import MacroFile

        # Load macros from a file saved by the macro panel
        macros = MacroFile.load(Path("macros.json")).macros

        # Save macros to a file
        MacroFile(macros).save(Path("macros.json"))
    """

    events: list[MacroEvent]
    name: str | None = None
    speed: float = 1.0
    qgis_version: int = Qgis.versionInt()
    uid: str = field(default_factory=new_macro_uid, compare=False)

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
            serialized_event = dataclasses.asdict(event)
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
            widget_path_data = event_data.pop("widget_path", None)
            if widget_path_data is not None:
                nodes = [
                    WidgetPathNode(
                        widget_class=node["widget_class"],
                        sibling_index=node["sibling_index"],
                        text=node.get("text", ""),
                    )
                    for node in widget_path_data["nodes"]
                ]
                event_data["widget_path"] = WidgetPath(
                    window_title=widget_path_data["window_title"],
                    nodes=nodes,
                    is_map_canvas=widget_path_data.get("is_map_canvas", False),
                )

            event_cls = globals()[class_name]
            event = event_cls(**event_data)
            events.append(event)
        return cls(events, data["name"], data["speed"], data["qgis_version"])
