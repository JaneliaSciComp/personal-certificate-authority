from datetime import timedelta

from personal_certificate_authority import certinfo, mkcert_wrapper, store
from personal_certificate_authority.settings import Settings


def test_read_cert_root_ca(initialized_settings: Settings):
    cert_file, _ = store.root_ca_paths(initialized_settings)
    info = certinfo.read_cert(cert_file)
    assert info.common_name
    assert len(info.sha256_fingerprint.split(":")) == 32
    assert not info.is_near_expiry(margin=timedelta(days=0))


def test_read_cert_leaf_sans(initialized_settings: Settings):
    cert_file, _ = mkcert_wrapper.issue(initialized_settings, "test", ["localhost", "127.0.0.1"])
    info = certinfo.read_cert(cert_file)
    assert "localhost" in info.subject_alternative_names
    assert "127.0.0.1" in info.subject_alternative_names


def test_is_near_expiry_true_for_large_margin(initialized_settings: Settings):
    cert_file, _ = mkcert_wrapper.issue(initialized_settings, "test", ["localhost"])
    info = certinfo.read_cert(cert_file)
    assert info.is_near_expiry(margin=timedelta(days=365 * 100))
