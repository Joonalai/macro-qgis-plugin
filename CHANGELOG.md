# CHANGELOG

## Unreleased

- Playback failures report the macro and event that failed
- Key events fail instead of typing elsewhere when their window is closed
- The cursor follows mouse drags during playback
- Right clicks recorded where context menus open on press play where they open on release
- Widget lookup errors tell if the window is not open or the widget is hidden
- Added `MacroRecorder(ignore_playback=True)`, `MacroFile.upsert_macro()` and a widget tree dump

## 1.1.0 - 2026-10-13

- Relicensed under GPL-2.0-or-later
- Updated from qgis-plugin-copier-template v0.8.1 and switched type checking to ty
- Fixed recording wheel events on Qt 6
- Fixed map canvas macros failing when the window has moved or is covered
- Widget paths find windows by object name, so macros play in other projects
- Widgets and menu items are matched by object name, so macros play in other locales
- Macros record the locale and the panel warns when playing with another one
- Macros and macro workflows are registered as parameterless processing algorithms, so they can be run from the Processing toolbox and used as steps of graphical models
- Added `MacroPlayer.stop()` to stop an ongoing playback
- Key events are replayed on the recorded widget, so typing works while another window (e.g. the model designer or a processing dialog) is active
- Macros and workflows can be played on QGIS startup
- Fixed clicks on the record button ending up in macros
- Added an option to move the mouse smoothly during playback
- Macros wait for the workflows they start, e.g. from processing
- Fixed macro speed, recorded delays, duplicate wheel events, hidden toolbar buttons, resized map canvas and unfocused key events in playback
- Macros can be renamed from the context menu and sorted by name

## 1.0.1 - 2026-10-04

- Fixed release process

## 1.0.0 - 2026-10-03

- Updated dependencies and added bandit security checks
- Adopted qgis-plugin-copier-template
- Dropped support for QGS < 3.40
- Fixed shift modifier not affecting typed text during playback
- Macros are autosaved to the QGIS profile (can be disabled in settings) and deleting a macro deletes its file
- Fixed playback of mouse moves with a button held (e.g. digitizing) and wheel events on Qt 6
- Fixed playback speed scale
- Added macro workflows that play existing macros in sequence
- Saved macro files contain macro workflows
- Fixed context menus not opening when replaying right clicks
- Menu items are recorded by their texts so that items in submenus replay reliably
