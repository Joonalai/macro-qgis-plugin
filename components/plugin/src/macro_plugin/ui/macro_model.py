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

from macro_plugin.macro_storage import MacroStorage


class MacroTableModel(QAbstractTableModel):
    """Table model for a list of :class:`~qgis_macros.macro.Macro` objects."""

    headers: ClassVar[dict[int, str]] = {0: tr("Macro")}

    def __init__(self, storage: MacroStorage | None = None) -> None:
        """Initialize the model with an empty macro list.

        :param storage: Optional storage that is kept in sync with the model.
            Added and renamed macros are saved and removed macros are deleted.
        """
        super().__init__()
        self.macros: list[Macro] = []
        self._storage = storage

    def add_macro(self, macro: Macro) -> None:
        """Append a macro and notify attached views."""
        self.add_macros([macro])

    def add_macros(self, macros: list[Macro]) -> None:
        """Append macros and notify attached views."""
        if not macros:
            return
        row = len(self.macros)
        self.beginInsertRows(QModelIndex(), row, row + len(macros) - 1)

        self.macros.extend(macros)

        # Notify the view that rows have been added
        self.endInsertRows()
        if self._storage is not None:
            for macro in macros:
                self._storage.save_macro(macro)

    def remove_macro(self, row: int) -> None:
        """Remove the macro at *row* and notify attached views."""
        self.beginRemoveRows(QModelIndex(), row, row)
        macro = self.macros.pop(row)
        self.endRemoveRows()
        if self._storage is not None:
            self._storage.delete_macro(macro)

    def reset_macros(self, macros: list[Macro]) -> None:
        """Replace the entire macro list and reset the model.

        The storage is not modified.
        """
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

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Return the flags for the given index."""
        default_flags = super().flags(index)
        if index.isValid():
            return default_flags | Qt.ItemFlag.ItemIsEditable
        return default_flags

    def data(
        self, index: QModelIndex, role: Qt.ItemDataRole = Qt.ItemDataRole.DisplayRole
    ) -> QVariant:
        """Return the data for the given index and role."""
        row = index.row()
        if not index.isValid():
            return NULL
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignLeft
        if role in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.ToolTipRole,
            Qt.ItemDataRole.EditRole,
        ):
            return QVariant(self.macros[row].name)

        return NULL

    def setData(  # noqa: N802
        self,
        index: QModelIndex,
        value: str,
        role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """Set the data for the given index and role."""
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        row = index.row()
        name = value.strip()
        if not name:
            return False
        self.macros[row].name = name
        self.dataChanged.emit(index, index, [role])
        if self._storage is not None:
            self._storage.save_macro(self.macros[row])
        return True
