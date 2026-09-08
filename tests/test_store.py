import os
import stat

from personal_certificate_authority import store
from personal_certificate_authority.settings import Settings


def _mode(path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_ensure_dir_chmods_leaf_and_all_ancestors_up_to_data_dir(settings: Settings):
    target = settings.certs_dir / "somename"

    store.ensure_dir(target, settings)

    assert _mode(target) == 0o700
    assert _mode(settings.certs_dir) == 0o700
    assert _mode(settings.data_dir) == 0o700


def test_ensure_dir_self_heals_a_previously_over_permissive_data_dir(settings: Settings):
    # Simulate the real bug this fixes: Path.mkdir(parents=True, mode=...)
    # only applies `mode` to the leaf it creates, so intermediate parents
    # (data_dir, certs_dir) previously ended up at the default umask-derived
    # mode (verified 0775 on a real install) instead of 0700.
    settings.data_dir.mkdir(parents=True)
    os.chmod(settings.data_dir, 0o775)
    (settings.data_dir / "certs").mkdir()
    os.chmod(settings.data_dir / "certs", 0o775)

    store.ensure_dir(settings.certs_dir / "somename", settings)

    assert _mode(settings.data_dir) == 0o700
    assert _mode(settings.certs_dir) == 0o700


def test_write_private_key_sets_mode_with_no_default_permission_window(settings: Settings, tmp_path):
    store.ensure_dir(settings.data_dir, settings)
    key_file = settings.data_dir / "key.pem"

    store.write_private_key(key_file, b"fake key material", mode=0o400)

    assert key_file.read_bytes() == b"fake key material"
    assert _mode(key_file) == 0o400


def test_touch_restricted_preserves_mode_through_a_later_truncating_write(settings: Settings):
    store.ensure_dir(settings.data_dir, settings)
    target = settings.data_dir / "leaf.pem"

    store.touch_restricted(target, mode=0o600)
    assert _mode(target) == 0o600

    # Simulate an external process (mkcert) truncating and writing to the
    # pre-created file, the way `open()` with O_CREAT preserves existing
    # permissions on an already-existing file.
    with open(target, "w") as f:
        f.write("leaf content")

    assert _mode(target) == 0o600
