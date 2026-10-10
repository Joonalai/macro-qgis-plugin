# CHANGELOG

## Unreleased

- Updated from qgis-plugin-copier-template v0.8.1 and switched type checking to ty

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
