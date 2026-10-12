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

"""Play a macro or a macro workflow from a macro file when QGIS starts.

Playback starts when QGIS has finished its initialization. It can be
requested from a QGIS startup script (``startup.py``)::

    from macro_plugin.startup import play_on_startup

    play_on_startup("/path/to/macros.json", workflow="Digitize")

or with environment variables, for example in a shell script that starts
QGIS::

    export QGIS_MACRO_STARTUP_FILE=/path/to/macros.json
    export QGIS_MACRO_STARTUP_WORKFLOW=Digitize
    export QGIS_MACRO_STARTUP_EXIT=true
    qgis

The workflow and the macro can be given by their name or uid. If neither a
workflow nor a macro is given, the only workflow of the file is played. A
file without workflows plays all of its macros in order.
"""

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from qgis import utils as qgis_utils
from qgis.core import QgsApplication, QgsProcessingFeedback
from qgis.PyQt.QtCore import QObject, QTimer
from qgis_macros.exceptions import MacroNotFoundError, MacroPluginError
from qgis_macros.macro import Macro
from qgis_macros.macro_file import MacroFile
from qgis_macros.macro_workflow import MacroWorkflow
from qgis_plugin_tools.tools.custom_logging import bar_msg
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.tools.messages import MsgBar

from macro_plugin import env
from macro_plugin.playback import play_macros

if TYPE_CHECKING:
    from qgis.gui import QgisInterface

    # Exceptions are not in the QGIS 3 stubs
    QgsProcessingException = Exception
else:
    from qgis.core import QgsProcessingException

LOGGER = logging.getLogger(__name__)

DEFAULT_START_DELAY_MS = 1000

# Keeps the requested playbacks alive until they have ended
_playbacks: list["StartupPlayback"] = []


class _StartupFeedback(QgsProcessingFeedback):
    """Report the progress of the playback to the log and the message bar."""

    def setProgressText(self, text: str | None) -> None:  # noqa: N802
        LOGGER.info(text)

    def pushInfo(self, info: str | None) -> None:  # noqa: N802
        LOGGER.info(info)

    def pushWarning(self, warning: str | None) -> None:  # noqa: N802
        MsgBar.warning(tr("Startup macros"), warning or "")


def _iface() -> "QgisInterface | None":
    """Return the QGIS interface, read at call time since it is set on startup."""
    # The type of the attribute differs between the QGIS versions
    return getattr(qgis_utils, "iface", None)


def _matches(item: Macro | MacroWorkflow, name_or_uid: str) -> bool:
    return name_or_uid in (item.name, item.uid)


class StartupPlayback(QObject):
    """Plays macros of a macro file once QGIS has been initialized."""

    def __init__(
        self,
        path: Path,
        workflow: str | None = None,
        macro: str | None = None,
        *,
        exit_on_finish: bool = False,
        start_delay_ms: int = DEFAULT_START_DELAY_MS,
    ) -> None:
        """Initialize the playback.

        :param path: Path of the macro file.
        :param workflow: Name or uid of the workflow to play.
        :param macro: Name or uid of the macro to play.
        :param exit_on_finish: Whether to quit QGIS when the playback ends.
            The project is closed without saving. The exit code is 1 if the
            playback fails and 0 otherwise.
        :param start_delay_ms: Time to wait after the initialization.
        """
        super().__init__()
        self.path = path
        self.workflow = workflow
        self.macro = macro
        self.exit_on_finish = exit_on_finish
        self.start_delay_ms = start_delay_ms

    def schedule(self) -> None:
        """Start the playback after QGIS has been initialized."""
        iface = _iface()
        main_window = iface.mainWindow() if iface is not None else None
        if main_window is not None and main_window.isVisible():
            # QGIS has already been initialized, e.g. the plugin was reloaded
            self._start_after_delay()
        elif iface is not None and hasattr(iface, "initializationCompleted"):
            iface.initializationCompleted.connect(self._start_after_delay)
        else:
            self._start_after_delay()

    def _start_after_delay(self) -> None:
        QTimer.singleShot(self.start_delay_ms, self.start)

    def start(self) -> None:
        """Load the macro file and play it, blocking until the playback ends."""
        try:
            macros = self.resolve_macros(MacroFile.load(self.path))
            LOGGER.info("Playing %d macros from %s on startup", len(macros), self.path)
            play_macros(macros, _StartupFeedback())
        except (MacroPluginError, QgsProcessingException) as e:
            self._finish(e)
            return
        self._finish()

    def resolve_macros(self, macro_file: MacroFile) -> list[Macro]:
        """Return the macros of *macro_file* to play.

        :raises MacroPluginError: If the macros cannot be chosen.
        """
        if self.workflow is not None and self.macro is not None:
            raise MacroPluginError(tr("Give either a macro workflow or a macro name."))
        if self.macro is not None:
            macros = [m for m in macro_file.macros if _matches(m, self.macro)]
            if not macros:
                raise MacroPluginError(
                    tr("Macro '{}' not found in {}", self.macro, str(self.path))
                )
            return macros[:1]

        workflow = self._choose_workflow(macro_file)
        if workflow is None:
            if not macro_file.macros:
                raise MacroPluginError(
                    tr("Macro file {} does not contain any macros.", str(self.path))
                )
            return list(macro_file.macros)

        try:
            macros = workflow.resolve_macros({m.uid: m for m in macro_file.macros})
        except MacroNotFoundError as e:
            raise MacroPluginError(
                tr("Macro workflow '{}' refers to a missing macro.", workflow.name),
                bar_msg(details=str(e)),
            ) from e
        if not macros:
            raise MacroPluginError(
                tr("Macro workflow '{}' does not contain any macros.", workflow.name)
            )
        return macros

    def _choose_workflow(self, macro_file: MacroFile) -> MacroWorkflow | None:
        """Return the workflow to play, or None if the file has no workflows.

        :raises MacroPluginError: If the workflow cannot be chosen.
        """
        workflows = macro_file.workflows
        if self.workflow is not None:
            workflows = [w for w in workflows if _matches(w, self.workflow)]
            if not workflows:
                raise MacroPluginError(
                    tr(
                        "Macro workflow '{}' not found in {}",
                        self.workflow,
                        str(self.path),
                    )
                )
        elif len(workflows) > 1:
            raise MacroPluginError(
                tr(
                    "Macro file {} contains several macro workflows. "
                    "Give the name or uid of the workflow to play.",
                    str(self.path),
                )
            )
        return workflows[0] if workflows else None

    def _finish(self, error: Exception | None = None) -> None:
        """Report the result and quit QGIS if requested."""
        if error is None:
            MsgBar.info(
                tr("Startup macros played"),
                tr("Macros of {} played successfully.", str(self.path)),
                success=True,
            )
        else:
            details = (
                error.bar_msg.get("details", "")
                if isinstance(error, MacroPluginError)
                else ""
            )
            MsgBar.error(
                tr("Playing startup macros failed: {}", str(error)), details or ""
            )
        if self in _playbacks:
            _playbacks.remove(self)
        if self.exit_on_finish:
            _exit_qgis(0 if error is None else 1)


def _exit_qgis(exit_code: int) -> None:
    """Close the project without saving it and quit QGIS with *exit_code*."""
    # Quitting with the project open crashes QGIS
    iface = _iface()
    if iface is not None and not iface.newProject(promptToSaveFlag=False):
        LOGGER.warning("Could not close the project before quitting QGIS")
    QTimer.singleShot(0, lambda: QgsApplication.exit(exit_code))


def play_on_startup(
    path: str | Path,
    workflow: str | None = None,
    macro: str | None = None,
    *,
    exit_on_finish: bool = False,
    start_delay_ms: int = DEFAULT_START_DELAY_MS,
) -> StartupPlayback:
    """Play a workflow or a macro of a macro file once QGIS has started.

    If neither *workflow* nor *macro* is given, the only workflow of the file is
    played, or all macros if the file has no workflows.

    :param path: Path of the macro file.
    :param workflow: Name or uid of the workflow to play.
    :param macro: Name or uid of the macro to play.
    :param exit_on_finish: Whether to quit QGIS when the playback ends.
        The project is closed without saving. The exit code is 1 if the
        playback fails and 0 otherwise.
    :param start_delay_ms: Time to wait after QGIS has been initialized.
    """
    playback = StartupPlayback(
        Path(path),
        workflow,
        macro,
        exit_on_finish=exit_on_finish,
        start_delay_ms=start_delay_ms,
    )
    _playbacks.append(playback)
    playback.schedule()
    return playback


def play_from_environment() -> StartupPlayback | None:
    """Play the macros requested with the ``QGIS_MACRO_STARTUP_*`` variables.

    The file variable is removed from the environment, so that the macros
    are not played again when the plugin is reloaded.
    """
    path = env.MACRO_STARTUP_FILE.get_optional_value()
    if path is None:
        return None
    del os.environ[env.MACRO_STARTUP_FILE.key]
    return play_on_startup(
        path,
        env.MACRO_STARTUP_WORKFLOW.get_optional_value(),
        env.MACRO_STARTUP_MACRO.get_optional_value(),
        exit_on_finish=bool(env.MACRO_STARTUP_EXIT),
        start_delay_ms=int(env.MACRO_STARTUP_DELAY_MS),
    )
