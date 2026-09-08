import os
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from loguru import logger

from personal_certificate_authority import store
from personal_certificate_authority.settings import Settings


class MkcertNotFoundError(RuntimeError):
    def __init__(self, binary: str):
        super().__init__(
            f"Could not find the '{binary}' binary on PATH. "
            "Add 'mkcert' to this project's pixi dependencies (conda-forge) "
            "and run inside the pixi environment (e.g. `pixi run pca ...`)."
        )


class MkcertError(RuntimeError):
    def __init__(self, args: Sequence[str], returncode: int, stdout: str, stderr: str):
        self.args_ = list(args)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(
            f"mkcert {' '.join(args)} failed with exit code {returncode}:\n{stderr or stdout}"
        )


def _env(settings: Settings) -> dict:
    env = dict(os.environ)
    env["CAROOT"] = str(settings.caroot_dir)
    return env


def _run(settings: Settings, args: Sequence[str], extra_env: dict | None = None) -> subprocess.CompletedProcess:
    binary = shutil.which(settings.mkcert_binary)
    if binary is None:
        raise MkcertNotFoundError(settings.mkcert_binary)

    store.ensure_dir(settings.caroot_dir)
    env = _env(settings)
    if extra_env:
        env.update(extra_env)
    logger.debug("Running: {} {}", binary, " ".join(args))
    result = subprocess.run(
        [binary, *args],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise MkcertError(args, result.returncode, result.stdout, result.stderr)
    return result


def is_root_ca_present(settings: Settings) -> bool:
    cert_file, key_file = store.root_ca_paths(settings)
    return cert_file.exists() and key_file.exists()


def init(settings: Settings, force: bool = False) -> None:
    """Create (if absent) and install the root CA under our pinned CAROOT.

    mkcert's `-install` both generates the root CA under CAROOT if one
    doesn't exist yet, and installs it into whatever local trust stores it
    can reach on this host (system store, Firefox/Chrome NSS db). The
    system-trust-store step commonly requires `sudo`, which isn't available
    non-interactively on a shared/headless host (e.g. an HPC node) — in that
    case we fall back to NSS-only (browser) trust so the CA still gets
    created and usable, and point the user at `pca trust`/`pca serve` for
    manual system-wide installation.
    """
    if force and is_root_ca_present(settings):
        logger.warning(
            "Regenerating the root CA invalidates all previously issued leaf "
            "certificates and any trust-store installs made from the old CA "
            "(on this host or any other machine that trusted the old "
            "rootCA.pem)."
        )
        uninstall(settings)
        cert_file, key_file = store.root_ca_paths(settings)
        cert_file.unlink(missing_ok=True)
        key_file.unlink(missing_ok=True)

    try:
        _run(settings, ["-install"])
    except MkcertError as exc:
        if not is_root_ca_present(settings):
            raise
        logger.warning(
            "The root CA was created, but installing it into the system "
            "trust store failed (likely needs 'sudo' privileges this "
            "process doesn't have):\n{}\n"
            "Retrying with browser-only (NSS) trust; run `pca trust` or "
            "`pca serve` for manual system-wide install instructions.",
            exc.stderr or exc.stdout,
        )
        try:
            _run(settings, ["-install"], extra_env={"TRUST_STORES": "nss"})
        except MkcertError as nss_exc:
            logger.warning(
                "Browser (NSS) trust install also failed, likely because "
                "'certutil' isn't installed:\n{}\n"
                "The CA was still created and can issue certificates; "
                "run `pca trust` for manual install instructions.",
                nss_exc.stderr or nss_exc.stdout,
            )


def uninstall(settings: Settings) -> None:
    """Best-effort removal from local trust stores on this host only."""
    if not is_root_ca_present(settings):
        return
    _run(settings, ["-uninstall"])


def issue(settings: Settings, name: str, sans: Sequence[str], force: bool = False) -> tuple[Path, Path]:
    if not is_root_ca_present(settings):
        raise RuntimeError("No root CA found. Run `pca init` first.")

    cert_file, key_file = store.cert_paths(settings, name)
    all_sans = list(dict.fromkeys([*settings.default_sans, *sans]))

    if not force and cert_file.exists() and key_file.exists():
        from personal_certificate_authority import certinfo

        info = certinfo.read_cert(cert_file)
        if not info.is_near_expiry() and set(all_sans) <= set(info.subject_alternative_names):
            logger.info("Certificate '{}' already covers requested SANs and is valid; skipping. Use --force to reissue.", name)
            return cert_file, key_file

    store.ensure_dir(store.cert_dir(settings, name))
    _run(settings, ["-cert-file", str(cert_file), "-key-file", str(key_file), *all_sans])
    cert_file.chmod(0o644)
    key_file.chmod(0o600)
    return cert_file, key_file


def caroot(settings: Settings) -> Path:
    result = _run(settings, ["-CAROOT"])
    return Path(result.stdout.strip())
