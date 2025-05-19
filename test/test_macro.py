#  Copyright (c) 2025 macro-qgis-plugin contributors.
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
from qgis_macros.macro import Macro

pytest_plugins = [
    "macro_test_utils.macro_fixture",
]


def test_macro_serialization_and_deserialization(
    digitize_polygon_macro: Macro,
):
    serialized = digitize_polygon_macro.serialize()
    assert serialized
    assert isinstance(serialized, dict)

    deserialized = Macro.deserialize(serialized)
    assert deserialized == digitize_polygon_macro
