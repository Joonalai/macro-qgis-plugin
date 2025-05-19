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

import dataclasses
import time
from functools import partial
from typing import TYPE_CHECKING, Optional

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QEvent, QObject, QPoint, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QAction,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QMenu,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from qgis_macros.macro import Position, WidgetSpec


class Dialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout()

        self.button = QPushButton("Click Me")
        self.button.clicked.connect(partial(wait, 2))

        self.button2 = QPushButton("Click Me too")
        self.button2.clicked.connect(partial(wait, 5))

        self.combobox = QComboBox()
        self.combobox.addItems(["Item 1", "Item 2", "Item 3"])
        self.line_edit = QLineEdit()
        self.radio_button = QRadioButton("Option 1")
        self.check_box = QCheckBox("Check Me")
        self.list_widget = QListWidget()
        self.list_widget.addItems(["List Item 1", "List Item 2", "List Item 3"])

        self.menu_button = QPushButton("Menu")
        self.menu = QMenu(self.menu_button)
        self.action1 = QAction("Action 1", self)
        self.action2 = QAction("Action 2", self)
        self.menu.addAction(self.action1)
        self.menu.addAction(self.action2)
        self.menu_button.setMenu(self.menu)

        menu_layout = QHBoxLayout()
        menu_layout.addWidget(self.menu_button)
        menu_layout.addStretch()

        layout.addLayout(menu_layout)
        layout.addWidget(self.button)
        layout.addWidget(self.button2)
        layout.addWidget(self.combobox)
        layout.addWidget(self.line_edit)
        layout.addWidget(self.radio_button)
        layout.addWidget(self.check_box)
        layout.addWidget(self.list_widget)

        self.setLayout(layout)


@dataclasses.dataclass
class WidgetInfo:
    """Helper class for macro tests."""

    name: str
    widget: QWidget
    position: "Position"

    @property
    def widget_spec(self) -> "WidgetSpec":
        from qgis_macros.macro import WidgetSpec

        return WidgetSpec.create(self.widget)

    @staticmethod
    def from_widget(name: str, widget: QWidget) -> "WidgetInfo":
        from qgis_macros.macro import Position

        geometry = widget.geometry()
        local_center = QPoint(geometry.width() // 2, geometry.height() // 2)
        if isinstance(widget, (QRadioButton, QCheckBox)):
            local_center = QPoint(10, local_center.y())
        global_center = widget.mapToGlobal(local_center)
        return WidgetInfo(
            name, widget, Position.from_points(local_center, global_center)
        )


def wait(wait_ms: int) -> None:
    """Wait for a given number of milliseconds."""
    t = time.time()
    while time.time() - t < wait_ms / 1000:
        QgsApplication.processEvents()


class WidgetEventListener(QObject):
    double_clicked = pyqtSignal()  # Signal emitted when a double click is detected.

    def __init__(self) -> None:
        super().__init__(None)
        self.widgets: list[QWidget] = []

    def start_listening(self, widget: QWidget) -> None:
        widget.installEventFilter(self)
        self.widgets.append(widget)

    def stop_listening(self) -> None:
        for widget in self.widgets:
            widget.removeEventFilter(self)
        self.widgets.clear()

    def eventFilter(self, watched_object: QObject, event: QEvent) -> bool:  # noqa: N802
        """Override of QObject.eventFilter to detect double clicks."""
        if event.type() == QEvent.MouseButtonDblClick:
            self.double_clicked.emit()
        return super().eventFilter(watched_object, event)
