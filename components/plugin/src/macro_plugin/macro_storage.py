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
"""Autosave storage that keeps each macro in its own JSON file."""

import json
import logging
from pathlib import Path

from qgis_macros.macro import Macro
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.tools.resources import profile_path

LOGGER = logging.getLogger(__name__)


def default_autosave_directory() -> Path:
    """Return the directory for autosaved macros inside the QGIS profile."""
    return Path(profile_path("macros", "autosave"))


class MacroStorage:
    """Persist macros as ``<uid>.json`` files in a directory."""

    def __init__(self, directory: Path) -> None:
        """Initialize the storage.

        :param directory: Directory for the macro files. Created on first save.
        """
        self.directory = directory

    def macro_path(self, macro: Macro) -> Path:
        """Return the file path of *macro*."""
        return self.directory / f"{macro.uid}.json"

    def load_macros(self) -> list[Macro]:
        """Load all stored macros in creation order.

        Files that cannot be read are skipped and logged.
        """
        if not self.directory.is_dir():
            return []

        macros: list[Macro] = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                with path.open(encoding="utf-8") as f:
                    macro = Macro.deserialize(json.load(f))
            except (OSError, ValueError, KeyError, TypeError) as e:
                LOGGER.warning(
                    tr("Could not load autosaved macro"),
                    extra={"details": f"{path}: {e}"},
                )
                continue
            macro.uid = path.stem
            macros.append(macro)
        return macros

    def save_macro(self, macro: Macro) -> None:
        """Write *macro* to its file, replacing any earlier version."""
        path = self.macro_path(macro)
        tmp_path = path.with_suffix(".json.tmp")
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(macro.serialize(), f, indent=4, ensure_ascii=False)
            tmp_path.replace(path)
        except OSError as e:
            LOGGER.warning(
                tr("Could not autosave macro {}", macro.name),
                extra={"details": f"{path}: {e}"},
            )

    def delete_macro(self, macro: Macro) -> None:
        """Delete the file of *macro* if it exists."""
        path = self.macro_path(macro)
        try:
            path.unlink(missing_ok=True)
        except OSError as e:
            LOGGER.warning(
                tr("Could not delete autosaved macro {}", macro.name),
                extra={"details": f"{path}: {e}"},
            )
