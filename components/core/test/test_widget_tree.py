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
from typing import TYPE_CHECKING

from macro_test_utils.utils import Dialog
from qgis.PyQt.QtWidgets import QLineEdit, QPushButton, QVBoxLayout, QWidget
from qgis_macros import widget_tree

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def _flatten(nodes: list[widget_tree.WidgetNode]) -> list[widget_tree.WidgetNode]:
    return [n for node in nodes for n in [node, *_flatten(node.children)]]


def test_dump_lists_visible_widgets_with_texts(dialog: Dialog):
    dialog.check_box.hide()

    tree = widget_tree.dump([dialog])

    [root] = tree.nodes
    assert root.widget_class == "Dialog"
    texts = [(n.widget_class, n.text) for n in root.children]
    assert ("QPushButton", "Click Me") in texts
    assert ("QComboBox", "Item 1") in texts
    assert ("QCheckBox", "Check Me") not in texts
    button = next(n for n in root.children if n.text == "Click Me")
    assert tree.widgets[button.id] is dialog.button
    top_left = dialog.button.mapToGlobal(dialog.button.rect().topLeft())
    assert button.rect == (
        top_left.x(),
        top_left.y(),
        dialog.button.width(),
        dialog.button.height(),
    )


def test_dump_leaves_out_unnamed_containers_but_keeps_their_children(
    qtbot: "QtBot",
):
    window = QWidget()
    window.setWindowTitle("Window")
    container = QWidget(window)
    button = QPushButton("Inner", container)
    QVBoxLayout(container).addWidget(button)
    QVBoxLayout(window).addWidget(container)
    qtbot.addWidget(window)
    window.show()

    tree = widget_tree.dump([window])

    [root] = tree.nodes
    assert [(n.widget_class, n.text) for n in root.children] == [
        ("QPushButton", "Inner")
    ]
    assert tree.widgets[root.children[0].id] is button


def test_dump_finds_widgets_ignoring_case(dialog: Dialog):
    tree = widget_tree.dump([dialog], find="click me")

    assert [n.text for n in tree.nodes] == ["Click Me", "Click Me too"]
    assert all(not n.children for n in tree.nodes)


def test_dump_finds_widgets_by_placeholder_and_tooltip(qtbot: "QtBot"):
    window = QWidget()
    line_edit = QLineEdit(window)
    line_edit.setPlaceholderText("Type to locate")
    button = QPushButton(window)
    button.setToolTip("Zoom in")
    qtbot.addWidget(window)
    window.show()

    assert widget_tree.dump([window], find="locate").widgets == {1: line_edit}
    assert widget_tree.dump([window], find="zoom").widgets == {1: button}


def test_dump_limits_depth(dialog: Dialog):
    tree = widget_tree.dump([dialog], max_depth=1)

    [root] = tree.nodes
    assert root.children == []


def test_serialize_includes_children(dialog: Dialog):
    data = widget_tree.dump([dialog]).serialize()

    assert data[0]["class"] == "Dialog"
    assert {"id", "class", "object_name", "text", "rect", "enabled"} <= set(
        data[0]["children"][0]
    )
