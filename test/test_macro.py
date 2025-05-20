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
import pytest

from qgis_macros.macro import Macro, Position

pytest_plugins = [
    "macro_test_utils.macro_fixture",
]


def _create_test_position(x: int, y: int) -> Position:
    return Position((x, y), (x + 10, y + 10))


def test_macro_serialization_and_deserialization(
    digitize_polygon_macro: Macro,
):
    serialized = digitize_polygon_macro.serialize()
    assert serialized
    assert isinstance(serialized, dict)

    deserialized = Macro.deserialize(serialized)
    assert deserialized == digitize_polygon_macro


@pytest.mark.parametrize(
    ("positions", "number_of_positions", "expected_positions"),
    [
        ([_create_test_position(0, 0)], 2, [_create_test_position(0, 0)]),
        (
            [
                _create_test_position(*point)
                for point in [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
            ],
            2,
            [_create_test_position(*point) for point in [(0, 0), (5, 5)]],
        ),
        (
            [
                _create_test_position(*point)
                for point in [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
            ],
            3,
            [_create_test_position(*point) for point in [(0, 0), (2, 2), (5, 5)]],
        ),
        (
            [
                _create_test_position(*point)
                for point in [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
            ],
            4,
            [
                _create_test_position(*point)
                for point in [(0, 0), (1, 1), (3, 3), (5, 5)]
            ],
        ),
    ],
)
def test_position_interpolation(
    positions: list[Position],
    number_of_positions: int,
    expected_positions: list[Position],
):
    assert Position.interpolate(positions, number_of_positions) == expected_positions
