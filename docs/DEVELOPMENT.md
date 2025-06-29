# Development instructions

The code for the plugin is in the [src](../src) folder. Make sure you have
required tools, such as
Qt with Qt Editor and Qt Linquist installed by following this
[tutorial](https://www.qgistutorials.com/en/docs/3/building_a_python_plugin.html#get-the-tools).

## Setting up development environment

This project uses [uv] to manage python packages.
Make sure to have it installed first.

- Create a venv that is aware of system QGIS libraries: `uv venv --system-site-packages`
  - On Windows OSGeo4W v2 installs use `<osgeo>/apps/PythonXX/python.exe`
      with [necessary patches](./osgeo-python-patch.md)
- Activate the venv
- Install the dependencies:
- `uv sync`
- Install pre-commit: `pre-commit install`
- Create a `.env` from `.env.example`, and configure
  at least the QGIS executable path
- Launch development QGIS: `qpdt s`

## Requirements changes

To update requirements, do `uv lock --upgrade-package <package>`.

## Commit message style

Commit messages should follow [Conventional Commits notation](https://www.conventionalcommits.org/en/v1.0.0/#summary).

## Adding or editing source files

If you create or edit source files make sure that:

- they contain absolute imports:

    ```python

    from plugin.utils.exceptions import TestException # Good

    from ..utils.exceptions import TestException # Bad


    ```

- you consider adding test files for the new functionality

## Testing

Install python packages listed in [requirements.txt](../requirements.txt) to
the virtual environment and run tests with:

```shell script
pytest
```

[uv](https://docs.astral.sh/uv/getting-started/installation/)
[OSGeo4W issue](https://trac.osgeo.org/osgeo4w/ticket/692)
