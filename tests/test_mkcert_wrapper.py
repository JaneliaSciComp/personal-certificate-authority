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


def _stub_mkcert_recording_trust_stores(tmp_path):
    """A fake `mkcert` that records the TRUST_STORES env var it was called
    with (on `-install`) and creates a root CA, without touching any real
    trust store or invoking sudo."""
    record_file = tmp_path / "trust_stores.txt"
    stub = tmp_path / "mkcert"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"-install\" ]]; then\n"
        f'  echo "${{TRUST_STORES:-<unset>}}" > "{record_file}"\n'
        '  mkdir -p "$CAROOT"\n'
        '  touch "$CAROOT/rootCA.pem" "$CAROOT/rootCA-key.pem"\n'
        "  exit 0\n"
        "fi\n"
        "exit 1\n"
    )
    stub.chmod(0o755)
    return stub, record_file


def test_init_default_never_touches_system_trust_store(settings: Settings, tmp_path):
    stub, record_file = _stub_mkcert_recording_trust_stores(tmp_path)
    settings.mkcert_binary = str(stub)

    mkcert_wrapper.init(settings)

    assert record_file.read_text().strip() == "nss"


def test_init_system_trust_lets_mkcert_autodetect(settings: Settings, tmp_path):
    stub, record_file = _stub_mkcert_recording_trust_stores(tmp_path)
    settings.mkcert_binary = str(stub)

    mkcert_wrapper.init(settings, system_trust=True)

    assert record_file.read_text().strip() == "<unset>"
