# Development

## Setup

```bash
pixi install
```

This installs `mkcert` (via conda-forge) into the pixi environment along with
all Python dependencies, and installs this package editable.

## Running

```bash
pixi run pca init
pixi run pca issue --name test --san localhost
pixi run pca serve
```

By default all state lives under `~/.local/share/personal-certificate-authority/`
(`mkcert/` for the root CA, `certs/<name>/` for issued leaf certs). Override
with `PCA_DATA_DIR` for local testing without touching your real CA.

## Testing

```bash
pixi run -e test test
```

Most tests need a real `mkcert` binary on `PATH` (which the pixi env
provides) and are skipped otherwise. Tests use `PCA_DATA_DIR`-equivalent
isolation via a `tmp_path`-based `Settings` fixture (see `tests/conftest.py`)
so they never touch your real root CA.

## Project structure

- `personal_certificate_authority/settings.py` — pydantic-settings config (env prefix `PCA_`)
- `personal_certificate_authority/mkcert_wrapper.py` — subprocess wrapper around the `mkcert` binary
- `personal_certificate_authority/certinfo.py` — read-only X.509 parsing (fingerprint/expiry/SANs) via `cryptography`
- `personal_certificate_authority/cli.py` — the `pca` click CLI
- `personal_certificate_authority/server.py` + `templates/` — the `pca serve` FastAPI app
