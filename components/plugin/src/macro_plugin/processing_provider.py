#  Copyright (c) 2026 macro-qgis-plugin contributors.
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
"""Processing providers that expose macros and macro workflows as algorithms.

Each macro and each macro workflow is registered as a parameterless
processing algorithm, so they can be run from the Processing toolbox and used
as steps of graphical models. The algorithm name is the uid of the macro or
workflow and the display name is its current name, so renaming does not break
models that refer to the algorithm.

The providers do not own the macros. Call
:meth:`MacroProcessingProvider.set_macros` and
:meth:`MacroWorkflowProcessingProvider.set_workflows` whenever the available
macros or workflows change to register and deregister the algorithms.

Example::

    from qgis.core import QgsApplication

    provider = MacroProcessingProvider()
    QgsApplication.processingRegistry().addProvider(provider)
    provider.set_macros(macros)
"""

import logging
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from qgis.core import (
    Qgis,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingProvider,
)
from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtGui import QIcon
from qgis_macros.exceptions import MacroNotFoundError
from qgis_macros.macro import Macro
from qgis_macros.macro_workflow import MacroWorkflow
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.tools.resources import resources_path

from macro_plugin.playback import play_macro, play_macros

if TYPE_CHECKING:
    # Exceptions are not in the QGIS 3 stubs
    QgsProcessingException = Exception
else:
    from qgis.core import QgsProcessingException

LOGGER = logging.getLogger(__name__)

MACRO_PROVIDER_ID = "macro"
WORKFLOW_PROVIDER_ID = "macroworkflow"
ICON_PATH = "icons/icon.svg"


def _ordering_help() -> str:
    return tr(
        "The algorithm has no parameters. To run several macros in a fixed "
        "order in a model, set the dependencies of the model steps."
    )


class _ParameterlessAlgorithm(QgsProcessingAlgorithm):
    """Base class of the algorithms that play macros in the main thread."""

    def flags(self) -> Any:  # The flag type differs between QGIS 3 and 4
        """Return the flags. Macros interact with the GUI, so no threading."""
        return super().flags() | Qgis.ProcessingAlgorithmFlag.NoThreading

    def group(self) -> str:
        return ""

    def groupId(self) -> str:  # noqa: N802
        return ""

    def icon(self) -> QIcon:
        return QIcon(resources_path(ICON_PATH))

    def svgIconPath(self) -> str:  # noqa: N802
        return resources_path(ICON_PATH)

    def initAlgorithm(  # noqa: N802
        self,
        configuration: dict[Any, Any] | None = None,
    ) -> None:
        """Define the parameters of the algorithm. Macros have none."""


class MacroAlgorithm(_ParameterlessAlgorithm):
    """Processing algorithm that plays a single macro."""

    def __init__(self, macro: Macro) -> None:
        """Initialize the algorithm.

        :param macro: The macro to play. The algorithm keeps a reference to it,
            so renaming the macro is reflected in the display name.
        """
        super().__init__()
        self._macro = macro

    @property
    def macro(self) -> Macro:
        """The macro played by the algorithm."""
        return self._macro

    def createInstance(self) -> "MacroAlgorithm":  # noqa: N802, D102
        return MacroAlgorithm(self._macro)

    def name(self) -> str:
        """Return the uid of the macro, which is stable across renames."""
        return self._macro.uid

    def displayName(self) -> str:  # noqa: N802, D102
        return self._macro.name or self._macro.uid

    def shortHelpString(self) -> str:  # noqa: N802, D102
        return tr("Plays the macro '{}'.", self.displayName()) + " " + _ordering_help()

    def processAlgorithm(  # noqa: N802
        self,
        parameters: dict[Any, Any],  # noqa: ARG002
        context: QgsProcessingContext,  # noqa: ARG002
        feedback: QgsProcessingFeedback | None,
    ) -> dict[str, Any]:
        """Play the macro and block until the playback has ended."""
        play_macro(self._macro, feedback or QgsProcessingFeedback())
        return {}


class MacroWorkflowAlgorithm(_ParameterlessAlgorithm):
    """Processing algorithm that plays the macros of a workflow in sequence."""

    def __init__(
        self, workflow: MacroWorkflow, macros_by_uid: Mapping[str, Macro]
    ) -> None:
        """Initialize the algorithm.

        :param workflow: The workflow to play. The algorithm keeps a reference
            to it, so changes to the workflow are reflected in the playback.
        :param macros_by_uid: Available macros keyed by their uid. The macros
            of the workflow are resolved from them when the algorithm runs.
        """
        super().__init__()
        self._workflow = workflow
        self._macros_by_uid = macros_by_uid

    @property
    def workflow(self) -> MacroWorkflow:
        """The workflow played by the algorithm."""
        return self._workflow

    def createInstance(self) -> "MacroWorkflowAlgorithm":  # noqa: N802, D102
        return MacroWorkflowAlgorithm(self._workflow, self._macros_by_uid)

    def name(self) -> str:
        """Return the uid of the workflow, which is stable across renames."""
        return self._workflow.uid

    def displayName(self) -> str:  # noqa: N802, D102
        return self._workflow.name or self._workflow.uid

    def shortHelpString(self) -> str:  # noqa: N802, D102
        names = [
            (macro.name or macro.uid) if macro is not None else tr("Missing macro")
            for macro in map(self._macros_by_uid.get, self._workflow.macro_uids)
        ]
        return " ".join(
            (
                tr("Plays the macro workflow '{}'.", self.displayName()),
                tr("Steps: {}", ", ".join(f"{name}" for name in names) or "-"),
                _ordering_help(),
            )
        )

    def processAlgorithm(  # noqa: N802
        self,
        parameters: dict[Any, Any],  # noqa: ARG002
        context: QgsProcessingContext,  # noqa: ARG002
        feedback: QgsProcessingFeedback | None,
    ) -> dict[str, Any]:
        """Play the macros of the workflow and block until they have ended."""
        try:
            macros = self._workflow.resolve_macros(self._macros_by_uid)
        except MacroNotFoundError as e:
            raise QgsProcessingException(
                tr(
                    "Macro workflow '{}' refers to a missing macro: {}",
                    self.displayName(),
                    e,
                )
            ) from e
        if not macros:
            raise QgsProcessingException(
                tr(
                    "Macro workflow '{}' does not contain any macros.",
                    self.displayName(),
                )
            )
        play_macros(macros, feedback or QgsProcessingFeedback())
        return {}


class _MacroProviderBase(QgsProcessingProvider):
    """Common parts of the macro providers."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    def icon(self) -> QIcon:
        return QIcon(resources_path(ICON_PATH))

    def svgIconPath(self) -> str:  # noqa: N802
        return resources_path(ICON_PATH)

    def supportsNonFileBasedOutput(self) -> bool:  # noqa: N802
        return False


class MacroProcessingProvider(_MacroProviderBase):
    """Processing provider with an algorithm for each macro."""

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the provider without macros."""
        super().__init__(parent)
        self._macros: list[Macro] = []

    @property
    def macros(self) -> list[Macro]:
        """The macros registered as algorithms."""
        return list(self._macros)

    def set_macros(self, macros: Iterable[Macro]) -> None:
        """Register an algorithm for each of *macros* and deregister the rest.

        Call this also when a macro is renamed to update the display name.
        """
        self._macros = list(macros)
        self.refreshAlgorithms()

    def id(self) -> str:  # noqa: D102
        return MACRO_PROVIDER_ID

    def name(self) -> str:  # noqa: D102
        return tr("Macros")

    def longName(self) -> str:  # noqa: N802, D102
        return tr("Macros recorded with the macro plugin")

    def loadAlgorithms(self) -> None:  # noqa: N802
        """Add an algorithm for each macro."""
        for macro in self._macros:
            self.addAlgorithm(MacroAlgorithm(macro))


class MacroWorkflowProcessingProvider(_MacroProviderBase):
    """Processing provider with an algorithm for each macro workflow."""

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the provider without workflows."""
        super().__init__(parent)
        self._workflows: list[MacroWorkflow] = []
        self._macros_by_uid: dict[str, Macro] = {}

    @property
    def workflows(self) -> list[MacroWorkflow]:
        """The workflows registered as algorithms."""
        return list(self._workflows)

    def set_workflows(
        self, workflows: Iterable[MacroWorkflow], macros_by_uid: Mapping[str, Macro]
    ) -> None:
        """Register an algorithm for each of *workflows* and deregister the rest.

        :param workflows: The workflows to register.
        :param macros_by_uid: Available macros keyed by their uid, used to
            resolve the steps of the workflows when they are played.
        """
        self._workflows = list(workflows)
        self.set_macros_by_uid(macros_by_uid)
        self.refreshAlgorithms()

    def set_macros_by_uid(self, macros_by_uid: Mapping[str, Macro]) -> None:
        """Update the macros used to resolve the steps of the workflows.

        The algorithms are not reloaded, since they resolve the steps when
        they are run.
        """
        # The algorithms share the mapping, so it is updated in place
        self._macros_by_uid.clear()
        self._macros_by_uid.update(macros_by_uid)

    def id(self) -> str:  # noqa: D102
        return WORKFLOW_PROVIDER_ID

    def name(self) -> str:  # noqa: D102
        return tr("Macro workflows")

    def longName(self) -> str:  # noqa: N802, D102
        return tr("Macro workflows built with the macro plugin")

    def loadAlgorithms(self) -> None:  # noqa: N802
        """Add an algorithm for each workflow."""
        for workflow in self._workflows:
            self.addAlgorithm(MacroWorkflowAlgorithm(workflow, self._macros_by_uid))
