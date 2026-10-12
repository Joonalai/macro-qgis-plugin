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

"""Pytest plugin choosing the number of pytest-xdist workers for ``-n auto``.

Load it before the conftest files with ``-p macro_test_utils.xdist_utils``.
pytest-qgis decides whether to start QGIS while the initial conftest files
are loaded, before pytest-xdist resolves ``-n auto``, so a
``pytest_xdist_auto_num_workers`` hook in a conftest would come too late.

Do not import QGIS here, the plugin is loaded before pytest-qgis sets it up.
"""

from collections.abc import Generator

import pytest

AUTO_NUM_PROCESSES = ("auto", "logical")


def get_number_of_workers(config: pytest.Config) -> int | None:
    """Return the number of workers, or None to let pytest-xdist decide.

    Tests run in the main process, which also makes debugging work, if

    - only individual tests are run, e.g. ``test_macro.py::test_name``, or
    - the QGIS GUI is enabled, since the workers would share the screen and
      the mouse cursor that the tests move.

    Otherwise pytest-xdist uses as many workers as there are CPUs.
    """
    paths = _option(config, "file_or_dir")
    if isinstance(paths, list) and paths and all("::" in path for path in paths):
        return 0
    if _gui_enabled(config):
        return 0
    return None


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_load_initial_conftests(
    early_config: pytest.Config,
) -> Generator[None, None, None]:
    """Resolve ``-n auto`` to 0 workers before pytest-qgis checks for workers."""
    namespace = early_config.known_args_namespace
    if (
        getattr(namespace, "numprocesses", None) in AUTO_NUM_PROCESSES
        and get_number_of_workers(early_config) == 0
    ):
        namespace.numprocesses = 0
    return (yield)


@pytest.hookimpl(tryfirst=True)
def pytest_xdist_auto_num_workers(config: pytest.Config) -> int | None:
    # Before the default implementation of pytest-xdist, which registers later
    return get_number_of_workers(config)


def _gui_enabled(config: pytest.Config) -> bool:
    """Return whether pytest-qgis shows the QGIS GUI."""
    if _option(config, "qgis_disable_gui"):
        return False
    return bool(config.getini("qgis_gui_enabled"))


def _option(config: pytest.Config, name: str) -> object:
    # The options are parsed only partly while the conftest files are loaded
    return getattr(config.known_args_namespace, name, None)
