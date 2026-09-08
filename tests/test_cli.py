from click.testing import CliRunner

from personal_certificate_authority.cli import cli
from personal_certificate_authority.settings import Settings


def _invoke(runner: CliRunner, settings: Settings, args: list[str]):
    import personal_certificate_authority.settings as settings_module

    settings_module._settings = settings
    try:
        return runner.invoke(cli, args)
    finally:
        settings_module._settings = None


def test_status_before_init(settings: Settings):
    runner = CliRunner()
    result = _invoke(runner, settings, ["status"])
    assert result.exit_code == 0
    assert "not initialized" in result.output


def test_init_then_issue_then_list_then_show(initialized_settings: Settings):
    runner = CliRunner()
    result = _invoke(runner, initialized_settings, ["issue", "--name", "test", "--san", "localhost"])
    assert result.exit_code == 0, result.output

    result = _invoke(runner, initialized_settings, ["list"])
    assert result.exit_code == 0
    assert "test" in result.output

    result = _invoke(runner, initialized_settings, ["show", "--name", "test"])
    assert result.exit_code == 0
    assert "localhost" in result.output


def test_show_unknown_cert_fails(settings: Settings):
    runner = CliRunner()
    result = _invoke(runner, settings, ["show", "--name", "nope"])
    assert result.exit_code != 0


def test_revoke_deletes_cert(initialized_settings: Settings):
    runner = CliRunner()
    _invoke(runner, initialized_settings, ["issue", "--name", "test", "--san", "localhost"])
    result = _invoke(runner, initialized_settings, ["revoke", "--name", "test"])
    assert result.exit_code == 0

    result = _invoke(runner, initialized_settings, ["show", "--name", "test"])
    assert result.exit_code != 0
