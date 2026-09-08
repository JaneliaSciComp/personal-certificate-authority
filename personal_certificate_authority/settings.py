import os
from pathlib import Path
from typing import List, Optional

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


def _default_data_dir() -> Path:
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
    return base / "personal-certificate-authority"


def _default_config_dir() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_config_home) if xdg_config_home else Path.home() / ".config"
    return base / "personal-certificate-authority"


class Settings(BaseSettings):
    """Settings can be read from a config.yaml file, or from the environment,
    with environment variables prepended with "pca_" (case insensitive). The
    environment variables can be passed in the environment or in a .env file.
    """

    model_config = SettingsConfigDict(env_prefix="pca_", env_nested_delimiter="__")

    log_level: str = "INFO"

    data_dir: Path = _default_data_dir()
    config_dir: Path = _default_config_dir()

    # Binary resolved via PATH (the pixi env provides this via conda-forge's
    # mkcert package). Overridable for testing with a stub binary.
    mkcert_binary: str = "mkcert"

    # Always merged into any `pca issue` SAN list so issued certs work out of
    # the box for the common local-dev case.
    default_sans: List[str] = ["localhost", "127.0.0.1", "::1"]

    web_host: str = "127.0.0.1"
    web_port: int = 8990

    @property
    def caroot_dir(self) -> Path:
        return self.data_dir / "mkcert"

    @property
    def certs_dir(self) -> Path:
        return self.data_dir / "certs"

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.yaml"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        yaml_settings = YamlConfigSettingsSource(settings_cls, yaml_file=_default_config_dir() / "config.yaml")
        return (init_settings, env_settings, dotenv_settings, yaml_settings, file_secret_settings)


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
