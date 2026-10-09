#  Copyright (c) 2026 macro-qgis-plugin contributors.
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
"""Steps shared by the macro playbacks of the panel and the processing algorithms."""

from qgis.core import QgsApplication
from qgis_macros.macro import Macro
from qgis_macros.settings import Settings
from qgis_macros.utils import current_locale
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.utils.typing_utils import require


def locale_mismatch_message(macro: Macro) -> str | None:
    """Return a warning if *macro* was recorded with another locale, else None."""
    locale = current_locale()
    if not macro.locale or macro.locale == locale:
        return None
    return tr(
        "Macro '{}' was recorded with locale {} but the current locale "
        "is {}. Widgets and menu items may not be found.",
        macro.name or macro.uid,
        macro.locale,
        locale,
    )


def start_profiling(macro: Macro) -> None:
    """Start profiling the playback of *macro* if profiling is enabled."""
    if Settings.profile_macros.get():
        require(QgsApplication.profiler()).start(
            f"Macro: {macro.name or macro.uid}", Settings.profile_macro_group.get()
        )


def end_profiling() -> None:
    """End profiling the playback started with :func:`start_profiling`."""
    if Settings.profile_macros.get():
        require(QgsApplication.profiler()).end(Settings.profile_macro_group.get())
