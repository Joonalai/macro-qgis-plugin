#  Copyright (c) 2025-2026 macro-qgis-plugin contributors.
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
"""Qt table model for displaying macros in the macro panel."""

from typing import ClassVar

from qgis.PyQt.QtCore import NULL, QAbstractTableModel, QModelIndex, Qt, QVariant
from qgis_macros.macro import Macro
from qgis_plugin_tools.tools.i18n import tr


class MacroTableModel(QAbstractTableModel):
    """Table model for a list of :class:`~qgis_macros.macro.Macro` objects."""

    headers: ClassVar[dict[int, str]] = {0: tr("Macro")}

    def __init__(self) -> None:
        """Initialize the model with an empty macro list."""
        super().__init__()
        self.macros: list[Macro] = []

    def add_macro(self, macro: Macro) -> None:
        """Append a macro and notify attached views."""
        row = len(self.macros)
        self.beginInsertRows(QModelIndex(), row, row)

        self.macros.append(macro)

        # Notify the view that rows have been added
        self.endInsertRows()

    def remove_macro(self, row: int) -> None:
        """Remove the macro at *row* and notify attached views."""
        self.beginRemoveRows(QModelIndex(), row, row)
        self.macros.pop(row)
        self.endRemoveRows()

    def reset_macros(self, macros: list[Macro]) -> None:
        """Replace the entire macro list and reset the model."""
        self.beginResetModel()
        self.macros = macros
        self.endResetModel()

    def rowCount(self, parent: QModelIndex) -> int:  # noqa: N802, D102
        valid = parent.isValid()
        return 0 if valid else len(self.macros)

    def columnCount(self, parent: QModelIndex) -> int:  # noqa: N802, D102
        return 0 if parent.isValid() else len(self.headers)

    def headerData(  # noqa: N802, D102
        self,
        section: int,
        orientation: Qt.Orientation,
        role: Qt.ItemDataRole = Qt.ItemDataRole.DisplayRole,
    ) -> QVariant:
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return self.headers.get(section, NULL)
        if (
            role == Qt.ItemDataRole.TextAlignmentRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return Qt.AlignmentFlag.AlignLeft
        return NULL

    def data(  # noqa: D102
        self, index: QModelIndex, role: Qt.ItemDataRole = Qt.ItemDataRole.DisplayRole
    ) -> QVariant:
        row = index.row()
        if not index.isValid():
            return NULL
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignLeft
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return QVariant(self.macros[row].name)

        return NULL
