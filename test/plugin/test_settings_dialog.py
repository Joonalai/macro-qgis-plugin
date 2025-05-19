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

from typing import TYPE_CHECKING

import pytest

from macro_plugin.ui.settings_dialog import SettingsDialog
from qgis_macros.settings import SettingCategory, Settings

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


@pytest.fixture
def settings_dialog(
    qtbot: "QtBot",
) -> "SettingsDialog":
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog


def test_settings_dialog_initialization(settings_dialog: "SettingsDialog") -> None:
    assert settings_dialog.combo_box_log_level_file.count() > 0
    assert settings_dialog.combo_box_log_level_console.count() > 0
    assert settings_dialog.combo_box_log_level_file.currentText() in [
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ]
    assert settings_dialog.combo_box_log_level_console.currentText() in [
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ]

    assert len(settings_dialog._widgets) == len(Settings)
    assert set(settings_dialog._widgets.keys()) == set(Settings)
    assert set(settings_dialog._groups.keys()) == set(SettingCategory)
    # utils.wait(10000)
