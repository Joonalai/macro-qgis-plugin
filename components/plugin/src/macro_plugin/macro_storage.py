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
"""Autosave storages that keep each macro and workflow in its own JSON file."""

import json
import logging
from collections.abc import Callable
from pathlib import Path

from qgis_macros.macro import Macro
from qgis_macros.macro_workflow import MacroWorkflow
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.tools.resources import profile_path

LOGGER = logging.getLogger(__name__)


def default_autosave_directory() -> Path:
    """Return the directory for autosaved macros inside the QGIS profile."""
    return Path(profile_path("macros", "autosave"))


def default_workflow_directory() -> Path:
    """Return the directory for autosaved macro workflows inside the QGIS profile."""
    return Path(profile_path("macros", "workflows"))


def _load_items[T: (Macro, MacroWorkflow)](
    directory: Path, deserialize: Callable[[dict], T], error_message: str
) -> list[T]:
    """Load all ``*.json`` files of *directory* in creation order.

    The uid of each item is taken from its file name. Files that cannot be
    read are skipped and logged with *error_message*.
    """
    if not directory.is_dir():
        return []

    items: list[T] = []
    for path in sorted(directory.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as f:
                item = deserialize(json.load(f))
        except (OSError, ValueError, KeyError, TypeError) as e:
            LOGGER.warning(error_message, extra={"details": f"{path}: {e}"})
            continue
        item.uid = path.stem
        items.append(item)
    return items


def _save_item(path: Path, data: dict, error_message: str) -> None:
    """Write *data* atomically to *path*, logging *error_message* on failure."""
    tmp_path = path.with_suffix(".json.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        tmp_path.replace(path)
    except OSError as e:
        LOGGER.warning(error_message, extra={"details": f"{path}: {e}"})


def _delete_item(path: Path, error_message: str) -> None:
    """Delete *path* if it exists, logging *error_message* on failure."""
    try:
        path.unlink(missing_ok=True)
    except OSError as e:
        LOGGER.warning(error_message, extra={"details": f"{path}: {e}"})


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
        return _load_items(
            self.directory, Macro.deserialize, tr("Could not load autosaved macro")
        )

    def save_macro(self, macro: Macro) -> None:
        """Write *macro* to its file, replacing any earlier version."""
        _save_item(
            self.macro_path(macro),
            macro.serialize(),
            tr("Could not autosave macro {}", macro.name),
        )

    def delete_macro(self, macro: Macro) -> None:
        """Delete the file of *macro* if it exists."""
        _delete_item(
            self.macro_path(macro),
            tr("Could not delete autosaved macro {}", macro.name),
        )


class WorkflowStorage:
    """Persist macro workflows as ``<uid>.json`` files in a directory."""

    def __init__(self, directory: Path) -> None:
        """Initialize the storage.

        :param directory: Directory for the workflow files. Created on first save.
        """
        self.directory = directory

    def workflow_path(self, workflow: MacroWorkflow) -> Path:
        """Return the file path of *workflow*."""
        return self.directory / f"{workflow.uid}.json"

    def load_workflows(self) -> list[MacroWorkflow]:
        """Load all stored workflows in creation order.

        Files that cannot be read are skipped and logged.
        """
        return _load_items(
            self.directory,
            MacroWorkflow.deserialize,
            tr("Could not load autosaved macro workflow"),
        )

    def save_workflow(self, workflow: MacroWorkflow) -> None:
        """Write *workflow* to its file, replacing any earlier version."""
        _save_item(
            self.workflow_path(workflow),
            workflow.serialize(),
            tr("Could not autosave macro workflow {}", workflow.name),
        )

    def delete_workflow(self, workflow: MacroWorkflow) -> None:
        """Delete the file of *workflow* if it exists."""
        _delete_item(
            self.workflow_path(workflow),
            tr("Could not delete autosaved macro workflow {}", workflow.name),
        )
