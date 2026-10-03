# CHANGELOG

## Unreleased

- Updated dependencies and added bandit security checks
- Adopted qgis-plugin-copier-template
- Dropped support for QGS < 3.40
- Fixed shift modifier not affecting typed text during playback
- Macros are autosaved to the QGIS profile (can be disabled in settings) and deleting a macro deletes its file
- Fixed playback of mouse moves with a button held (e.g. digitizing) and wheel events on Qt 6
- Fixed playback speed scale
- Added macro workflows that play existing macros in sequence
- Saved macro files contain macro workflows
