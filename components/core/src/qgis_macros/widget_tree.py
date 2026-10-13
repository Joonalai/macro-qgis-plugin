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
"""Compact tree of the visible widgets, for finding widgets to interact with.

Widgets without a text or an object name are left out and their children
take their place, which keeps the tree of the QGIS main window readable.

Example::

    from qgis_macros import widget_tree

    tree = widget_tree.dump(find="OK")
    for node in tree.nodes:
        print(node.id, node.widget_class, node.text, node.rect)
    widget = tree.widgets[tree.nodes[0].id]
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from qgis.PyQt.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QWidget,
)

from qgis_macros.utils import widget_object_name


@dataclass
class WidgetNode:
    """A visible widget and the visible widgets under it."""

    id: int
    widget_class: str
    object_name: str
    text: str
    # Global geometry: x, y, width, height
    rect: tuple[int, int, int, int]
    enabled: bool
    children: list["WidgetNode"] = field(default_factory=list)

    def serialize(self) -> dict:
        """Serialize the node and its children to a JSON-compatible dict."""
        data: dict = {
            "id": self.id,
            "class": self.widget_class,
            "object_name": self.object_name,
            "text": self.text,
            "rect": list(self.rect),
            "enabled": self.enabled,
        }
        if self.children:
            data["children"] = [child.serialize() for child in self.children]
        return data


@dataclass
class WidgetTree:
    """Result of :func:`dump`."""

    nodes: list[WidgetNode]
    # Widgets by the ids of their nodes
    widgets: dict[int, QWidget]

    def serialize(self) -> list[dict]:
        """Serialize the nodes to a JSON-compatible list."""
        return [node.serialize() for node in self.nodes]


def display_text(widget: QWidget) -> str:
    """Return the text a user sees on *widget*, or an empty string."""
    if widget.isWindow():
        return widget.windowTitle()
    if isinstance(widget, (QAbstractButton, QLabel, QLineEdit)):
        return widget.text()
    if isinstance(widget, QComboBox):
        return widget.currentText()
    if isinstance(widget, QGroupBox):
        return widget.title()
    return ""


def dump(
    roots: Iterable[QWidget] | None = None,
    *,
    find: str | None = None,
    max_depth: int | None = None,
) -> WidgetTree:
    """Return the tree of the visible widgets under *roots*.

    :param roots: Widgets to start from. Defaults to the visible top level
        widgets.
    :param find: If given, return a flat list of the widgets whose text,
        object name or class contains it, ignoring case.
    :param max_depth: Number of levels to include. Unlimited by default.
    """
    if roots is None:
        roots = [w for w in QApplication.topLevelWidgets() if w.isVisible()]
    widgets: dict[int, QWidget] = {}

    def node_of(widget: QWidget) -> WidgetNode:
        node_id = len(widgets) + 1
        widgets[node_id] = widget
        top_left = widget.mapToGlobal(widget.rect().topLeft())
        return WidgetNode(
            node_id,
            widget.__class__.__name__,
            widget_object_name(widget),
            display_text(widget),
            (top_left.x(), top_left.y(), widget.width(), widget.height()),
            widget.isEnabled(),
        )

    def visit(widget: QWidget, depth: int) -> list[WidgetNode]:
        if not widget.isVisible():
            return []
        children = [
            child
            for child in widget.children()
            if isinstance(child, QWidget) and not child.isWindow()
        ]
        is_window = widget.isWindow()
        if find is not None:
            matches = [node_of(widget)] if _matches(widget, find) else []
            return matches + [n for child in children for n in visit(child, depth)]
        if (
            not is_window
            and not widget_object_name(widget)
            and not display_text(widget)
        ):
            return [n for child in children for n in visit(child, depth)]
        node = node_of(widget)
        if max_depth is None or depth + 1 < max_depth:
            node.children = [n for child in children for n in visit(child, depth + 1)]
        return [node]

    nodes = [node for root in roots for node in visit(root, 0)]
    return WidgetTree(nodes, widgets)


def _matches(widget: QWidget, find: str) -> bool:
    needle = find.casefold()
    return any(
        needle in value.casefold()
        for value in (
            display_text(widget),
            widget_object_name(widget),
            widget.__class__.__name__,
        )
    )
