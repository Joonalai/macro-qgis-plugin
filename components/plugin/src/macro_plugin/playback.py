#  Copyright (c) 2026 macro-qgis-plugin contributors.
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
"""Steps shared by the macro playbacks of the panel, processing and startup."""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from qgis.core import QgsApplication, QgsProcessingFeedback
from qgis.PyQt.QtCore import QEventLoop
from qgis_macros.macro import Macro
from qgis_macros.macro_player import (
    MacroPlaybackReport,
    MacroPlaybackStatus,
    MacroPlayer,
)
from qgis_macros.settings import Settings
from qgis_macros.utils import current_locale
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.utils.typing_utils import require

if TYPE_CHECKING:
    # Exceptions are not in the QGIS 3 stubs
    QgsProcessingException = Exception
else:
    from qgis.core import QgsProcessingException


def locale_mismatch_message(macro: Macro) -> str | None:
    """Return a warning if *macro* was recorded with another locale, else None."""
    locale = current_locale()
    if not macro.locale or macro.locale == locale:
        return None
    return tr(
        "Macro '{}' was recorded with locale {} but the current locale "
        "is {}. Widgets and menu items may not be found.",
        macro.name or macro.uid,
        macro.locale,
        locale,
    )


def start_profiling(macro: Macro) -> None:
    """Start profiling the playback of *macro* if profiling is enabled."""
    if Settings.profile_macros.get():
        require(QgsApplication.profiler()).start(
            f"Macro: {macro.name or macro.uid}", Settings.profile_macro_group.get()
        )


def end_profiling() -> None:
    """End profiling the playback started with :func:`start_profiling`."""
    if Settings.profile_macros.get():
        require(QgsApplication.profiler()).end(Settings.profile_macro_group.get())


def play_macro(
    macro: Macro,
    feedback: QgsProcessingFeedback,
    *,
    speed: float | None = None,
    smooth_mouse_movement: bool | None = None,
) -> None:
    """Play *macro* and block until the playback has ended.

    Events are processed while waiting, so the function must be called from
    the main thread. Canceling *feedback* stops the playback.

    :param speed: Playback speed. If None, the speed setting is used.
    :param smooth_mouse_movement: Whether to move the mouse smoothly. If None,
        the setting is used.
    :raises QgsProcessingException: If the playback fails or is canceled.
    """
    if feedback.isCanceled():
        raise QgsProcessingException(tr("Macro playback was canceled."))

    player = MacroPlayer(
        Settings.speed.get() if speed is None else speed,
        smooth_mouse_movement=smooth_mouse_movement,
    )
    loop = QEventLoop()
    reports: list[MacroPlaybackReport] = []

    def playback_ended(report: MacroPlaybackReport) -> None:
        reports.append(report)
        loop.quit()

    player.playback_ended.connect(playback_ended)
    feedback.canceled.connect(player.stop)
    locale_message = locale_mismatch_message(macro)
    if locale_message is not None:
        feedback.pushWarning(locale_message)
    start_profiling(macro)
    try:
        feedback.pushInfo(tr("Playing macro '{}'", macro.name or macro.uid))
        player.play(macro)
        # Playback of an empty macro ends before the loop is entered
        if not reports:
            loop.exec()
    finally:
        feedback.canceled.disconnect(player.stop)
        # The loop also returns if e.g. the application quits
        player.stop()
        end_profiling()

    if not reports:
        raise QgsProcessingException(tr("Macro playback was canceled."))
    report = reports[0]
    if report.status == MacroPlaybackStatus.STOPPED:
        raise QgsProcessingException(tr("Macro playback was canceled."))
    if report.status == MacroPlaybackStatus.FAILURE:
        error = report.error
        details = getattr(error, "bar_msg", {}).get("details")
        message = tr("Macro '{}' playback failed: {}", macro.name or macro.uid, error)
        if details:
            message = f"{message} {details}"
        raise QgsProcessingException(message) from error


def play_macros(
    macros: Sequence[Macro],
    feedback: QgsProcessingFeedback,
    *,
    speed: float | None = None,
    smooth_mouse_movement: bool | None = None,
) -> None:
    """Play *macros* one after another, reporting the progress to *feedback*.

    See :func:`play_macro` for the parameters.

    :raises QgsProcessingException: If a playback fails or is canceled.
    """
    for step, macro in enumerate(macros):
        feedback.setProgressText(
            tr(
                "Playing macro '{}' ({}/{})",
                macro.name or macro.uid,
                step + 1,
                len(macros),
            )
        )
        play_macro(
            macro,
            feedback,
            speed=speed,
            smooth_mouse_movement=smooth_mouse_movement,
        )
        feedback.setProgress(100 * (step + 1) / len(macros))
