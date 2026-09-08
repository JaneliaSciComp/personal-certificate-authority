from pathlib import Path

from personal_certificate_authority.settings import Settings


def ensure_dir(path: Path, mode: int = 0o700) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=mode)
    path.chmod(mode)
    return path


def cert_dir(settings: Settings, name: str) -> Path:
    return settings.certs_dir / name


def cert_paths(settings: Settings, name: str) -> tuple[Path, Path]:
    """Return (cert_file, key_file) paths for a named leaf certificate."""
    d = cert_dir(settings, name)
    return d / "cert.pem", d / "key.pem"


def root_ca_paths(settings: Settings) -> tuple[Path, Path]:
    """Return (rootCA.pem, rootCA-key.pem) paths under our pinned CAROOT."""
    caroot = settings.caroot_dir
    return caroot / "rootCA.pem", caroot / "rootCA-key.pem"


def list_cert_names(settings: Settings) -> list[str]:
    if not settings.certs_dir.is_dir():
        return []
    return sorted(
        p.name for p in settings.certs_dir.iterdir()
        if p.is_dir() and (p / "cert.pem").exists()
    )
