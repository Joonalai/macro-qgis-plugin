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

import enum
import logging
from dataclasses import dataclass
from functools import partial

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QElapsedTimer, QObject, QTimer, pyqtSignal

from qgis_macros.exceptions import MacroPlaybackEndedError
from qgis_macros.macro import Macro, MacroEvent

LOGGER = logging.getLogger(__name__)

MIN_PLAYBACK_SPEED = 0.1


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

    def __init__(self, playback_speed: float = 1.0) -> None:
        """Initialize the player with the given speed factor."""
        super().__init__()
        self._speed = playback_speed
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
        """Scale the recorded delay so that a higher speed means a shorter wait."""
        speed = max(self._speed, MIN_PLAYBACK_SPEED)
        return int(ms_since_last_event / speed) + 15

    def is_playing(self) -> bool:
        """Return whether a macro is being played back."""
        return self._playing

    def play(self, macro: Macro) -> None:
        """Play back the recorded events asynchronously."""
        self._playback_id += 1
        self._playing = True
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

    def _play_next_event(self, playback_id: int) -> None:
        if playback_id != self._playback_id:
            return

        if not self._event_queue:
            # If the queue is empty, playback is complete.
            LOGGER.info("Macro playback completed.")
            self._playback_id += 1
            self._end_playback(MacroPlaybackReport(MacroPlaybackStatus.SUCCESS))
            return

        # Pop the next event from the queue
        macro_event = self._event_queue.pop(0)

        def on_event_finished() -> None:
            # Events call this right before their action, which is skipped if
            # the playback was stopped while the event was being prepared
            if playback_id != self._playback_id:
                raise _PlaybackStoppedError
            QTimer.singleShot(
                self._wait_time(macro_event.ms_since_last_event),
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
