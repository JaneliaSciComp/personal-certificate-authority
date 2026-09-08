import stat

import pytest

from personal_certificate_authority import mkcert_wrapper, store
from personal_certificate_authority.settings import Settings


def test_mkcert_not_found_raises_clear_error(settings: Settings):
    settings.mkcert_binary = "definitely-not-a-real-binary"
    with pytest.raises(mkcert_wrapper.MkcertNotFoundError):
        mkcert_wrapper.init(settings)


def test_init_creates_root_ca(initialized_settings: Settings):
    cert_file, key_file = store.root_ca_paths(initialized_settings)
    assert cert_file.exists()
    assert key_file.exists()


def test_issue_creates_leaf_cert_with_correct_permissions(initialized_settings: Settings):
    cert_file, key_file = mkcert_wrapper.issue(initialized_settings, "test", ["localhost", "127.0.0.1"])
    assert cert_file.exists()
    assert key_file.exists()
    assert stat.S_IMODE(cert_file.stat().st_mode) == 0o644
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600


def test_issue_is_idempotent_without_force(initialized_settings: Settings):
    cert_file, _ = mkcert_wrapper.issue(initialized_settings, "test", ["localhost"])
    first_mtime = cert_file.stat().st_mtime_ns

    mkcert_wrapper.issue(initialized_settings, "test", ["localhost"])
    assert cert_file.stat().st_mtime_ns == first_mtime


def test_issue_reissues_with_force(initialized_settings: Settings):
    cert_file, _ = mkcert_wrapper.issue(initialized_settings, "test", ["localhost"])
    first_mtime = cert_file.stat().st_mtime_ns

    mkcert_wrapper.issue(initialized_settings, "test", ["localhost"], force=True)
    assert cert_file.stat().st_mtime_ns != first_mtime


def test_issue_without_root_ca_raises(settings: Settings):
    with pytest.raises(RuntimeError, match="No root CA found"):
        mkcert_wrapper.issue(settings, "test", ["localhost"])
