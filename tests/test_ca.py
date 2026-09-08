import stat
import subprocess

from personal_certificate_authority import ca, certinfo, store
from personal_certificate_authority.settings import Settings


def test_detect_common_name_uses_explicit_setting(settings: Settings):
    settings.root_ca_common_name = "explicit@example.org"
    assert ca.detect_common_name(settings) == "explicit@example.org"


def test_detect_common_name_falls_back_to_user_hostname(settings: Settings, monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "")
    )
    monkeypatch.delenv("EMAIL", raising=False)

    name = ca.detect_common_name(settings)

    assert "@" in name


def test_detect_common_name_uses_email_env_when_no_git_config(settings: Settings, monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "")
    )
    monkeypatch.setenv("EMAIL", "from-env@example.org")

    assert ca.detect_common_name(settings) == "from-env@example.org"


def test_generate_root_ca_uses_resolved_common_name(settings: Settings):
    settings.root_ca_common_name = "test-ca@example.org"

    ca.generate_root_ca(settings)

    cert_file, _ = store.root_ca_paths(settings)
    info = certinfo.read_cert(cert_file)
    assert info.common_name == "test-ca@example.org"


def test_generate_root_ca_sets_restrictive_permissions(settings: Settings):
    settings.root_ca_common_name = "test-ca@example.org"

    ca.generate_root_ca(settings)

    cert_file, key_file = store.root_ca_paths(settings)
    assert stat.S_IMODE(cert_file.stat().st_mode) == 0o644
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o400
