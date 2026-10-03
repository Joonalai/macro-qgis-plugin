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
"""Macro workflows that chain existing macros into a single playable sequence.

A workflow does not copy the macros it contains. Each step refers to a macro
by its :attr:`~qgis_macros.macro.Macro.uid`, so the same macro can appear in
many workflows, and several times in one workflow.

Example usage::

    from qgis_macros.macro_workflow import MacroWorkflow

    workflow = MacroWorkflow(name="Digitize", macro_uids=[first.uid, second.uid])
    macros = workflow.resolve_macros({m.uid: m for m in all_macros})
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from qgis_macros.exceptions import MacroNotFoundError
from qgis_macros.macro import Macro, new_macro_uid


@dataclass
class MacroWorkflow:
    """An ordered list of macro references that are played back one by one."""

    name: str | None = None
    macro_uids: list[str] = field(default_factory=list)
    uid: str = field(default_factory=new_macro_uid, compare=False)

    def serialize(self) -> dict:
        """Serialize the workflow to a JSON-compatible dict."""
        return {"name": self.name, "macro_uids": list(self.macro_uids)}

    @classmethod
    def deserialize(cls, data: dict) -> "MacroWorkflow":
        """Construct a workflow from a dict produced by :meth:`serialize`."""
        macro_uids = data["macro_uids"]
        if not isinstance(macro_uids, list):
            raise TypeError(macro_uids)
        return cls(name=data.get("name"), macro_uids=[str(uid) for uid in macro_uids])

    def resolve_macros(self, macros_by_uid: Mapping[str, Macro]) -> list[Macro]:
        """Return the macros of the workflow in playback order.

        :param macros_by_uid: Available macros keyed by their uid.
        :raises MacroNotFoundError: If a step refers to an unavailable macro.
        """
        try:
            return [macros_by_uid[uid] for uid in self.macro_uids]
        except KeyError as e:
            raise MacroNotFoundError(str(e.args[0])) from e
