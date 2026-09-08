import sys

import click
from loguru import logger

from personal_certificate_authority import certinfo, mkcert_wrapper, store
from personal_certificate_authority.logconf import configure_logging
from personal_certificate_authority.settings import get_settings

TRUST_INSTRUCTIONS = """\
Root CA certificate: {cert_file}

If you're browsing from this same machine, `pca init` already installed the
CA into the local system/browser trust stores via `mkcert -install`.

If you're browsing from a *different* machine (e.g. this is running on a
remote host), download the certificate above and trust it manually:

  Windows:  Double-click the .pem/.crt file -> Install Certificate ->
            Local Machine -> Trusted Root Certification Authorities.
  macOS:    Open in Keychain Access, add to the "System" keychain, then
            double-click it and set "When using this certificate" to
            "Always Trust".
  Linux:    sudo cp rootCA.pem /etc/pki/ca-trust/source/anchors/personal-ca.pem
            sudo update-ca-trust extract
            (Debian/Ubuntu: cp to /usr/local/share/ca-certificates/personal-ca.crt
             and run `sudo update-ca-certificates` instead)
  Firefox/  certutil -d sql:$HOME/.pki/nssdb -A -t "C,," \\
  Chrome        -n "Personal CA" -i rootCA.pem
  (Linux, NSS db; requires the `certutil` tool from libnss3-tools/nss-tools)

Or run `pca serve` for a web page with a download button and these same
instructions.
"""


@click.group()
@click.option("--log-level", default=None, help="Override log level (e.g. DEBUG, INFO, WARNING).")
def cli(log_level: str | None):
    """pca: a personal certificate authority for local TLS, built on mkcert."""
    settings = get_settings()
    if log_level:
        settings.log_level = log_level
    configure_logging()


@cli.command()
@click.option("--force", is_flag=True, help="Regenerate the root CA, invalidating all issued certs.")
def init(force: bool):
    """Create (if needed) and install the personal root CA."""
    settings = get_settings()
    mkcert_wrapper.init(settings, force=force)
    cert_file, _ = store.root_ca_paths(settings)
    info = certinfo.read_cert(cert_file)
    click.echo(f"Root CA ready: {cert_file}")
    click.echo(f"  Common name: {info.common_name}")
    click.echo(f"  Fingerprint: {info.sha256_fingerprint}")
    click.echo(f"  Valid until: {info.not_valid_after.isoformat()}")


@cli.command()
@click.option("--name", required=True, help="Name to store the issued certificate under.")
@click.option("--san", "sans", multiple=True, help="Additional Subject Alternative Name (repeatable).")
@click.option("--force", is_flag=True, help="Reissue even if a valid certificate already exists.")
def issue(name: str, sans: tuple[str, ...], force: bool):
    """Issue (or reuse) a server TLS certificate signed by the personal CA."""
    settings = get_settings()
    cert_file, key_file = mkcert_wrapper.issue(settings, name, sans, force=force)
    click.echo(f"Certificate: {cert_file}")
    click.echo(f"Private key: {key_file}")


@cli.command()
@click.option("--name", required=True)
def renew(name: str):
    """Reissue an existing certificate (alias for `issue --force`)."""
    settings = get_settings()
    cert_file, key_file = mkcert_wrapper.issue(settings, name, sans=(), force=True)
    click.echo(f"Renewed certificate: {cert_file}")
    click.echo(f"Private key: {key_file}")


@cli.command(name="list")
def list_certs():
    """List issued leaf certificates."""
    settings = get_settings()
    names = store.list_cert_names(settings)
    if not names:
        click.echo("No certificates issued yet. Run `pca issue --name <name> --san <san>`.")
        return
    for name in names:
        cert_file, _ = store.cert_paths(settings, name)
        info = certinfo.read_cert(cert_file)
        status = "EXPIRING SOON" if info.is_near_expiry() else "ok"
        click.echo(f"{name}\t{info.not_valid_after.isoformat()}\t{status}\t{','.join(info.subject_alternative_names)}")


@cli.command()
@click.option("--name", required=True)
def show(name: str):
    """Show details about one issued certificate."""
    settings = get_settings()
    cert_file, key_file = store.cert_paths(settings, name)
    if not cert_file.exists():
        click.echo(f"No certificate named '{name}'.", err=True)
        sys.exit(1)
    info = certinfo.read_cert(cert_file)
    click.echo(f"Name:        {name}")
    click.echo(f"Cert file:   {cert_file}")
    click.echo(f"Key file:    {key_file}")
    click.echo(f"Common name: {info.common_name}")
    click.echo(f"Fingerprint: {info.sha256_fingerprint}")
    click.echo(f"Valid until: {info.not_valid_after.isoformat()}")
    click.echo(f"SANs:        {', '.join(info.subject_alternative_names)}")


@cli.command()
@click.option("--name", required=True)
def revoke(name: str):
    """Delete an issued certificate's files.

    mkcert has no CRL/OCSP mechanism, so "revocation" here just means the
    files are removed and can no longer be pointed at by an app; any process
    that already has the old cert/key loaded is unaffected until restarted.
    """
    settings = get_settings()
    cert_dir = store.cert_dir(settings, name)
    if not cert_dir.exists():
        click.echo(f"No certificate named '{name}'.", err=True)
        sys.exit(1)
    for f in cert_dir.iterdir():
        f.unlink()
    cert_dir.rmdir()
    click.echo(f"Deleted certificate files for '{name}'. This does not revoke trust; regenerate the root CA (`pca init --force`) if a key was compromised.")


@cli.command()
def trust():
    """Print instructions for trusting the root CA on another machine."""
    settings = get_settings()
    cert_file, _ = store.root_ca_paths(settings)
    if not cert_file.exists():
        click.echo("No root CA found. Run `pca init` first.", err=True)
        sys.exit(1)
    click.echo(TRUST_INSTRUCTIONS.format(cert_file=cert_file))


@cli.command()
@click.option("--host", default=None)
@click.option("--port", default=None, type=int)
def serve(host: str | None, port: int | None):
    """Start the local web app with a CA download page and trust instructions."""
    import uvicorn

    from personal_certificate_authority.server import create_app

    settings = get_settings()
    app = create_app()
    uvicorn.run(app, host=host or settings.web_host, port=port or settings.web_port)


@cli.command()
def status():
    """Show root CA status and a summary of issued certificates."""
    settings = get_settings()
    cert_file, _ = store.root_ca_paths(settings)
    if not cert_file.exists():
        click.echo("Root CA: not initialized. Run `pca init`.")
    else:
        info = certinfo.read_cert(cert_file)
        state = "EXPIRING SOON" if info.is_near_expiry() else "ok"
        click.echo(f"Root CA: {info.common_name} ({state}, valid until {info.not_valid_after.isoformat()})")
        click.echo(f"  {cert_file}")

    names = store.list_cert_names(settings)
    click.echo(f"Issued certificates: {len(names)}")
    for name in names:
        cert_file, _ = store.cert_paths(settings, name)
        info = certinfo.read_cert(cert_file)
        state = "EXPIRING SOON" if info.is_near_expiry() else "ok"
        click.echo(f"  {name}: {state}, valid until {info.not_valid_after.isoformat()}")


if __name__ == "__main__":
    cli()
