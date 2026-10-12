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

from qgis_macros import settings
from qgis_macros.settings import Settings
from qgis_plugin_tools.tools.exceptions import PluginNotFoundError

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_setting_falls_back_to_default_without_plugin(mocker: "MockerFixture"):
    # E.g. the library is used outside of plugins while several are loaded
    mocker.patch.object(
        settings, "get_setting", side_effect=PluginNotFoundError("ambiguous")
    )

    assert Settings.move_event_interpolation_count.get() == 4
    assert Settings.speed.get() == 1.0
