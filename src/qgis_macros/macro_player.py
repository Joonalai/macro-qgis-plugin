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
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QElapsedTimer

from qgis_macros.macro import Macro


class MacroPlayer:
    """
    Represents an object used for macro playback with adjustable speed.

    Used to execute a sequence of predefined events at a specified playback speed.
    """

    def __init__(self, playback_speed: float = 1.0) -> None:
        """
        Represents an object used for macro playback with adjustable speed.

        :param playback_speed: Playback speed factor.
        """
        self._speed = playback_speed
        self._timer = QElapsedTimer()

    def play(self, macro: Macro) -> None:
        """Play back the recorded events."""
        playback_speed = self._speed * macro.speed
        for event in macro.events:
            self._timer.restart()
            while self._timer.elapsed() < event.ms_since_last_event * playback_speed:
                QgsApplication.processEvents()
            QgsApplication.processEvents()
            event.perform_event_action()
