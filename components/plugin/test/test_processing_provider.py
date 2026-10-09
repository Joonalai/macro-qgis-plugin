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
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from macro_test_utils import macro_utils
from macro_test_utils.utils import Dialog, WidgetInfo
from qgis import processing
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsProcessingContext,
    QgsProcessingFeedback,
)
from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtGui import QCursor
from qgis_macros.macro import Macro
from qgis_macros.macro_workflow import MacroWorkflow
from qgis_plugin_tools.utils.typing_utils import require

from macro_plugin import processing_provider
from macro_plugin.processing_provider import (
    MACRO_PROVIDER_ID,
    WORKFLOW_PROVIDER_ID,
    MacroAlgorithm,
    MacroProcessingProvider,
    MacroWorkflowAlgorithm,
    MacroWorkflowProcessingProvider,
    QgsProcessingException,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from pytestqt.qtbot import QtBot
    from qgis.PyQt.QtWidgets import QWidget

TIMEOUT = 1000


class RecordingFeedback(QgsProcessingFeedback):
    """Feedback that keeps the progress texts."""

    def __init__(self) -> None:
        super().__init__()
        self.progress_texts: list[str] = []
        self.warnings: list[str] = []

    def setProgressText(self, text: str | None) -> None:  # noqa: N802
        self.progress_texts.append(text or "")

    def pushWarning(self, warning: str | None) -> None:  # noqa: N802
        self.warnings.append(warning or "")


@pytest.fixture
def feedback() -> RecordingFeedback:
    return RecordingFeedback()


@pytest.fixture
def context() -> QgsProcessingContext:
    return QgsProcessingContext()


@pytest.fixture
def dialog(qtbot: "QtBot", qgis_parent: "QWidget") -> Dialog:
    dialog = Dialog(qgis_parent)
    qtbot.addWidget(dialog)
    dialog.show()
    QCursor.setPos(dialog.pos())
    qtbot.mouseMove(dialog)
    qtbot.wait(1)
    return dialog


def _click_macro(dialog: Dialog, name: str, delay_ms: int = 0) -> Macro:
    button = WidgetInfo.from_widget("button", dialog.button)
    return Macro(
        events=[
            macro_utils.mouse_move_macro_event(button),
            *macro_utils.widget_clicking_macro_events(button, elapsed=(delay_ms, 0)),
        ],
        name=name,
    )


@pytest.fixture
def click_macro(dialog: Dialog) -> Macro:
    return _click_macro(dialog, "click")


@pytest.fixture
def macros(click_macro: Macro) -> list[Macro]:
    return [click_macro, Macro(events=[], name="empty")]


@pytest.fixture
def macro_provider(
    qgis_processing: None, macros: list[Macro]
) -> Iterator[MacroProcessingProvider]:
    provider = MacroProcessingProvider()
    registry = require(QgsApplication.processingRegistry())
    assert registry.addProvider(provider)
    provider.set_macros(macros)
    yield provider
    registry.removeProvider(provider)


@pytest.fixture
def workflow(macros: list[Macro]) -> MacroWorkflow:
    return MacroWorkflow("workflow", [macros[0].uid, macros[1].uid, macros[0].uid])


@pytest.fixture
def workflow_provider(
    qgis_processing: None, macros: list[Macro], workflow: MacroWorkflow
) -> Iterator[MacroWorkflowProcessingProvider]:
    provider = MacroWorkflowProcessingProvider()
    registry = require(QgsApplication.processingRegistry())
    assert registry.addProvider(provider)
    provider.set_workflows([workflow], {macro.uid: macro for macro in macros})
    yield provider
    registry.removeProvider(provider)


def test_macro_provider_registers_an_algorithm_for_each_macro(
    macro_provider: MacroProcessingProvider, macros: list[Macro]
) -> None:
    registry = require(QgsApplication.processingRegistry())
    assert registry.providerById(MACRO_PROVIDER_ID) is macro_provider

    algorithms = macro_provider.algorithms()
    assert [alg.name() for alg in algorithms] == [macro.uid for macro in macros]
    assert [alg.displayName() for alg in algorithms] == ["click", "empty"]
    assert [alg.id() for alg in algorithms] == [
        f"{MACRO_PROVIDER_ID}:{macro.uid}" for macro in macros
    ]
    assert registry.algorithmById(f"{MACRO_PROVIDER_ID}:{macros[0].uid}") is not None
    for alg in algorithms:
        assert isinstance(alg, MacroAlgorithm)
        assert alg.flags() & Qgis.ProcessingAlgorithmFlag.NoThreading
        assert not alg.parameterDefinitions()
        assert alg.group() == ""
        assert "click" in algorithms[0].shortHelpString()


def test_macro_provider_set_macros_replaces_and_renames_algorithms(
    macro_provider: MacroProcessingProvider, macros: list[Macro]
) -> None:
    new_macro = Macro(events=[], name="new")
    macros[0].name = "renamed"

    macro_provider.set_macros([macros[0], new_macro])

    assert [alg.displayName() for alg in macro_provider.algorithms()] == [
        "renamed",
        "new",
    ]
    assert macro_provider.macros == [macros[0], new_macro]
    registry = require(QgsApplication.processingRegistry())
    assert registry.algorithmById(f"{MACRO_PROVIDER_ID}:{macros[1].uid}") is None

    macro_provider.set_macros([])

    assert macro_provider.algorithms() == []


def test_macro_algorithm_plays_the_macro(
    macro_provider: MacroProcessingProvider,
    click_macro: Macro,
    dialog: Dialog,
    feedback: RecordingFeedback,
    context: QgsProcessingContext,
    qtbot: "QtBot",
) -> None:
    algorithm = require(macro_provider.algorithm(click_macro.uid))

    with qtbot.waitSignal(dialog.button.clicked, timeout=TIMEOUT):
        result = processing.run(algorithm, {}, feedback=feedback, context=context)

    assert result == {}


def test_macro_algorithm_can_be_run_by_id(
    macro_provider: MacroProcessingProvider,
    macros: list[Macro],
    feedback: RecordingFeedback,
    context: QgsProcessingContext,
) -> None:
    empty_macro = macros[1]

    result = processing.run(
        f"{MACRO_PROVIDER_ID}:{empty_macro.uid}",
        {},
        feedback=feedback,
        context=context,
    )

    assert result == {}


def test_macro_algorithm_fails_when_playback_fails(
    macro_provider: MacroProcessingProvider,
    click_macro: Macro,
    dialog: Dialog,
    feedback: RecordingFeedback,
    context: QgsProcessingContext,
) -> None:
    dialog.close()
    algorithm = require(macro_provider.algorithm(click_macro.uid))

    with pytest.raises(QgsProcessingException, match=r"'click'.*not found"):
        processing.run(algorithm, {}, feedback=feedback, context=context)


def test_macro_algorithm_can_be_canceled(
    macro_provider: MacroProcessingProvider,
    dialog: Dialog,
    feedback: RecordingFeedback,
    context: QgsProcessingContext,
    qtbot: "QtBot",
) -> None:
    slow_macro = _click_macro(dialog, "slow", delay_ms=10_000)
    macro_provider.set_macros([slow_macro])
    algorithm = require(macro_provider.algorithm(slow_macro.uid))
    QTimer.singleShot(50, feedback.cancel)

    with (
        qtbot.assertNotEmitted(dialog.button.clicked, wait=100),
        pytest.raises(QgsProcessingException, match="canceled"),
    ):
        processing.run(algorithm, {}, feedback=feedback, context=context)


def test_macro_algorithm_fails_if_event_loop_exits_before_playback_ends(
    macro_provider: MacroProcessingProvider,
    click_macro: Macro,
    feedback: RecordingFeedback,
    context: QgsProcessingContext,
    mocker: "MockerFixture",
) -> None:
    # E.g. the application quits while the macro is played
    mocker.patch.object(processing_provider, "QEventLoop")
    mocker.patch.object(processing_provider.MacroPlayer, "play")
    algorithm = require(macro_provider.algorithm(click_macro.uid))

    with pytest.raises(QgsProcessingException, match="canceled"):
        processing.run(algorithm, {}, feedback=feedback, context=context)


def test_macro_algorithm_warns_about_another_locale(
    macro_provider: MacroProcessingProvider,
    feedback: RecordingFeedback,
    context: QgsProcessingContext,
) -> None:
    macro = Macro(events=[], name="foreign", locale="xx_XX")
    macro_provider.set_macros([macro])
    algorithm = require(macro_provider.algorithm(macro.uid))

    processing.run(algorithm, {}, feedback=feedback, context=context)

    assert len(feedback.warnings) == 1
    assert "xx_XX" in feedback.warnings[0]


def test_workflow_provider_registers_an_algorithm_for_each_workflow(
    workflow_provider: MacroWorkflowProcessingProvider,
    workflow: MacroWorkflow,
) -> None:
    registry = require(QgsApplication.processingRegistry())
    assert registry.providerById(WORKFLOW_PROVIDER_ID) is workflow_provider

    algorithms = workflow_provider.algorithms()
    assert len(algorithms) == 1
    algorithm = algorithms[0]
    assert isinstance(algorithm, MacroWorkflowAlgorithm)
    assert algorithm.name() == workflow.uid
    assert algorithm.displayName() == "workflow"
    assert algorithm.flags() & Qgis.ProcessingAlgorithmFlag.NoThreading
    assert not algorithm.parameterDefinitions()
    assert "click, empty, click" in algorithm.shortHelpString()
    assert workflow_provider.workflows == [workflow]


def test_workflow_provider_set_workflows_replaces_algorithms(
    workflow_provider: MacroWorkflowProcessingProvider,
    workflow: MacroWorkflow,
) -> None:
    other = MacroWorkflow("other", ["missing"])

    workflow_provider.set_workflows([workflow, other], {})

    algorithms = workflow_provider.algorithms()
    assert [alg.displayName() for alg in algorithms] == ["workflow", "other"]
    assert "Missing macro" in algorithms[1].shortHelpString()


def test_workflow_algorithm_plays_the_macros_in_sequence(
    workflow_provider: MacroWorkflowProcessingProvider,
    workflow: MacroWorkflow,
    dialog: Dialog,
    feedback: RecordingFeedback,
    context: QgsProcessingContext,
    qtbot: "QtBot",
) -> None:
    algorithm = require(workflow_provider.algorithm(workflow.uid))
    clicks = []
    dialog.button.clicked.connect(lambda *_: clicks.append(1))

    result = processing.run(algorithm, {}, feedback=feedback, context=context)

    assert result == {}
    assert len(clicks) == 2
    assert feedback.progress_texts == [
        "Playing macro 'click' (1/3)",
        "Playing macro 'empty' (2/3)",
        "Playing macro 'click' (3/3)",
    ]
    assert feedback.progress() == 100


@pytest.mark.parametrize(
    ("macro_uids", "expected_error"),
    [(["missing"], "missing macro"), ([], "does not contain any macros")],
    ids=["missing_macro", "empty"],
)
def test_workflow_algorithm_fails_when_it_cannot_be_played(
    workflow_provider: MacroWorkflowProcessingProvider,
    feedback: RecordingFeedback,
    context: QgsProcessingContext,
    macro_uids: list[str],
    expected_error: str,
) -> None:
    workflow = MacroWorkflow("broken", macro_uids)
    workflow_provider.set_workflows([workflow], {})
    algorithm = require(workflow_provider.algorithm(workflow.uid))

    with pytest.raises(QgsProcessingException, match=expected_error):
        processing.run(algorithm, {}, feedback=feedback, context=context)


def test_workflow_algorithm_shows_uid_of_unnamed_macro(
    workflow_provider: MacroWorkflowProcessingProvider,
    feedback: RecordingFeedback,
    context: QgsProcessingContext,
) -> None:
    macro = Macro(events=[])
    workflow = MacroWorkflow("unnamed steps", [macro.uid])
    workflow_provider.set_workflows([workflow], {macro.uid: macro})
    algorithm = require(workflow_provider.algorithm(workflow.uid))

    processing.run(algorithm, {}, feedback=feedback, context=context)

    assert f"Steps: {macro.uid}" in algorithm.shortHelpString()
    assert feedback.progress_texts == [f"Playing macro '{macro.uid}' (1/1)"]


def test_workflow_provider_set_macros_by_uid_updates_algorithms_in_place(
    workflow_provider: MacroWorkflowProcessingProvider,
    workflow: MacroWorkflow,
    macros: list[Macro],
) -> None:
    algorithm = require(workflow_provider.algorithm(workflow.uid))
    loads = []
    workflow_provider.algorithmsLoaded.connect(lambda: loads.append(1))

    workflow_provider.set_macros_by_uid({macros[1].uid: macros[1]})

    assert loads == []
    assert workflow_provider.algorithm(workflow.uid) is algorithm
    assert "Missing macro" in algorithm.shortHelpString()


def test_workflow_algorithm_stops_at_failing_step(
    workflow_provider: MacroWorkflowProcessingProvider,
    workflow: MacroWorkflow,
    dialog: Dialog,
    feedback: RecordingFeedback,
    context: QgsProcessingContext,
) -> None:
    dialog.close()
    algorithm = require(workflow_provider.algorithm(workflow.uid))

    with pytest.raises(QgsProcessingException):
        processing.run(algorithm, {}, feedback=feedback, context=context)

    assert feedback.progress_texts == ["Playing macro 'click' (1/3)"]
