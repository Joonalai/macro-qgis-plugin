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
import pytest
from qgis_macros.exceptions import MacroNotFoundError
from qgis_macros.macro import Macro
from qgis_macros.macro_workflow import MacroWorkflow


def test_workflow_serialization_and_deserialization() -> None:
    workflow = MacroWorkflow("workflow", ["a", "b", "a"])

    deserialized = MacroWorkflow.deserialize(workflow.serialize())

    assert deserialized == workflow
    assert deserialized.uid != workflow.uid


def test_workflow_deserialization_rejects_invalid_steps() -> None:
    with pytest.raises(TypeError):
        MacroWorkflow.deserialize({"name": "workflow", "macro_uids": "a"})


def test_workflow_resolves_macros_in_step_order() -> None:
    first, second = Macro(events=[], name="first"), Macro(events=[], name="second")
    workflow = MacroWorkflow("workflow", [second.uid, first.uid, second.uid])

    macros = workflow.resolve_macros({m.uid: m for m in (first, second)})

    assert [macro.name for macro in macros] == ["second", "first", "second"]


def test_workflow_resolve_raises_for_missing_macro() -> None:
    workflow = MacroWorkflow("workflow", ["missing"])

    with pytest.raises(MacroNotFoundError):
        workflow.resolve_macros({})
