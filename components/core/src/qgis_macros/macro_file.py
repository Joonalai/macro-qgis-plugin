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
"""Reading and writing macro files that contain macros and macro workflows.

A macro file is a JSON document::

    {
        "format_version": 2,
        "macros": [{"uid": "...", "name": "...", "events": [...], ...}],
        "workflows": [{"uid": "...", "name": "...", "macro_uids": ["..."]}]
    }

The uids link the workflow steps to the macros of the file. Files of the
first format, a plain list of serialized macros, can still be read. The
macros of such files get new uids.

Example usage::

    from pathlib import Path

    from qgis_macros.macro_file import MacroFile

    macro_file = MacroFile.load(Path("macros.json"))
    macros, workflows = macro_file.macros, macro_file.workflows

    MacroFile(macros, workflows).save(Path("copy.json"))
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qgis_macros.exceptions import InvalidMacroFileError
from qgis_macros.macro import Macro
from qgis_macros.macro_workflow import MacroWorkflow

FORMAT_VERSION = 2


@dataclass
class MacroFile:
    """Contents of a macro file."""

    macros: list[Macro] = field(default_factory=list)
    workflows: list[MacroWorkflow] = field(default_factory=list)

    @classmethod
    def for_workflows(
        cls, workflows: Iterable[MacroWorkflow], macros_by_uid: Mapping[str, Macro]
    ) -> "MacroFile":
        """Create a file of *workflows* and the macros they use.

        Each macro is included once in the order of first use. Steps that
        refer to unavailable macros are kept but their macros are left out.
        """
        workflows = list(workflows)
        uids = dict.fromkeys(uid for w in workflows for uid in w.macro_uids)
        macros = [macros_by_uid[uid] for uid in uids if uid in macros_by_uid]
        return cls(macros, workflows)

    def serialize(self) -> dict:
        """Serialize the file contents to a JSON-compatible dict."""
        return {
            "format_version": FORMAT_VERSION,
            "macros": [{"uid": m.uid, **m.serialize()} for m in self.macros],
            "workflows": [{"uid": w.uid, **w.serialize()} for w in self.workflows],
        }

    @classmethod
    def deserialize(cls, data: Any) -> "MacroFile":
        """Construct the file contents from :meth:`serialize` output.

        A plain list of serialized macros is also accepted.

        :raises ValueError: If the format version is not supported.
        :raises KeyError: If required data is missing.
        :raises TypeError: If the data has a wrong type.
        """
        if isinstance(data, list):
            return cls([Macro.deserialize(macro_data) for macro_data in data])
        if not isinstance(data, dict):
            raise TypeError(type(data).__name__)
        version = data.get("format_version")
        if version != FORMAT_VERSION:
            msg = f"Unsupported format version: {version}"
            raise ValueError(msg)

        macros = [
            _with_uid(Macro.deserialize(macro_data), macro_data)
            for macro_data in data["macros"]
        ]
        workflows = [
            _with_uid(MacroWorkflow.deserialize(workflow_data), workflow_data)
            for workflow_data in data.get("workflows", [])
        ]
        return cls(macros, workflows)

    @classmethod
    def load(cls, path: Path) -> "MacroFile":
        """Read a macro file.

        :raises InvalidMacroFileError: If the file cannot be read or parsed.
        """
        try:
            with path.open(encoding="utf-8") as f:
                return cls.deserialize(json.load(f))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            raise InvalidMacroFileError(str(path), e) from e

    def save(self, path: Path) -> None:
        """Write the file contents to *path*."""
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.serialize(), f, indent=4, ensure_ascii=False)


def _with_uid[T: (Macro, MacroWorkflow)](item: T, data: dict) -> T:
    """Set the uid of *item* from *data* if the data has one."""
    uid = data.get("uid")
    if uid:
        item.uid = str(uid)
    return item
