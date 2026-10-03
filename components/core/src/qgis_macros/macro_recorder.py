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
"""Event filter-based macro recorder that captures user interactions."""

import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from qgis.PyQt.QtCore import QElapsedTimer, QEvent, QObject
from qgis.PyQt.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from qgis.PyQt.QtWidgets import QApplication, QMenu, QWidget

from qgis_macros import utils
from qgis_macros.macro import (
    LOGGER,
    Macro,
    MacroEvent,
    MacroKeyEvent,
    MacroMenuActionEvent,
    MacroMouseDoubleClickEvent,
    MacroMouseEvent,
    MacroMouseMoveEvent,
    MacroWheelEvent,
    Position,
    WidgetPath,
    WidgetSpec,
)
from qgis_macros.settings import Settings
from qgis_macros.utils import enum_value

if TYPE_CHECKING:
    from qgis.PyQt.QtGui import QAction


@dataclass
class _WatchedMenuItem:
    menu: QMenu
    action: "QAction"
    action_path: list[str]
    release_event: MacroMouseEvent | None


class MacroRecorder(QObject):
    """Manages recording of user actions like mouse and keyboard events.

    Tracks and collects events during a recording session, allowing
    filtered or unfiltered playback of these events for automation.
    """

    def __init__(
        self,
        filter_out_mouse_movements: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        """Initialize the recorder.

        Args:
            filter_out_mouse_movements: If True, leading/trailing mouse
                move events are trimmed from the recording.

        """
        super().__init__(None)
        self._recorded_events: list[MacroEvent] = []
        self._timer = QElapsedTimer()
        self.last_record_time = 0  # Tracks the last timestamp
        self._recording = False
        self._filter_out_mouse_movements = filter_out_mouse_movements
        self._widgets_to_filter_events_out: list[QWidget] = []
        # Mouse events inside popup menus, replaced by a menu action event
        # when a menu item is activated
        self._menu_mouse_events: list[MacroEvent] = []
        self._menu_pressed_buttons: set[int] = set()
        # Menu item under a mouse release, recorded if the menu triggers it
        self._watched_menu_item: _WatchedMenuItem | None = None

    def add_widget_to_filter_events_out(self, widget: QWidget) -> None:
        """Add a widget to filter events out from the recorded events."""
        self._widgets_to_filter_events_out.append(widget)

    def is_recording(self) -> bool:
        """Check if the recorder is currently recording."""
        return self._recording

    def start_recording(self) -> None:
        """Start recording user actions."""
        self._recorded_events.clear()
        self._menu_mouse_events.clear()
        self._menu_pressed_buttons.clear()
        self._recording = True
        self._timer.restart()
        QApplication.instance().installEventFilter(self)

    def stop_recording(self) -> Macro:
        """Stop recording user actions.

        :return: New Macro object with recorded events
        """
        if not self._recording:
            return Macro([])
        self._recording = False
        self._stop_watching_menu_item()
        QApplication.instance().removeEventFilter(self)
        events = (
            self._get_filtered_events()
            if self._filter_out_mouse_movements
            else self._recorded_events
        )
        self._interpolate_mouse_move_events(events)
        macro = Macro(events)
        LOGGER.debug("Recorded macro %s", macro)
        return macro

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        """Event filter to record keyboard and mouse events."""
        if not self._recording or not isinstance(obj, QWidget):
            return super().eventFilter(obj, event)

        widget = cast("QWidget", obj)
        elapsed = self._timer.elapsed()
        ms_since_last_event = elapsed - self.last_record_time
        self.last_record_time = elapsed

        if (
            isinstance(event, QMouseEvent)
            and widget in self._widgets_to_filter_events_out
        ):
            return super().eventFilter(obj, event)

        if event.type() in [QEvent.Type.KeyPress, QEvent.Type.KeyRelease]:
            self._record_key_event(event, widget, ms_since_last_event)
        elif event.type() in [
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
        ]:
            self._stop_watching_menu_item()
            macro_event = self._record_mouse_button_event(
                event, widget, ms_since_last_event
            )
            if event.type() == QEvent.Type.MouseButtonRelease:
                self._watch_menu_item(event, widget, macro_event)
        elif event.type() == QEvent.Type.MouseButtonDblClick:
            self._record_mouse_button_double_click_event(
                event, widget, ms_since_last_event
            )
        elif event.type() == QEvent.Type.MouseMove:
            self._record_mouse_move_event(event, widget)
        elif event.type() == QEvent.Type.Wheel:
            self._record_mouse_wheel_event(event, widget)

        return super().eventFilter(obj, event)

    def _get_filtered_events(self) -> list[MacroEvent]:
        filtered_events: list[MacroEvent] = []

        if not self._recorded_events:
            return []

        # Take just the last mouse position for the first element
        first_element = self._recorded_events[0]
        if isinstance(first_element, MacroMouseMoveEvent):
            first_index = 1
            filtered_events.append(
                MacroMouseMoveEvent(
                    widget_spec=first_element.widget_spec,
                    ms_since_last_event=0,
                    positions=[first_element.positions[-1]],
                    widget_path=first_element.widget_path,
                )
            )
        else:
            first_index = 0

        last_index = len(self._recorded_events) - 1
        if isinstance(self._recorded_events[last_index], MacroMouseMoveEvent):
            last_index -= 1

        for event in self._recorded_events[first_index : last_index + 1]:
            if isinstance(event, MacroMouseMoveEvent) and not self._is_map_canvas_event(
                event
            ):
                # For non-map-canvas moves, keep only the last position
                filtered_events.append(
                    MacroMouseMoveEvent(
                        widget_spec=event.widget_spec,
                        ms_since_last_event=event.ms_since_last_event,
                        positions=[event.positions[-1]],
                        buttons=event.buttons,
                        modifiers=event.modifiers,
                        widget_path=event.widget_path,
                    )
                )
            else:
                filtered_events.append(event)

        return filtered_events

    @staticmethod
    def _is_map_canvas_event(event: MacroMouseMoveEvent) -> bool:
        return event.widget_path is not None and event.widget_path.is_map_canvas

    def _interpolate_mouse_move_events(self, events: list[MacroEvent]) -> None:
        """Interpolate mouse move events."""
        point_count = Settings.move_event_interpolation_count.get()
        for event in events:
            if (
                isinstance(event, MacroMouseMoveEvent)
                and len(event.positions) > point_count
            ):
                event.interpolate_positions(point_count)

    def _record_key_event(
        self, event: QKeyEvent, widget: QWidget, elapsed: int
    ) -> None:
        """Record key press or release events."""
        macro_event = MacroKeyEvent(
            ms_since_last_event=elapsed,
            key=event.key(),
            is_release=event.type() == QEvent.Type.KeyRelease,
            modifiers=enum_value(event.modifiers()),
            text=event.text(),
            widget_spec=WidgetSpec.create(widget),
            widget_path=WidgetPath.create(widget),
        )

        # Do not add if the last mouse button event was the same
        for i in range(len(self._recorded_events) - 1, -1, -1):
            if isinstance((previous_event := self._recorded_events[i]), MacroKeyEvent):
                if (
                    previous_event.key == macro_event.key
                    and previous_event.is_release == macro_event.is_release
                ):
                    return
                break

        self._recorded_events.append(macro_event)

    def _record_mouse_button_event(
        self, event: QMouseEvent, widget: QWidget, elapsed: int
    ) -> MacroMouseEvent | None:
        """Record mouse button press or release events."""
        macro_event = MacroMouseEvent(
            ms_since_last_event=elapsed,
            position=Position.from_event(event),
            is_release=event.type() == QEvent.Type.MouseButtonRelease,
            button=enum_value(event.button()),
            modifiers=enum_value(event.modifiers()),
            widget_spec=WidgetSpec.create(widget),
            widget_path=WidgetPath.create(widget),
        )

        # Do not add if the last mouse button event was the same
        for i in range(len(self._recorded_events) - 1, -1, -1):
            if isinstance(
                (previous_event := self._recorded_events[i]), MacroMouseEvent
            ):
                if (
                    previous_event.button == macro_event.button
                    and previous_event.is_release == macro_event.is_release
                ):
                    return None
                break

        self._recorded_events.append(macro_event)
        if isinstance(widget, QMenu):
            # A release belongs to the menu only if the press was in a menu
            # too. The release of a right click that opened a context menu
            # is kept so that the press has its release on playback.
            if not macro_event.is_release:
                self._menu_pressed_buttons.add(macro_event.button)
                self._menu_mouse_events.append(macro_event)
            elif macro_event.button in self._menu_pressed_buttons:
                self._menu_pressed_buttons.discard(macro_event.button)
                self._menu_mouse_events.append(macro_event)
        return macro_event

    def _watch_menu_item(
        self,
        event: QMouseEvent,
        widget: QWidget,
        release_event: MacroMouseEvent | None,
    ) -> None:
        """Record the menu item under a mouse release if the menu triggers it.

        Menu items are recorded by their texts instead of their positions,
        because submenus open only when their item is hovered long enough.
        The menu decides whether a release activates the item, e.g. the
        release of the right click that opened a context menu does not.
        """
        if not isinstance(widget, QMenu):
            return
        action = widget.actionAt(utils.event_pos(event))
        if action is None or action.menu() is not None or action.isSeparator():
            return
        # The path must be read while the menus are still open
        self._watched_menu_item = _WatchedMenuItem(
            menu=widget,
            action=action,
            action_path=utils.menu_action_path(widget, action),
            release_event=release_event,
        )
        widget.triggered.connect(self._menu_item_triggered)

    def _stop_watching_menu_item(self) -> None:
        watched = self._watched_menu_item
        self._watched_menu_item = None
        if watched is not None:
            with contextlib.suppress(TypeError, RuntimeError):
                watched.menu.triggered.disconnect(self._menu_item_triggered)

    def _menu_item_triggered(self, action: "QAction") -> None:
        """Replace the mouse events inside the menus with a menu action."""
        watched = self._watched_menu_item
        self._stop_watching_menu_item()
        if watched is None or action is not watched.action:
            return

        elapsed = 0
        if (
            watched.release_event is not None
            and self._recorded_events
            and self._recorded_events[-1] is watched.release_event
        ):
            elapsed += self._recorded_events.pop().ms_since_last_event
        while self._recorded_events and any(
            self._recorded_events[-1] is menu_event
            for menu_event in self._menu_mouse_events
        ):
            elapsed += self._recorded_events.pop().ms_since_last_event
        self._menu_mouse_events.clear()
        self._menu_pressed_buttons.clear()

        self._recorded_events.append(
            MacroMenuActionEvent(
                widget_spec=WidgetSpec.create(watched.menu),
                ms_since_last_event=elapsed,
                action_path=watched.action_path,
            )
        )

    def _record_mouse_button_double_click_event(
        self, event: QMouseEvent, widget: QWidget, elapsed: int
    ) -> None:
        """Record mouse double click events."""
        self._recorded_events.append(
            MacroMouseDoubleClickEvent(
                ms_since_last_event=elapsed,
                position=Position.from_event(event),
                button=enum_value(event.button()),
                modifiers=enum_value(event.modifiers()),
                widget_spec=WidgetSpec.create(widget),
                widget_path=WidgetPath.create(widget),
            )
        )

    def _record_mouse_move_event(self, event: QMouseEvent, widget: QWidget) -> None:
        """Record mouse movement events."""
        current_position = Position.from_event(event)
        last_event = self._recorded_events[-1] if self._recorded_events else None
        if isinstance(last_event, MacroMouseMoveEvent):
            last_event.add_position(current_position)
        else:
            move_event = MacroMouseMoveEvent(
                widget_spec=WidgetSpec.create(widget),
                ms_since_last_event=0,
                positions=[current_position],
                buttons=enum_value(event.buttons()),
                modifiers=enum_value(event.modifiers()),
                widget_path=WidgetPath.create(widget),
            )
            self._recorded_events.append(move_event)
            if isinstance(widget, QMenu):
                self._menu_mouse_events.append(move_event)

    def _record_mouse_wheel_event(self, event: QWheelEvent, widget: QWidget) -> None:
        """Record mouse wheel events."""
        self._recorded_events.append(
            MacroWheelEvent(
                WidgetSpec.create(widget),
                ms_since_last_event=0,
                position=Position.from_event(event),
                delta=event.angleDelta().y(),
                phase=event.phase(),
                source=event.source(),
                inverted=event.inverted(),
                widget_path=WidgetPath.create(widget),
            )
        )
