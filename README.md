# QGIS macro plugin

![tests](https://github.com/Joonalai/macro-qgis-plugin/workflows/Tests/badge.svg)
[![GPLv3 license](https://img.shields.io/badge/License-GPLv3-blue.svg)](http://perso.crans.org/besson/LICENSE.html)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

The QGIS Macro Plugin is a plugin ment to extend QGIS development tools
dock widget with macro panel to allow user to record simple macros
![macro.gif](docs/macro.gif?raw=True "Profiling")

## Features

* Record and playback macros, ie. user mouse and keyboard events
* Save macros to disk for later usage
* Optionally profile macros

## Installation

1. Clone the repository from GitHub.
2. Install requirements (in a venv created with --system-site-packages): `[uv] sync`
3. Build a package: `qpdt b`
4. Open QGIS and navigate to `Plugins > Manage and Install Plugins`.
5. Click the `Install from ZIP` option and install the packaged plugin zip.

## Usage

Open QGIS development tools and interact with macro panel.

## Requirements

* QGIS version **3.34** or higher.

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

See [development readme](docs/DEVELOPMENT.md) for details.

## Inspirations

These awesome plugins are used as an inspiration for the plugin structure:

* <https://github.com/Joonalai/profiler-qgis-plugin>
  * Initially this plugin was part of profiler-qgis-plugin
* <https://github.com/nlsfi/pickLayer>
* <https://github.com/nlsfi/segment-reshape-qgis-plugin>
* <https://github.com/GispoCoding/pytest-qgis>

## License & copyright

Licensed under GNU GPL v3.0.

Copyright (C) 2025 macro-qgis-plugin contributors.

[uv](https://docs.astral.sh/uv/getting-started/installation/)
