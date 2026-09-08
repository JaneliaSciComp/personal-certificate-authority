import shutil
import subprocess
from pathlib import Path

import pytest

from personal_certificate_authority.settings import Settings


@pytest.fixture
def real_mkcert_available() -> bool:
    return shutil.which("mkcert") is not None


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        config_dir=tmp_path / "config",
    )


@pytest.fixture
def initialized_settings(settings: Settings) -> Settings:
    if shutil.which("mkcert") is None:
        pytest.skip("mkcert binary not available on PATH")
    from personal_certificate_authority import mkcert_wrapper

    mkcert_wrapper.init(settings)
    return settings
