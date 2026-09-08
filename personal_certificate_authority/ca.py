import datetime
import getpass
import os
import socket
import subprocess

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from loguru import logger

from personal_certificate_authority import store
from personal_certificate_authority.settings import Settings

ROOT_CA_VALIDITY_DAYS = 3650


def detect_common_name(settings: Settings) -> str:
    """Resolve the identity string used as the root CA's Subject/Issuer
    CommonName.

    mkcert hardcodes its own root CA's CommonName to "mkcert
    <user>@<hostname>" with no flag or env var to override it (verified
    against mkcert's source: that exact format is required by iOS to show
    the cert in Settings, so upstream won't add a knob for it). mkcert does
    not care who created rootCA.pem/rootCA-key.pem, though -- if valid files
    already exist at CAROOT when `mkcert -install` runs, it uses them
    as-is (verified live) -- so generating just the root CA ourselves (see
    `generate_root_ca`) lets us pick a CommonName that's actually
    meaningful, while leaf-cert issuance and trust-store installation stay
    entirely mkcert's job, unchanged.

    Resolution order: the `root_ca_common_name` setting (env var
    `PCA_ROOT_CA_COMMON_NAME`) > `git config user.email` > `$EMAIL` >
    mkcert's own `user@hostname` format, so a host with none of the above
    configured still gets a sensible, unique default.
    """
    if settings.root_ca_common_name:
        return settings.root_ca_common_name

    try:
        result = subprocess.run(
            ["git", "config", "--get", "user.email"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass

    email = os.environ.get("EMAIL")
    if email:
        return email

    return f"{getpass.getuser()}@{socket.getfqdn()}"


def generate_root_ca(settings: Settings) -> None:
    """Generate a self-signed root CA under CAROOT, using the same
    filenames mkcert itself would use there (`rootCA.pem`/`rootCA-key.pem`)
    so a subsequent `mkcert -install` finds them already present and skips
    its own generation, only performing the trust-store install.

    Only called when no root CA exists yet -- never overwrites one.
    """
    cert_file, key_file = store.root_ca_paths(settings)
    common_name = detect_common_name(settings)
    logger.info("Generating root CA with CommonName '{}'", common_name)

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)

    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=ROOT_CA_VALIDITY_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
        )
        .sign(key, hashes.SHA256())
    )

    store.ensure_dir(settings.caroot_dir, settings)
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    cert_file.chmod(0o644)

    key_bytes = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    store.write_private_key(key_file, key_bytes)
