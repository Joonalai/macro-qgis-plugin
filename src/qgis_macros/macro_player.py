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
import enum
import logging
from dataclasses import dataclass
from typing import Optional

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QElapsedTimer, QObject, QTimer, pyqtSignal

from qgis_macros.macro import Macro, MacroEvent

LOGGER = logging.getLogger(__name__)


class MacroPlaybackStatus(enum.Enum):
    SUCCESS = enum.auto()
    FAILURE = enum.auto()
    # TODO: implement stopped
    STOPPED = enum.auto()


@dataclass
class MacroPlaybackReport:
    status: MacroPlaybackStatus = MacroPlaybackStatus.SUCCESS
    error: Optional[Exception] = None


class MacroPlayer(QObject):
    """
    Represents an object used for macro playback with adjustable speed.

    Used to execute a sequence of predefined events at a specified playback speed.
    """

    playback_ended = pyqtSignal(MacroPlaybackReport)

    def __init__(self, playback_speed: float = 1.0) -> None:
        """
        Represents an object used for macro playback with adjustable speed.

        :param playback_speed: Playback speed factor.
        """
        super().__init__()
        self._speed = playback_speed
        self._timer = QElapsedTimer()
        self._playback_halted = False
        self._event_queue: list[MacroEvent] = []

    def play(self, macro: Macro) -> None:
        """Play back the recorded events asynchronously."""
        self._playback_halted = False
        self._event_queue = macro.events[:]
        LOGGER.info("Playing macro %s", macro.name)
        self._play_next_event()

    def _play_next_event(self) -> None:
        if self._playback_halted:
            return

        if not self._event_queue:
            # If the queue is empty, playback is complete.
            LOGGER.info("Macro playback completed.")
            self.playback_ended.emit(MacroPlaybackReport(MacroPlaybackStatus.SUCCESS))
            return

        # Pop the next event from the queue
        macro_event = self._event_queue.pop(0)

        def on_event_finished() -> None:
            wait_time = int(macro_event.ms_since_last_event * self._speed) + 5
            QTimer.singleShot(wait_time, self._play_next_event)

        try:
            LOGGER.debug("Playing event: %s", macro_event)
            macro_event.perform_event_action(on_event_finished)
            QgsApplication.processEvents()

        except Exception as e:
            # If an error occurs, halt playback and report failure.
            self._playback_halted = True
            LOGGER.exception("Playing macro stopped due to exception.")
            self.playback_ended.emit(
                MacroPlaybackReport(MacroPlaybackStatus.FAILURE, e)
            )
