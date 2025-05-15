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
import logging
from typing import TYPE_CHECKING

import pytest
from qgis.PyQt.QtGui import QCursor
from qgis.PyQt.QtWidgets import (
    QWidget,
)

from macro_test_utils import utils
from macro_test_utils.utils import Dialog

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

LOGGER = logging.getLogger(__name__)

WAIT_AFTER_MOUSE_MOVE = 1


@pytest.fixture
def dialog(qtbot: "QtBot", qgis_parent: "QWidget") -> Dialog:
    dialog = Dialog(qgis_parent)
    qtbot.addWidget(dialog)
    dialog.show()

    # Move mouse to the dialog and simulate some mouse movements
    QCursor.setPos(dialog.pos())
    qtbot.mouseMove(dialog)
    qtbot.mouseMove(dialog)
    qtbot.wait(WAIT_AFTER_MOUSE_MOVE)
    qtbot.wait(WAIT_AFTER_MOUSE_MOVE)
    return dialog


@pytest.fixture
def dialog_widget_positions(dialog: Dialog) -> dict[str, utils.WidgetInfo]:
    return {
        name: utils.WidgetInfo.from_widget(name, widget)
        for name in dir(dialog)
        if isinstance((widget := getattr(dialog, name, None)), QWidget)
    }
