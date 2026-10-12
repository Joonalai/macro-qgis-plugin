# macro plugin

![tests](https://github.com/Joonalai/macro-qgis-plugin/workflows/Tests/badge.svg)
[![docs](https://readthedocs.org/projects/macro-qgis-plugin/badge/?version=latest)](https://macro-qgis-plugin.readthedocs.io/en/latest/)
[![GPL-2.0-or-later license](https://img.shields.io/badge/License-GPL--2.0--or--later-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![prek](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/j178/prek/master/docs/assets/badge-v0.json)](https://github.com/j178/prek)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)

The QGIS Macro Plugin extends QGIS development tools with a macro panel
that allows users to record and playback simple macros.

![macro.gif](docs/macro.gif?raw=True "Macro recording")

## Features

* Record and playback macros (mouse and keyboard events)
* Combine macros into macro workflows that play them in sequence
* Save macros and macro workflows to disk for later usage
* Run macros and macro workflows as processing algorithms, for example as model steps
* Optionally profile macros
* Play a macro workflow automatically when QGIS starts

## Installation

Install the plugin from the QGIS plugin repository
or download the zip from the repository releases.

### From Release ZIP

1. Download the latest release ZIP from the
   [GitHub releases](https://github.com/Joonalai/macro-qgis-plugin/releases)
2. In QGIS, go to **Plugins** > **Manage and Install Plugins...**
3. Select **Install from ZIP** and choose the downloaded file

## Usage

Open QGIS Development Tools and interact with the Macro tab.

### Recording a Macro

Click the **Record** button in the macro panel, then interact with QGIS normally
(click, type, navigate, etc.). The macro records your mouse and keyboard events.
Click **Record** again to stop and name the macro.

### Playing Back a Macro

Select a saved macro from the table and click the **Play** button to replay
the recorded events.

### Building Macro Workflows

A macro workflow plays existing macros one after another, and the same macro
can be used several times. On the **Macro workflows** tab, create a workflow
and add macros to it by dragging them from the **All macros** tab or with the
add menus. Drag the steps or use the arrow buttons to reorder them.

### Saving and Loading Macros

Click the **Save** button to export all macros and macro workflows as a `.json`
file. To share a single workflow, use **Export workflow** on the
**Macro workflows** tab. It saves the workflow with the macros it uses.
Selected macros can be exported from the context menu of the **All macros** tab.

Use the **Open** button to load previously saved macros and workflows from disk.
Macros and workflows that are already in the panel are not loaded again.

### Running Macros from Processing

Every macro and macro workflow is also available as a parameterless
processing algorithm. The algorithms are listed under the **Macros** and
**Macro workflows** providers of the Processing toolbox, and they can be used
as steps of graphical models. The algorithms are added and removed as macros
and workflows are recorded, loaded, renamed and deleted. The algorithm id is
based on the uid of the macro, so renaming a macro does not break models that
use it.

Because the steps have no parameters, model steps are not automatically run
in a fixed order. Set the **Dependencies** of the model steps to run the macros
one after another, or use a macro workflow as a single step.

### Running Macros on Startup

A macro workflow or a macro can be played automatically when QGIS starts.
Playback begins after QGIS has finished loading. Use environment variables,
for example in a `.bat` or `.sh` script that starts QGIS:

```bat
set QGIS_MACRO_STARTUP_FILE=C:\macros\macros.json
set QGIS_MACRO_STARTUP_WORKFLOW=Digitize
"C:\Program Files\QGIS 3.44\bin\qgis-bin.exe"
```

| Variable                      | Description                                     |
|-------------------------------|-------------------------------------------------|
| `QGIS_MACRO_STARTUP_FILE`     | Path of the macro file to play                  |
| `QGIS_MACRO_STARTUP_WORKFLOW` | Name or uid of the workflow to play             |
| `QGIS_MACRO_STARTUP_MACRO`    | Name or uid of a macro to play instead          |
| `QGIS_MACRO_STARTUP_EXIT`     | `true` quits QGIS afterwards (1 on failure)     |
| `QGIS_MACRO_STARTUP_DELAY_MS` | Wait after QGIS has loaded (default 1000)       |

Or call the plugin from a
[startup script](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/intro.html#running-python-code-when-qgis-starts)
(`startup.py`):

```python
from macro_plugin.startup import play_on_startup

play_on_startup("/path/to/macros.json", workflow="Digitize")
```

Without a workflow or macro, the only workflow of the file is played.
A file without workflows plays all of its macros in order.

### Using the Core Library

The core library (`qgis_macros`) can be used independently of the plugin.
See the [API documentation](https://macro-qgis-plugin.readthedocs.io/en/latest/core/index.html)
for details.

```python
from qgis_macros.macro import Macro
from qgis_macros.macro_player import MacroPlayer
from qgis_macros.macro_recorder import MacroRecorder

# Record a macro
recorder = MacroRecorder()
recorder.start_recording()
# ... user interactions ...
macro = recorder.stop_recording()

# Play it back
player = MacroPlayer(playback_speed=1.5)
player.play(macro)
```

## Requirements

* QGIS version **3.34** or higher (including QGIS 4).
* Python **3.12** or higher.

## Documentation

Full documentation is available at
[macro-qgis-plugin.readthedocs.io](https://macro-qgis-plugin.readthedocs.io/en/latest/).

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

See [development readme](DEVELOPMENT.md) for details.

## Inspirations

These awesome plugins are used as an inspiration for the plugin structure:

* <https://github.com/Joonalai/profiler-qgis-plugin>
  * Initially this plugin was part of profiler-qgis-plugin
* <https://github.com/nlsfi/pickLayer>
* <https://github.com/nlsfi/segment-reshape-qgis-plugin>
* <https://github.com/GispoCoding/pytest-qgis>

## License & copyright

Licensed under GNU GPL v2.0 or later.

Copyright (C) 2025-2026 macro-qgis-plugin contributors.
