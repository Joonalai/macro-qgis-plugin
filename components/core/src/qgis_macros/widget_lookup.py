#  Copyright (c) 2025-2026 macro-qgis-plugin contributors.
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
"""Resolve the target widgets of macro events on playback.

The widget of an event is searched with the strategies below, in this order,
and the first visible widget found is used:

1. Events recorded on the map canvas target the current map canvas, so they
   play even if the canvas has moved on screen or another window covers it.
2. The recorded :class:`~qgis_macros.macro.WidgetPath` is followed from its
   window down to the widget.
3. A toolbar button found by the path but hidden, because the toolbar is too
   narrow for it, is shown by expanding the toolbar from its extension button.
4. The widget at the recorded screen position is used, or its nearest visible
   neighbour that matches the recorded :class:`~qgis_macros.macro.WidgetSpec`.
"""

import logging
import time
from collections.abc import Iterable
from typing import TYPE_CHECKING

from qgis.PyQt.QtCore import QElapsedTimer, QPoint, Qt
from qgis.PyQt.QtGui import QCursor
from qgis.PyQt.QtWidgets import QApplication, QToolBar, QToolButton, QWidget

from qgis_macros import utils
from qgis_macros.constants import (
    MAXIMUM_NEAREST_CANDIDATES,
    MAXIMUM_PARENT_DEPTH,
    TOOLBAR_EXPAND_TIMEOUT_MS,
)
from qgis_macros.exceptions import WidgetNotFoundError

if TYPE_CHECKING:
    from qgis_macros.macro import Position, WidgetPath, WidgetPathNode, WidgetSpec

LOGGER = logging.getLogger(__name__)

#: Object name of the button that expands a toolbar too narrow for its items.
TOOLBAR_EXTENSION_NAME = "qt_toolbar_ext_button"


def resolve_widget(
    spec: "WidgetSpec", path: "WidgetPath | None", position: "Position"
) -> QWidget:
    """Return the visible widget targeted by an event.

    Raises:
        WidgetNotFoundError: If none of the strategies finds a widget.

    """
    for strategy in STRATEGIES:
        widget = strategy(spec, path, position)
        if widget is not None:
            LOGGER.debug("Found %s with %s", spec, strategy.__name__)
            return widget
    raise WidgetNotFoundError(spec.widget_class, spec.text)


def find_map_canvas(
    _spec: "WidgetSpec", path: "WidgetPath | None", _position: "Position"
) -> QWidget | None:
    """Return the viewport of the current map canvas for map canvas events."""
    if path is None or not path.is_map_canvas:
        return None
    canvas = utils.map_canvas_viewport()
    if canvas is None or not canvas.isVisible():
        LOGGER.debug("Map canvas is not available or not visible")
        return None
    return canvas


def find_by_path(
    spec: "WidgetSpec", path: "WidgetPath | None", _position: "Position"
) -> QWidget | None:
    """Follow *path* from its window down to a visible widget matching *spec*.

    The text of the widget is not compared, so that the widget is found by
    its place in the path even if its text is translated.
    """
    if path is None:
        return None
    widget = find_widget(path)
    if widget is None or not widget.isVisible():
        return None
    return widget if spec.matches_structure(widget) else None


def find_in_toolbar_extension(
    spec: "WidgetSpec", path: "WidgetPath | None", _position: "Position"
) -> QWidget | None:
    """Expand the toolbar of a hidden button found by *path* to show the button.

    A toolbar hides the buttons that do not fit in it, e.g. if the window is
    narrower than when the macro was recorded, and shows them when its
    extension button is clicked.
    """
    if path is None:
        return None
    widget = find_widget(path)
    if (
        widget is None
        or widget.isVisible()
        or not spec.matches_structure(widget)
        or not isinstance(toolbar := widget.parentWidget(), QToolBar)
        or not toolbar.isVisible()
    ):
        return None
    extension = toolbar.findChild(QToolButton, TOOLBAR_EXTENSION_NAME)
    # Toolbars outside main windows show the hidden buttons in a menu instead
    if extension is None or not extension.isVisible() or extension.menu():
        return None
    if not extension.isChecked():
        QCursor.setPos(extension.mapToGlobal(extension.rect().center()))
        extension.click()
    timer = QElapsedTimer()
    timer.start()
    while not widget.isVisible() and timer.elapsed() < TOOLBAR_EXPAND_TIMEOUT_MS:
        QApplication.processEvents()
        time.sleep(0.01)
    return widget if widget.isVisible() else None


def find_by_position(
    spec: "WidgetSpec", _path: "WidgetPath | None", position: "Position"
) -> QWidget | None:
    """Return the widget at *position* or its nearest neighbour matching *spec*."""
    global_point = position.global_point
    widget = QApplication.widgetAt(global_point)
    if widget is None:
        return None
    if spec.matches(widget):
        return widget
    # Dialogs might appear in a slightly different position
    return find_nearest_matching_widget(spec, global_point, widget.parentWidget())


#: The lookup strategies in the order they are tried.
STRATEGIES = (
    find_map_canvas,
    find_by_path,
    find_in_toolbar_extension,
    find_by_position,
)


# Widget paths


def find_widget(path: "WidgetPath") -> QWidget | None:
    """Follow *path* from its window down to the widget.

    All the windows matching the path are tried, since windows without a
    title or an object name cannot be told apart before following the path.
    """
    for window in _matching_windows(path):
        widget = _follow_nodes(window, path.nodes)
        if widget is not None:
            return widget
    return None


def path_leads_to(path: "WidgetPath", widget: QWidget) -> bool:
    """Check whether *path* describes *widget*, without searching the windows.

    Each ancestor of *widget* must be the child that :func:`find_child`
    picks first for the corresponding node, i.e. have the sibling index of
    the node and match it exactly, and the window must match by its object
    name or title. This is much cheaper than :func:`find_widget`.
    """
    current = widget
    for node in reversed(path.nodes):
        parent = current.parentWidget()
        if (
            parent is None
            or current.isWindow()
            or not node.matches(current, exact=True)
            or utils.get_sibling_index(current, parent) != node.sibling_index
        ):
            return False
        current = parent
    if (
        not current.isWindow()
        or not current.isVisible()
        or current.windowType() == Qt.WindowType.Popup
    ):
        return False
    if path.window_object_name and current.objectName() == path.window_object_name:
        return True
    return current.windowTitle() == path.window_title


def _matching_windows(path: "WidgetPath") -> list[QWidget]:
    """Return the visible windows matching *path*, by object name or title.

    Object names are stable while titles often contain e.g. the project or
    layer name. Many windows share a generic object name (e.g. ``Dialog``),
    so the windows matching both come first, then the ones matching the
    object name and last the ones matching the title. Popups are never
    matched, since they are located by position.
    """

    def score(window: QWidget) -> int:
        name_matches = bool(path.window_object_name) and (
            window.objectName() == path.window_object_name
        )
        title_matches = window.windowTitle() == path.window_title
        return 2 * name_matches + title_matches

    windows = [
        widget
        for widget in QApplication.topLevelWidgets()
        if widget.isVisible() and widget.windowType() != Qt.WindowType.Popup
    ]
    return sorted(
        (window for window in windows if score(window)), key=score, reverse=True
    )


def _follow_nodes(window: QWidget, nodes: Iterable["WidgetPathNode"]) -> QWidget | None:
    current = window
    for node in nodes:
        child = find_child(current, node)
        if child is None:
            return None
        current = child
    return current


def find_child(parent: QWidget, node: "WidgetPathNode") -> QWidget | None:
    """Return the direct child of *parent* described by *node*.

    The child is found by its sibling index and name or text, by its name
    or text alone, or by its index alone, in this order. Children matching
    both the name and the text come first, since children may share a name.
    """
    same_class_children = [
        child
        for child in parent.findChildren(QWidget)
        if child.__class__.__name__ == node.widget_class
        and child.parentWidget() is parent
    ]
    indexed = (
        same_class_children[node.sibling_index]
        if node.sibling_index < len(same_class_children)
        else None
    )
    for exact in (True, False):
        if indexed is not None and node.matches(indexed, exact=exact):
            return indexed
        if node.text:
            for child in same_class_children:
                if node.matches(child, exact=exact):
                    return child
    return indexed


# Positions


def find_nearest_matching_widget(
    spec: "WidgetSpec", point: QPoint, widget: QWidget | None
) -> QWidget | None:
    """Return the visible descendant of *widget* matching *spec* nearest to *point*.

    The search walks up ``MAXIMUM_PARENT_DEPTH`` parents of *widget* and
    considers the ``MAXIMUM_NEAREST_CANDIDATES`` nearest descendants of the
    class of *spec* at each level.
    """
    for _ in range(MAXIMUM_PARENT_DEPTH):
        if widget is None:
            return None
        candidates = sorted(
            (
                child
                for child in widget.findChildren(QWidget)
                if child.isVisible() and child.__class__.__name__ == spec.widget_class
            ),
            key=lambda child: _squared_distance(point, child),
        )
        for exact in (True, False):
            for candidate in candidates[:MAXIMUM_NEAREST_CANDIDATES]:
                if spec.matches(candidate, exact=exact):
                    return candidate
        widget = widget.parentWidget()
    return None


def _squared_distance(point: QPoint, widget: QWidget) -> int:
    """Return the squared distance from the global *point* to the widget center."""
    center = widget.mapToGlobal(widget.rect().center())
    return (point.x() - center.x()) ** 2 + (point.y() - center.y()) ** 2
