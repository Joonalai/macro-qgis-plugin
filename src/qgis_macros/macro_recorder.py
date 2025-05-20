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
from typing import cast

from qgis.PyQt.QtCore import QElapsedTimer, QEvent, QObject
from qgis.PyQt.QtGui import QKeyEvent, QMouseEvent
from qgis.PyQt.QtWidgets import QApplication, QWidget

from qgis_macros.macro import (
    LOGGER,
    Macro,
    MacroEvent,
    MacroKeyEvent,
    MacroMouseDoubleClickEvent,
    MacroMouseEvent,
    MacroMouseMoveEvent,
    Position,
    WidgetSpec,
)


class MacroRecorder(QObject):
    """
    Manages recording of user actions like mouse and keyboard events.

    Tracks and collects events during a recording session, allowing
    filtered or unfiltered playback of these events for automation.
    """

    def __init__(
        self,
        filter_out_mouse_movements: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        super().__init__(None)
        self._recorded_events: list[MacroEvent] = []
        self._timer = QElapsedTimer()
        self.last_record_time = 0  # Tracks the last timestamp
        self._recording = False
        self._filter_out_mouse_movements = filter_out_mouse_movements
        self._widgets_to_filter_events_out: list[QWidget] = []

    def add_widget_to_filter_events_out(self, widget: QWidget) -> None:
        """Add a widget to filter events out from the recorded events."""
        self._widgets_to_filter_events_out.append(widget)

    def is_recording(self) -> bool:
        """Check if the recorder is currently recording."""
        return self._recording

    def start_recording(self) -> None:
        """Start recording user actions."""
        self._recorded_events.clear()
        self._recording = True
        self._timer.restart()
        QApplication.instance().installEventFilter(self)

    def stop_recording(self) -> Macro:
        """
        Stop recording user actions.

        :return: New Macro object with recorded events
        """
        if not self._recording:
            return Macro([])
        self._recording = False
        QApplication.instance().removeEventFilter(self)
        events = (
            self._get_filtered_events()
            if self._filter_out_mouse_movements
            else self._recorded_events
        )
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

        # TODO: mouse wheel
        if event.type() in [QEvent.KeyPress, QEvent.KeyRelease]:
            self._record_key_event(event, widget, ms_since_last_event)
        elif event.type() in [QEvent.MouseButtonPress, QEvent.MouseButtonRelease]:
            self._record_mouse_button_event(event, widget, ms_since_last_event)
        elif event.type() == QEvent.MouseButtonDblClick:
            self._record_mouse_button_double_click_event(
                event, widget, ms_since_last_event
            )
        elif event.type() == QEvent.MouseMove:
            self._record_mouse_move_event(event, widget)

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
                )
            )
        else:
            first_index = 0

        last_index = len(self._recorded_events) - 1
        if isinstance(self._recorded_events[last_index], MacroMouseMoveEvent):
            last_index -= 1

        filtered_events.extend(self._recorded_events[first_index : last_index + 1])

        return filtered_events

    def _record_key_event(
        self, event: QKeyEvent, widget: QWidget, elapsed: int
    ) -> None:
        """Record key press or release events."""
        macro_event = MacroKeyEvent(
            ms_since_last_event=elapsed,
            key=event.key(),
            is_release=event.type() == QEvent.KeyRelease,
            modifiers=int(event.modifiers()),
            widget_spec=WidgetSpec.create(widget),
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
    ) -> None:
        """Record mouse button press or release events."""
        macro_event = MacroMouseEvent(
            ms_since_last_event=elapsed,
            position=Position.from_event(event),
            is_release=event.type() == QEvent.MouseButtonRelease,
            button=event.button(),
            modifiers=int(event.modifiers()),
            widget_spec=WidgetSpec.create(widget),
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
                    return
                break

        self._recorded_events.append(macro_event)

    def _record_mouse_button_double_click_event(
        self, event: QMouseEvent, widget: QWidget, elapsed: int
    ) -> None:
        """Record mouse double click events."""
        self._recorded_events.append(
            MacroMouseDoubleClickEvent(
                ms_since_last_event=elapsed,
                position=Position.from_event(event),
                button=event.button(),
                modifiers=int(event.modifiers()),
                widget_spec=WidgetSpec.create(widget),
            )
        )

    def _record_mouse_move_event(self, event: QMouseEvent, widget: QWidget) -> None:
        """Record mouse movement events."""
        current_position = Position.from_event(event)
        last_event = self._recorded_events[-1] if self._recorded_events else None
        if isinstance(last_event, MacroMouseMoveEvent):
            last_event.add_position(current_position)
        else:
            self._recorded_events.append(
                MacroMouseMoveEvent(
                    widget_spec=WidgetSpec.create(widget),
                    ms_since_last_event=0,
                    positions=[current_position],
                    buttons=int(event.buttons()),
                    modifiers=int(event.modifiers()),
                )
            )
