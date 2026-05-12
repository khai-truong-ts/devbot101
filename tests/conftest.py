import pytest
from bot import config as _config


@pytest.fixture(autouse=True)
def restore_config():
    saved = {k: getattr(_config, k) for k in dir(_config) if not k.startswith("_")}
    yield
    for k, v in saved.items():
        try:
            setattr(_config, k, v)
        except AttributeError:
            pass
