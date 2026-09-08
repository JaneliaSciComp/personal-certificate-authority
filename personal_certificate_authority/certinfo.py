from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import NameOID

# Reissue proactively once a cert is within this many days of expiring.
EXPIRY_SAFETY_MARGIN = timedelta(days=7)


@dataclass
class CertInfo:
    common_name: str
    sha256_fingerprint: str
    not_valid_after: datetime
    subject_alternative_names: List[str]

    def is_near_expiry(self, margin: timedelta = EXPIRY_SAFETY_MARGIN) -> bool:
        return datetime.now(timezone.utc) + margin >= self.not_valid_after


def read_cert(path: Path) -> CertInfo:
    cert = x509.load_pem_x509_certificate(path.read_bytes())

    cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    common_name = cn_attrs[0].value if cn_attrs else ""

    try:
        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        sans = san_ext.value.get_values_for_type(x509.DNSName)
        sans += [str(ip) for ip in san_ext.value.get_values_for_type(x509.IPAddress)]
    except x509.ExtensionNotFound:
        sans = []

    fingerprint = cert.fingerprint(hashes.SHA256()).hex(":")

    not_valid_after = cert.not_valid_after_utc

    return CertInfo(
        common_name=common_name,
        sha256_fingerprint=fingerprint,
        not_valid_after=not_valid_after,
        subject_alternative_names=sans,
    )
