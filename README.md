# macro plugin

![tests](https://github.com/Joonalai/macro-qgis-plugin/workflows/Tests/badge.svg)
[![docs](https://readthedocs.org/projects/macro-qgis-plugin/badge/?version=latest)](https://macro-qgis-plugin.readthedocs.io/en/latest/)
[![GPLv3 license](https://img.shields.io/badge/License-GPLv3-blue.svg)](http://perso.crans.org/besson/LICENSE.html)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

The QGIS Macro Plugin extends QGIS development tools with a macro panel
that allows users to record and playback simple macros.

![macro.gif](docs/macro.gif?raw=True "Macro recording")

## Features

* Record and playback macros (mouse and keyboard events)
* Combine macros into macro workflows that play them in sequence
* Save macros and macro workflows to disk for later usage
* Optionally profile macros

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

Licensed under GNU GPL v3.0.

Copyright (C) 2025-2026 macro-qgis-plugin contributors.
