# personal-certificate-authority

A personal certificate authority for local TLS. Creates a one-time root CA
for a single user and issues server certificates that local apps — such as
[Fileglancer](https://github.com/JaneliaSciComp/fileglancer) — can serve
HTTPS with, instead of relying on unsigned self-signed certs (which break
CORS/`fetch` in browsers) or a full organizational PKI.

Built on top of [`mkcert`](https://github.com/FiloSottile/mkcert), which
already solves the hard part of this problem: installing a root CA into the
Windows/macOS/Linux system trust store and Firefox/Chrome's NSS databases.
This project adds:

- A `pca` CLI that pins mkcert's `CAROOT` to a predictable per-user location
  and wraps common workflows (`init`, `issue`, `renew`, `list`, `revoke`).
- A small local web app (`pca serve`) that serves a download link for the
  root CA certificate plus OS/browser-specific trust instructions — useful
  when this tool runs on a remote host (e.g. a compute cluster node) but
  your browser is on your own laptop, where `mkcert -install` can't reach
  your local trust store automatically. It creates the root CA itself on
  first visit if one doesn't exist yet, so `pca serve` alone is enough to
  get started — no separate `pca init` required first.

## Quick start

```bash
pixi install
pixi run pca serve                                    # http://127.0.0.1:8990 — creates the root CA on first visit
pixi run pca issue --name myapp --san localhost       # issue a server cert
```

(Or run `pca init` yourself first if you're not going to use the web UI.)

Point any app's `--ssl-keyfile`/`--ssl-certfile` flags (e.g. Fileglancer's
`fileglancer start`) at the files printed by `pca issue`.

## CLI reference

| Command | Description |
|---|---|
| `pca init [--force]` | Create and install the root CA |
| `pca issue --name NAME [--san SAN ...] [--force]` | Issue or reuse a server certificate |
| `pca renew --name NAME` | Reissue an existing certificate |
| `pca list` | List issued certificates |
| `pca show --name NAME` | Show details about one certificate |
| `pca revoke --name NAME` | Delete a certificate's files |
| `pca trust` | Print instructions for trusting the CA on another machine |
| `pca serve [--host] [--port]` | Start the download + trust-instructions web app |
| `pca status` | Show root CA and certificate inventory status |

## Configuration

Settings can be set via environment variables prefixed `PCA_` (e.g.
`PCA_WEB_PORT=9000`) or via `~/.config/personal-certificate-authority/config.yaml`
— see `config.yaml.template`.

## Fileglancer App

This repo ships a [`runnables.yaml`](runnables.yaml) so it can be added to
Fileglancer as an App: `Initialize Root CA`, `Issue Certificate`, `Renew
Certificate`, `Revoke Certificate`, `List`/`Show`/`Status`, and a
long-running `Certificate Authority Web UI` service (the `pca serve` page
above) are all exposed as launchable entry points.

## Using this from other apps or agents

See [`docs/Integration.md`](docs/Integration.md) for how other Fileglancer
apps (or any local service) should issue and reuse a cert from this CA, and
how agents/automated scripts should do the same instead of minting one-off,
untrusted self-signed certificates. If the app in question uses
[Caddy](https://caddyserver.com/) as its own local reverse proxy/TLS
terminator (rather than terminating TLS itself), see
[`docs/CaddyIntegration.md`](docs/CaddyIntegration.md) instead — includes
worked examples of the exact change against two real apps.

## Development

See `docs/Development.md`.
