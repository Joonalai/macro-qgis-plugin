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

"""Utility functions for widget lookup, event position handling, and Qt compat."""

from enum import Enum
from typing import (
    TYPE_CHECKING,
    SupportsInt,
    cast,
)

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QObject, QPoint, Qt
from qgis.PyQt.QtGui import QMouseEvent, QWheelEvent
from qgis.PyQt.QtWidgets import (
    QAbstractButton,
    QApplication,
    QDialogButtonBox,
    QMenu,
    QWidget,
)
from qgis.utils import iface as iface_
from qgis_plugin_tools.utils.typing_utils import require

from qgis_macros.constants import MAXIMUM_PARENT_DEPTH

if TYPE_CHECKING:
    from qgis.gui import QgisInterface
    from qgis.PyQt.QtGui import QAction

iface = cast("QgisInterface", iface_)


def is_object_map_canvas(obj: QObject) -> bool:
    """Return True if *obj* is the map canvas viewport widget."""
    return obj == map_canvas_viewport()


def map_canvas_viewport() -> QWidget | None:
    """Return the viewport widget of the main map canvas, if any."""
    canvas = iface.mapCanvas()
    return canvas.viewport() if canvas is not None else None


def current_locale() -> str:
    """Return the locale of the QGIS user interface, e.g. ``fi``."""
    return QgsApplication.locale()


def widget_object_name(widget: QWidget) -> str:
    """Return the object name of *widget*, which is the same in every locale.

    The standard buttons of a QDialogButtonBox have no object name, so
    they are named after their standard button value instead.
    """
    name = widget.objectName()
    if name:
        return name
    parent = widget.parentWidget()
    if isinstance(widget, QAbstractButton) and isinstance(parent, QDialogButtonBox):
        standard_button = parent.standardButton(widget)
        if standard_button != QDialogButtonBox.StandardButton.NoButton:
            return f"QDialogButtonBox.StandardButton.{enum_value(standard_button)}"
    return ""


def widget_matches(
    widget: QWidget,
    widget_class: str,
    text: str,
    object_name: str,
    *,
    exact: bool = False,
) -> bool:
    """Return True if *widget* has the class and the object name or the text.

    Object names are compared when both are known, since texts are
    translated. Otherwise the texts are compared. With *exact*, the texts
    are compared also when the object names match, which tells apart
    widgets sharing an object name.
    """
    if widget.__class__.__name__ != widget_class:
        return False
    widget_name = widget_object_name(widget)
    if object_name and widget_name:
        if object_name != widget_name:
            return False
        if not exact:
            return True
    return text == get_widget_text(widget)


def widget_matches_structure(
    widget: QWidget, widget_class: str, object_name: str
) -> bool:
    """Return True if the class matches and the object names, if both are known."""
    if widget.__class__.__name__ != widget_class:
        return False
    widget_name = widget_object_name(widget)
    return not (object_name and widget_name) or object_name == widget_name


def get_widget_text(widget: QWidget) -> str:
    """Return the display text of *widget*, falling back to its object name."""
    text = ""
    if isinstance(widget, QAbstractButton):
        text = widget.text()
    return text or widget.objectName()


def get_sibling_index(widget: QWidget, parent: QWidget) -> int:
    """Get the index of a widget among its same-class siblings in the parent."""
    widget_class = widget.__class__.__name__
    same_class_siblings = [
        child
        for child in parent.findChildren(QWidget)
        if child.__class__.__name__ == widget_class and child.parentWidget() is parent
    ]
    for i, sibling in enumerate(same_class_siblings):
        if sibling is widget:
            return i
    return 0


def enum_value(enum_or_flag: SupportsInt | Enum) -> int:
    """Convert a Qt enum/flag to int, compatible with both PyQt5 and PyQt6."""
    if isinstance(enum_or_flag, Enum):
        return enum_or_flag.value
    return int(enum_or_flag)


def keyboard_modifiers(modifiers: int) -> Qt.KeyboardModifier:
    """Convert an int to Qt keyboard modifier flags (PyQt5/6 compatible)."""
    # PyQt5 has a separate class for combined flags
    flags_class = getattr(Qt, "KeyboardModifiers", Qt.KeyboardModifier)
    return flags_class(modifiers)


def mouse_buttons(buttons: int) -> Qt.MouseButton:
    """Convert an int to Qt mouse button flags (PyQt5/6 compatible)."""
    flags_class = getattr(Qt, "MouseButtons", Qt.MouseButton)
    return flags_class(buttons)


def event_pos(event: QMouseEvent | QWheelEvent) -> QPoint:
    """Get local position from a mouse/wheel event (PyQt5/6 compatible)."""
    # Wheel events have position() on PyQt6 and pos() on PyQt5
    position = getattr(event, "position", None)
    if position is not None:
        return position().toPoint()
    return require(getattr(event, "pos", None))()


def event_global_pos(event: QMouseEvent | QWheelEvent) -> QPoint:
    """Get global position from a mouse/wheel event (PyQt5/6 compatible)."""
    global_position = getattr(event, "globalPosition", None)
    if global_position is not None:
        return global_position().toPoint()
    return require(getattr(event, "globalPos", None))()


def menu_item_text(action: "QAction") -> str:
    """Return the text of a menu item without mnemonics and shortcuts."""
    text = action.text().split("\t")[0]
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&")


def visible_menus() -> list[QMenu]:
    """Return the visible popup menus, the active popup first."""
    menus = [
        widget
        for widget in QApplication.topLevelWidgets()
        if isinstance(widget, QMenu) and widget.isVisible()
    ]
    active_popup = QApplication.activePopupWidget()
    if isinstance(active_popup, QMenu) and active_popup in menus:
        menus.remove(active_popup)
        menus.insert(0, active_popup)
    return menus


def menu_action_path(menu: QMenu, action: "QAction") -> list[str]:
    """Return the texts of the menu items leading to *action*.

    The path starts from the outermost visible menu, e.g.
    ``["Styles", "fast"]`` for an item of the Styles submenu.
    """
    return [menu_item_text(item) for item in menu_action_chain(menu, action)]


def menu_action_chain(menu: QMenu, action: "QAction") -> list["QAction"]:
    """Return the menu items leading to *action*, the outermost first."""
    chain = [action]
    menus = visible_menus()
    current = menu
    for _ in range(MAXIMUM_PARENT_DEPTH):
        parent = next(
            (
                (parent_menu, parent_action)
                for parent_menu in menus
                if parent_menu is not current
                for parent_action in parent_menu.actions()
                if parent_action.menu() is current
            ),
            None,
        )
        if parent is None:
            break
        current, parent_action = parent
        chain.insert(0, parent_action)
    return chain
