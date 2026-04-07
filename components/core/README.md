# QGIS Macros Core component

[![docs](https://readthedocs.org/projects/macro-qgis-plugin/badge/?version=latest)](https://macro-qgis-plugin.readthedocs.io/en/latest/core/index.html)

This library contains the core macro recording and playback engine.
It can be used independently by other plugins without requiring the
UI plugin with [qgis-plugin-dev-tools](https://github.com/nlsfi/qgis-plugin-dev-tools?tab=readme-ov-file#setup)
`runtime_requires`.

**Package:** `macro-qgis-core` (PyPI) / `qgis_macros` (import)

## Quick start

```python
from qgis_macros.macro_recorder import MacroRecorder
from qgis_macros.macro_player import MacroPlayer

# Record
recorder = MacroRecorder()
recorder.start_recording()
# ... user interactions ...
macro = recorder.stop_recording()
macro.name = "My macro"

# Play back
player = MacroPlayer(playback_speed=1.0)
player.play(macro)
```

## API documentation

See the full [core library documentation](https://macro-qgis-plugin.readthedocs.io/en/latest/core/index.html).
