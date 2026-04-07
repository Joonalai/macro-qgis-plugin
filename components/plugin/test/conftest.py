import pytest
from qgis_macros.settings import Settings


@pytest.fixture(autouse=True)
def _reset_settings():
    Settings.reset()
