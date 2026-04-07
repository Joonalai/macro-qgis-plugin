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

"""Stub modules for QGIS/PyQt dependencies used during Sphinx doc builds."""

import sys
import types


class _Stub:
    """Universal stub that accepts any args and returns stubs for any attr."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __getattr__(self, name):
        if name == "value":
            return 0
        return _Stub()

    def __call__(self, *args, **kwargs):
        return _Stub()

    def __bool__(self) -> bool:
        return False

    def __str__(self) -> str:
        return ""

    def __repr__(self) -> str:
        return ""

    def __iter__(self):
        return iter([])

    def __eq__(self, other):
        return isinstance(other, _Stub)

    def __hash__(self):
        return 0

    def __int__(self) -> int:
        return 0

    def __float__(self) -> float:
        return 0.0

    def __gt__(self, other):
        return False

    def __lt__(self, other):
        return False

    def __ge__(self, other):
        return True

    def __le__(self, other):
        return True


class _StubSignal:
    """Minimal pyqtSignal stub usable as a class attribute."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def connect(self, *args, **kwargs) -> None:
        pass

    def disconnect(self, *args, **kwargs) -> None:
        pass

    def emit(self, *args, **kwargs) -> None:
        pass


class _QObjectStub:
    """Minimal QObject stub that supports being a base class."""

    def __init__(self, *args, **kwargs) -> None:
        pass


class _QWidgetStub(_QObjectStub):
    """Stub for QWidget."""

    def setupUi(self, *args, **kwargs) -> None:
        pass


class _QDialogStub(_QWidgetStub):
    """Stub for QDialog."""

    def exec(self, *args, **kwargs) -> None:
        pass


def _make_module(name, attrs=None):
    """Create a stub module and register it in sys.modules."""
    mod = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    mod.__getattr__ = lambda attr: _Stub()  # type: ignore
    sys.modules[name] = mod
    return mod


def install_stubs() -> None:
    """Install all QGIS/PyQt stub modules into sys.modules."""

    # -- qgis package hierarchy --
    qgis = _make_module("qgis")

    # Qgis stub needs versionInt() to return a real int (used as dataclass default)
    _qgis_class = type(
        "Qgis",
        (),
        {
            "versionInt": staticmethod(lambda: 0),
            "__getattr__": lambda self, name: _Stub(),
        },
    )
    qgis_core = _make_module(
        "qgis.core",
        {
            "Qgis": _qgis_class(),
            "QgsApplication": _Stub(),
            "QgsLineString": _Stub,
        },
    )
    qgis.core = qgis_core

    qgis_gui = _make_module(
        "qgis.gui",
        {
            "QgisInterface": _Stub,
            "QgsCollapsibleGroupBox": _Stub,
            "QgsDevToolWidget": _QWidgetStub,
            "QgsDevToolWidgetFactory": _Stub,
        },
    )
    qgis.gui = qgis_gui

    # -- qgis.PyQt stubs --
    pyqt = _make_module("qgis.PyQt")
    qgis.PyQt = pyqt

    qtwidgets = _make_module(
        "qgis.PyQt.QtWidgets",
        {
            "QApplication": _Stub(),
            "QWidget": _QWidgetStub,
            "QDialog": _QDialogStub,
            "QAbstractButton": _Stub,
            "QCheckBox": _Stub,
            "QComboBox": _Stub,
            "QDialogButtonBox": _Stub,
            "QDockWidget": _Stub,
            "QDoubleSpinBox": _Stub,
            "QFileDialog": _Stub,
            "QFormLayout": _Stub,
            "QLabel": _Stub,
            "QLineEdit": _Stub,
            "QPushButton": _Stub,
            "QSpinBox": _Stub,
            "QToolButton": _Stub,
            "QTreeView": _Stub,
            "QVBoxLayout": _Stub,
        },
    )
    pyqt.QtWidgets = qtwidgets

    qtcore = _make_module(
        "qgis.PyQt.QtCore",
        {
            "QObject": _QObjectStub,
            "QAbstractItemModel": _Stub,
            "QAbstractTableModel": _Stub,
            "QCoreApplication": _Stub(),
            "QEvent": type(
                "QEvent",
                (),
                {
                    "Type": _Stub(),
                    "registerEventType": staticmethod(lambda: 0),
                    "type": lambda self: 0,
                },
            ),
            "QEventLoop": _Stub,
            "QElapsedTimer": _Stub,
            "QModelIndex": _Stub,
            "QPoint": _Stub,
            "QPointF": _Stub,
            "Qt": _Stub(),
            "QThread": _Stub,
            "QTimer": _Stub,
            "QT_VERSION_STR": "6.8.0",
            "pyqtSignal": _StubSignal,
            "pyqtSlot": lambda *args, **kwargs: lambda fn: fn,
        },
    )
    pyqt.QtCore = qtcore

    qtgui = _make_module(
        "qgis.PyQt.QtGui",
        {
            "QCursor": _Stub(),
            "QIcon": _Stub,
            "QMouseEvent": _Stub,
            "QWheelEvent": _Stub,
            "QKeyEvent": _Stub,
        },
    )
    pyqt.QtGui = qtgui

    _make_module(
        "qgis.PyQt.QtTest",
        {
            "QTest": _Stub(),
        },
    )

    _make_module(
        "qgis.utils",
        {
            "iface": _Stub(),
        },
    )

    # -- qgis_plugin_tools --
    _make_module("qgis_plugin_tools")
    _make_module("qgis_plugin_tools.tools")
    _make_module(
        "qgis_plugin_tools.tools.custom_logging",
        {
            "setup_loggers": lambda *args, **kwargs: lambda: None,
            "bar_msg": lambda *args, **kwargs: "",
            "log": lambda *args, **kwargs: None,
            "LogTarget": _Stub(),
            "get_log_level_key": lambda *args: "",
            "get_log_level_name": lambda *args: "",
        },
    )
    _make_module(
        "qgis_plugin_tools.tools.exceptions",
        {
            "QgsPluginException": Exception,
        },
    )
    _make_module(
        "qgis_plugin_tools.tools.i18n",
        {
            "tr": lambda *args, **kwargs: args[0] if args else "",
        },
    )
    _make_module(
        "qgis_plugin_tools.tools.messages",
        {
            "MsgBar": _Stub(),
            "bar_msg": lambda *args, **kwargs: "",
        },
    )
    _make_module(
        "qgis_plugin_tools.tools.resources",
        {
            "profile_path": lambda *args: "/tmp/macro",
            "load_ui_from_file": lambda *args: type(
                "_UiClass",
                (),
                {
                    "setupUi": lambda self, *a, **kw: None,
                },
            ),
        },
    )
    _make_module(
        "qgis_plugin_tools.tools.settings",
        {
            "get_setting": lambda name, default=None, **kwargs: default,
            "set_setting": lambda *args, **kwargs: None,
            "save_settings": lambda *args, **kwargs: None,
        },
    )
    _make_module(
        "qgis_plugin_tools.tools.decorations",
        {
            "log_if_fails": lambda *args, **kwargs: lambda fn: fn,
        },
    )
