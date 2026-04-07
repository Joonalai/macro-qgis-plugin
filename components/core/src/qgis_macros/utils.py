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

from collections.abc import Iterator
from typing import (
    TYPE_CHECKING,
    cast,
)

from qgis.PyQt.QtCore import QObject, QPoint
from qgis.PyQt.QtWidgets import QAbstractButton, QWidget
from qgis.utils import iface as iface_

if TYPE_CHECKING:
    from qgis.gui import QgisInterface

iface = cast("QgisInterface", iface_)


def is_object_map_canvas(obj: QObject) -> bool:
    return obj == iface.mapCanvas().viewport()


def get_widget_text(widget: QWidget) -> str:
    text = ""
    if isinstance(widget, QAbstractButton):
        text = widget.text()
    return text or widget.objectName()


def find_nearest_visible_children_of_type(
    target_point: QPoint, parent_widget: QWidget, widget_class: str
) -> Iterator[QWidget]:
    widgets = find_nearest_visible_children_with_threshold(target_point, parent_widget)
    return (widget for widget in widgets if widget.__class__.__name__ == widget_class)


def find_nearest_visible_children_with_threshold(
    target_point: QPoint, parent_widget: QWidget
) -> Iterator[QWidget]:
    nearest_visible_children = set()

    def distance_to_widget(widget: QWidget) -> int:
        widget_center = widget.geometry().center()

        # Calculate the Euclidean distance (squared)
        return (target_point.x() - widget_center.x()) ** 2 + (
            target_point.y() - widget_center.y()
        ) ** 2

    def find_recursive(widget: QWidget) -> None:
        for child in widget.findChildren(QWidget):
            if child.isVisible():
                nearest_visible_children.add((child, (distance_to_widget(child))))
                find_recursive(child)

    # Start the recursive search from the parent widget
    find_recursive(parent_widget)

    # Sort the results by distance
    return (child[0] for child in sorted(nearest_visible_children, key=lambda x: x[1]))
