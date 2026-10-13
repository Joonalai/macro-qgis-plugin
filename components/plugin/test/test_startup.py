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

import os
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis_macros.exceptions import MacroPlaybackEndedError, MacroPluginError
from qgis_macros.macro import Macro
from qgis_macros.macro_file import MacroFile
from qgis_macros.macro_player import (
    MacroPlaybackReport,
    MacroPlaybackStatus,
    MacroPlayer,
)
from qgis_macros.macro_workflow import MacroWorkflow

from macro_plugin import env, startup
from macro_plugin.startup import StartupPlayback, play_on_startup

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture
    from pytestqt.qtbot import QtBot


class StubIface(QObject):
    initializationCompleted = pyqtSignal()  # noqa: N815

    def __init__(self, *, visible: bool = False) -> None:
        super().__init__()
        self.visible = visible

    def mainWindow(self) -> "StubIface":  # noqa: N802
        return self

    def isVisible(self) -> bool:  # noqa: N802
        return self.visible

    def newProject(self, promptToSaveFlag: bool) -> None:  # noqa: N802, N803
        pass


@pytest.fixture
def first() -> Macro:
    return Macro([], name="first")


@pytest.fixture
def second() -> Macro:
    return Macro([], name="second")


@pytest.fixture
def macro_file(first: Macro, second: Macro) -> MacroFile:
    return MacroFile(
        [first, second],
        [
            MacroWorkflow("both", [second.uid, first.uid]),
            MacroWorkflow("one", [first.uid]),
        ],
    )


@pytest.fixture
def macro_file_path(macro_file: MacroFile, tmp_path: "Path") -> "Path":
    path = tmp_path / "macros.json"
    macro_file.save(path)
    return path


@pytest.fixture
def stub_iface(mocker: "MockerFixture") -> StubIface:
    iface = StubIface()
    mocker.patch.object(startup.qgis_utils, "iface", iface)
    return iface


@pytest.fixture
def play_spy(mocker: "MockerFixture") -> "MagicMock":
    # Macros without events end immediately
    return mocker.spy(MacroPlayer, "play")


@pytest.fixture
def mock_exit(mocker: "MockerFixture") -> "MagicMock":
    return mocker.patch.object(startup.QgsApplication, "exit")


@pytest.fixture
def mock_msg_bar(mocker: "MockerFixture") -> "MagicMock":
    return mocker.patch.object(startup, "MsgBar")


@pytest.fixture(autouse=True)
def _clear_playbacks() -> Iterator[None]:
    yield
    startup._playbacks.clear()


def played_names(play_spy: "MagicMock") -> list[str | None]:
    return [call.args[1].name for call in play_spy.call_args_list]


@pytest.mark.parametrize(
    ("workflow", "macro", "expected"),
    [
        ("both", None, ["second", "first"]),
        ("one", None, ["first"]),
        (None, "second", ["second"]),
    ],
    ids=["workflow", "other workflow", "macro"],
)
def test_resolve_named_macros(
    macro_file: MacroFile,
    tmp_path: "Path",
    workflow: str | None,
    macro: str | None,
    expected: list[str],
):
    playback = StartupPlayback(tmp_path, workflow, macro)

    macros = playback.resolve_macros(macro_file)

    assert [m.name for m in macros] == expected


def test_resolve_macros_by_uid(macro_file: MacroFile, second: Macro, tmp_path: "Path"):
    workflow = macro_file.workflows[1]

    workflow_macros = StartupPlayback(tmp_path, workflow.uid).resolve_macros(macro_file)
    macros = StartupPlayback(tmp_path, macro=second.uid).resolve_macros(macro_file)

    assert [m.name for m in workflow_macros] == ["first"]
    assert macros == [second]


def test_playback_warns_about_another_locale(
    stub_iface: StubIface,
    tmp_path: "Path",
    mock_msg_bar: "MagicMock",
):
    path = tmp_path / "foreign.json"
    MacroFile([Macro([], name="foreign", locale="xx_XX")]).save(path)

    StartupPlayback(path).start()

    mock_msg_bar.warning.assert_called_once()
    assert "xx_XX" in mock_msg_bar.warning.call_args.args[1]
    mock_msg_bar.info.assert_called_once()


def test_resolve_only_workflow_without_name(first: Macro, tmp_path: "Path"):
    macro_file = MacroFile([first], [MacroWorkflow("w", [first.uid, first.uid])])

    macros = StartupPlayback(tmp_path).resolve_macros(macro_file)

    assert macros == [first, first]


def test_resolve_all_macros_of_file_without_workflows(
    first: Macro, second: Macro, tmp_path: "Path"
):
    macros = StartupPlayback(tmp_path).resolve_macros(MacroFile([first, second]))

    assert macros == [first, second]


@pytest.mark.parametrize(
    ("macro_file", "workflow", "macro"),
    [
        (
            MacroFile([], [MacroWorkflow("a"), MacroWorkflow("b")]),
            None,
            None,
        ),
        (MacroFile(), None, None),
        (MacroFile([], [MacroWorkflow("a")]), "missing", None),
        (MacroFile([Macro([], name="a")]), None, "missing"),
        (MacroFile([], [MacroWorkflow("a", ["missing"])]), "a", None),
        (MacroFile([], [MacroWorkflow("a")]), "a", None),
        (MacroFile([Macro([], name="a")], [MacroWorkflow("a")]), "a", "a"),
    ],
    ids=[
        "several workflows",
        "empty file",
        "missing workflow",
        "missing macro",
        "workflow with missing macro",
        "empty workflow",
        "workflow and macro",
    ],
)
def test_resolve_macros_fails(
    macro_file: MacroFile, workflow: str | None, macro: str | None, tmp_path: "Path"
):
    with pytest.raises(MacroPluginError):
        StartupPlayback(tmp_path, workflow, macro).resolve_macros(macro_file)


def test_playback_starts_after_qgis_initialization(
    stub_iface: StubIface,
    macro_file_path: "Path",
    play_spy: "MagicMock",
    mock_msg_bar: "MagicMock",
    mock_exit: "MagicMock",
    qtbot: "QtBot",
):
    play_on_startup(macro_file_path, "both", start_delay_ms=0)
    qtbot.wait(10)
    assert not play_spy.called

    stub_iface.initializationCompleted.emit()

    qtbot.waitUntil(lambda: mock_msg_bar.info.called)
    assert played_names(play_spy) == ["second", "first"]
    mock_exit.assert_not_called()
    assert not startup._playbacks


def test_playback_starts_if_qgis_is_already_initialized(
    stub_iface: StubIface,
    macro_file_path: "Path",
    play_spy: "MagicMock",
    mock_msg_bar: "MagicMock",
    qtbot: "QtBot",
):
    stub_iface.visible = True

    play_on_startup(macro_file_path, macro="first", start_delay_ms=0)

    qtbot.waitUntil(lambda: mock_msg_bar.info.called)
    assert played_names(play_spy) == ["first"]


def test_playback_closes_project_and_exits_with_success(
    mocker: "MockerFixture",
    macro_file_path: "Path",
    mock_msg_bar: "MagicMock",
    mock_exit: "MagicMock",
    qtbot: "QtBot",
):
    iface = mocker.patch.object(startup.qgis_utils, "iface")
    playback = StartupPlayback(macro_file_path, "one", exit_on_finish=True)

    playback.start()

    mock_msg_bar.info.assert_called_once()
    iface.newProject.assert_called_once_with(promptToSaveFlag=False)
    qtbot.waitUntil(lambda: mock_exit.called)
    mock_exit.assert_called_once_with(0)


def test_playback_exits_with_failure_if_file_is_invalid(
    stub_iface: StubIface,
    tmp_path: "Path",
    mock_msg_bar: "MagicMock",
    mock_exit: "MagicMock",
    qtbot: "QtBot",
):
    playback = StartupPlayback(tmp_path / "missing.json", exit_on_finish=True)

    playback.start()

    mock_msg_bar.error.assert_called_once()
    qtbot.waitUntil(lambda: mock_exit.called)
    mock_exit.assert_called_once_with(1)


def test_playback_stops_when_a_macro_fails(
    mocker: "MockerFixture",
    stub_iface: StubIface,
    macro_file_path: "Path",
    mock_msg_bar: "MagicMock",
    mock_exit: "MagicMock",
    qtbot: "QtBot",
):
    playback = StartupPlayback(macro_file_path, "both", exit_on_finish=True)
    failure = MacroPlaybackReport(
        MacroPlaybackStatus.FAILURE, MacroPlaybackEndedError(ValueError("boom"))
    )

    def fail(player: MacroPlayer, macro: Macro) -> None:
        player.playback_ended.emit(failure)

    play = mocker.patch.object(MacroPlayer, "play", autospec=True, side_effect=fail)

    playback.start()

    play.assert_called_once()
    mock_msg_bar.error.assert_called_once()
    assert "boom" in mock_msg_bar.error.call_args.args[0]
    qtbot.waitUntil(lambda: mock_exit.called)
    mock_exit.assert_called_once_with(1)


def test_play_from_environment(
    monkeypatch: pytest.MonkeyPatch,
    mocker: "MockerFixture",
    macro_file_path: "Path",
):
    mock_play = mocker.patch.object(startup, "play_on_startup")
    monkeypatch.setenv(env.MACRO_STARTUP_FILE.key, str(macro_file_path))
    monkeypatch.setenv(env.MACRO_STARTUP_WORKFLOW.key, "both")
    monkeypatch.setenv(env.MACRO_STARTUP_EXIT.key, "true")
    monkeypatch.setenv(env.MACRO_STARTUP_DELAY_MS.key, "50")

    startup.play_from_environment()

    mock_play.assert_called_once_with(
        str(macro_file_path), "both", None, exit_on_finish=True, start_delay_ms=50
    )
    # The macros are not played again when the plugin is reloaded
    assert env.MACRO_STARTUP_FILE.key not in os.environ


def test_play_from_environment_does_nothing_without_file(
    monkeypatch: pytest.MonkeyPatch, mocker: "MockerFixture"
):
    mock_play = mocker.patch.object(startup, "play_on_startup")
    monkeypatch.delenv(env.MACRO_STARTUP_FILE.key, raising=False)

    assert startup.play_from_environment() is None

    mock_play.assert_not_called()


def test_play_raises_without_reporting(
    tmp_path: "Path",
    mock_msg_bar: "MagicMock",
    mock_exit: "MagicMock",
):
    playback = StartupPlayback(tmp_path / "missing.json", exit_on_finish=True)

    with pytest.raises(MacroPluginError):
        playback.play()

    mock_msg_bar.error.assert_not_called()
    mock_exit.assert_not_called()


def test_play_plays_the_macros_with_the_given_speed(
    macro_file_path: "Path",
    play_spy: "MagicMock",
    mock_msg_bar: "MagicMock",
    mocker: "MockerFixture",
):
    init_spy = mocker.spy(MacroPlayer, "__init__")

    StartupPlayback(
        macro_file_path, "both", speed=2.5, smooth_mouse_movement=True
    ).play()

    assert played_names(play_spy) == ["second", "first"]
    assert init_spy.call_args.args[1:] == (2.5,)
    assert init_spy.call_args.kwargs == {"smooth_mouse_movement": True}
    mock_msg_bar.info.assert_not_called()
