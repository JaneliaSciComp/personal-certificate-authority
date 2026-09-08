import os
from pathlib import Path

from personal_certificate_authority.settings import Settings


def ensure_dir(path: Path, settings: Settings, mode: int = 0o700) -> Path:
    """Create `path` (and any missing parents) and ensure `mode` is applied
    at every level from `path` up through `settings.data_dir`.

    `Path.mkdir(parents=True, mode=mode)` only applies `mode` to the leaf
    directory it creates -- any missing intermediate parents (here, that
    can include `data_dir` itself, or `certs_dir`) are created with the
    default umask-derived mode instead. Verified on a real install: this
    left the whole data directory `0775` (group-writable, world-readable),
    not `0700`, even though every leaf directory this function was called
    on directly was correctly `0700`. Walking every level and chmod'ing
    unconditionally (not just newly-created ones) also self-heals any
    directory left over-permissive by a prior run.
    """
    path.mkdir(parents=True, exist_ok=True)
    data_dir = settings.data_dir.resolve()
    p = path.resolve()
    p.chmod(mode)
    while p != data_dir and data_dir in p.parents:
        p = p.parent
        p.chmod(mode)
    return path


def write_private_key(path: Path, data: bytes, mode: int = 0o400) -> None:
    """Write a private key file with `mode` applied atomically at creation
    -- never a moment where it's readable at the default umask-derived
    permissions. `Path.write_bytes` followed by a separate `chmod` leaves a
    (small but real) window where a new file sits at the default mode
    before the chmod call catches up; opening with the restrictive mode
    from the start closes that window entirely.
    """
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    path.chmod(mode)  # os.open's mode is affected by umask; re-assert it.


def touch_restricted(path: Path, mode: int = 0o600) -> None:
    """Pre-create an empty file with restrictive permissions before an
    external process (mkcert) writes the real content into it.

    POSIX `open()` with `O_CREAT` only applies the given mode when it
    creates the file; if the file already exists, a subsequent truncating
    write preserves the existing permissions instead of resetting them.
    Pre-creating the file here means mkcert's own write (e.g. for a leaf
    key via `-key-file`) can never leave it briefly at whatever default,
    less restrictive permissions mkcert would otherwise create it with.
    """
    fd = os.open(path, os.O_WRONLY | os.O_CREAT, mode)
    os.close(fd)
    path.chmod(mode)


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
