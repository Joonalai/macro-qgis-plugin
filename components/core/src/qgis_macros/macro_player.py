#  Copyright (c) 2025-2026 macro-qgis-plugin contributors.
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
"""Asynchronous macro playback engine.

Example::

    from qgis_macros.macro_player import MacroPlayer

    player = MacroPlayer(playback_speed=1.5)
    player.playback_ended.connect(on_playback_finished)
    player.play(macro)
"""

import dataclasses
import enum
import logging
from dataclasses import dataclass
from functools import partial
from typing import ClassVar
from weakref import WeakSet

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QElapsedTimer, QObject, QTimer, pyqtSignal

from qgis_macros.exceptions import MacroPlaybackEndedError
from qgis_macros.macro import Macro, MacroEvent, MacroMouseMoveEvent, Position
from qgis_macros.settings import Settings

LOGGER = logging.getLogger(__name__)

MIN_PLAYBACK_SPEED = 0.1
# Distance and recorded delay between the steps of a smooth mouse movement
SMOOTH_STEP_PX = 12
SMOOTH_STEP_MS = 10
# How often a player checks whether the playbacks it started have ended
NESTED_PLAYBACK_POLL_MS = 50


class MacroPlaybackStatus(enum.Enum):
    """Status of a completed macro playback."""

    SUCCESS = enum.auto()
    FAILURE = enum.auto()
    STOPPED = enum.auto()


@dataclass
class MacroPlaybackReport:
    """Report emitted when macro playback completes."""

    status: MacroPlaybackStatus = MacroPlaybackStatus.SUCCESS
    error: Exception | None = None

    def __post_init__(self) -> None:
        if self.status == MacroPlaybackStatus.FAILURE and self.error is None:
            raise ValueError("Error must be provided if status is failure.")  # noqa: TRY003, EM101


class MacroPlayer(QObject):
    """Represents an object used for macro playback with adjustable speed.

    Used to execute a sequence of predefined events at a specified playback speed.
    """

    playback_ended = pyqtSignal(MacroPlaybackReport)

    _players: ClassVar["WeakSet[MacroPlayer]"] = WeakSet()
    # Incremented for every playback, so that playbacks can be ordered
    _playback_count: ClassVar[int] = 0

    def __init__(
        self,
        playback_speed: float = 1.0,
        *,
        smooth_mouse_movement: bool | None = None,
    ) -> None:
        """Initialize the player.

        :param playback_speed: Speed factor, 2.0 plays twice as fast.
        :param smooth_mouse_movement: Whether to move the mouse in small steps
            along the recorded path. If None, the
            :attr:`~qgis_macros.settings.Settings.smooth_mouse_movement`
            setting is used.
        """
        super().__init__()
        self._smooth_mouse_movement = smooth_mouse_movement
        self._smooth = False
        self._started = 0
        MacroPlayer._players.add(self)
        self._speed = playback_speed
        # The speed of the macro being played, relative to the player speed
        self._macro_speed = 1.0
        self._timer = QElapsedTimer()
        self._playing = False
        self._event_queue: list[MacroEvent] = []
        # Incremented whenever a playback starts or ends, so that the events
        # scheduled by an earlier playback are not played
        self._playback_id = 0

    def set_speed(self, speed: float) -> None:
        """Set the playback speed."""
        self._speed = speed

    def _wait_time(self, ms_since_last_event: int) -> int:
        """Scale the recorded delay so that a higher speed means a shorter wait.

        The speed of the player and the speed of the macro are multiplied.
        """
        speed = max(self._speed * self._macro_speed, MIN_PLAYBACK_SPEED)
        return int(ms_since_last_event / speed) + 15

    def is_playing(self) -> bool:
        """Return whether a macro is being played back."""
        return self._playing

    @property
    def playback_order(self) -> int:
        """Order of the latest playback of the player among all playbacks."""
        return self._started

    def play(self, macro: Macro) -> None:
        """Play back the recorded events asynchronously."""
        self._playback_id += 1
        self._playing = True
        MacroPlayer._playback_count += 1
        self._started = MacroPlayer._playback_count
        self._macro_speed = macro.speed
        self._smooth = (
            Settings.smooth_mouse_movement.get()
            if self._smooth_mouse_movement is None
            else self._smooth_mouse_movement
        )
        self._event_queue = macro.events[:]
        LOGGER.info("Playing macro %s", macro.name)
        self._play_next_event(self._playback_id)

    def stop(self) -> None:
        """Stop the ongoing playback.

        The remaining events are not played and :attr:`playback_ended` is
        emitted with :attr:`MacroPlaybackStatus.STOPPED`. Does nothing if no
        macro is being played.
        """
        if not self._playing:
            return
        self._halt()
        LOGGER.info("Macro playback stopped.")
        self._end_playback(MacroPlaybackReport(MacroPlaybackStatus.STOPPED))

    def _halt(self) -> None:
        # Events scheduled by the halted playback are not played
        self._playback_id += 1
        self._event_queue.clear()

    def _end_playback(self, report: MacroPlaybackReport) -> None:
        self._playing = False
        self.playback_ended.emit(report)

    @staticmethod
    def _smooth_steps(event: MacroMouseMoveEvent) -> list[MacroMouseMoveEvent]:
        """Split a mouse movement into steps of one position each.

        The steps follow the recorded path a few pixels apart. The first step
        keeps the recorded delay of the movement.
        """
        positions = Position.densify(event.positions, SMOOTH_STEP_PX)
        if len(positions) <= 1:
            return [event]
        return [
            dataclasses.replace(
                event,
                positions=[position],
                ms_since_last_event=event.ms_since_last_event
                if i == 0
                else SMOOTH_STEP_MS,
            )
            for i, position in enumerate(positions)
        ]

    def _nested_playback_running(self) -> bool:
        """Return whether a playback started after this one is running.

        E.g. a click on the run button of a processing algorithm plays a
        macro workflow, and the macro continues only after the workflow.
        """
        return any(
            player is not self
            and player.is_playing()
            and player.playback_order > self.playback_order
            for player in list(MacroPlayer._players)
        )

    def _play_next_event(self, playback_id: int) -> None:
        if playback_id != self._playback_id:
            return

        if self._nested_playback_running():
            QTimer.singleShot(
                NESTED_PLAYBACK_POLL_MS, partial(self._play_next_event, playback_id)
            )
            return

        if not self._event_queue:
            # If the queue is empty, playback is complete.
            LOGGER.info("Macro playback completed.")
            self._playback_id += 1
            self._end_playback(MacroPlaybackReport(MacroPlaybackStatus.SUCCESS))
            return

        # Pop the next event from the queue
        macro_event = self._event_queue.pop(0)
        if self._smooth and isinstance(macro_event, MacroMouseMoveEvent):
            steps = self._smooth_steps(macro_event)
            macro_event = steps[0]
            self._event_queue[:0] = steps[1:]

        def on_event_finished() -> None:
            # Events call this right before their action, which is skipped if
            # the playback was stopped while the event was being prepared
            if playback_id != self._playback_id:
                raise _PlaybackStoppedError
            # The delay of an event is the time before it was recorded
            next_delay = (
                self._event_queue[0].ms_since_last_event if self._event_queue else 0
            )
            QTimer.singleShot(
                self._wait_time(next_delay),
                partial(self._play_next_event, playback_id),
            )

        try:
            LOGGER.debug("Playing event: %s", macro_event)
            macro_event.perform_event_action(on_event_finished)
            QgsApplication.processEvents()

        except _PlaybackStoppedError:
            LOGGER.debug("Skipped event of a stopped playback: %s", macro_event)

        except Exception as e:
            if playback_id != self._playback_id:
                LOGGER.exception("Event of a stopped playback failed.")
                return
            # If an error occurs, halt playback and report failure.
            self._halt()
            LOGGER.exception("Playing macro stopped due to exception.")
            self._end_playback(
                MacroPlaybackReport(
                    MacroPlaybackStatus.FAILURE, MacroPlaybackEndedError(e)
                )
            )


class _PlaybackStoppedError(Exception):
    """Raised to skip the action of an event when its playback was stopped."""
